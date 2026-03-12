from odoo import models, fields, api
from odoo.exceptions import UserError, AccessError

class FeedFormula(models.Model):
    _name = 'feed.formula'
    _description = 'Feed Formula'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Formula Name', tracking=True, readonly=True)
    poultry_type = fields.Selection([
        ('broiler', 'Broiler'),
        ('layer', 'Layer'),
        ('breeder', 'Breeder'),
        ('duck', 'Duck'),
        ('other', 'Other'),
    ], string='Poultry Type', tracking=True)
    age_from = fields.Integer(string='Age From', required=True, tracking=True)
    age_to = fields.Integer(string='Age To', required=True, tracking=True)
    date_type = fields.Selection([
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months'),
        ('years', 'Years'),
    ], string='Date Type', default='days', required=True, tracking=True)
    batch_name = fields.Many2one('mrp.bom', string='Batch Name', required=True, tracking=True)
    actual_batch_size = fields.Float(string='Actual Batch Size (kg)', related='batch_name.product_qty', readonly=True, tracking=True)
    
    # Observation fields
    ingredient_observation_ids = fields.One2many(
        'feed.formula.ingredient.observation', 
        'formula_id', 
        string='Ingredient Observation',
        compute='_compute_observations',
        store=True
    )
    nutrient_observation_ids = fields.One2many(
        'feed.formula.nutrient.observation', 
        'formula_id', 
        string='Nutrient Observation', 
        compute='_compute_observations',
        store=True
    )
    total_nutrient_summary_ids = fields.One2many(
        'feed.formula.nutrient.summary', 
        'formula_id', 
        string='Total Nutrient Summary',
        compute='_compute_observations',
        store=True
    )
    
    total_cost_per_100kg = fields.Float(string='Total Cost per 100kg Batch', compute='_compute_total_cost_per_100kg', store=True, tracking=True)
    nutrition_status = fields.Selection([
        ('satisfied', 'Satisfied'),
        ('unsatisfied', 'Unsatisfied')
    ], string='Nutrition Status', compute='_compute_nutrition_status', store=True, tracking=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to generate automatic formula name and track creation"""
        # First, generate formula names for all records
        for vals in vals_list:
            if 'batch_name' in vals and 'date_type' in vals and 'age_from' in vals and 'age_to' in vals:
                batch = self.env['mrp.bom'].browse(vals['batch_name'])
                
                # Get first letter of date type (D for Days, W for Weeks, etc.)
                date_type_char = vals['date_type'][0].upper() if vals['date_type'] else 'D'
                
                # Generate formula name: FR/BatchNameWithoutSpace/D1020
                batch_name_clean = batch.display_name.replace(' ', '') if batch.display_name else 'UnknownBatch'
                age_from = vals.get('age_from', 0)
                age_to = vals.get('age_to', 0)
                
                vals['name'] = f"FR/{batch_name_clean}/{date_type_char}{age_from}{age_to}"
        
        records = super(FeedFormula, self).create(vals_list)
        
        # Track each created record
        for record in records:
            create_messages = []
            if record.name:
                create_messages.append(f"Formula Name: {record.name}")
            if record.poultry_type:
                poultry_type_label = dict(record._fields['poultry_type'].selection).get(record.poultry_type)
                create_messages.append(f"Poultry Type: {poultry_type_label}")
            if record.age_from or record.age_to:
                date_type_label = dict(record._fields['date_type'].selection).get(record.date_type, 'Days')
                create_messages.append(f"Age Range: {record.age_from}-{record.age_to} {date_type_label}")
            if record.batch_name:
                create_messages.append(f"Batch Name: {record.batch_name.display_name}")
            if record.actual_batch_size:
                create_messages.append(f"Batch Size: {record.actual_batch_size} kg")
            
            if create_messages:
                record.message_post(body="Record created with: " + ", ".join(create_messages))
        
        return records

    def write(self, vals):
        """Override write to update formula name if batch, date_type, or ages change"""
        if 'batch_name' in vals or 'date_type' in vals or 'age_from' in vals or 'age_to' in vals:
            for rec in self:
                batch = self.env['mrp.bom'].browse(vals.get('batch_name', rec.batch_name.id))
                date_type = vals.get('date_type', rec.date_type)
                age_from = vals.get('age_from', rec.age_from)
                age_to = vals.get('age_to', rec.age_to)
                
                # Get first letter of date type
                date_type_char = date_type[0].upper()
                
                # Generate formula name: FR/BatchNameWithoutSpace/D1020
                batch_name_clean = batch.display_name.replace(' ', '')
                
                vals['name'] = f"FR/{batch_name_clean}/{date_type_char}{age_from}{age_to}"
                break  # Only update once
        
        return super().write(vals)

    @api.depends('batch_name', 'batch_name.bom_line_ids', 'batch_name.bom_line_ids.product_id', 
                 'batch_name.bom_line_ids.product_qty', 'batch_name.product_qty',
                 'batch_name.bom_line_ids.product_id.standard_price')
    def _compute_observations(self):
        """AUTOMATICALLY generate all observations when Batch Name is entered"""
        for formula in self:
            if not formula.batch_name:
                formula.ingredient_observation_ids = [(5, 0, 0)]
                formula.nutrient_observation_ids = [(5, 0, 0)]
                formula.total_nutrient_summary_ids = [(5, 0, 0)]
                continue

            # Store old summaries for comparison
            old_summaries = {s.nutrition_id.id: s.actual_used_percent for s in formula.total_nutrient_summary_ids}
            old_ingredients = {i.ingredient_id.id: i.quantity_per_100kg for i in formula.ingredient_observation_ids}

            # 1. Process Ingredient Observations
            ingredient_observations = []
            actual_batch_size = formula.batch_name.product_qty or 100.0  # Default to 100kg
            
            # Clear existing observations
            formula.ingredient_observation_ids = [(5, 0, 0)]
            
            ingredient_names = []
            for bom_line in formula.batch_name.bom_line_ids:
                quantity_per_100kg = bom_line.product_qty  # Already in 100kg batch
                
                # Find existing ingredient for this product
                ingredient = self.env['feed.ingredient'].search([
                    ('product_id', '=', bom_line.product_id.id)
                ], limit=1)
                
                if ingredient:
                    cost_per_100kg = quantity_per_100kg * bom_line.product_id.standard_price
                    ingredient_names.append(ingredient.name)
                    
                    # Create observation record
                    ingredient_observations.append((0, 0, {
                        'ingredient_id': ingredient.id,
                        'quantity_per_100kg': quantity_per_100kg,
                        'unit_cost': bom_line.product_id.standard_price,
                        'cost_per_100kg': cost_per_100kg,
                    }))

            formula.ingredient_observation_ids = ingredient_observations

            # 2. Process Nutrient Observations - Group by nutrition first
            nutrient_observations = []
            formula.nutrient_observation_ids = [(5, 0, 0)]  # Clear existing
            
            # Create a dictionary to group by nutrition_id
            nutrition_groups = {}
            
            for ing_obs_command in ingredient_observations:
                if ing_obs_command[2].get('ingredient_id'):
                    ingredient = self.env['feed.ingredient'].browse(ing_obs_command[2]['ingredient_id'])
                    quantity_per_100kg = ing_obs_command[2].get('quantity_per_100kg', 0.0)
                    
                    for nutrient_line in ingredient.nutrient_line_ids:
                        total_percentage_per_100kg = nutrient_line.percentage_per_100kg * quantity_per_100kg / 100.0
                        
                        nutrition_id = nutrient_line.nutrition_id.id
                        nutrition_name = nutrient_line.nutrition_id.name
                        
                        if nutrition_id not in nutrition_groups:
                            nutrition_groups[nutrition_id] = {
                                'nutrition_name': nutrition_name,
                                'ingredients': []
                            }
                        
                        nutrition_groups[nutrition_id]['ingredients'].append({
                            'ingredient_id': ingredient.id,
                            'ingredient_name': ingredient.name,
                            'percentage_per_100kg': nutrient_line.percentage_per_100kg,
                            'quantity_per_100kg': quantity_per_100kg,
                            'total_percentage_per_100kg': total_percentage_per_100kg
                        })
            
            # Now create nutrient observations grouped by nutrition
            for nutrition_id, group_data in nutrition_groups.items():
                for ingredient_data in group_data['ingredients']:
                    nutrient_observations.append((0, 0, {
                        'nutrition_id': nutrition_id,
                        'ingredient_id': ingredient_data['ingredient_id'],
                        'percentage_per_100kg': ingredient_data['percentage_per_100kg'],
                        'quantity_per_100kg': ingredient_data['quantity_per_100kg'],
                        'total_percentage_per_100kg': ingredient_data['total_percentage_per_100kg'],
                    }))

            formula.nutrient_observation_ids = nutrient_observations

            # 3. Process Total Nutrient Summary (group by nutrition_id)
            summary_dict = {}
            formula.total_nutrient_summary_ids = [(5, 0, 0)]  # Clear existing
            
            for obs_command in nutrient_observations:
                nutrition_id = obs_command[2].get('nutrition_id')
                total_percent = obs_command[2].get('total_percentage_per_100kg', 0.0)
                
                if nutrition_id not in summary_dict:
                    summary_dict[nutrition_id] = 0.0
                summary_dict[nutrition_id] += total_percent

            summary_lines = []
            for nutrition_id, actual_used_percent in summary_dict.items():
                nutrition = self.env['feed.nutrition'].browse(nutrition_id)
                standard = self.env['feed.nutrition.standard'].search([
                    ('nutrition_id', '=', nutrition_id)
                ], limit=1)
                
                summary_lines.append((0, 0, {
                    'nutrition_id': nutrition_id,
                    'min_standard': standard.min_standard if standard else 0.0,
                    'max_standard': standard.max_standard if standard else 0.0,
                    'required_standard': standard.required_standard if standard else 0.0,
                    'actual_used_percent': actual_used_percent,
                }))

            formula.total_nutrient_summary_ids = summary_lines

            # Post consolidated message about changes
            self._post_batch_change_message(formula, ingredient_names, old_summaries)

    @api.depends('ingredient_observation_ids.cost_per_100kg')
    def _compute_total_cost_per_100kg(self):
        for formula in self:
            total = 0.0
            for ing_obs in formula.ingredient_observation_ids:
                total += ing_obs.cost_per_100kg
            formula.total_cost_per_100kg = total

    @api.depends('total_nutrient_summary_ids.actual_used_percent', 
                 'total_nutrient_summary_ids.min_standard', 
                 'total_nutrient_summary_ids.max_standard')
    def _compute_nutrition_status(self):
        for formula in self:
            if not formula.total_nutrient_summary_ids:
                formula.nutrition_status = 'satisfied'
                continue
                
            status = 'satisfied'
            
            for summary in formula.total_nutrient_summary_ids:
                actual = summary.actual_used_percent
                min_std = summary.min_standard
                max_std = summary.max_standard
                
                # Check min and max standards
                if min_std and actual < min_std:
                    status = 'unsatisfied'
                    break
                elif max_std and actual > max_std:
                    status = 'unsatisfied'
                    break
            
            formula.nutrition_status = status

    def _post_batch_change_message(self, formula, ingredient_names, old_summaries):
        """Post consolidated message about batch changes"""
        if not formula.id:
            return
            
        messages = []
        
        # 1. Ingredient changes summary
        if ingredient_names:
            ingredient_count = len(ingredient_names)
            messages.append(f"Batch updated with {ingredient_count} ingredient(s)")
        
        # 2. Track nutrients that are NOT within range
        problem_nutrients = []
        changed_nutrients = []
        
        for summary in formula.total_nutrient_summary_ids:
            nutrition_name = summary.nutrition_id.name
            actual = summary.actual_used_percent
            min_std = summary.min_standard
            max_std = summary.max_standard
            
            # Check if this nutrient has problems
            if min_std and actual < min_std:
                problem_nutrients.append(f"{nutrition_name}: {actual:.2f}% (Below Min: {min_std}%)")
            elif max_std and actual > max_std:
                problem_nutrients.append(f"{nutrition_name}: {actual:.2f}% (Above Max: {max_std}%)")
            
            # Check if value changed from before
            if summary.nutrition_id.id in old_summaries:
                old_value = old_summaries[summary.nutrition_id.id]
                if abs(old_value - actual) > 0.001:  # Changed
                    changed_nutrients.append(f"{nutrition_name}: {old_value:.2f}% → {actual:.2f}%")
        
        # Add problem nutrients section
        if problem_nutrients:
            messages.append("Nutrients Outside Range: " + ", ".join(problem_nutrients))
        
        # Add changed nutrients section
        if changed_nutrients:
            messages.append("Nutrient Changes: " + ", ".join(changed_nutrients))
        
        # Post single consolidated message
        if messages:
            formula.message_post(body=" | ".join(messages))


class FeedFormulaIngredientObservation(models.Model):
    _name = 'feed.formula.ingredient.observation'
    _description = 'Formula Ingredient Observation per 100kg'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    formula_id = fields.Many2one('feed.formula', string='Formula', ondelete='cascade')
    ingredient_id = fields.Many2one('feed.ingredient', string='Ingredient', required=True, tracking=True)
    quantity_per_100kg = fields.Float(string='Quantity per 100kg', tracking=True, digits=(16, 6))
    unit_cost = fields.Float(string='Unit Cost', tracking=True, digits=(16, 4))
    cost_per_100kg = fields.Float(string='Cost per 100kg', tracking=True, digits=(16, 4))


class FeedFormulaNutrientObservation(models.Model):
    _name = 'feed.formula.nutrient.observation'
    _description = 'Formula Nutrient Observation per 100kg'
    _order = 'nutrition_id, ingredient_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    formula_id = fields.Many2one('feed.formula', string='Formula', ondelete='cascade')
    nutrition_id = fields.Many2one('feed.nutrition', string='Nutrient', required=True, tracking=True)
    percentage_per_100kg = fields.Float(string='Percentage per 100kg (%)', tracking=True, digits=(16, 6))
    quantity_per_100kg = fields.Float(string='Quantity per 100kg batch', tracking=True, digits=(16, 6))
    total_percentage_per_100kg = fields.Float(string='Total Percentage per 100kg batch (%)', tracking=True, digits=(16, 6))
    ingredient_id = fields.Many2one('feed.ingredient', string='Ingredient')



class FeedFormulaNutrientSummary(models.Model):
    _name = 'feed.formula.nutrient.summary'
    _description = 'Formula Nutrient Summary per 100kg'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    formula_id = fields.Many2one('feed.formula', string='Formula', ondelete='cascade')
    nutrition_id = fields.Many2one('feed.nutrition', string='Nutrient', required=True, tracking=True)
    min_standard = fields.Float(string='Min Standard (%)', tracking=True, digits=(16, 6))
    max_standard = fields.Float(string='Max Standard (%)', tracking=True, digits=(16, 6))
    required_standard = fields.Float(string='Required Standard (%)', tracking=True, digits=(16, 6))
    actual_used_percent = fields.Float(string='Actual Used (%) per 100kg', tracking=True, digits=(16, 6))
    
    status = fields.Selection([
        ('within_range', 'Within Range'),
        ('below_min', 'Below Minimum'),
        ('above_max', 'Above Maximum'),
        ('no_standard', 'No Standard')
    ], string='Status', compute='_compute_status', store=True)

    @api.depends('min_standard', 'max_standard', 'actual_used_percent')
    def _compute_status(self):
        for rec in self:
            if not rec.min_standard and not rec.max_standard:
                rec.status = 'no_standard'
            elif rec.min_standard and rec.actual_used_percent < rec.min_standard:
                rec.status = 'below_min'
            elif rec.max_standard and rec.actual_used_percent > rec.max_standard:
                rec.status = 'above_max'
            else:
                rec.status = 'within_range'
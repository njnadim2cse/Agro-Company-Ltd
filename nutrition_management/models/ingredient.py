from odoo import models, fields, api
from odoo.exceptions import UserError, AccessError

class FeedIngredient(models.Model):
    _name = 'feed.ingredient'
    _description = 'Feed Ingredient'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    
    product_id = fields.Many2one(
        'product.product', 
        string='Ingredient Name', 
        required=True,
        domain="[('is_feed', '=', True)]",
        tracking=True
    )
    code = fields.Char(string='Code', tracking=True)
    ingredient_type = fields.Selection([
        ('grain', 'Grain'),
        ('protein', 'Protein'),
        ('mineral', 'Mineral'),
        ('additive', 'Additive'),
        ('other', 'Other')
    ], string='Ingredient Type', tracking=True)
    unit_cost = fields.Float(string='Unit Cost', tracking=True, digits=(16, 6))
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', tracking=True)
    
    nutrient_line_ids = fields.One2many('feed.ingredient.nutrient', 'ingredient_id', string='Nutrients', copy=True)
    extra_nutrients = fields.Html(string='Extra Nutrients', tracking=True)
    remarks = fields.Html(string='Remarks', tracking=True)
    
    name = fields.Char(string='Name', compute='_compute_name', store=True, readonly=False, tracking=True)

    @api.depends('product_id', 'product_id.name')
    def _compute_name(self):
        """Automatically update name when product name changes"""
        for rec in self:
            if rec.product_id:
                rec.name = rec.product_id.name
            elif not rec.name:
                rec.name = False

    
    @api.onchange('product_id')
    def _onchange_product(self):
        for rec in self:
            if rec.product_id:
                rec.unit_cost = rec.product_id.standard_price
                rec.uom_id = rec.product_id.uom_id
                if not rec.code:
                    rec.code = rec.product_id.default_code

    @api.model_create_multi
    def create(self, vals_list):
        """Create ingredient records and track creation values"""
        records = super(FeedIngredient, self).create(vals_list)
        
        # Track each created record
        for record in records:
            create_messages = []
            if record.product_id:
                create_messages.append(f"Ingredient Name: {record.product_id.name}")
            if record.code:
                create_messages.append(f"Code: {record.code}")
            if record.ingredient_type:
                ingredient_type_label = dict(record._fields['ingredient_type'].selection).get(record.ingredient_type)
                create_messages.append(f"Ingredient Type: {ingredient_type_label}")
            if record.unit_cost:
                create_messages.append(f"Unit Cost: {record.unit_cost}")
            if record.uom_id:
                create_messages.append(f"Unit of Measure: {record.uom_id.name}")
            
            if create_messages:
                record.message_post(body="Record created with: " + ", ".join(create_messages))
        
        return records

    def write(self, vals):
        """Track parent field changes"""
        result = super().write(vals)
        
        # Track which fields changed for each record
        for rec in self:
            parent_changes = []
            
            if 'product_id' in vals:
                old_product = rec._origin.product_id.name if rec._origin.product_id else 'None'
                new_product = rec.product_id.name if rec.product_id else 'None'
                parent_changes.append(f"Ingredient Name: {old_product} → {new_product}")
            
            if 'code' in vals:
                old_code = rec._origin.code or 'None'
                new_code = rec.code or 'None'
                parent_changes.append(f"Code: {old_code} → {new_code}")
            
            if 'ingredient_type' in vals:
                old_type = dict(rec._fields['ingredient_type'].selection).get(rec._origin.ingredient_type, 'None') if rec._origin.ingredient_type else 'None'
                new_type = dict(rec._fields['ingredient_type'].selection).get(rec.ingredient_type, 'None') if rec.ingredient_type else 'None'
                parent_changes.append(f"Ingredient Type: {old_type} → {new_type}")
            
            if 'unit_cost' in vals:
                old_cost = rec._origin.unit_cost
                new_cost = rec.unit_cost
                parent_changes.append(f"Unit Cost: {old_cost} → {new_cost}")
            
            if 'uom_id' in vals:
                old_uom = rec._origin.uom_id.name if rec._origin.uom_id else 'None'
                new_uom = rec.uom_id.name if rec.uom_id else 'None'
                parent_changes.append(f"Unit of Measure: {old_uom} → {new_uom}")
            
            # Post message immediately if there are changes
            if parent_changes:
                message = "Field changes: " + ", ".join(parent_changes)
                rec.message_post(body=message)
        
        return result


class FeedIngredientNutrient(models.Model):
    _name = 'feed.ingredient.nutrient'
    _description = 'Ingredient Nutrient'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    ingredient_id = fields.Many2one('feed.ingredient', string='Ingredient', required=True, ondelete='cascade')
    nutrition_id = fields.Many2one('feed.nutrition', string='Nutrient', required=True, tracking=True)
    percentage_per_100kg = fields.Float(string='Percentage per 100kg (%)', tracking=True, digits=(16, 6))

    @api.model_create_multi
    def create(self, vals_list):
        """Track nutrient line creation in parent ingredient - consolidated"""
        records = super().create(vals_list)
        
        # Group by ingredient_id to send one message per ingredient
        ingredient_nutrients = {}
        for record in records:
            if record.ingredient_id:
                if record.ingredient_id.id not in ingredient_nutrients:
                    ingredient_nutrients[record.ingredient_id.id] = {
                        'ingredient': record.ingredient_id,
                        'nutrients': []
                    }
                nutrition_name = record.nutrition_id.name or 'Unknown'
                percentage = record.percentage_per_100kg
                ingredient_nutrients[record.ingredient_id.id]['nutrients'].append(f"{nutrition_name}: {percentage}%")
        
        # Post consolidated message for each ingredient
        for ingredient_id, data in ingredient_nutrients.items():
            ingredient = data['ingredient']
            nutrient_lines = data['nutrients']
            count = len(nutrient_lines)
            
            messages = []
            
            # Check for parent write changes
            if hasattr(ingredient, '_parent_field_changes'):
                if ingredient._parent_field_changes:
                    messages.append("Field changes: " + ", ".join(ingredient._parent_field_changes))
                delattr(ingredient, '_parent_field_changes')
            
            # Add nutrient changes
            if count == 1:
                messages.append(f"Nutrient added: {nutrient_lines[0]}")
            else:
                nutrients_list = ", ".join(nutrient_lines)
                messages.append(f"{count} nutrients added: {nutrients_list}")
            
            # Post combined message
            if messages:
                ingredient.message_post(body=" | ".join(messages))
        
        return records

    def write(self, vals):
        """Track nutrient line changes in parent ingredient - consolidated"""
        # Group changes by ingredient
        ingredient_changes = {}
        
        for record in self:
            if record.ingredient_id:
                if record.ingredient_id.id not in ingredient_changes:
                    ingredient_changes[record.ingredient_id.id] = {
                        'ingredient': record.ingredient_id,
                        'changes': []
                    }
                
                changes = []
                if 'nutrition_id' in vals:
                    old_nutrition = self.env['feed.nutrition'].browse(record._origin.nutrition_id.id)
                    new_nutrition = self.env['feed.nutrition'].browse(vals['nutrition_id'])
                    changes.append(f"Nutrient changed: {old_nutrition.name} → {new_nutrition.name}")
                
                if 'percentage_per_100kg' in vals:
                    old_percentage = record._origin.percentage_per_100kg
                    new_percentage = vals['percentage_per_100kg']
                    nutrition_name = record.nutrition_id.name or 'Unknown'
                    changes.append(f"{nutrition_name}: {old_percentage}% → {new_percentage}%")
                
                if changes:
                    ingredient_changes[record.ingredient_id.id]['changes'].extend(changes)
        
        result = super().write(vals)
        
        # Post consolidated messages
        for ingredient_id, data in ingredient_changes.items():
            ingredient = data['ingredient']
            change_lines = data['changes']
            count = len(change_lines)
            
            # Check if parent has pending changes
            messages = []
            if hasattr(ingredient, '_parent_field_changes') and ingredient._parent_field_changes:
                messages.append("Field changes: " + ", ".join(ingredient._parent_field_changes))
                delattr(ingredient, '_parent_field_changes')
            
            # Add nutrient changes
            if count == 1:
                messages.append(f"Nutrient updated: {change_lines[0]}")
            else:
                changes_list = ", ".join(change_lines)
                messages.append(f"{count} nutrient changes: {changes_list}")
            
            # Post combined message
            ingredient.message_post(body=" | ".join(messages))
        
        return result

    def unlink(self):
        """Track nutrient line deletion in parent ingredient - consolidated"""
        # Group deletions by ingredient
        ingredient_deletions = {}
        
        for record in self:
            if record.ingredient_id:
                if record.ingredient_id.id not in ingredient_deletions:
                    ingredient_deletions[record.ingredient_id.id] = {
                        'ingredient': record.ingredient_id,
                        'nutrients': []
                    }
                nutrition_name = record.nutrition_id.name or 'Unknown'
                percentage = record.percentage_per_100kg
                ingredient_deletions[record.ingredient_id.id]['nutrients'].append(f"{nutrition_name}: {percentage}%")
        
        result = super().unlink()
        
        # Post consolidated messages
        for ingredient_id, data in ingredient_deletions.items():
            ingredient = data['ingredient']
            nutrient_lines = data['nutrients']
            count = len(nutrient_lines)
            
            # Check if parent has pending changes
            messages = []
            if hasattr(ingredient, '_parent_field_changes') and ingredient._parent_field_changes:
                messages.append("Field changes: " + ", ".join(ingredient._parent_field_changes))
                delattr(ingredient, '_parent_field_changes')
            
            # Add nutrient deletions
            if count == 1:
                messages.append(f"Nutrient removed: {nutrient_lines[0]}")
            else:
                nutrients_list = ", ".join(nutrient_lines)
                messages.append(f"{count} nutrients removed: {nutrients_list}")
            
            # Post combined message
            ingredient.message_post(body=" | ".join(messages))
        
        return result
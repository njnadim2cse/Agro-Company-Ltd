from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    nutrition_status = fields.Selection([
        ('satisfied', 'Satisfied'),
        ('unsatisfied', 'Unsatisfied'),
        ('no_formula', 'No Formula')
    ], string='Nutrition Status', compute='_compute_nutrition_status')
    
    formula_id = fields.Many2one('feed.formula', string='Linked Formula')
   
    @api.depends('formula_id.nutrition_status')
    def _compute_nutrition_status(self):
        for bom in self:
            if bom.formula_id:
                bom.nutrition_status = bom.formula_id.nutrition_status
            else:
                bom.nutrition_status = 'no_formula'

    def action_check_nutrition(self):
        self.ensure_one()
        
        if not self.formula_id:
            raise UserError("No formula linked to this BOM.")
        
        issues = []
        for summary in self.formula_id.total_nutrient_summary_ids:
            actual = summary.actual_used_percent
            nutrition_name = summary.nutrition_id.name
            
            if summary.min_standard and actual < summary.min_standard:
                issues.append({
                    'nutrition': nutrition_name,
                    'actual': actual,
                    'required': summary.min_standard,
                    'type': 'below_min'
                })
            elif summary.max_standard and actual > summary.max_standard:
                issues.append({
                    'nutrition': nutrition_name,
                    'actual': actual,
                    'required': summary.max_standard,
                    'type': 'above_max'
                })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Nutrition Check Results',
            'res_model': 'nutrition.check.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_bom_id': self.id,
                'default_formula_id': self.formula_id.id,
                'default_has_issues': bool(issues),
                'default_issue_details': '\n'.join([
                    f"{issue['nutrition']}: {issue['actual']:.6f}% {'<' if issue['type'] == 'below_min' else '>'} {issue['required']:.6f}%"
                    for issue in issues
                ])
            }
        }


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'
    
    product_qty = fields.Float(
        string='Quantity',
        digits=(16, 6),
        required=True,
        default=1.0
    )
    
    cost = fields.Float(
        string='Cost', 
        compute='_compute_cost', 
        store=True, 
        digits=(16, 6)
    )
    
    ingredient_id = fields.Many2one('feed.ingredient', string='Linked Ingredient')

    @api.depends('product_qty', 'product_id.standard_price')
    def _compute_cost(self):
        for line in self:
            line.cost = line.product_qty * line.product_id.standard_price

    def action_view_nutrients(self):
        self.ensure_one()
        
        ingredient = self.env['feed.ingredient'].search([
            ('product_id', '=', self.product_id.id),
        ], limit=1)
        
        if ingredient:
            return {
                'type': 'ir.actions.act_window',
                'name': f'Nutrients - {ingredient.name}',
                'res_model': 'feed.ingredient.nutrient',
                'view_mode': 'list,form',
                'domain': [('ingredient_id', '=', ingredient.id)],
                'context': {
                    'default_ingredient_id': ingredient.id,
                    'search_default_ingredient_id': ingredient.id
                },
                'target': 'current',
            }

        return {
            'type': 'ir.actions.act_window',
            'name': f'Nutrients - {self.product_id.display_name}',
            'res_model': 'feed.ingredient.nutrient',
            'view_mode': 'list,form',
            'domain': [('ingredient_id', '=', False)],
            'target': 'current',
        }

    @api.constrains('product_id')
    def _check_product_exists_in_nutrition(self):
        for line in self:
            if not line.product_id:
                continue
            ingredient_exists = self.env['feed.ingredient'].search_count([
                ('product_id', '=', line.product_id.id)
            ])
            if not ingredient_exists:
                product_name = line.product_id.display_name or line.product_id.name
                raise ValidationError(
                    f"{product_name} does not exist in Nutrition Module. "
                    "Please add it as an Ingredient in the Nutrition Module first."
                )

    @api.constrains('product_id', 'product_qty')
    def _check_formula_up_to_date(self):
        for line in self:
            bom = line.bom_id
            if bom and bom.formula_id:
                formula = bom.formula_id
                if bom.write_date and formula.write_date:
                    if bom.write_date > formula.write_date:
                        raise ValidationError(
                            "Linked Formula isn't up to date. "
                            "Please update your formula from Nutrition Module."
                        )

    @api.constrains('product_qty')
    def _check_product_qty_not_zero(self):
        for line in self:
            if line.product_qty == 0:
                raise ValidationError(
                    "Quantity cannot be zero. "
                    "Please enter a valid quantity for this component."
                )

class NutritionCheckWizard(models.TransientModel):
    _name = 'nutrition.check.wizard'
    _description = 'Nutrition Check Wizard'

    bom_id = fields.Many2one('mrp.bom', string='BOM')
    formula_id = fields.Many2one('feed.formula', string='Formula')
    has_issues = fields.Boolean(string='Has Issues')
    issue_details = fields.Text(string='Issue Details')
    
    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}
    
    def action_view_formula(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Formula',
            'res_model': 'feed.formula',
            'view_mode': 'form',
            'res_id': self.formula_id.id,
            'target': 'current',
        }
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    nutrition_status = fields.Selection([
        ('satisfied', 'Satisfied'),
        ('unsatisfied', 'Unsatisfied'),
        ('no_formula', 'No Formula')
    ], string='Nutrition Status', compute='_compute_nutrition_status')
    
    formula_id = fields.Many2one('feed.formula', string='Linked Formula', 
                                  compute='_compute_formula_id')

    @api.depends('bom_id')
    def _compute_formula_id(self):
        for production in self:
            if production.bom_id and production.bom_id.formula_id:
                production.formula_id = production.bom_id.formula_id.id
            else:
                production.formula_id = False

    @api.depends('formula_id.nutrition_status')
    def _compute_nutrition_status(self):
        for production in self:
            if production.formula_id:
                production.nutrition_status = production.formula_id.nutrition_status
            else:
                production.nutrition_status = 'no_formula'

    def action_confirm(self):
        for production in self:
            if production.bom_id:
                bom_write = production.bom_id.write_date
                mo_write = production.write_date
                if bom_write and mo_write and bom_write > mo_write:
                    raise UserError(
                        "BOM has not been latest updated. "
                        "The Bill of Materials has been modified after this "
                        "Manufacturing Order was created. Please discard this "
                        "order and create a new one, or reload the BOM components."
                    )
                    
            if production.formula_id:
                if production.formula_id.nutrition_status == 'unsatisfied':
                    raise UserError(
                        "Cannot confirm manufacturing order. "
                        "Nutrition standards are not satisfied."
                    )
            elif not production.formula_id:
                raise UserError("No Formula Linked.")
        
        return super().action_confirm()

    def action_check_nutrition(self):
        self.ensure_one()
        
        if not self.formula_id:
            raise UserError("No formula linked.")
        
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
                'default_bom_id': self.bom_id.id,
                'default_formula_id': self.formula_id.id,
                'default_has_issues': bool(issues),
                'default_issue_details': '\n'.join([
                    f"{issue['nutrition']}: {issue['actual']:.6f}% {'<' if issue['type'] == 'below_min' else '>'} {issue['required']:.6f}%"
                    for issue in issues
                ])
            }
        }
    

class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.constrains('product_id', 'raw_material_production_id')
    def _check_product_in_bom(self):
        """Validate that added component products exist in the BoM"""
        for move in self:
            # Only check for raw materials (components) in manufacturing orders
            if move.raw_material_production_id and move.raw_material_production_id.bom_id:
                production = move.raw_material_production_id
                bom = production.bom_id
                
                # Get all product IDs from BoM lines
                bom_product_ids = bom.bom_line_ids.mapped('product_id').ids
                
                # Check if the move's product exists in BoM
                if move.product_id.id not in bom_product_ids:
                    raise ValidationError(
                        f" ** {move.product_id.name} ** doesn't exist in the Bill of Materials (BoM): ** {bom.display_name} **.\n\n"
                        f"Please add the product to the BoM first before adding it to this Manufacturing Order."
                    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to validate products on creation"""
        moves = super().create(vals_list)
        # Trigger the constraint check
        moves._check_product_in_bom()
        return moves

    def write(self, vals):
        """Override write to validate products on update"""
        res = super().write(vals)
        # Only check if product_id is being changed
        if 'product_id' in vals:
            self._check_product_in_bom()
        return res
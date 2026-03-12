from odoo import models, fields, api
from odoo.exceptions import UserError

class NutritionReportWizard(models.TransientModel):
    _name = 'nutrition.report.wizard'
    _description = 'Nutrition Report Wizard'

    name = fields.Char(string='Report Name')
    report_type = fields.Selection([
        ('ingredient', 'Ingredients Details Report'),
        ('nutrient', 'Nutrients Details Report'),
        ('summary', 'Total Nutrients Summary Report')
    ], string='Report Type', required=True, default='ingredient')
    formula_id = fields.Many2one('feed.formula', string='Formula Name', required=True)

    def action_generate_report(self):
        self.ensure_one()
        report_action = None
        if self.report_type == 'ingredient':
            report_action = self.env.ref('nutrition_management.report_action_ingredient_details').report_action(self.formula_id)
        elif self.report_type == 'nutrient':
            report_action = self.env.ref('nutrition_management.report_action_nutrient_details').report_action(self.formula_id)
        elif self.report_type == 'summary':
            report_action = self.env.ref('nutrition_management.report_action_nutrient_summary').report_action(self.formula_id)
        else:
            raise UserError('Unknown report type')
            
        return report_action
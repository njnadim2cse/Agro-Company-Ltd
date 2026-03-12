from odoo import models, fields, api
from odoo.exceptions import UserError, AccessError

class FeedNutritionStandard(models.Model):
    _name = 'feed.nutrition.standard'
    _description = 'Nutrition Standard per 100kg batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Standard Name', required=False, readonly=True, tracking=True)
    nutrition_id = fields.Many2one('feed.nutrition', string='Nutrient', required=True, tracking=True)
    min_standard = fields.Float(string='Min Standard (%)', digits=(16, 6), 
                               help='Minimum required percentage per 100kg batch', tracking=True)
    max_standard = fields.Float('Max Standard (%)', digits=(16, 6),
                               help='Maximum allowed percentage per 100kg batch', tracking=True)
    required_standard = fields.Float(string='Required Standard (%)', digits=(16, 6),
                                  help='Required target percentage per 100kg batch', tracking=True)

    _sql_constraints = [
        ('nutrition_standard_unique', 'unique(nutrition_id)', 
         'Nutrition standard for this nutrient already exists!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Override create_multi to generate automatic name and track creation"""
        # Generate automatic names BEFORE creating records
        for vals in vals_list:
            if 'nutrition_id' in vals:
                nutrition = self.env['feed.nutrition'].browse(vals['nutrition_id'])
                nutrition_name_clean = nutrition.name.replace(' ', '') if nutrition.name else 'UnknownNutrient'
                vals['name'] = f"Std/{nutrition_name_clean}"
        
        # Create the records
        records = super(FeedNutritionStandard, self).create(vals_list)
        
        # Track each created record with log message
        for record in records:
            create_messages = []
            if record.nutrition_id:
                create_messages.append(f"Nutrient: {record.nutrition_id.name}")
            if record.min_standard:
                create_messages.append(f"Min Standard: {record.min_standard}%")
            if record.max_standard:
                create_messages.append(f"Max Standard: {record.max_standard}%")
            if record.required_standard:
                create_messages.append(f"Required Standard: {record.required_standard}%")
            
            if create_messages:
                record.message_post(body="Record created with: " + ", ".join(create_messages))
        
        return records

    def write(self, vals):
        """Override write to update standard name if nutrition changes and track modifications"""
        if 'nutrition_id' in vals:
            for rec in self:
                nutrition = self.env['feed.nutrition'].browse(vals.get('nutrition_id', rec.nutrition_id.id))
                nutrition_name_clean = nutrition.name.replace(' ', '') if nutrition.name else 'UnknownNutrient'
                vals['name'] = f"Std/{nutrition_name_clean}"
                break
        
        return super().write(vals)
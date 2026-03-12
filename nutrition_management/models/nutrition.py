from odoo import models, fields, api
from odoo.exceptions import UserError, AccessError

class FeedNutrition(models.Model):
    _name = 'feed.nutrition'
    _description = 'Nutrition Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Full Name', required=True, tracking=True)
    sname = fields.Char(string='Short Name', tracking=True)
    nutrient_type = fields.Selection([
        ('protein', 'Protein'),
        ('mineral', 'Mineral'),
        ('vitamin', 'Vitamin'),
        ('fat', 'Fat'),
        ('fiber', 'Fiber'),
        ('other', 'Other')
    ], string='Nutrient Type', tracking=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True, tracking=True)

    _sql_constraints = [
        ('feed_nutrition_sname_uniq', 'unique(sname)', 'Short name must be unique'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Override create_multi for tracking creation and bulk imports"""
        records = super(FeedNutrition, self).create(vals_list)
        
        # Track each created record
        for record in records:
            create_messages = []
            if record.name:
                create_messages.append(f"Full Name: {record.name}")
            if record.sname:
                create_messages.append(f"Short Name: {record.sname}")
            if record.nutrient_type:
                nutrient_type_label = dict(record._fields['nutrient_type'].selection).get(record.nutrient_type)
                create_messages.append(f"Nutrient Type: {nutrient_type_label}")
            if record.uom_id:
                create_messages.append(f"Unit of Measure: {record.uom_id.name}")
            
            if create_messages:
                record.message_post(body="Record created with: " + ", ".join(create_messages))
        
        return records
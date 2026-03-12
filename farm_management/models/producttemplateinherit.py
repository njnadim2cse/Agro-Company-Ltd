
import requests
from datetime import date
from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError, UserError
from datetime import datetime

class ProductTemplate(models.Model):

    _inherit = 'product.template'
    

    is_medicine = fields.Boolean(string="Is Medicine")
    egg_type = fields.Selection([
        ("small", "Small"),
        ("medium", "Medium"),
        ("high_medium", "High Medium"),
        ("high", "High"),
        ("double_yolk", "Double Yolk"),
        ("broken", "Broken"),
        ("white", "White"),
        ("damage", "Damage"),
        ('misshaped','Misshaped'),
        ('liquid' ,'Liquid')
    ], string="Egg Type",tracking=True)


    is_feed = fields.Boolean(string="Is Feed")

    @api.constrains('egg_type')
    @api.onchange("egg_type")
    def _check_unique_egg_type(self):
        for record in self:
            if record.egg_type:
                existing = self.env['product.template'].search([
                    ('egg_type', '=', record.egg_type),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise UserError(f"Egg type '{record.egg_type}' is already used in another product.")
                

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    is_for_production_egg = fields.Boolean(
        string="For Egg Production"
    )
    
    @api.constrains('is_for_production_egg', 'code')
    def _check_single_egg_production_type(self):
        for record in self:
            if record.is_for_production_egg:
                if record.code != 'incoming':
                    raise ValidationError(
                        "Egg Production can ONLY be set for Receive (Incoming) operation type."
                    )
                count = self.search_count([
                    ('is_for_production_egg', '=', True),
                    ('id', '!=', record.id),
                    ('company_id', '=', record.company_id.id),
                ])
                if count:
                    raise ValidationError(
                        "Only ONE Picking Type can be marked as 'For Egg Production' per company."
                    )

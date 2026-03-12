from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_egg_product = fields.Boolean(string="Is Egg Product?")

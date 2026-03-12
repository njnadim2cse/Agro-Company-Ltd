from odoo import models, fields, api

class MrpBom(models.Model):
    _inherit = 'mrp.bom'
    
    total_bom_quantity = fields.Float(
        string='Total BOM Quantity',
        compute='_compute_total_bom_quantity',
        store=False,
        digits=(16, 2)
    )
    
    @api.depends('bom_line_ids.product_qty')
    def _compute_total_bom_quantity(self):
        for bom in self:
            total = sum(bom.bom_line_ids.mapped('product_qty'))
            bom.total_bom_quantity = total
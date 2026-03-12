from odoo import models, fields, api, _

# -----------------------
# Egg Selection
# -----------------------
class EggSelection(models.Model):
    _name = 'hatchery.egg.selection'
    _description = 'Egg Selection'

    egg_batch_id = fields.Many2one('hatchery.egg.batch', ondelete='cascade', string="Egg Batch")
    lot = fields.Char(tracking=True)
    qty = fields.Integer(tracking=True)
    date = fields.Date(tracking=True)


# -----------------------
# Egg Equipment
# -----------------------
class EggEquipment(models.Model):
    _name = 'hatchery.egg.equipment'
    _description = 'Egg Equipment'

    egg_batch_id = fields.Many2one('hatchery.egg.batch', ondelete='cascade', string="Egg Batch")

    def _default_stock_farm(self):
        return self.env['stock.location'].search([('name', '=', 'Alim Agro')], limit=1)

    equipment_id = fields.Many2one(
        'stock.location',
        string='Equipment / Rack',
        default=_default_stock_farm,
        ondelete='set null',
        tracking=True
    )

    # ✅ New fields
    lot = fields.Char(string="Lot", tracking=True)
    qty = fields.Integer(string="Quantity", tracking=True)
    date = fields.Date(string="Date", tracking=True)
    production_summary = fields.Text(string="Production Summary", tracking=True)

    notes = fields.Text(tracking=True)


# -----------------------
# Egg Material
# -----------------------
class EggMaterial(models.Model):
    _name = 'hatchery.egg.material'
    _description = 'Egg Material'

    egg_batch_id = fields.Many2one('hatchery.egg.batch', ondelete='cascade', string="Egg Batch")

    # ✅ New fields
    product_id = fields.Many2one('product.product', string="Product", ondelete='set null')
    description = fields.Char(string="Description")
    lot = fields.Char(string="Lot")
    qty = fields.Float(string="Quantity", tracking=True)
    uom_id = fields.Many2one('uom.uom', string="Unit of Measure")
    unit_price = fields.Float(string="Unit Price")
    subtotal = fields.Float(string="Subtotal", compute="_compute_subtotal", store=True)

    notes = fields.Text(tracking=True)

    @api.depends('qty', 'unit_price')
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = rec.qty * rec.unit_price if rec.qty and rec.unit_price else 0.0


# -----------------------
# Egg Temperature
# -----------------------
class EggTemperature(models.Model):
    _name = 'hatchery.egg.temperature'
    _description = 'Egg Temperature'

    egg_batch_id = fields.Many2one('hatchery.egg.batch', ondelete='cascade', string="Egg Batch")
    date = fields.Date(tracking=True)
    min_temp = fields.Float(tracking=True)
    max_temp = fields.Float(tracking=True)
    avg_temp = fields.Float(tracking=True)

    # ✅ New fields
    user_id = fields.Many2one('res.users', string="Responsible", default=lambda self: self.env.user)
    humidity = fields.Float(string="Humidity (%)")


# -----------------------
# Egg Sanitizer / Cleaning
# -----------------------
class EggSanitizer(models.Model):
    _name = 'hatchery.egg.sanitizer'
    _description = 'Sanitizer Cleaning'

    egg_batch_id = fields.Many2one('hatchery.egg.batch', ondelete='cascade', string="Egg Batch")
    checklist = fields.Text(tracking=True)
    date = fields.Date(tracking=True)
    user_id = fields.Many2one(
        'res.users',
        default=lambda self: self.env.user,
        ondelete='set null',
        string="Responsible"
    )

from odoo import models, fields, api, _
from odoo.exceptions import UserError

# -----------------------
# Hatcher Machine
# -----------------------
class HatcherMachine(models.Model):
    _name = 'hatchery.hatcher.machine'
    _description = 'Hatcher Machine'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True)
    capacity = fields.Integer(default=50000)
    hatcher_stage_ids = fields.One2many(
        'hatchery.hatcher.stage', 'machine_id', string="Hatcher Stages"
    )


# -----------------------
# Hatcher Stage
# -----------------------
class HatcherStage(models.Model):
    _name = 'hatchery.hatcher.stage'
    _description = 'Hatcher Stage'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string="Serial Number",
        required=True,
        copy=False,
        readonly=True,
        default='New'
    )
    batch_id = fields.Many2one(
        'hatchery.egg.batch',
        string='Egg Batch',
        required=True,
        tracking=True,
        default=lambda self: self.env['hatchery.egg.batch'].search([], order='id desc', limit=1).id
    )
    setter_stage_id = fields.Many2one(
        'hatchery.setter.stage',
        string='Setter Stage',
        required=True,
        tracking=True
    )
    machine_id = fields.Many2one(
        'hatchery.hatcher.machine',
        string='Hatcher Machine',
        required=True
    )
    quantity_loaded = fields.Integer(string='Quantity Loaded', required=True)
    qty_available = fields.Integer(
        string="Available Quantity",
        compute="_compute_qty_available",
        store=True
    )
    mortality = fields.Integer(string='Mortality', default=0)
    success_rate = fields.Float(
        string='Success Rate (%)',
        compute='_compute_success_rate',
        store=True
    )
    start_date = fields.Datetime(string='Start Date', default=fields.Datetime.now)
    end_date = fields.Datetime(string='End Date')
    state = fields.Selection([
        ('in_hatcher', '🐣 In Hatcher'),
        ('ready_for_packaging', '📦 Ready for Packaging'),
        ('done', '✅ Done')
    ], string='Status', default='in_hatcher', tracking=True)

    # Button visibility
    show_move_to_packaging = fields.Boolean(
        string="Show Move to Packaging Button",
        compute='_compute_button_visibility'
    )
    show_done = fields.Boolean(
        string="Show Done Button",
        compute='_compute_button_visibility'
    )

    # -----------------------
    # One2many relationships
    # -----------------------
    equipment_ids = fields.One2many(
        'hatchery.hatcher.stage.equipment', 'hatcher_stage_id', string="Equipments"
    )
    material_ids = fields.One2many(
        'hatchery.hatcher.stage.material', 'hatcher_stage_id', string="Materials"
    )
    temperature_ids = fields.One2many(
        'hatchery.hatcher.stage.temperature', 'hatcher_stage_id', string="Temperature"
    )
    sanitizer_ids = fields.One2many(
        'hatchery.hatcher.stage.sanitizer', 'hatcher_stage_id', string="Sanitizer Cleaning"
    )
    hatcher_break_line_ids = fields.One2many(
        'hatchery.hatcher.break.history', 'hatcher_stage_id', string="Hatcher Break History"
    )

    # -----------------------
    # Compute Methods
    # -----------------------
    @api.depends('quantity_loaded', 'mortality', 'hatcher_break_line_ids.break_qty')
    def _compute_qty_available(self):
        for rec in self:
            broken_qty = sum(rec.hatcher_break_line_ids.mapped('break_qty') or [0])
            rec.qty_available = max((rec.quantity_loaded or 0) - (rec.mortality or 0) - broken_qty, 0)

    @api.depends('quantity_loaded', 'mortality', 'hatcher_break_line_ids.break_qty')
    def _compute_success_rate(self):
        for rec in self:
            broken_qty = sum(rec.hatcher_break_line_ids.mapped('break_qty') or [0])
            total_losses = (rec.mortality or 0) + broken_qty
            rec.success_rate = ((rec.quantity_loaded - total_losses) / rec.quantity_loaded * 100) if rec.quantity_loaded else 0

    @api.depends('state')
    def _compute_button_visibility(self):
        for rec in self:
            rec.show_move_to_packaging = rec.state == 'in_hatcher'
            rec.show_done = rec.state == 'ready_for_packaging'

    # -----------------------
    # Constraints
    # -----------------------
    @api.constrains('start_date', 'end_date')
    def _check_setter_duration(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                duration = rec.end_date - rec.start_date
                if duration.days > 3:
                    raise UserError(
                        f"⚠️ The duration of this Hatcher Stage is {duration.days} days, which exceeds the allowed 3 days."
                    )

    # -----------------------
    # Actions
    # -----------------------
    def action_move_to_packaging(self):
      ChickPackaging = self.env['chick.packaging']
      for rec in self:
        # Check if packaging already exists for this hatcher stage
        existing_packaging = ChickPackaging.search([('hatcher_stage_id', '=', rec.id)], limit=1)
        if existing_packaging:
            raise UserError(f"⚠️ Packaging record already exists for Hatcher Stage {rec.name}. Cannot create duplicate.")

        broken_qty = sum(rec.hatcher_break_line_ids.mapped('break_qty') or [0])
        chicks_after_hatcher = (rec.quantity_loaded or 0) - (rec.mortality or 0) - broken_qty
        rec.state = 'ready_for_packaging'
        rec.message_post(
            body=f"Hatcher Stage ready for packaging. Mortality: {rec.mortality}, Broken: {broken_qty}, Success Rate: {rec.success_rate:.1f}%"
        )
        
        ChickPackaging.create({
            'hatcher_stage_id': rec.id,
            'batch_id': rec.batch_id.id,
            'chicks_count': chicks_after_hatcher,
        })

    def action_done(self):
        for rec in self:
            if rec.state != 'ready_for_packaging':
                raise UserError("Cannot mark as Done. Move batch to Hatcher first.")
            rec.state = 'done'
            rec.end_date = fields.Datetime.now()
            rec.message_post(body="Batch marked as Done in Setter.")

    # -----------------------
    # Override create method
    # -----------------------
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('hatchery.hatcher.stage') or 'HATCHER/0001'
        stage = super().create(vals)
        setter_stage = stage.setter_stage_id
        if setter_stage:
            # Copy Equipments
            for eq in setter_stage.equipment_ids:
                self.env['hatchery.hatcher.stage.equipment'].create({
                    'hatcher_stage_id': stage.id,
                    'equipment_id': eq.equipment_id.id if eq.equipment_id else False,
                    'lot': eq.lot or '',
                    'qty': eq.qty or 0,
                    'date': eq.date,
                    'production_summary': eq.production_summary or '',
                })
            # Copy Materials
            for mat in setter_stage.material_ids:
                self.env['hatchery.hatcher.stage.material'].create({
                    'hatcher_stage_id': stage.id,
                    'product_id': mat.product_id.id if mat.product_id else False,
                    'description': mat.description,
                    'lot': mat.lot,
                    'qty': mat.qty,
                    'uom_id': mat.uom_id.id if mat.uom_id else False,
                    'unit_price': mat.unit_price,
                    'subtotal': mat.subtotal,
                })
            # Copy Temperature
            for temp in setter_stage.temperature_ids:
                self.env['hatchery.hatcher.stage.temperature'].create({
                    'hatcher_stage_id': stage.id,
                    'date': temp.date,
                    'min_temp': temp.min_temp,
                    'max_temp': temp.max_temp,
                    'avg_temp': temp.avg_temp,
                    'humidity': temp.humidity,
                    'user_id': temp.user_id.id if temp.user_id else False,
                })
            # Copy Sanitizer
            for san in setter_stage.sanitizer_ids:
                self.env['hatchery.hatcher.stage.sanitizer'].create({
                    'hatcher_stage_id': stage.id,
                    'checklist': san.checklist,
                    'date': san.date,
                    'user_id': san.user_id.id if san.user_id else False,
                })
        return stage


# -----------------------
# Related Models: Equipment, Material, Temperature, Sanitizer
# -----------------------
class HatcherStageEquipment(models.Model):
    _name = 'hatchery.hatcher.stage.equipment'
    _description = 'Hatcher Stage Equipment'

    hatcher_stage_id = fields.Many2one('hatchery.hatcher.stage', string="Hatcher Stage", ondelete='cascade')
    equipment_id = fields.Many2one('stock.location', string="Equipment / Rack", ondelete='set null')
    lot = fields.Char(string="Lot")
    qty = fields.Integer(string="Quantity")
    date = fields.Date(string="Date")
    production_summary = fields.Text(string="Production Summary")


class HatcherStageMaterial(models.Model):
    _name = 'hatchery.hatcher.stage.material'
    _description = 'Hatcher Stage Material'

    hatcher_stage_id = fields.Many2one('hatchery.hatcher.stage', string="Hatcher Stage", ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Product", ondelete='set null')
    description = fields.Text(string="Description")
    lot = fields.Char(string="Lot")
    qty = fields.Float(string="Quantity")
    uom_id = fields.Many2one('uom.uom', string="Unit of Measure", ondelete='set null')
    unit_price = fields.Float(string="Unit Price")
    subtotal = fields.Float(string="Subtotal", compute="_compute_subtotal", store=True)

    @api.depends('qty', 'unit_price')
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = rec.qty * rec.unit_price if rec.qty and rec.unit_price else 0.0


class HatcherStageTemperature(models.Model):
    _name = 'hatchery.hatcher.stage.temperature'
    _description = 'Hatcher Stage Temperature'

    hatcher_stage_id = fields.Many2one('hatchery.hatcher.stage', string="Hatcher Stage", ondelete='cascade')
    date = fields.Datetime(string="Date")
    min_temp = fields.Float(string="Min Temperature")
    max_temp = fields.Float(string="Max Temperature")
    avg_temp = fields.Float(string="Average Temperature")
    humidity = fields.Float(string="Humidity (%)")
    user_id = fields.Many2one('res.users', string="Recorded By", ondelete='set null')


class HatcherStageSanitizer(models.Model):
    _name = 'hatchery.hatcher.stage.sanitizer'
    _description = 'Hatcher Stage Sanitizer'

    hatcher_stage_id = fields.Many2one('hatchery.hatcher.stage', string="Hatcher Stage", ondelete='cascade')
    checklist = fields.Text(string="Checklist")
    date = fields.Datetime(string="Date")
    user_id = fields.Many2one('res.users', string="Checked By", ondelete='set null')

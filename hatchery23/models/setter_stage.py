import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta

logger = logging.getLogger(__name__)

# -----------------------
# Setter Stage
# -----------------------
class SetterStage(models.Model):
    _name = 'hatchery.setter.stage'
    _description = 'Setter Stage'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(
        string="Serial Number",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: 'New'
    )

    batch_id = fields.Many2one(
        'hatchery.egg.batch', string='Egg Batch', required=True, tracking=True,
        default=lambda self: self.env['hatchery.egg.batch'].search([], order='id desc', limit=1).id
    )
    machine_id = fields.Many2one(
        'hatchery.setter.machine', string='Setter Machine', required=True)
    quantity_loaded = fields.Integer(string='Quantity Loaded', required=True)
    mortality = fields.Integer(string='Mortality', default=0)
    qty_available = fields.Integer(
        string="Available Quantity", compute="_compute_qty_available", store=True)
    success_rate = fields.Float(
        string='Success Rate (%)', compute='_compute_success_rate', store=True)
    start_date = fields.Datetime(string='Start Date', default=fields.Datetime.now)
    end_date = fields.Datetime(string='End Date')

    state = fields.Selection([
        ('draft', '🏭 Draft'),
        ('in_setter', '🔄 In Setter'),
        ('ready_for_hatcher', '🐣 Ready for Hatcher'),
        ('done', '✅ Done')
    ], string='Status', default='in_setter', tracking=True)

    show_move_to_hatcher = fields.Boolean(
        string="Show Move to Hatcher Button",
        compute='_compute_button_visibility'
    )
    show_done = fields.Boolean(
        string="Show Done Button",
        compute='_compute_button_visibility'
    )

    # Related One2many fields
    equipment_ids = fields.One2many(
        'hatchery.setter.stage.equipment', 'setter_stage_id', string="Equipments")
    material_ids = fields.One2many(
        'hatchery.setter.stage.material', 'setter_stage_id', string="Materials")
    temperature_ids = fields.One2many(
        'hatchery.setter.stage.temperature', 'setter_stage_id', string="Temperature")
    sanitizer_ids = fields.One2many(
        'hatchery.setter.stage.sanitizer', 'setter_stage_id', string="Sanitizer Cleaning")

    setter_break_line_ids = fields.One2many(
       'hatchery.setter.break.history', 'setter_stage_id', string="Setter Break History")

    total_broken = fields.Float(
        string="Total Broken Eggs",
        compute='_compute_total_broken', store=True
    )

    # -----------------------
    # Compute Methods
    # -----------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'batch_id' in fields_list and not res.get('batch_id'):
            first_batch = self.env['hatchery.egg.batch'].search([], limit=1)
            if first_batch:
                res['batch_id'] = first_batch.id
        return res
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('hatchery.setter.stage') or 'SETTER/0001'
        return super().create(vals)
    @api.onchange('machine_id')
    def _onchange_machine(self):
        for rec in self:
            if not rec.batch_id:
                batch = self.env['hatchery.egg.batch'].search([], limit=1)
                if batch:
                    rec.batch_id = batch.id
    
    @api.depends('quantity_loaded', 'mortality', 'setter_break_line_ids.break_qty')
    def _compute_qty_available(self):
        for rec in self:
            broken_qty = sum(rec.setter_break_line_ids.mapped('break_qty') or [0])
            rec.qty_available = max((rec.quantity_loaded or 0) - (rec.mortality or 0) - broken_qty, 0)

    @api.depends('quantity_loaded', 'mortality', 'setter_break_line_ids.break_qty')
    def _compute_success_rate(self):
        for rec in self:
            broken_qty = sum(rec.setter_break_line_ids.mapped('break_qty') or [0])
            total_losses = (rec.mortality or 0) + broken_qty
            if rec.quantity_loaded:
                rec.success_rate = ((rec.quantity_loaded - total_losses) / rec.quantity_loaded) * 100
            else:
                rec.success_rate = 0

    @api.depends('state')
    def _compute_button_visibility(self):
        for rec in self:
            rec.show_move_to_hatcher = rec.state == 'in_setter'
            rec.show_done = rec.state == 'ready_for_hatcher'

    @api.depends('setter_break_line_ids.break_qty')
    def _compute_total_broken(self):
        for rec in self:
            rec.total_broken = sum(rec.setter_break_line_ids.mapped('break_qty') or [0])

    # -----------------------
    # Constraint: Maximum 18 Days
    # -----------------------
    @api.constrains('start_date', 'end_date')
    def _check_setter_duration(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                duration = rec.end_date - rec.start_date
                if duration.days > 18:
                    raise UserError(
                        f"⚠️ The duration of this Setter Stage is {duration.days} days, which exceeds the allowed 18 days."
                    )

    # -----------------------
    # Stage Actions
    # -----------------------
    def action_move_to_hatcher(self):
        HatcherStage = self.env['hatchery.hatcher.stage']
        HatcherMachine = self.env['hatchery.hatcher.machine']

        for rec in self:
            existing_hatcher = HatcherStage.search([('setter_stage_id', '=', rec.id)], limit=1)
            if existing_hatcher:
                 raise UserError(f"⚠️ Hatcher Stage already created for Setter Stage {rec.name}. Cannot create duplicate.")
            rec.state = 'ready_for_hatcher'
            rec.end_date = fields.Datetime.now()

            eggs_after_setter = rec.qty_available
            success_rate = ((eggs_after_setter / rec.quantity_loaded) * 100) if rec.quantity_loaded else 0

            machine = HatcherMachine.search([], limit=1)
            if not machine:
                machine = HatcherMachine.create({'name': 'Default Hatcher Machine', 'capacity': 50000})

            HatcherStage.create({
                'batch_id': rec.batch_id.id,
                'setter_stage_id': rec.id,
                'machine_id': machine.id,
                'quantity_loaded': eggs_after_setter,
                'mortality': rec.mortality,
                'success_rate': success_rate,
                'state': 'in_hatcher',
            })

            rec.message_post(body=f"Moved {eggs_after_setter} eggs to Hatcher. Mortality: {rec.mortality}, Success Rate: {success_rate:.1f}%")
    def action_done(self):
        for rec in self:
            if rec.state != 'ready_for_hatcher':
                raise UserError("Cannot mark as Done. Move batch to Hatcher first.")
            rec.state = 'done'
            rec.end_date = fields.Datetime.now()
            rec.message_post(body="Batch marked as Done in Setter.")


# -----------------------
# Related Models
# -----------------------
class SetterStageEquipment(models.Model):
    _name = 'hatchery.setter.stage.equipment'
    _description = 'Setter Stage Equipment'

    setter_stage_id = fields.Many2one('hatchery.setter.stage', string="Setter Stage", ondelete='cascade')
    equipment_id = fields.Many2one('stock.location', string="Equipment / Rack", ondelete='set null')
    lot = fields.Char(string="Lot")
    qty = fields.Integer(string="Quantity")
    date = fields.Date(string="Date")
    production_summary = fields.Text(string="Production Summary")


class SetterStageMaterial(models.Model):
    _name = 'hatchery.setter.stage.material'
    _description = 'Setter Stage Material'

    setter_stage_id = fields.Many2one('hatchery.setter.stage', string="Setter Stage", ondelete='cascade')
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


class SetterStageTemperature(models.Model):
    _name = 'hatchery.setter.stage.temperature'
    _description = 'Setter Stage Temperature'

    setter_stage_id = fields.Many2one('hatchery.setter.stage', string="Setter Stage", ondelete='cascade')
    date = fields.Datetime(string="Date")
    min_temp = fields.Float(string="Min Temperature")
    max_temp = fields.Float(string="Max Temperature")
    avg_temp = fields.Float(string="Average Temperature")
    humidity = fields.Float(string="Humidity (%)")
    user_id = fields.Many2one('res.users', string="Recorded By", ondelete='set null')


class SetterStageSanitizer(models.Model):
    _name = 'hatchery.setter.stage.sanitizer'
    _description = 'Setter Stage Sanitizer'

    setter_stage_id = fields.Many2one('hatchery.setter.stage', string="Setter Stage", ondelete='cascade')
    checklist = fields.Text(string="Checklist")
    date = fields.Datetime(string="Date")
    user_id = fields.Many2one('res.users', string="Checked By", ondelete='set null')

import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EggBatch(models.Model):
    _name = 'hatchery.egg.batch'
    _description = 'Egg Batch'
    _rec_name = 'batch_no'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company
    )
    user_id = fields.Many2one(
        'res.users', string='Responsible', default=lambda self: self.env.user
    )
    batch_no = fields.Char(
        string='Batch / Lot Number', required=True, tracking=True, default='New'
    )
    date_received = fields.Date(string='Date Received')
    qty_received = fields.Integer(string='Quantity Received')
    broken_qty = fields.Integer(string="Broken Quantity", default=0)
    delivered_qty = fields.Integer(string="Delivered Quantity", default=0)
    location_id = fields.Many2one(
        'stock.location',
        string="Pre-Storage Location",
        required=True,
        default=lambda self: self.env.ref('stock.stock_location_stock').id
    )

    qty_available = fields.Integer(
        string="Available Quantity", compute="_compute_qty_available", store=True
    )
    break_line_ids = fields.One2many(
        'hatchery.egg.batch.break.history', 'batch_id', string='Break Lines'
    )
    egg_transfer_ids = fields.One2many(
        'hatchery.egg.selection', 'egg_batch_id', string="Transfers from Pre-Storage"
    )

    prestorage_id = fields.Many2one(
        'hatchery.prestorage.batch',
        string="Pre-Storage Batch",
        default=lambda self: self._get_current_prewaste()
    )
    transfer_qty = fields.Float(
        string="Transfer Quantity", compute="_compute_transfer_qty", store=True
    )
    pre_storage_waste = fields.Integer(string='Pre-storage Waste')
    notes = fields.Text(string='Notes')

    state = fields.Selection([
        ('draft', '🏭 Draft'),
        ('in_setter', '🔄 In Setter'),
        ('ready_for_hatcher', '➡️ Ready for Hatcher'),
        ('in_hatcher', '🐣 In Hatcher'),
    
    ], string='Status', default='draft', tracking=True)

    # Button visibility
    show_send_to_setter = fields.Boolean(compute='_compute_button_visibility')
    show_move_to_hatcher = fields.Boolean(compute='_compute_button_visibility')
    show_done = fields.Boolean(compute='_compute_button_visibility')

    # Supporting fields
    success_rate = fields.Float(string='Success Rate', digits=(12, 2), default=0.0)
    

    # Relations
    egg_selection_ids = fields.One2many('hatchery.egg.selection', 'egg_batch_id', string='Selection of Eggs')
    equipment_ids = fields.One2many('hatchery.egg.equipment', 'egg_batch_id', string='Equipments')
    material_ids = fields.One2many('hatchery.egg.material', 'egg_batch_id', string='Materials')
    temperature_ids = fields.One2many('hatchery.egg.temperature', 'egg_batch_id', string='Temperature')
    sanitizer_ids = fields.One2many('hatchery.egg.sanitizer', 'egg_batch_id', string='Sanitizer Cleaning')

    # ----------------------------
    # Computed Fields
    # ----------------------------
    @api.depends('qty_received', 'broken_qty', 'delivered_qty')
    def _compute_qty_available(self):
        for rec in self:
            rec.qty_available = max((rec.qty_received or 0) - (rec.broken_qty or 0) - (rec.delivered_qty or 0), 0)

    @api.depends('state')
    def _compute_button_visibility(self):
        for rec in self:
            rec.show_send_to_setter = rec.state == 'draft'
            rec.show_move_to_hatcher = rec.state == 'in_setter'
            rec.show_done = rec.state == 'in_hatcher'

    @api.depends('egg_transfer_ids.transfer_qty')
    def _compute_transfer_qty(self):
        for rec in self:
            rec.transfer_qty = sum(rec.egg_transfer_ids.mapped('transfer_qty'))

    # ----------------------------
    # Overrides
    # ----------------------------
    @api.model
    def create(self, vals):
        if not vals.get('batch_no') or vals['batch_no'] == 'New':
            vals['batch_no'] = self.env['ir.sequence'].next_by_code('hatchery.egg.batch') or 'BATCH-001'
        return super().create(vals)

    def _get_current_prewaste(self):
        prebatch = self.env['hatchery.prestorage.batch'].search([], order='id desc', limit=1)
        return prebatch.id if prebatch else False

    # ----------------------------
    # Workflow Actions
    # ----------------------------
    def action_send_to_setter(self):
        SetterStage = self.env['hatchery.setter.stage']
        setter_machines = self.env['hatchery.setter.machine'].search([], order='id asc')
        if not setter_machines:
            setter_machines = self.env['hatchery.setter.machine'].create([
                {'name': f'Default Setter Machine {i+1}', 'capacity': 100000} for i in range(7)
            ])
        for rec in self:
            if rec.state != 'draft':
                raise UserError("⚠ This batch has already been sent to Setter.")
            qty_remaining = rec.qty_available
            for machine in setter_machines:
                if qty_remaining <= 0:
                    break
                qty_for_machine = min(qty_remaining, machine.capacity)
                SetterStage.create({
                    'batch_id': rec.id,
                    'machine_id': machine.id,
                    'quantity_loaded': qty_for_machine,
                    'mortality': 0,
                    'state': 'in_setter',
                })
                qty_remaining -= qty_for_machine
            rec.state = 'in_setter'
            rec.message_post(body="✅ Batch sent to Setter.")

    def action_move_to_hatcher(self, mortality=0):
        HatcherStage = self.env['hatchery.hatcher.stage']
        SetterStage = self.env['hatchery.setter.stage']
        for rec in self:
            if rec.state != 'in_setter':
                raise UserError("⚠ This batch cannot be moved to Hatcher.")
            setter_stages = SetterStage.search([('batch_id', '=', rec.id)])
            if not setter_stages:
                raise UserError("⚠ You must send this batch to Setter before moving to Hatcher.")
            total_qty = sum(s.quantity_loaded for s in setter_stages)
            final_qty = total_qty - mortality
            if final_qty < 0:
                raise UserError("Mortality cannot exceed total quantity in Setter Stage.")
            HatcherStage.create({
                'egg_batch_id': rec.id,
                'machine_id': False,
                'quantity_loaded': final_qty,
                'mortality': mortality,
                'state': 'in_hatcher',
            })
            rec.state = 'in_hatcher'
            rec.message_post(body="✅ Batch moved to Hatcher.")

  

    # ----------------------------
    # Stock / Waste Updates
    # ----------------------------
    def _update_quant(self):
        for rec in self:
            rec.qty_available = max(
                (rec.qty_received or 0) - (rec.broken_qty or 0) - (rec.pre_storage_waste or 0), 0
            )
            rec.success_rate = (rec.qty_available / rec.qty_received * 100) if rec.qty_received else 0.0

            if rec.pre_storage_waste > 0:
                product = self.env['product.product'].search([('name', '=', 'Eggs')], limit=1)
                if not product:
                    raise UserError("Product 'Eggs' not found.")
                location = rec.location_id or self.env['stock.location'].search([('usage', '=', 'internal')], limit=1)
                if not location:
                    raise UserError("No internal stock location found.")
                if rec.stock_scrap_id:
                    rec.stock_scrap_id.sudo().write({
                        'scrap_qty': rec.pre_storage_waste,
                        'location_id': location.id,
                        'product_id': product.id,
                        'company_id': rec.company_id.id,
                        'date_done': fields.Datetime.now(),
                        'name': f"Pre-Storage Waste - {rec.batch_no}",
                    })
                else:
                    scrap = self.env['stock.scrap'].create({
                        'product_id': product.id,
                        'scrap_qty': rec.pre_storage_waste,
                        'location_id': location.id,
                        'company_id': rec.company_id.id,
                        'date_done': fields.Datetime.now(),
                        'name': f"Pre-Storage Waste - {rec.batch_no}",
                    })
                    scrap.action_validate()
                    rec.stock_scrap_id = scrap.id


class EggBatchBreakHistory(models.Model):
    _name = 'hatchery.egg.batch.break.history'
    _description = 'Egg Batch Break History'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    batch_id = fields.Many2one(
        'hatchery.egg.batch', string="Egg Batch", required=True, ondelete='cascade'
    )
    date = fields.Datetime(string="Date", default=fields.Datetime.now)
    break_qty = fields.Float(string="Broken Quantity", required=True)
    break_reason = fields.Selection([
        ('accidental', 'Accidental'),
        ('mortality', 'Mortality'),
        ('other', 'Other')
    ], string="Break Reason", required=True)
    note = fields.Text(string="Note")
    user_id = fields.Many2one('res.users', string="User", default=lambda self: self.env.user)
    processed = fields.Boolean(string="Processed", default=False)

    def action_break_eggs(self):
        product = self.env['product.product'].search([('name', '=', 'Eggs')], limit=1)
        if not product:
            raise UserError("Product 'Eggs' not found in inventory.")

        for line in self.filtered(lambda l: not l.processed):
            batch = line.batch_id
            if not batch:
                raise UserError("Break line is not linked to any Egg Batch!")

            quant = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id.usage', '=', 'internal'),
                ('quantity', '>=', line.break_qty)
            ], limit=1)

            if not quant:
                raise UserError(f"Not enough eggs in stock to scrap for batch {batch.batch_no}.")

            scrap = self.env['stock.scrap'].create({
                'product_id': product.id,
                'scrap_qty': line.break_qty,
                'location_id': quant.location_id.id,
                'company_id': getattr(batch, 'company_id', self.env.company).id,
                'origin': f"Break: {line.break_reason} - Batch {batch.batch_no}"
            })
            scrap.action_validate()

            batch.pre_storage_waste += line.break_qty
            batch.qty_available = max(batch.qty_received - batch.broken_qty - batch.pre_storage_waste, 0)
            line.processed = True

            batch.message_post(
                body=f"🥚 {line.break_qty} eggs broken in batch {batch.batch_no} "
                     f"due to {line.break_reason} on {line.date}. Note: {line.note or 'N/A'}"
            )
            _logger.info("Break processed: Batch %s, Qty %s", batch.batch_no, line.break_qty)


  

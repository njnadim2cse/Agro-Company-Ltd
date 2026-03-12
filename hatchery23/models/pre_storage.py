from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class HatcheryPreStorage(models.Model):
    _name = 'hatchery.prestorage.batch'
    _description = 'Pre-Storage Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ===========================
    # Basic Fields
    # ===========================
    name = fields.Char(
        string="Serial Number",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: 'New'
    )
    picking_id = fields.Many2one('stock.picking', string="Origin Picking")
    date_in = fields.Date(string="Date In", default=fields.Date.today)
    qty_received = fields.Float(string="Quantity Received", required=True)
    broken_qty = fields.Integer(string="Broken Quantity", default=0)
    pre_storage_waste = fields.Float(string="Pre-Storage Waste", default=0.0)
    location_id = fields.Many2one(
        'stock.location',
        string="Pre-Storage Location",
        required=True,
        default=lambda self: self.env.ref('stock.stock_location_stock').id
    )
    egg_transfer_ids = fields.One2many(
        'hatchery.egg.selection',
        'prestorage_id',
        string="Transfers to Egg Batch"
    )

    # ===========================
    # Computed Fields
    # ===========================
    available_qty = fields.Float(
        string="Available Quantity",
        compute='_compute_available_qty',
        store=True
    )
    success_rate = fields.Float(
        string='Success Rate (%)',
        compute='_compute_success_rate',
        store=True
    )
    temperature_logs = fields.Text(string="Temperature / Condition Logs")
    break_history_ids = fields.One2many(
        'hatchery.prestorage.break.history',
        'batch_id',
        string="Break History"
    )

    # ===========================
    # Status & Company
    # ===========================
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_setter', 'In Setter'),
        ('in_hatcher', 'In Hatcher'),
        ('done', 'Done')
    ], string='Status', default='draft', tracking=True)
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        default=lambda self: self.env.company
    )
    stock_scrap_id = fields.Many2one('stock.scrap', string="Related Scrap")
    deducted_qty = fields.Float(string="Transferred Quantity", default=0.0)

    # ===========================
    # Button Visibility
    # ===========================
    show_send_to_setter = fields.Boolean(
        compute='_compute_button_visibility',
        string="Show Send to Setter Button"
    )
    show_move_to_hatcher = fields.Boolean(
        compute='_compute_button_visibility',
        string="Show Move to Hatcher Button"
    )
    show_done = fields.Boolean(
        compute='_compute_button_visibility',
        string="Show Done Button"
    )
    equipment_ids = fields.One2many(
        'hatchery.egg.equipment',
        'egg_batch_id',
        string='Equipments'
    )
    transfer_status = fields.Char(string="Transfer Status", compute="_compute_transfer_status", store=False)

    @api.depends('egg_transfer_ids.state')
    def _compute_transfer_status(self):
        for rec in self:
            if not rec.egg_transfer_ids:
                rec.transfer_status = "📝 Draft"
                continue

            states = rec.egg_transfer_ids.mapped('state')

            # If all are done → ✅ Done
            if all(state == 'done' for state in states):
                rec.transfer_status = "✅ Done"
            else:
                rec.transfer_status = "📝 Draft"

    # ===========================
    # Compute Available Quantity
    # ===========================
   
    @api.depends('qty_received', 'broken_qty', 'pre_storage_waste', 'egg_transfer_ids.state', 'egg_transfer_ids.transfer_qty')
    def _compute_available_qty(self):
       for rec in self:
        # ✅ Sum only "done" transfers
          done_transfers = rec.egg_transfer_ids.filtered(lambda t: t.state == 'done')
          transferred = sum(done_transfers.mapped('transfer_qty'))

        # ✅ Compute remaining quantity safely
          rec.available_qty = max(
             rec.qty_received - rec.broken_qty - rec.pre_storage_waste - transferred,
             0
        )


    # ===========================
    # Compute Success Rate
    # ===========================
    @api.depends('qty_received', 'available_qty')
    def _compute_success_rate(self):
        for rec in self:
            if rec.qty_received > 0:
                rec.success_rate = (rec.available_qty / rec.qty_received) * 100
            else:
                rec.success_rate = 0.0

    # ===========================
    # Compute Button Visibility
    # ===========================
    @api.depends('state')
    def _compute_button_visibility(self):
        for rec in self:
            rec.show_send_to_setter = rec.state == 'draft'
            rec.show_move_to_hatcher = rec.state == 'in_setter'
            rec.show_done = rec.state == 'in_setter'

    # ===========================
    # Update Quantities and Scrap
    # ===========================
    def _update_quant(self):
        """Update available quantity, success rate, and scrap."""
        for rec in self:
            # Update available quantity and success rate
            rec.available_qty = max(
                rec.qty_received - rec.broken_qty - rec.pre_storage_waste - rec.deducted_qty,
                0
            )
            rec.success_rate = (rec.available_qty / rec.qty_received) * 100 if rec.qty_received > 0 else 0.0

            # Create or update scrap record
            if rec.pre_storage_waste > 0:
                product = self.env['product.product'].search([('name', '=', 'Eggs')], limit=1)
                if not product:
                    raise UserError(_("Product 'Eggs' not found in inventory."))

                location = rec.location_id or self.env['stock.location'].search([('usage', '=', 'internal')], limit=1)
                if not location:
                    raise UserError(_("No internal stock location found."))

                tag = self.env['stock.scrap.reason.tag'].search([('name', '=', 'Pre-Storage Waste')], limit=1)
                if not tag:
                    tag = self.env['stock.scrap.reason.tag'].create({'name': 'Pre-Storage Waste'})

                if rec.stock_scrap_id:
                    # Update existing scrap
                    rec.stock_scrap_id.sudo().write({
                        'scrap_qty': rec.pre_storage_waste,
                        'location_id': location.id,
                        'product_id': product.id,
                        'company_id': rec.company_id.id,
                        'date_done': fields.Datetime.now(),
                        'name': f"Pre-Storage Waste - {rec.name}",
                        'scrap_reason_tag_ids': [(6, 0, [tag.id])],
                    })
                    _logger.info("🔄 Updated Scrap for Pre-Storage %s: %s eggs", rec.name, rec.pre_storage_waste)
                else:
                    # Create new scrap
                    scrap = self.env['stock.scrap'].create({
                        'product_id': product.id,
                        'scrap_qty': rec.pre_storage_waste,
                        'location_id': location.id,
                        'company_id': rec.company_id.id,
                        'date_done': fields.Datetime.now(),
                        'name': f"Pre-Storage Waste - {rec.name}",
                        'scrap_reason_tag_ids': [(6, 0, [tag.id])],
                    })
                    scrap.action_validate()
                    rec.stock_scrap_id = scrap.id
                    _logger.info("📦 Scrap created for Pre-Storage %s: %s eggs", rec.name, rec.pre_storage_waste)

            _logger.info(
                "🔄 Updated quantities for Pre-Storage Batch %s: Available %s, Success Rate %.2f%%",
                rec.name, rec.available_qty, rec.success_rate
            )

    # ===========================
    # Create Record
    # ===========================
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('hatchery.prestorage.batch') or 'New'
        record = super().create(vals)
        record._update_quant()
        return record

    # ===========================
    # Write (Update Record)
    # ===========================
    def write(self, vals):
        res = super(HatcheryPreStorage, self).write(vals)
        if 'pre_storage_waste' in vals or 'broken_qty' in vals or 'qty_received' in vals:
            for rec in self:
                rec._update_quant()
        return res

    # ===========================
    # Onchange (Instant UI Feedback)
    # ===========================
    @api.onchange('pre_storage_waste', 'broken_qty', 'qty_received')
    def _onchange_pre_storage_waste(self):
        self._compute_available_qty()
        self._compute_success_rate()

    # ===========================
    # Send to Setter
    # ===========================
    def action_send_to_setter(self):
        SetterStage = self.env['hatchery.setter.stage']
        setter_machines = self.env['hatchery.setter.machine'].search([], order='id asc')
        if not setter_machines:
            setter_machines = self.env['hatchery.setter.machine'].create([
                {'name': f'Default Setter Machine {i+1}', 'capacity': 100000} for i in range(7)
            ])

        for rec in self:
            qty_remaining = rec.available_qty
            for machine in setter_machines:
                if qty_remaining <= 0:
                    break
                qty_for_machine = min(qty_remaining, machine.capacity)
                SetterStage.create({
                    'prestorage_batch_id': rec.id,
                    'machine_id': machine.id,
                    'quantity_loaded': qty_for_machine,
                    'mortality': 0,
                    'state': 'in_setter',
                })
                qty_remaining -= qty_for_machine

            sent_qty = rec.available_qty
            rec.qty_received -= sent_qty
            rec.state = 'in_setter'
            rec.message_post(body=f"✅ Batch sent to Setter. Quantity sent: {sent_qty}")
            _logger.info("➡ Batch %s sent to setter: %s eggs", rec.name, sent_qty)
            rec._update_quant()

    # ===========================
    # Mark as Done
    # ===========================
    def action_done(self):
        SetterStage = self.env['hatchery.setter.stage']
        for rec in self:
            setter_stages = SetterStage.search([('prestorage_batch_id', '=', rec.id)])
            if not setter_stages:
                raise UserError(_("Cannot mark as Done. Process the batch in Setter first."))
            rec.state = 'done'
            rec.message_post(body="✅ Batch marked as Done.")
            _logger.info("✅ Batch %s marked as Done", rec.name)










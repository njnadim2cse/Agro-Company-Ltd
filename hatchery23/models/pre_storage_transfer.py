import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)  

class EggSelection(models.Model):
    _name = 'hatchery.egg.selection'
    _description = 'Egg Transfer from Pre-Storage'
    _inherit = ['mail.thread']

    # --------------------------
    # Relations
    # --------------------------
    egg_batch_id = fields.Many2one(
        'hatchery.egg.batch',
        string='Egg Batch',
        required=False,
        ondelete='cascade'
    )
    prestorage_id = fields.Many2one(
        'hatchery.prestorage.batch',
        string='Pre-Storage Batch',
        store=True
    )

    # --------------------------
    # Quantities
    # --------------------------
    available_qty = fields.Float(
        string='Available Quantity',
        compute='_compute_available_qty',
        store=True
    )
    transfer_qty = fields.Float(
        string='Transfer Quantity',
        required=True
    )

    transferred = fields.Boolean(
        string="Transferred",
        default=False,
        help="Indicates whether this line has been transferred"
    )
    
  
    state = fields.Selection([
    ('draft', '📝 Draft'),
    ('done', '✅ Done'),
    ], string='Status', default='draft', tracking=True)


    can_transfer = fields.Boolean(
        string="Can Transfer",
        compute="_compute_can_transfer",
        store=True
    )

    @api.depends('state')
    def _compute_can_transfer(self):
        """Button visibility: only show if not done"""
        for rec in self:
            rec.can_transfer = rec.state != 'done'

    # --------------------------
    # Compute Available Qty
    # --------------------------
    @api.depends('prestorage_id')
    def _compute_available_qty(self):
        """Show available qty from selected Pre-Storage batch"""
        for rec in self:
            rec.available_qty = rec.prestorage_id.available_qty if rec.prestorage_id else 0.0

    # --------------------------
    # Transfer Logic
    # --------------------------
    def action_transfer(self):
        """Transfer eggs from Pre-Storage to Egg Batch with auto batch creation"""
        for rec in self:
            if rec.transferred:
                raise UserError(_("This line has already been transferred."))

            # --- Auto-create Egg Batch if missing ---
            if not rec.egg_batch_id:
                egg_batch = self.env['hatchery.egg.batch'].create({
                    'batch_no': self.env['ir.sequence'].next_by_code('hatchery.egg.batch') or 'BATCH-001',
                    'date_received': fields.Date.today(),
                    'qty_received': 0,
                })
                rec.egg_batch_id = egg_batch

            # Auto-generate batch_no if still 'New'
            if rec.egg_batch_id.batch_no == 'New':
                rec.egg_batch_id.batch_no = self.env['ir.sequence'].next_by_code('hatchery.egg.batch') or 'BATCH-001'

            # Validation
            if not rec.prestorage_id:
                raise UserError(_("Pre-Storage batch not selected."))

            if rec.transfer_qty <= 0:
                raise UserError(_("Transfer Quantity must be greater than 0."))

            if rec.transfer_qty > rec.prestorage_id.available_qty:
                raise UserError(_("Cannot transfer more than available quantity in Pre-Storage."))

            # Deduct from Pre-Storage batch
            # rec.prestorage_id.qty_received -= rec.transfer_qty
            # NEW (safe)
            rec.prestorage_id.deducted_qty += rec.transfer_qty
            if hasattr(rec.prestorage_id, '_update_quant'):
                rec.prestorage_id._update_quant()  # recompute available qty
            

            # Add to Egg Batch
            # --- Add to Egg Batch ---
            rec.egg_batch_id.qty_received = (rec.egg_batch_id.qty_received or 0) + rec.transfer_qty
            rec.egg_batch_id._update_quant()  

            # Mark this selection line as transferred
            rec.transferred = True
            rec.state = 'done'
            
            _logger.info("EggSelection ID %s state after transfer: %s", rec.id, rec.state)
            # or just for console debugging (less recommended)
            print(f"EggSelection ID {rec.id} state after transfer: {rec.state}")

            # Log message on Egg Batch
            rec.egg_batch_id.message_post(
                body=_("✅ Transferred %s eggs from Pre-Storage <b>%s</b> into this Egg Batch.") %
                     (rec.transfer_qty, rec.prestorage_id.name)
            )

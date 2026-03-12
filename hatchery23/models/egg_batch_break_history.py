import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

logger = logging.getLogger(__name__)

class EggBatchBreakHistory(models.Model):
    _name = 'hatchery.egg.batch.break.history'
    _description = 'Egg Batch Break History'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    batch_id = fields.Many2one('hatchery.egg.batch', string="Egg Batch", required=True, ondelete='cascade')
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
    stock_scrap_id = fields.Many2one('stock.scrap', string="Related Scrap")  # ❌ remove default

    def action_break_eggs(self):
        """Break egg lines and update stock + batch quantities"""
        product = self.env['product.product'].search([('name', '=', 'Eggs')], limit=1)
        if not product:
            raise UserError("Product 'Eggs' not found in inventory.")

        for line in self.filtered(lambda l: not l.processed):
            batch = line.batch_id
            if not batch:
                raise UserError("Break line is not linked to any Egg Batch!")

            # Find available stock quant
            quant = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id', '=', batch.location_id.id),
                ('quantity', '>=', line.break_qty)
            ], limit=1)

            if not quant:
                raise UserError(f"Not enough eggs in stock to scrap for batch {batch.batch_no}.")

            # Create a scrap specifically for this egg batch break
            scrap = self.env['stock.scrap'].create({
                'product_id': product.id,
                'scrap_qty': line.break_qty,
                'location_id': quant.location_id.id,
                'company_id': batch.company_id.id if batch.company_id else self.env.company.id,
                'origin': f"Egg Break: {line.break_reason} - Batch {batch.batch_no}"
            })
            scrap.action_validate()

            # Update Egg Batch counts correctly
            batch.broken_qty += line.break_qty  # ✅ use broken_qty, not pre_storage_waste
            batch.qty_available = max(batch.qty_received - batch.broken_qty - getattr(batch, 'pre_storage_waste', 0), 0)

            # Link scrap to the break line
            line.stock_scrap_id = scrap.id
            line.processed = True

            # Post message
            batch.message_post(
                body=f"🥚{line.break_qty} eggs broken in batch {batch.batch_no} "
                     f"due to {line.break_reason} on {line.date}. Note: {line.note or 'N/A'}"
            )
            logger.info("Egg batch break processed: Batch %s, Qty %s, Scrap ID %s", batch.batch_no, line.break_qty, scrap.id)

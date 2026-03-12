import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class PreStorageBreakHistory(models.Model):
    _name = 'hatchery.prestorage.break.history'
    _description = 'Pre-Storage Break History'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    batch_id = fields.Many2one(
        'hatchery.prestorage.batch', 
        string="Pre-Storage Batch", 
        required=True, 
        ondelete='cascade'
    )
    date = fields.Datetime(string="Date", default=fields.Datetime.now)
    break_qty = fields.Float(string="Broken Quantity", required=True)
    break_reason = fields.Selection(
        [('accidental','Accidental'),('mortality','Mortality'),('other','Other')], 
        string="Break Reason", 
        required=True
    )
    note = fields.Text(string="Note")
    user_id = fields.Many2one('res.users', string="User", default=lambda self: self.env.user)
    processed = fields.Boolean(string="Processed", default=False)
    stock_scrap_id = fields.Many2one(
        'stock.scrap', 
        string="Related Scrap", 
        default=lambda self: self._get_latest_scrap()
    )
    
    def _get_latest_scrap(self):
        scrap = self.env['stock.scrap'].search(
            [('name', 'ilike', 'Pre-Storage Waste')],
            order='id desc',
            limit=1
        )
        return scrap.id if scrap else False

    def action_break_eggs(self):
        product = self.env['product.product'].search([('name', '=', 'Eggs')], limit=1)
        if not product:
            raise UserError("Product 'Eggs' not found.")

        for line in self.filtered(lambda l: not l.processed):
            batch = line.batch_id
            if not batch or not batch.location_id:
                raise UserError("Batch or batch location is not set!")

            batch._update_quant()

            # Check total available quantity across all quants
            quants = self.env['stock.quant'].search([
                ('product_id','=',product.id),
                ('location_id','=',batch.location_id.id)
            ])
            total_qty = sum(quants.mapped('quantity'))
            if total_qty < line.break_qty:
                raise UserError(
                    f"Not enough eggs in stock to scrap for batch {batch.name}. "
                    f"Available: {total_qty}, Requested: {line.break_qty}"
                )

            # Create scrap
            scrap = self.env['stock.scrap'].create({
                'product_id': product.id,
                'scrap_qty': line.break_qty,
                'location_id': batch.location_id.id,
                'company_id': getattr(batch, 'company_id', self.env.company).id,
                'origin': f"Pre-Storage Break: {line.break_reason} - Batch {batch.name}"
            })

            # Allocate scrap from multiple quants if necessary
            remaining_qty = line.break_qty
            for quant in quants:
                consume_qty = min(quant.quantity, remaining_qty)
                if consume_qty <= 0:
                    continue
                quant.quantity -= consume_qty
                remaining_qty -= consume_qty
                if remaining_qty <= 0:
                    break

            scrap.action_validate()

            # Update batch
            batch.broken_qty += line.break_qty
            batch._update_quant()
            batch.available_qty = max(batch.qty_received - batch.broken_qty - batch.pre_storage_waste, 0)

            # Link scrap to line
            line.stock_scrap_id = scrap.id
            line.processed = True

            batch.message_post(
                body=f"🥚{line.break_qty} eggs broken in Pre-Storage batch '{batch.name}' due to '{line.break_reason}' on {line.date}. Note: {line.note or 'N/A'}"
            )

            _logger.info(
                "Pre-Storage break processed: Batch %s, Qty %s, Scrap ID %s", 
                batch.name, line.break_qty, scrap.id
            )

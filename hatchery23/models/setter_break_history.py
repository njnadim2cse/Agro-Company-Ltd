import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class SetterBreakHistory(models.Model):
    _name = 'hatchery.setter.break.history'
    _description = 'Setter Break History'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    setter_stage_id = fields.Many2one(
        'hatchery.setter.stage',
        string="Setter Stage",
        required=True,
        ondelete='cascade'
    )
    batch_id = fields.Many2one(
        'hatchery.egg.batch',
        string="Egg Batch",
        ondelete='cascade'
    )
    date = fields.Datetime(string="Date", default=fields.Datetime.now)
    break_qty = fields.Float(string="Broken Quantity", required=True)
    break_reason = fields.Selection([
        ('temperature', 'High Temperature'),
        ('humidity', 'Low Humidity'),
        ('handling', 'Improper Handling'),
        ('machine_fault', 'Machine Fault'),
        ('transport', 'During Transfer'),
        ('other', 'Other')
    ], string="Break Reason", required=True)
    note = fields.Text(string="Note")
    user_id = fields.Many2one(
        'res.users',
        string="User",
        default=lambda self: self.env.user
    )
    processed = fields.Boolean(string="Processed", default=False)
    stock_scrap_id = fields.Many2one('stock.scrap', string="Related Scrap")

    @api.model
    def create(self, vals):
        # Auto-assign batch_id from setter_stage if not provided
        if vals.get('setter_stage_id') and not vals.get('batch_id'):
            stage = self.env['hatchery.setter.stage'].browse(vals['setter_stage_id'])
            vals['batch_id'] = stage.batch_id.id if stage.batch_id else False
        return super().create(vals)

    def action_break_eggs(self):
        """Process break lines during setter stage and create stock scrap."""
        product = self.env['product.product'].search([('name', '=', 'Eggs')], limit=1)
        if not product:
            raise UserError("Product 'Eggs' not found in inventory.")

        for line in self.filtered(lambda l: not l.processed):
            stage = line.setter_stage_id
            if not stage:
                raise UserError("Break line is not linked to any Setter Stage!")

            batch = line.batch_id or stage.batch_id
            if not batch:
                raise UserError("No linked Egg Batch found for this Setter Stage.")

            if line.break_qty > stage.qty_available:
                raise UserError(
                    f"Cannot break {line.break_qty} eggs. Only {stage.qty_available} available in this stage."
                )

            # Find stock quant to scrap
            quant = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id.usage', '=', 'internal'),
                ('quantity', '>=', line.break_qty)
            ], limit=1)

            if not quant:
                raise UserError(f"Not enough eggs in stock to scrap for batch {batch.batch_no}.")

            # Create scrap entry
            scrap = self.env['stock.scrap'].create({
                'product_id': product.id,
                'scrap_qty': line.break_qty,
                'location_id': quant.location_id.id,
                'company_id': batch.company_id.id if batch.company_id else self.env.company.id,
                'origin': f"Setter Break: {line.break_reason} - Batch {batch.batch_no}"
            })
            scrap.action_validate()

            # Mark line processed
            line.stock_scrap_id = scrap.id
            line.processed = True

            # Update stage qty_available
            stage._compute_qty_available()

            # Post messages to chatter
            stage.message_post(
                body=f"🥚 {line.break_qty} eggs broken in Setter Stage ({stage.machine_id.name}) "
                     f"due to {line.break_reason} on {line.date}. Note: {line.note or 'N/A'}"
            )
            batch.message_post(
                body=f"🥚 {line.break_qty} eggs broken during Setter Stage ({stage.machine_id.name}) "
                     f"due to {line.break_reason}."
            )

            _logger.info(
                "Setter Break processed: Batch %s | Stage %s | Qty %s | Reason: %s",
                batch.batch_no, stage.id, line.break_qty, line.break_reason
            )
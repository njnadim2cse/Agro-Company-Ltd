from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

class HatcherBreakHistory(models.Model):
    _name = 'hatchery.hatcher.break.history'
    _description = 'Hatcher Egg Break History'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    hatcher_stage_id = fields.Many2one(
        'hatchery.hatcher.stage',
        string="Hatcher Stage",
        required=True,
        ondelete='cascade'
    )
    batch_id = fields.Many2one(
        'hatchery.egg.batch',
        string="Egg Batch",
        required=True,
        ondelete='restrict',
        help="Egg batch associated with this hatcher stage"
    )

    date = fields.Datetime(string="Date", default=fields.Datetime.now)
    break_qty = fields.Float(string="Broken Quantity", required=True)
    break_reason = fields.Selection([
        ('accidental', 'Accidental'),
        ('mortality', 'Mortality'),
        ('other', 'Other'),
    ], string="Break Reason", required=True)
    note = fields.Text(string="Note")
    user_id = fields.Many2one('res.users', string="User", default=lambda self: self.env.user)
    processed = fields.Boolean(string="Processed", default=False)
    active = fields.Boolean(string="Active", default=True)

    # -----------------------
    # Auto-set batch_id from stage
    # -----------------------
    @api.model
    def create(self, vals):
        if 'hatcher_stage_id' in vals and not vals.get('batch_id'):
            stage = self.env['hatchery.hatcher.stage'].browse(vals['hatcher_stage_id'])
            if not stage.egg_batch_id:
                raise UserError("Hatcher Stage has no Egg Batch assigned.")
            vals['batch_id'] = stage.egg_batch_id.id
        return super().create(vals)

    # -----------------------
    # Constraints
    # -----------------------
    @api.constrains('break_qty', 'batch_id')
    def _check_break_qty(self):
        for rec in self:
            if rec.break_qty <= 0:
                raise ValidationError("Broken quantity must be greater than zero.")
            if not rec.batch_id:
                raise ValidationError("Egg Batch is required!")
            if rec.break_qty > (rec.hatcher_stage_id.qty_available or 0):
                raise ValidationError(
                    f"Cannot break {rec.break_qty} eggs. Only {rec.hatcher_stage_id.qty_available} eggs available."
                )

    # -----------------------
    # Process Breakage
    # -----------------------
    def action_break_hatcher(self):
        """Process all unprocessed hatcher break lines in the batch"""
        product = self.env['product.product'].search([('name', '=', 'Eggs')], limit=1)
        if not product:
            raise UserError("Product 'Eggs' not found in inventory.")

        for line in self.filtered(lambda l: not l.processed and l.active):
            batch = line.batch_id
            if not batch:
                raise UserError("Break line is not linked to any Egg Batch!")

            qty_to_scrap = line.break_qty

            quants = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id.usage', '=', 'internal'),
                ('quantity', '>', 0)
            ], order='quantity desc')

            if not quants:
                raise UserError(f"No eggs in stock for batch {batch.batch_no}.")

            for quant in quants:
                if qty_to_scrap <= 0:
                    break
                deduct_qty = min(quant.quantity, qty_to_scrap)
                scrap = self.env['stock.scrap'].create({
                    'product_id': product.id,
                    'scrap_qty': deduct_qty,
                    'location_id': quant.location_id.id,
                    'company_id': batch.company_id.id or self.env.company.id,
                    'origin': f"Hatcher Breakage - Batch: {batch.batch_no} - Reason: {line.break_reason}"
                })
                scrap.action_validate()
                qty_to_scrap -= deduct_qty

            if qty_to_scrap > 0:
                raise UserError(f"Not enough eggs in stock to process {line.break_qty} breakage.")

            # Mark line as processed
            line.processed = True

            # Update batch broken quantity
            batch.broken_qty += line.break_qty

            # Post simple message to batch chatter
            batch.message_post(
                body=f"{line.break_qty} eggs broken at hatcher stage due to '{line.break_reason}' "
                     f"on {line.date}. Recorded by: {line.user_id.name}"
            )

    # -----------------------
    # Override Write & Unlink
    # -----------------------
    def write(self, vals):
        if self.filtered(lambda r: r.processed):
            restricted_fields = ['break_qty', 'hatcher_stage_id', 'batch_id', 'break_reason', 'date']
            if any(field in vals for field in restricted_fields):
                raise UserError(
                    "Cannot modify processed break records. Create a new record instead."
                )
        for rec in self:
            if not rec.batch_id and rec.hatcher_stage_id and 'batch_id' not in vals:
                vals['batch_id'] = rec.hatcher_stage_id.egg_batch_id.id
        return super().write(vals)

    def unlink(self):
        processed_records = self.filtered(lambda r: r.processed)
        unprocessed_records = self - processed_records

        if processed_records:
            processed_records.write({'active': False})
            self.env.user.notify_warning(
                message=f"{len(processed_records)} processed record(s) archived instead of deleted."
            )

        if unprocessed_records:
            return super(HatcherBreakHistory, unprocessed_records).unlink()

        return True

    # -----------------------
    # Archive / Unarchive
    # -----------------------
    def action_archive_record(self):
        self.write({'active': False})
        self.env.user.notify_info(message="Break record(s) archived successfully.")

    def action_unarchive_record(self):
        self.write({'active': True})
        self.env.user.notify_info(message="Break record(s) restored successfully.")

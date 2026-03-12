from odoo import models, fields, api
from odoo.exceptions import UserError

class EggBreakWizard(models.TransientModel):
    _name = 'hatchery.egg.break.wizard'
    _description = 'Egg Break Wizard'

    break_qty = fields.Float(string="Broken Quantity", required=True)

    def action_confirm_break(self):
        batch_id = self.env.context.get('active_id')
        batch = self.env['hatchery.egg.batch'].browse(batch_id)
        if not batch:
            raise UserError("No Egg Batch found.")

        if self.break_qty <= 0:
            raise UserError("Broken quantity must be greater than zero.")

        if self.break_qty > batch.qty_available:
            raise UserError(f"Cannot break more than remaining {batch.qty_available} eggs in batch.")

        # Find Egg product
        product = self.env['product.product'].search([('name', '=', 'Eggs')], limit=1)
        if not product:
            raise UserError("Product 'Eggs' not found in inventory.")

        # Get all internal quants with quantity > 0
        quants = self.env['stock.quant'].search([
            ('product_id', '=', product.id),
            ('location_id.usage', '=', 'internal'),
            ('quantity', '>', 0)
        ], order='quantity desc')

        qty_to_scrap = self.break_qty
        for quant in quants:
            if qty_to_scrap <= 0:
                break
            deduct_qty = min(quant.quantity, qty_to_scrap)

            # Create scrap for this quant
            scrap = self.env['stock.scrap'].create({
                'product_id': product.id,
                'scrap_qty': deduct_qty,
                'location_id': quant.location_id.id,
                'company_id': batch.company_id.id or self.env.company.id,
            })
            scrap.action_validate()

            qty_to_scrap -= deduct_qty

        if qty_to_scrap > 0:
            raise UserError("Not enough eggs in stock to scrap the requested quantity.")

        # Update batch broken quantity
        batch.broken_qty += self.break_qty

        # Remove from egg_selection_ids
        qty_to_remove = self.break_qty
        for line in batch.egg_selection_ids.sorted(key=lambda l: l.id):
            if qty_to_remove <= 0:
                break
            if line.quantity <= qty_to_remove:
                qty_to_remove -= line.quantity
                line.unlink()
            else:
                line.quantity -= qty_to_remove
                qty_to_remove = 0

        # Record broken history
        self.env['hatchery.egg.break.history'].create({
            'batch_id': batch.id,
            'broken_qty': self.break_qty,
            'user_id': self.env.user.id,
        })

        batch.message_post(
            body=f"{self.break_qty} eggs were broken and removed from inventory and batch list."
        )

        return {'type': 'ir.actions.client', 'tag': 'reload'}

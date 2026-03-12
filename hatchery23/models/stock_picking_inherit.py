import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # Flag to prevent double pre-storage processing
    x_prestorage_created = fields.Boolean(string="Pre-Storage Batch Created", default=False)

    def button_validate(self):
        """
        Override stock.picking validate button to create a pre-storage batch for eggs.
        Ensures no duplicate batch is created for the same picking.
        """
        _logger.info("Button Validate called for Picking(s): %s", self.mapped('name'))

        # Call the original validate
        res = super().button_validate()

        for picking in self:
            _logger.info("Processing Picking: %s", picking.name)

            # Skip if pre-storage already processed
            if picking.x_prestorage_created:
                _logger.info("Picking %s already has Pre-Storage Batch, skipping.", picking.name)
                continue

            # Filter only egg product moves
            egg_moves = picking.move_ids.filtered(
                lambda m: m.product_id.product_tmpl_id.is_egg_product
            )
            if not egg_moves:
                _logger.info("No egg products in Picking: %s", picking.name)
                continue

            total_qty = sum(egg_moves.mapped('product_uom_qty'))
            _logger.info("Total egg quantity in Picking %s: %s", picking.name, total_qty)

            # Check if Pre-Storage batch already exists (atomic safety)
            existing_batch = self.env['hatchery.prestorage.batch'].sudo().with_context(check_access=False).search([
                ('picking_id', '=', picking.id)
            ], limit=1)

            if existing_batch:
                _logger.info("Pre-Storage Batch already exists for picking %s, skipping creation", picking.name)
                picking.x_prestorage_created = True
                continue

            # Create new Pre-Storage batch
            pre_storage = self.env['hatchery.prestorage.batch'].sudo().create({
                'picking_id': picking.id,
                'qty_received': total_qty,
                'date_in': picking.scheduled_date or fields.Date.today(),
                'location_id': picking.location_dest_id.id,
            })
            _logger.info("Created Pre-Storage Batch %s with qty: %s", pre_storage.name, total_qty)

            # Mark picking as processed to prevent duplicates
            picking.x_prestorage_created = True
            _logger.info("Marked Picking %s as pre-storage processed", picking.name)

        return res








import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class InternalTransfer(models.Model):
    _name = 'internal.transfer'
    _description = 'Internal Transfer of Chicks'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ----------------------------
    # Fields
    # ----------------------------
    name = fields.Char(
    string="Transfer Reference",
    required=True,
    copy=False,
    readonly=True,
    default=lambda self: _('New')
    )
    packaging_id = fields.Many2one(
        'chick.packaging', string="Source Packaging", readonly=True, ondelete='set null'
    )
    source_location = fields.Many2one(
        'stock.location', string="Source Location", required=True
    )
    destination_location = fields.Many2one(
        'stock.location', string="Destination Location", required=True
    )
    chicks_count = fields.Integer(string="Chicks Count", required=True, tracking=True)
    transfer_date = fields.Date(default=fields.Date.context_today, string="Transfer Date")
    picking_id = fields.Many2one('stock.picking', string="Stock Picking", readonly=True)

    state = fields.Selection([
        ('draft', '📝 Draft'),
        ('done', '📦 Stock Created'),
        ('delivered', '✅ Delivered'),
    ], default='draft', string="Status", tracking=True)

    note = fields.Text(string="Notes")

    _sql_constraints = [
        ('positive_chicks', 'CHECK(chicks_count > 0)', 'Chicks count must be greater than 0!'),
    ]
    @api.model
    def create(self, vals):
       if vals.get('name', 'New') == 'New':
          vals['name'] = self.env['ir.sequence'].next_by_code('internal.transfer.seq') or _('New')
       return super().create(vals)
    

    def name_get(self):
        return [(rec.id, f"Internal Transfer {rec.id}") for rec in self]

    # ----------------------------
    # CREATE STOCK PICKING
    # ----------------------------
    def action_done(self):
        """Create stock picking and moves safely."""
        Product = self.env['product.product']
        PickingType = self.env['stock.picking.type']

        product_eggs = Product.search([('name', '=', 'Eggs')], limit=1)
        if not product_eggs:
            raise UserError(_("Product 'Eggs' not found. Please create it in Products."))

        picking_type = PickingType.search([('code', '=', 'internal')], limit=1)
        if not picking_type:
            raise UserError(_("No internal picking type found in Inventory."))

        for rec in self:
            if rec.state in ['done', 'delivered']:
                _logger.info("Internal Transfer %s already has picking created, skipping", rec.id)
                continue

            if rec.picking_id:
                rec.state = 'done'
                continue

            # Create picking
            picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'location_id': rec.source_location.id,
                'location_dest_id': rec.destination_location.id,
                'scheduled_date': rec.transfer_date,
                'origin': rec.note or f'Packaging {rec.packaging_id.id}',
            })

            # Create move
            self.env['stock.move'].create({
                'name': 'Eggs Internal Transfer',
                'product_id': product_eggs.id,
                'product_uom_qty': rec.chicks_count,
                'product_uom': product_eggs.uom_id.id,
                'picking_id': picking.id,
                'location_id': rec.source_location.id,
                'location_dest_id': rec.destination_location.id,
            })

            rec.picking_id = picking.id
            rec.state = 'done'
            rec.message_post(
                body=f"🐣🚚 Internal Transfer #{rec.id} created picking #{picking.name} for product 'Eggs'."
            )
            _logger.info("Created picking %s with move qty %s for transfer %s",
                         picking.name, rec.chicks_count, rec.id)

    # ----------------------------
    # VALIDATE DELIVERY
    # ----------------------------
    def action_delivered(self):
        """Deliver only remaining quantity, avoid duplication."""
        for rec in self:
            if rec.state == 'delivered':
                _logger.info("Transfer %s already delivered, skipping.", rec.id)
                continue

            if not rec.picking_id:
                raise UserError(_("No related picking found for Internal Transfer %s." % rec.id))

            picking = rec.picking_id
            _logger.info("Delivering Transfer %s, Picking %s, State %s", rec.id, picking.name, picking.state)

            # Ensure only 'Eggs' are moved
            for move in picking.move_ids_without_package:
                if move.product_id.name != 'Eggs':
                    raise UserError(_("This transfer can only deliver product 'Eggs'."))

            # Confirm & assign picking
            if picking.state == 'draft':
                picking.action_confirm()
                _logger.info("Picking %s confirmed", picking.name)
            if picking.state in ['confirmed', 'waiting']:
                picking.action_assign()
                _logger.info("Picking %s assigned", picking.name)

            # ✅ Safely set done qty only for remaining quantity
            for move in picking.move_ids_without_package:
                qty_done_already = sum(line.qty_done for line in move.move_line_ids)
                qty_remaining = move.product_uom_qty - qty_done_already
                if qty_remaining > 0:
                    _logger.info("Setting qty_done for move %s to %s", move.id, qty_remaining)
                    move._set_quantity_done(qty_remaining)
                else:
                    _logger.info("Move %s already fully delivered, skipping.", move.id)

            # Validate picking
            if picking.state not in ['done', 'cancel']:
                picking.button_validate()
                _logger.info("Picking %s validated", picking.name)

            rec.state = 'delivered'
            rec.message_post(
                body=f"🚚 Internal Transfer #{rec.id} delivered. "
                     f"Stock moved from {rec.source_location.display_name} "
                     f"to {rec.destination_location.display_name}."
            )
            _logger.info("Transfer %s marked delivered", rec.id)




import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class ChickPackaging(models.Model):
    _name = 'chick.packaging'
    _description = 'Chick Packaging'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(
        string="Packaging Serial", 
        required=True, 
        copy=False, 
        readonly=True, 
        default='New',
        tracking=True
    )
    distribution_date = fields.Date(string="Distribution Date", default=fields.Date.context_today)
    batch_id = fields.Many2one('hatchery.egg.batch', string='Egg Batch', required=True)
    hatcher_stage_id = fields.Many2one('hatchery.hatcher.stage', string="Hatcher Stage", required=True)
    chicks_count = fields.Integer(string="Chicks Count", required=True, tracking=True)
    boxes_count = fields.Integer(string="Boxes Count", compute='_compute_boxes_count', store=True)
    packaging_mortality = fields.Integer(string="Packaging Mortality", default=0, tracking=True)
    
    state = fields.Selection([
        ('draft', '🏭 Draft'),
        ('ready_for_transfer', '🚚 Ready for Transfer'),
        ('done', '✅ Done')
    ], default='draft', tracking=True, string='Status')

    note = fields.Text(string="Notes")
    
    # -------------------------------
    # Transfer fields
    # -------------------------------
    transfer_type = fields.Selection([
        ('internal', 'Own Grower Farm (Internal Transfer)'),
        ('external', 'Customer Farm (External / Sale Order)')
    ], string="Transfer Type", default='internal')

    transfer_id = fields.Many2one('internal.transfer', string="Internal Transfer", readonly=True)
    distribution_id = fields.Many2one('chicken.egg.distribution', string="Distribution / Sale Order", readonly=True)
    stock_scrap_id = fields.Many2one('stock.scrap', string="Packaging Scrap")
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        default=lambda self: self.env.company
    )
    available_chicks = fields.Integer(
        string="Available Chicks After Mortality",
        compute="_compute_available_chicks",
        store=True,
        tracking=True
    )

    boxes_after_mortality = fields.Integer(
        string="Boxes After Mortality",
        compute='_compute_boxes_after_mortality',
        store=True,
        tracking=True
    )


    
    destination_location = fields.Many2one('stock.location', string="Destination Location")
    customer_ids = fields.Many2many('res.partner', string="Customers for External Transfer")

    @api.depends('chicks_count')
    def _compute_boxes_count(self):
        for rec in self:
            rec.boxes_count = rec.chicks_count // 40 if rec.chicks_count else 0
            
    @api.depends('chicks_count', 'packaging_mortality')
    def _compute_available_chicks(self):
        for rec in self:
            rec.available_chicks = max(rec.chicks_count - rec.packaging_mortality, 0)

    @api.depends('available_chicks')
    def _compute_boxes_after_mortality(self):
        for rec in self:
            rec.boxes_after_mortality = rec.available_chicks // 40 if rec.available_chicks else 0

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('chick.packaging') or 'PACK/0001'
        return super().create(vals)
        
    def write(self, vals):
        res = super(ChickPackaging, self).write(vals)
        if 'packaging_mortality' in vals:
            self._update_packaging_scrap()
        return res
    
    def _update_packaging_scrap(self):
        """Create or update scrap when packaging mortality occurs."""
        for rec in self:
            if rec.packaging_mortality and rec.packaging_mortality > 0:
                # Find product - adjust name to your product ('Eggs' or 'Chicks')
                product = self.env['product.product'].search([('name', '=', 'Eggs')], limit=1)
                if not product:
                    raise UserError(_("Product 'Eggs' not found in inventory. Please create it or change the product name."))

                # Location: prefer destination_location if set, else any internal location
                location = rec.destination_location or self.env['stock.location'].search([('usage', '=', 'internal')], limit=1)
                if not location:
                    raise UserError(_("No internal stock location found. Please configure a stock location."))

                # Find or create tag
                tag = self.env['stock.scrap.reason.tag'].search([('name', '=', 'Packaging Mortality')], limit=1)
                if not tag:
                    tag = self.env['stock.scrap.reason.tag'].create({'name': 'Packaging Mortality'})

                vals = {
                    'scrap_qty': rec.packaging_mortality,
                    'location_id': location.id,
                    'product_id': product.id,
                    'company_id': rec.company_id.id,
                    'date_done': fields.Datetime.now(),
                    'name': f"Packaging Mortality - {rec.name}",
                    'scrap_reason_tag_ids': [(6, 0, [tag.id])],
                }

                if rec.stock_scrap_id:
                    try:
                        rec.stock_scrap_id.sudo().write(vals)
                        _logger.info("🔄 Updated Scrap for Packaging Mortality %s: %s chicks", rec.name, rec.packaging_mortality)
                    except Exception as e:
                        _logger.exception("Failed to update scrap for %s: %s", rec.name, e)
                        raise UserError(_("Failed to update existing scrap: %s") % e)
                else:
                    try:
                        scrap = self.env['stock.scrap'].create({
                            'product_id': vals['product_id'],
                            'scrap_qty': vals['scrap_qty'],
                            'location_id': vals['location_id'],
                            'company_id': vals['company_id'],
                            'date_done': vals['date_done'],
                            'name': vals['name'],
                            'scrap_reason_tag_ids': [(6, 0, [tag.id])],
                        })
                        # Validate scrap if action available
                        
                        scrap.action_validate()
                        rec.stock_scrap_id = scrap.id
                        _logger.info("📦 Scrap created for Packaging Mortality %s: %s chicks", rec.name, rec.packaging_mortality)
                    except Exception as e:
                        _logger.exception("Failed to create scrap for %s: %s", rec.name, e)
                        raise UserError(_("Failed to create scrap record: %s") % e)

            _logger.info("✅ Packaging Scrap processed for %s", rec.name)


    # -------------------------------
    # Action to process transfer
    def action_ready_for_transfer(self):
      for rec in self:
        # Ensure scrap is handled first
        rec._update_packaging_scrap()

        transfer_qty = rec.chicks_count - rec.packaging_mortality
        if transfer_qty <= 0:
            raise UserError(_("No chicks available for transfer after mortality."))

        rec.state = 'ready_for_transfer'

        if rec.transfer_type == 'internal':
            # ----------------------
            # Internal Transfer
            # ----------------------
            # Only create internal transfer if it doesn't exist yet
            if not rec.transfer_id:
                InternalTransfer = self.env['internal.transfer']

                # Try to resolve references safely
                stock_loc = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
                out_loc = self.env.ref('stock.stock_location_output', raise_if_not_found=False)
                if not stock_loc or not out_loc:
                    raise UserError(_("Required stock locations not found (stock_stock / stock_output). Please check module data."))

                transfer = InternalTransfer.create({
                    'packaging_id': rec.id,
                    'chicks_count': transfer_qty,
                    'source_location': stock_loc.id,
                    'destination_location': out_loc.id,
                    'note': f"Transfer from Packaging ID {rec.id}",
                })
                rec.transfer_id = transfer.id

                rec.message_post(body=f"🐣 Created draft Internal Transfer #{transfer.id} with {transfer_qty} chicks.")

        else:
            # ----------------------
            # External Transfer → Sale Order
            # ----------------------
            # Only allow single record external transfer
            if len(self) > 1:
                raise UserError(_("⚠️ You can only perform External Transfer for one record at a time."))

            # Only create distribution if it doesn't exist yet
            if not rec.distribution_id:
                Distribution = self.env['chicken.egg.distribution']

                product_for_dist = self.env['product.product'].search([('name', '=', 'Eggs')], limit=1)
                if not product_for_dist:
                    raise UserError(_("Product 'Eggs' not found for distribution."))

                stock_loc = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
                if not stock_loc:
                    raise UserError(_("Source stock location not found for distribution."))

                distribution = Distribution.create({
                    'product_id': product_for_dist.id,
                    'farm_id': stock_loc.id,
                    'user_id': self.env.user.id,
                    'distribution_date': fields.Datetime.now(),
                    'parent_transfer_qty': transfer_qty
                })
                rec.distribution_id = distribution.id

                # Create distribution lines for each customer only once
                for customer in rec.customer_ids:
                    self.env['chicken.egg.distribution.line'].create({
                        'distribution_id': distribution.id,
                        'customer_id': customer.id,
                        'done_qty': transfer_qty // len(rec.customer_ids),
                        'price': 15,  # default or calculated
                    })

                # Confirm and approve distribution, create sale orders if missing
            
                distribution.button_approve()
                for line in distribution.distribution_line_ids:
                    if not line.sale_order_id:
                        line.button_create_sale_order()

                rec.message_post(body=f"External Sale Order created via Distribution #{distribution.id}.")



    # -------------------------------
    # Mark packaging done
    # -------------------------------
    def action_done(self):
        for rec in self:
            if rec.state != 'ready_for_transfer':
                raise UserError(_("⚠️ You must be in 'Ready for Transfer' state before marking as done."))
            rec.state = 'done'
            rec.message_post(body="✅ Chick Packaging marked as Done.")
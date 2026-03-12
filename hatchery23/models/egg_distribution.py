from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    distribution_id = fields.Many2one(
        'chicken.egg.distribution', string='Distribution', readonly=True,
        ondelete='set null',
    )


class ChickenEggDistribution(models.Model):
    _name = 'chicken.egg.distribution'
    _description = 'Chicken Egg Distribution'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string="Serial Number",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: 'New'
    )
    distribution_date = fields.Datetime(
        string="Distribution Date", default=fields.Datetime.now, tracking=True
    )
    product_id = fields.Many2one('product.product', string='Product', required=True)
    farm_id = fields.Many2one('stock.location', string='Warehouse')
    distribution_line_ids = fields.One2many(
        'chicken.egg.distribution.line', 'distribution_id', string='Distribution Lines',
        copy=True
    )
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    # changed: multiple sale orders per distribution
    sale_order_ids = fields.One2many('sale.order', 'distribution_id', string='Sale Orders', readonly=True)
    parent_transfer_qty = fields.Float(string="Total Transfer Quantity", required=True)
    remaining_qty = fields.Float(
        string="Remaining Quantity", compute="_compute_remaining_qty", store=True
    )

    states = fields.Selection([
       
        ('approve', '✅ Approved'),
        ('sale_order', '🚚 Sale Order Created'),
    ], default='approve', tracking=True)

    @api.depends('distribution_line_ids.cus_qty', 'parent_transfer_qty')
    def _compute_remaining_qty(self):
        """
        Allocate quantities across lines in order. For each line:
         - allocated = min(line.cus_qty, remaining)
         - line.done_qty = allocated
         - remaining -= allocated
        After loop, rec.remaining_qty = remaining
        """
        for rec in self:
            remaining = rec.parent_transfer_qty or 0.0
            # iterate in the order of distribution_line_ids (sequence/order)
            for line in rec.distribution_line_ids:
                # allocate as much as possible to this line
                allocate = min(line.cus_qty or 0.0, remaining)
                # done_qty means allocated / fulfilled qty for this line
                line.done_qty = allocate
                remaining -= allocate
            rec.remaining_qty = max(remaining, 0.0)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('chicken.egg.distribution') or 'CED/0001'
        return super(ChickenEggDistribution, self).create(vals)

    
            
    def button_approve(self):
        for rec in self:
            rec.states = 'approve'
    

    def _all_lines_have_orders(self):
        """Helper to detect whether all lines already have sale orders."""
        for rec in self:
            if any(not l.sale_order_id for l in rec.distribution_line_ids):
                return False
        return True


class ChickenEggDistributionLine(models.Model):
    _name = 'chicken.egg.distribution.line'
    _description = 'Distribution Line'

    distribution_id = fields.Many2one('chicken.egg.distribution', string='Distribution', ondelete='cascade')
    customer_id = fields.Many2one('res.partner', string='Customer', required=True)
    cus_qty = fields.Float(string="Customer Required Quantity", default=0.0)
    # done_qty = allocated quantity for this line (computed)
    done_qty = fields.Float(string='Allocated Quantity', compute='_compute_done_qty', store=True)
    price = fields.Float(string='Price', default=10)
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', readonly=True)

    @api.depends('cus_qty', 'distribution_id.parent_transfer_qty', 'distribution_id.distribution_line_ids')
    def _compute_done_qty(self):
        """
        Recompute allocation for all lines of parent distribution.
        This ensures consistent allocation across sibling lines.
        """
        # work per distribution
        for parent in self.mapped('distribution_id'):
            remaining = parent.parent_transfer_qty or 0.0
            for line in parent.distribution_line_ids:
                allocate = min(line.cus_qty or 0.0, remaining)
                line.done_qty = allocate
                remaining -= allocate

    def button_create_sale_order(self):
        """
        For each selected distribution line: create a separate sale.order
        linking it back to the distribution, only if:
         - distribution is approved
         - the allocated (done_qty) covers the requested quantity (cus_qty)
        """
        SaleOrder = self.env['sale.order']
        SaleOrderLine = self.env['sale.order.line']

        for line in self:
            parent = line.distribution_id
            if not parent:
                raise UserError("⚠️ Distribution not set for this line.")
            if parent.states != 'approve':
                raise UserError("⚠️ You can only create Sale Orders after the distribution is approved.")
            # Check available allocation
            if (line.done_qty or 0.0) < (line.cus_qty or 0.0):
                raise UserError(
                    _(
                        "⚠️ Customer '%s' requires %.2f, but only %.2f is allocated/available. "
                        "Adjust the quantities or parent transfer quantity first."
                    ) % (line.customer_id.name or 'n/a', line.cus_qty or 0.0, line.done_qty or 0.0)
                )
            # if sale order already created skip
            if line.sale_order_id:
                continue

            order = SaleOrder.create({
                'partner_id': line.customer_id.id,
                'date_order': fields.Datetime.now(),
                'user_id': parent.user_id.id or self.env.uid,
                'distribution_id': parent.id,
            })

            # Create order line
            SaleOrderLine.create({
                'order_id': order.id,
                'product_id': parent.product_id.id,
                'product_uom_qty': line.cus_qty,
                'product_uom': parent.product_id.uom_id.id,
                'price_unit': line.price,
            })

            # link the Sale Order to this line
            line.sale_order_id = order.id

        # mark distribution state if all lines have Sale Orders
        # (recompute on related distributions)
        for parent in self.mapped('distribution_id'):
            if all(l.sale_order_id for l in parent.distribution_line_ids):
                parent.states = 'sale_order'

   
   

    







    
    
 
    
   
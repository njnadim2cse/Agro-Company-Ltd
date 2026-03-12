from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class FeedDetails(models.Model):
    
    _name = "feed.details"
    _description = "Feed Details"
    _rec_name = "flock_id"
    _inherit = ['mail.thread', 'mail.activity.mixin']
   
   
    datetime =fields.Date(string="Date", default=fields.Date.context_today)
    name = fields.Char(string="Reference", default="New", readonly=True )
    flock_id = fields.Many2one( 'farm.layer.flock',string="Flock",required=True )
    created_by = fields.Many2one('res.users', string="Responsible Person", default=lambda self: self.env.user, )
    current_bird = fields.Integer( string="Current Bird")
    current_age_days = fields.Integer(string="Current Age in Days")
    feed_per_bird = fields.Float(string="Feed Per Bird (day/gm)",compute="_compute_feed_per_bird",store=True)
    feed_product_id = fields.Many2one('product.product', string="Product",domain="[('is_feed', '=', True)]", tracking=True)
    product_id = fields.Many2one('product.product', string="Product")
    on_hand_qty = fields.Float(string="On hand Qty",related='feed_product_id.qty_available',tracking =True)
    feed_kg = fields.Float(string="Feed (kg)", help="Feed quantity in kilograms" )
    cumm_feed = fields.Float( string="Cumm. Feed", compute="_compute_cumm_feed",store=True )
    status = fields.Boolean( string="Status", default=False )
    state = fields.Selection([('draft','Draft'),('done','Done')],string="Status",default='draft',tracking=True)
    description_html = fields.Html(string='HTML Description', sanitize_attributes=False)
    feed_time = fields.Selection([
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
        ('night', 'Night'),
    ], string="Feed Time", required=True, tracking=True)

    @api.model
    def create(self, vals):
        
        existing = self.search([
        ('flock_id', '=', vals.get('flock_id')),
        ('datetime', '=', vals.get('datetime')),
        ('feed_time', '=', vals.get('feed_time')),
        ], limit=1)
        if existing:
            raise UserError("A feed record already exists for this flock, date, and time!")
        
        if vals.get('name', 'New') == 'New':
            last_record = self.search([('name', 'like', 'F/M/%')], 
                                      order='id desc', limit=1)
            if last_record and last_record.name:
                try:
                    last_seq = int(last_record.name.split('/')[-1])
                    next_seq = str(last_seq + 1).zfill(5)  
                except ValueError:
                    next_seq = '00001'
            else:
                next_seq = '00001'
            today_str = datetime.today().strftime('%d-%m-%Y')
            vals['name'] = f"F/M/{today_str}"

        return super(FeedDetails, self).create(vals)
    
    @api.onchange('flock_id')
    def _on_change_get_flock_info(self):
        if self.flock_id:
            self.product_id = self.flock_id.product_id
            self.current_bird = self.flock_id.total_qty
            self.current_age_days = self.flock_id.current_age_in_days

    @api.depends('feed_kg', 'current_bird')
    def _compute_feed_per_bird(self):
        for rec in self:
            if rec.current_bird and rec.feed_kg:
                rec.feed_per_bird = round((rec.feed_kg * 1000) / rec.current_bird, 2)
            else:
                rec.feed_per_bird = 0

    @api.depends('feed_kg')
    def _compute_cumm_feed(self):
        for rec in self:
            records = self.search([('flock_id', '=', rec.flock_id.id)], order='datetime')
            total = 0
            for r in records:
                total += r.feed_kg
                r.cumm_feed = total

    def unlink(self):
        for rec in self:
            if rec.state == 'done':
                raise UserError("Record can't be deleted because it is linked with a picking!")
            if not self.env.user.has_group('base.group_system'):
                raise UserError("Only Settings users can delete records!")
        return super(FeedDetails, self).unlink()
    
    def action_confirm(self):

        for record in self:
            if record.state == 'done':
                continue
            if not record.feed_product_id:
                raise UserError("Feed Product is not assigned!")

            if record.feed_kg <= 0:
                raise UserError("Feed quantity must be greater than zero!")
            qty_to_scrap = record.feed_kg

            quants = self.env['stock.quant'].search([
                ('product_id', '=', record.feed_product_id.id),
                ('location_id.usage', '=', 'internal'),
                ('quantity', '>', 0)
            ], order='quantity desc')

            total_available = sum(q.quantity for q in quants)
            if total_available < qty_to_scrap:
                raise UserError(
                    f"Not enough feed in stock!\nAvailable: {total_available} kg, Required: {qty_to_scrap} kg"
                )
            qty_remaining = qty_to_scrap
            for quant in quants:
                if qty_remaining <= 0:
                    break
                remove_qty = min(quant.quantity, qty_remaining)
                scrap = self.env['stock.scrap'].create({
                    'product_id': record.feed_product_id.id,
                    'scrap_qty': remove_qty,
                    'location_id': quant.location_id.id,
                    'company_id': self.env.company.id,
                    'origin': f"Feed Details Record {record.id} - Flock {record.flock_id.name}"
                })
                scrap.action_validate()
                qty_remaining -= remove_qty

            _logger.info("Feed transferred (scrapped) for flock %s: %s kg", record.flock_id.name, record.feed_kg)
            record.message_post(body=f"Feed used: {record.feed_kg} kg has been scrapped from stock.")
            
            record.state = 'done'

    def action_draft(self):
        if self.state =="draft":
            return 
        self.state = "draft"

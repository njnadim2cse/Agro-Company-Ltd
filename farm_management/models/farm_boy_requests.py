from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime
import logging
_logger = logging.getLogger(__name__)

class FarmBoyRequest(models.Model):

    _name = "farm.boy.request.data"
    _description = "Farm Boy Medicine Request"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "name desc"
    
    
    date = fields.Date(string="Request Date",tracking=True)
    created_by = fields.Many2one('res.users', string="Responsible Person", default=lambda self: self.env.user, readonly=True)
    requested_by = fields.Many2one('res.users', string="Responsible Person", default=lambda self: self.env.user, readonly=True)
    name = fields.Char(string="Request Reference")
    medicine_id = fields.Many2one("product.product", string="Medicine",tracking=True)
    quantity = fields.Float(string="Requested Quantity", tracking=True)
    flock_id = fields.Many2one("farm.layer.flock", string="Flock", tracking=True)
    bird_type = fields.Selection([('layer','Layer'),('broiler','Broiler')],string="Bird Type" ,tracking =True)
    opening_bird_count = fields.Integer(string="Opening Brids",tracking =True)
    age_in_days = fields.Integer(string="Starting Age in Days")
    temp_instant = fields.Float(string="Instant Temperature (°C)")
    temp_max = fields.Float(string="Inside Temp Max (°C)", required=True, tracking=True)
    temp_min = fields.Float(string="Inside Temp Min (°C)", required=True, tracking=True)
    age_in_weeks = fields.Char(string="Starting Age in Weeks", store=True,tracking =True)
    current_age_in_days =fields.Integer(string="Current Age in Days", store=True,tracking=True)
    current_age_in_weeks = fields.Integer(string="'pCurrent Age in Weeks", store=True)
    current_extra_days = fields.Integer(string="Current Extra Days", store=True)
    current_birds = fields.Integer(string="Current Birds")
    temp_days = fields.Integer(string="Temp store")
    current_age_display = fields.Char(string="Current Age in Weeks",tracking=True)
    product_id = fields.Many2one('product.product', string="Product",tracking =True)
    total_qty = fields.Float(string="Current Birds",related='product_id.qty_available',tracking =True)
    note_html = fields.Html(string="Notes (HTML)",tracking=True)
    temp_max = fields.Float(string="Inside Temp Max (°C)", required=True)
    temp_min = fields.Float(string="Inside Temp Min (°C)", required=True)

    farmboy_request_line_ids = fields.One2many(
        comodel_name='farmboy.request.add.line', 
        inverse_name='request_id',                
        string="Requested Lines"
    )

    state = fields.Selection([
    ('draft', 'Draft'),
    ('requested', 'Requested'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected')
    ], default='draft', string="Status", tracking=True)

    def action_confirm(self):
        for record in self:
            record.state = 'requested'

            for line in record.farmboy_request_line_ids:
                if line.state != 'requested':
                    line.action_done() 
                    
    def action_draft(self):
        for record in self:
            record.state ="draft"
            if record.farmboy_request_line_ids:
                record.farmboy_request_line_ids.write({"state":"draft"})
        
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            today_str = datetime.today().strftime('%d-%m-%Y')
            last_record = self.search([('name', 'like', f'F/B/{today_str}/%')], order='id desc', limit=1)
            if last_record and last_record.name:
                try:
                    last_seq = int(last_record.name.split('/')[-1])
                    next_seq = str(last_seq + 1).zfill(5)
                except ValueError:
                    next_seq = '00001'
            else:
                next_seq = '00001'
            vals['name'] = f"F/B/{today_str}/{next_seq}"
        return super(FarmBoyRequest, self).create(vals)
    
    def _update_parent_state(self):

        for request in self:
            line_states = request.farmboy_request_line_ids.mapped('state')
            if not line_states:
                request.state = 'draft'
                continue
            
            if all(state == 'draft' for state in line_states):
                request.state = 'draft'
            elif any(state == 'refused' for state in line_states):
                request.state = 'rejected'
            elif all(state == 'approved' for state in line_states):
                request.state = 'approved'
            elif any(state == 'requested' for state in line_states):
                request.state = 'requested'



class FarmBoyRequestAddLine(models.Model):

    _name = "farmboy.request.add.line"
    _description = "Requested from live temperature or manually added medicine"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    

    

    product_id = fields.Many2one(
        'product.product',
        string="Medicine Name",
        domain=[('is_medicine','=',True)],
        tracking=True
    )

    flock_id = fields.Many2one("farm.layer.flock", string="Flock", tracking=True)
    product_id = fields.Many2one('product.product', string="Product",tracking =True)
    request_id = fields.Many2one('farm.boy.request.data',string="Request Reference")
    total_dose = fields.Float(string="Available Quantity", tracking=True)
    dose_per_bird = fields.Float(string="Dose Per Bird (ml)", tracking=True)
    bird_count = fields.Integer(string="Number of Birds", default=0, tracking=True)
    short_note = fields.Text(string="Short Note", tracking=True)
    consume_quantity = fields.Float(string="Consumed Quantity", tracking=True)
    remaining_dose = fields.Float(string="Remaining Dose (ml)", compute="_compute_remaining_dose", store=True)
    cost_per_unit = fields.Float(string="Medicine Cost", related='product_id.standard_price', tracking=True)
    total_cost = fields.Float(string="Total Cost", compute="_compute_total_cost", store=True)
    daily_temperature_id = fields.Many2one('temperature.details.data', string="Temperature Data", ondelete='cascade', tracking=True)
    farmboy_request_id = fields.Many2one('farm.boy.request.data', string="Farm Boy Request")

    state = fields.Selection([
        ('draft', 'Draft'), 
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('refused', 'Rejected'), 
    ], string="Status", default='draft', tracking=True)

    approval_id = fields.Many2one(
        'farm.medicine.approval',
        string="Approval Reference"
    )
    request_date = fields.Date(
        string="Request Date", 
        default=fields.Date.today,
        tracking=True
    )
    
    @api.depends('total_dose', 'dose_per_bird', 'bird_count')
    def _compute_remaining_dose(self):
        for record in self:
            if record.total_dose and record.dose_per_bird and record.bird_count:
                used = record.dose_per_bird * record.bird_count
                record.remaining_dose = max(record.total_dose - used, 0)
            else:
                record.remaining_dose = record.total_dose or 0.0

    @api.depends('total_dose', 'cost_per_unit')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = (record.total_dose or 0.0) * (record.cost_per_unit or 0.0)


    def action_done(self):
            
            approval_record = False
            for record in self:
                if record.state == 'requested':
                    continue
                
                # Get requested_by from parent or current user
                requested_by_id = False
                if record.request_id and record.request_id.requested_by:
                    requested_by_id = record.request_id.requested_by.id
                else:
                    requested_by_id = self.env.user.id
                
                # Get fields from parent request to transfer to approval
                current_age_display = False
                current_birds = False
                bird_type = False
                
                if record.request_id:
                    current_age_display = record.request_id.current_age_display
                    current_birds = record.request_id.current_birds
                    bird_type = record.request_id.bird_type
                
                request_date = record.request_id.date if record.request_id else fields.Date.today()
                
                # Search for existing approval record
                approval_record = self.env['farm.medicine.approval'].search([
                    ('flock_id', '=', record.flock_id.id),
                    ('request_date', '=', request_date),
                    ('state', 'in', ['draft', 'submitted'])
                ], limit=1)
                
                if not approval_record:
                    approval_vals = {
                        'flock_id': record.flock_id.id,
                        'request_date': request_date,
                        'state': 'draft',
                        'requested_by': requested_by_id,
                        'current_age_display': current_age_display,
                        'current_birds': current_birds,
                        'bird_type': bird_type,
                    }
                    approval_record = self.env['farm.medicine.approval'].create(approval_vals)
                    _logger.info(f"Created new approval for flock {record.flock_id.name} on date {request_date}")

                # Link approval record to current line
                record.approval_id = approval_record.id

                # Create approval line WITHOUT requested_by field
                line_vals = {
                    'approval_id': approval_record.id,
                    'farm_boy_request_id': record.id,
                    'product_id': record.product_id.id,
                    'requested_quantity': record.total_dose,
                    'dose_per_bird': record.dose_per_bird,
                    'remaining_dose': record.remaining_dose,
                    'bird_count': record.bird_count,
                    'consume_quantity': record.consume_quantity,
                    'total_cost': record.total_cost,
                    # Remove requested_by from here since it doesn't exist in the target model
                    # 'requested_by': requested_by_id,
                }
                
                # Only add fields that exist in the target model
                approval_line_model = self.env['farm.medicine.approval.line']
                if 'short_note' in approval_line_model._fields:
                    line_vals['short_note'] = record.short_note or ''
                if 'cost_per_unit' in approval_line_model._fields:
                    line_vals['cost_per_unit'] = record.cost_per_unit
                if 'total_cost' in approval_line_model._fields:
                    line_vals['total_cost'] = record.total_cost
                
                self.env['farm.medicine.approval.line'].create(line_vals)

                # Update line state
                record.state = 'requested'
                
                _logger.info(f"Request {record.id} transferred to approval {approval_record.name}")


    def write(self, vals):
        res = super(FarmBoyRequestAddLine, self).write(vals)
        if 'state' in vals:
            self.request_id._update_parent_state()
            self.action_state()
        return res

    def create(self, vals):
        rec = super(FarmBoyRequestAddLine, self).create(vals)
        rec.request_id._update_parent_state()
        if 'state' in vals:
            rec.action_state()
        return rec

    def action_state(self):
        print("done")
        for record in self:  # loop over all records safely
            # Only process records in approved state
            if record.state != "approved":
                continue

            if not record.product_id:
                raise UserError("Product not assigned!")

            if record.consume_quantity <= 0:
                raise UserError("Consume quantity must be greater than zero!")

            product = record.product_id
            quants = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id.usage', '=', 'internal'),
                ('quantity', '>', 0)
            ], order='quantity desc')

            total_available = sum(q.quantity for q in quants)
            if total_available < record.consume_quantity:
                raise UserError(
                    f"Not enough Medicine available!\nAvailable: {total_available}, Required: {record.consume_quantity}"
                )

            qty_to_remove = record.consume_quantity
            for quant in quants:
                if qty_to_remove <= 0:
                    break

                remove_qty = min(quant.quantity, qty_to_remove)
                scrap = self.env['stock.scrap'].create({
                    'product_id': product.id,
                    'scrap_qty': remove_qty,
                    'location_id': quant.location_id.id,
                    'company_id': self.env.company.id,
                    'origin': f"Consume Quantity Record ({product.display_name}) - Flock ({record.flock_id.name})"
                })
                scrap.action_validate()
                qty_to_remove -= remove_qty
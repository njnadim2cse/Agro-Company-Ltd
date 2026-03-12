from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class AddMedicineByTemp(models.Model):

    _name = "farm.medicine.temperature"
    _description = "Temperature-based Medicine Record"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "create_date desc"
    

    medicine_line_ids = fields.One2many(
        'farm.medicine.temperature.line', 'temperature_id', string="Medicine Suggestions"
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('done', 'Done')],
        string="Status", default='draft', tracking=True
    )

    date = fields.Date(string="Date", default=fields.Date.context_today)
    name = fields.Char(string="Reference", default="New", readonly=True)
    inside_min = fields.Float(string="Inside Temp Min (°C)", required=True, tracking=True)
    inside_max = fields.Float(string="Inside Temp Max (°C)", required=True, tracking=True)
    outside_min = fields.Float(string="Outside Temp Min (°C)", required=True, tracking=True)
    outside_max = fields.Float(string="Outside Temp Max (°C)", required=True, tracking=True)
    notes = fields.Text(string="Notes", tracking=True)
    note_html = fields.Html(string="Note")
    
    @api.constrains('inside_min', 'inside_max', 'outside_min', 'outside_max')
    def _check_temperature_values(self):
        for record in self:
            if (record.inside_min <= 0 or record.inside_max <= 0 or
                record.outside_min <= 0 or record.outside_max <= 0):
                raise ValidationError("Temperature values must be greater than 0°C.")

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            today_str = datetime.today().strftime('%d-%m-%Y')
            last_record = self.search(
                [('name', 'like', f'T/M/{today_str}/%')],
                order='id desc', limit=1
            )
            if last_record:
                last_seq = int(last_record.name.split('/')[-1])
                next_seq = str(last_seq + 1).zfill(5)
            else:
                next_seq = '00001'
            vals['name'] = f"A/M/{today_str}/{next_seq}"
        return super(AddMedicineByTemp, self).create(vals)

    def action_draft(self):
        for rec in self:
            if rec.state != "draft":
                rec.state = "draft"


    def action_confirm(self):
        for rec in self:
            if rec.state != "done":
                rec.state = "done"

            

class FarmTemperature(models.Model):

    _name = "farm.temperature"
    _description = "Daily Temperature Record"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "date desc"
    

    

    name = fields.Char(string="Reference", default="New", readonly=True)
    created_by = fields.Many2one('res.users', string="Responsible Person", default=lambda self: self.env.user, readonly=True)
    date = fields.Date(
        string="Date", required=True, tracking=True, default=fields.Date.context_today
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('done', 'Done')],
        string="Status", default='draft', tracking=True
    )
    flock_id = fields.Many2one("farm.layer.flock", string="Flock", tracking=True)
    current_birds = fields.Integer(string="Current Birds")
    birds_type = fields.Selection(
        [('broiler', 'Broiler'), ('layer', 'Layer'), ('duck', 'Duck')],
        string="Birds Type", tracking=True
    )
    age_in_days = fields.Integer(string="Age in Days")
    temp_max = fields.Float(string="Inside Temp Max (°C)", required=True, tracking=True)
    temp_min = fields.Float(string="Inside Temp Min (°C)", required=True, tracking=True)

    daily_temperature_ids = fields.One2many(
        'daily.temperature.medicine.line', 'daily_temperature_id', string="Medicine Lines",ondelate="casecade"
    )
    @api.model
    def create(self, vals):
        record = super(FarmTemperature, self).create(vals)
        record._assign_medicines_by_temperature()
        return record
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            today_str = datetime.today().strftime('%d-%m-%Y')
            last_record = self.search(
                [('name', 'like', f'M/S/{today_str}/%')],
                order='id desc', limit=1
            )
            if last_record:
                last_seq = int(last_record.name.split('/')[-1])
                next_seq = str(last_seq + 1).zfill(5)
            else:
                next_seq = '00001'
            vals['name'] = f"M/S/{today_str}/{next_seq}"
        return super(FarmTemperature, self).create(vals)
    

    def write(self, vals):
        res = super(FarmTemperature, self).write(vals)
        if any(k in vals for k in ['flock_id', 'temp_max', 'temp_min']):
            self._assign_medicines_by_temperature()
        return res


    @api.onchange('flock_id')
    def _on_change_get_flock_info(self):
        if self.flock_id:
            self.current_birds = self.flock_id.total_qty
            self.birds_type = self.flock_id.bird_type
            self.age_in_days = self.flock_id.age_in_days

    @api.onchange('flock_id', 'temp_min','temp_max')
    def call_assign(self):
        self._assign_medicines_by_temperature()

    @api.onchange("flock_id")
    def _assign_medicines_by_temperature(self):
        for record in self:
            record.daily_temperature_ids = [(5, 0, 0)]
            medicine_lines_dict = {}
            age = record.age_in_days or 0
            tmin = record.temp_min or 0
            tmax = record.temp_max or 0

            medicine_records = self.env['add.medicine.by.live.temperature'].search([])
            matched_medicines = self.env['add.medicine.by.live.temperature']

            for med in medicine_records:
                if med.state != 'done':  
                    continue
                ok = False
                if med.selection_type == 'age':
                    if med.min_age is not None and med.max_age is not None:
                        if med.min_age <= age <= med.max_age:
                            ok = True
                elif med.selection_type == 'temp':
                    if med.min_temp is not None and med.max_temp is not None:
                        if med.min_temp <= tmax and med.max_temp >= tmin:
                            ok = True
                elif med.selection_type == 'age_temp':
                    age_ok = med.min_age is not None and med.max_age is not None and med.min_age <= age <= med.max_age
                    temp_ok = med.min_temp is not None and med.max_temp is not None and med.min_temp <= tmax and med.max_temp >= tmin
                    if age_ok and temp_ok:
                        ok = True
                if ok:
                    matched_medicines |= med

            for med in matched_medicines:
                for line in med.medicine_line_ids:
                    pid = line.product_id.id
                    qty = (line.dose_per_water_liter or 0) * (record.current_birds or 0)
                    if qty <= 0:
                        continue
                    if pid in medicine_lines_dict:
                        medicine_lines_dict[pid] += qty
                    else:
                        medicine_lines_dict[pid] = qty

            lines_to_add = []
            for pid, total_qty in medicine_lines_dict.items():
                product = self.env['product.product'].browse(pid)
                lines_to_add.append((0, 0, {
                    'product_id': pid,
                    'total_quantity': product.qty_available,
                    'consume_quantity': total_qty,
                    'flock_id': record.flock_id.id,
                    'date': record.date,
                }))
            record.daily_temperature_ids = lines_to_add

    def action_draft(self):
        for rec in self:
            if rec.state != "draft":
                rec.state = "draft"

       
    def action_confirm(self):
        for record in self:
            record.state = 'done'

            for line in record.daily_temperature_ids:
                if line.state != 'done':
                    line.action_done() 
    

class MedicineTemperatureLine(models.Model):
    _name = "farm.medicine.temperature.line"
    _description = "Medicine Line for Temperature"
    

    

    temperature_id = fields.Many2one(
        'farm.medicine.temperature', string="Temperature Record", required=True,
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('done', 'Done')],
        string="Status", tracking=True
    )
    product_id = fields.Many2one('product.product', string="Medicine Name",domain=[('is_medicine','=',True)])
    user_id = fields.Many2one("res.users", string="Suggested By", default=lambda self: self.env.user, tracking=True)
    total_dose = fields.Float(string="Total Dose (ml)")
    dose_per_water_liter = fields.Float(string="Dose Per Water liter")
    short_note = fields.Text(string="Short Note")

    def action_done(self):
        if self.state=="done":
            return
        self.state = 'done'

    def action_draft(self):
        if self.state=="draft":
            return
        self.state = 'draft'


class DailyTemperatureMedicineLine(models.Model):
    
    _name = 'daily.temperature.medicine.line'
    _description = "Daily Temperature Medicine Line"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    

    

    date = fields.Datetime(string="Date and time", default=fields.Datetime.now, required=True, tracking=True)
    product_id = fields.Many2one("product.product", string="Medicine", tracking=True,domain=[('is_medicine','=',True)])
    total_quantity = fields.Float(string="Available Quantity")
    consume_quantity = fields.Float(string="Consumed Quantity", tracking=True)
    daily_temperature_id = fields.Many2one('farm.temperature', string="Temperature Record")
    flock_id = fields.Many2one("farm.layer.flock", string="Flock", tracking=True)
    remaining_quantity = fields.Float(string="Remaining Quantity")
    medicine_cost = fields.Float(string="Current Birds", related='product_id.standard_price', tracking=True)
    cost = fields.Float(string="Total Cost", compute="_compute_medicine_cost", store=True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], string="Status", default='draft', tracking=True)
    bird_type = fields.Selection([('layer','Layer'),('broiler','Broiler')],string="Bird Type" ,tracking =True)

    @api.onchange("flock_id")
    def get_flock_data(self):
        self.bird_type = self.flock_id.bird_type 
    
    @api.depends('consume_quantity')
    def _compute_medicine_cost(self):

        for record in self:
            record.cost = (record.medicine_cost or 0.0) * (record.consume_quantity or 0.0)
    
    def action_draft(self):
        if self.state =="draft":
            return 
        self.state = 'draft'

    # @api.constrains('consume_quantity', 'total_quantity')
    # def _check_consume_quantity(self):
    #     for rec in self:
    #         if rec.consume_quantity < 0:
    #             raise ValidationError("Consumed Quantity cannot be negative.")

    #         if rec.total_quantity < 0:
    #             raise ValidationError("Total Quantity cannot be negative.")

    #         if rec.consume_quantity > rec.total_quantity:
    #             raise ValidationError(
    #                 f"Consumed Quantity ({rec.consume_quantity}) "
    #                 f"cannot be more than Total Quantity ({rec.total_quantity})."
    #             )
    
    @api.onchange("product_id")
    def available_quantity(self):
        self.total_quantity = self.product_id.qty_available

    def action_done(self):
        flock_id = self.daily_temperature_id.flock_id.id if self.daily_temperature_id.flock_id else False
        birds_type = self.daily_temperature_id.flock_id.bird_type
        current_birds = self.daily_temperature_id.flock_id.total_qty 
        current_age_in_weeks = self.daily_temperature_id.flock_id.current_age_display


        request_data = self.env['farm.boy.request.data'].search([
            ('date', '=', self.date),
            ('flock_id', '=', flock_id)
        ], limit=1)

        if not request_data:

            request_data = self.env['farm.boy.request.data'].create({
                'date': self.date,
                'flock_id':flock_id,
                'bird_type':birds_type,
                'current_birds':current_birds,
                'current_age_display':current_age_in_weeks,
                'requested_by': self.env.user.id,
                'temp_max': self.daily_temperature_id.temp_max,
                'temp_min': self.daily_temperature_id.temp_min,
            })

        existing_line = self.env['farmboy.request.add.line'].search([
            ('request_id', '=', request_data.id),
            ('product_id', '=', self.product_id.id)
        ], limit=1)

        if not existing_line:
            self.env['farmboy.request.add.line'].create({
                'request_id': request_data.id,
                'product_id': self.product_id.id,
                'total_dose': self.total_quantity,
                'short_note': "Auto-generated from Suggested Medicine Line",
                'remaining_dose': self.remaining_quantity,
                'flock_id': flock_id,
                'consume_quantity':self.consume_quantity
            })
        self.state = 'done'


    def unlink(self):
        for rec in self:
            if rec.state == 'done':
                raise UserError("You cannot delete records in Done state.")
        return super().unlink()


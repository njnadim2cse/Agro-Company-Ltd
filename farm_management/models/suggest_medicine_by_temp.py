import requests
from datetime import date
from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError, UserError
from datetime import datetime
import logging
import json 
_logger = logging.getLogger(__name__)

class WeatherData(models.Model):
    _name = 'weather.data'
    _description = 'Daily Weather Data'
    _order = 'date desc'
    


    date = fields.Date(string="Date", default=fields.Date.today)
    api_response = fields.Json(string="Full API Response", readonly=True)

    @api.model
    def remove_old_data(self):
        today = date.today()
        old_records = self.search([('date', '!=', today)])
        if old_records:
            old_records.unlink() 
        return True


class TemperatureDetailsData(models.Model):

    _inherit = ['mail.thread', 'mail.activity.mixin']
    _name = 'temperature.details.data'
    _description = "Live Temperature Data"
    _order = "date desc"
    

    

    state = fields.Boolean(string="State" , default= False)
    date = fields.Date(string="Date", default=fields.Date.today)
    created_by = fields.Many2one('res.users', string="Responsible Person", default=lambda self: self.env.user, readonly=True)
    name = fields.Char(string="Reference", default="New", readonly=True )
    City = fields.Char(string="City", default="Dhaka")
    temp_instant = fields.Float(string="Instant Temperature (°C)")
    temp_max = fields.Float(string="Max Temperature (°C)")
    temp_min = fields.Float(string="Min Temperature (°C)")
    wind_min = fields.Float(string="Min Wind Speed (km/h)")
    wind_max = fields.Float(string="Max Wind Speed (km/h)")
    now_time = fields.Datetime(string="Now Time", default=lambda self: fields.Datetime.now())
    weather_raw_data = fields.Text(string="Weather Raw Data")
    modelrun_updatetime_utc = fields.Datetime(string="Model Run Update UTC")
    modelrun_utc = fields.Datetime(string="Model Run UTC")
    height = fields.Float(string="Height")
    timezone = fields.Char(string="Timezone")
    latitude = fields.Float(string="Latitude")
    longitude = fields.Float(string="Longitude")
    utc_offset = fields.Float(string="UTC Offset")
    generation_time_ms = fields.Float(string="Generation Time (ms)")
    temp_unit = fields.Char(string="Temperature Unit")
    windspeed_unit = fields.Char(string="Windspeed Unit")
    precip_unit = fields.Char(string="Precipitation Unit")
    humidity_unit = fields.Char(string="Humidity Unit")
    pressure_unit = fields.Char(string="Pressure Unit")
    snowfraction_unit = fields.Char(string="Snow Fraction Unit")
    precipprob_unit = fields.Char(string="Precipitation Probability Unit")

    suggested_medicine_line_ids = fields.One2many(
        'suggested.medicine.line', 
        'daily_temperature_id', 
        string="Suggested Medicines",
        tracking=True,
        ondelate='cascade'
    )

    flock_id = fields.Many2one("farm.layer.flock", string="Flock", tracking=True)

    current_birds = fields.Integer(string="Current Birds")
    birds_type = fields.Selection([
        ('broiler', 'Broiler'),
        ('layer', 'Layer'),
        ('duck', 'Duck'),
    ], string="Birds Type", tracking=True)
    age_in_days = fields.Integer(string="Age in Days")
    age_in_weeks = fields.Char(string="Age in Weeks")
    state = fields.Selection(
        [('draft', 'Draft'), ('done', 'Done')],
        string="Status", default='draft', tracking=True
    )

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals.get('name') == 'New':
            today_str = datetime.today().strftime('%d-%m-%Y')
            last_record = self.search([('name', 'like', f'S/M/{today_str}/%')], order='id desc', limit=1)
            if last_record and last_record.name:
                try:
                    last_seq = int(last_record.name.split('/')[-1])
                    next_seq = str(last_seq + 1).zfill(5)
                except ValueError:
                    next_seq = '00001'
            else:
                next_seq = '00001'

            vals['name'] = f"S/M/{today_str}/{next_seq}"

        record = super(TemperatureDetailsData, self).create(vals)
        return record
    

    @api.onchange("flock_id")
    def get_flock_data(self):
        
        self.birds_type = self.flock_id.bird_type
        self.age_in_days = self.flock_id.current_age_in_days
        self.age_in_weeks = self.flock_id.current_age_display
        self.current_birds = self.flock_id.total_qty
    
    def action_fetch_live_temperature(self):

        if not self.flock_id:
          raise UserError("Operation cannot be performed: Flock is not assigned. Please provide a Flock.")
        existing = self.env['weather.data'].search([])

        if not existing:

            url = "https://my.meteoblue.com/packages/basic-1h_basic-day"
            params = {
                "lat": 23.8041,
                "lon": 90.4152,
                "apikey": "XzAjEYK052Sfonue"
            }

            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            self.env['weather.data'].create({
                'date': fields.Date.today(),
                'api_response': data
            })
            
        elif existing:
            try:
                record = self.env['weather.data'].search([], order='create_date desc', limit=1)
                data = record.api_response
                
                metadata = data.get("metadata", {})
                units = data.get("units", {})
                today_str = date.today().isoformat()
                data_day = data.get("data_day", {})
                dates = data_day.get("time", [])
                temp_instant_list = data_day.get("temperature_instant", [])
                temp_max_list = data_day.get("temperature_max", [])
                temp_min_list = data_day.get("temperature_min", [])
                wind_min_list = data_day.get("windspeed_min", [])
                wind_max_list = data_day.get("windspeed_max", [])
                time_zone = metadata.get("timezone_abbrevation")
                update_model_run_time = metadata.get("modelrun_updatetime_utc")
                pressure_unit = units.get("pressure")
                config_param = self.env['ir.config_parameter'].sudo()
                config_param.set_param('weather.raw.data', json.dumps(data))
                data_1h = data.get("data_1h", {})
                times = data_1h.get("time", [])
                temps = data_1h.get("temperature",[])
                winds = data_1h.get("windspeed", [])
                rains = data_1h.get("precipitation", [])
                self.timezone = time_zone 
                self.pressure_unit = pressure_unit
                self.modelrun_updatetime_utc = update_model_run_time
                if not dates:
                    raise UserError("No daily data returned from API.")
                daily_record = self.search([('date', '=', today_str)], limit=1)
                self.temp_instant = temp_instant_list[0]
                self.temp_max = temp_max_list[0]
                self.temp_min = temp_min_list[0]
                self.wind_max = wind_max_list[0]
                self.wind_min = wind_min_list[0]
                self.date = dates[0]
                
                self.env["farm.boy.request.data"].create({
                    "flock_id": self.flock_id.id if self.flock_id else False,
                    "date": dates[0],
                    "bird_type": self.birds_type,
                    "age_in_weeks": self.age_in_weeks,
                    "current_birds": self.current_birds,
                    "temp_max": temp_max_list[0],
                    "temp_min": temp_min_list[0],
                    "temp_instant": temp_instant_list[0]
                })

                for record in self:
                    record.suggested_medicine_line_ids = [(5, 0, 0)]
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
                            'consume_quantity': total_qty,
                            'total_quantity':product.qty_available,
                            'flock_id': record.flock_id.id,
                            'date': record.date,
                        }))

                    record.suggested_medicine_line_ids = lines_to_add
                    
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Live Temperature Data',
                    'view_mode': 'form',
                    'res_model': 'temperature.details.data',
                    'res_id': self.id,
                    'target': 'current',
                    "data": data,
                }
            except Exception as e:
                _logger.error("Error fetching live temperature: %s", e)
                raise UserError(f"Error fetching live temperature: {e}")
            

    def action_view_dashboard(self):
        """Open a separate form/dashboard view for this record"""
        return {
            'type': 'ir.actions.client',
            'name': 'Dhaka Dashboard',
            'tag': 'layer_temp_dash.DashboardAction',
            'target': 'current',
            'params': {},
        }
    
    def action_draft(self):
        if self.state =="draft":
            return 
        self.state = 'draft'
    

    def action_confirm(self):
        for record in self:
            record.state = 'done'

            for line in record.suggested_medicine_line_ids:
                if line.state != 'done':
                    line.action_done() 
    
class SuggestedeMedicineLine(models.Model):

    _name = 'suggested.medicine.line'
    _description = "Daily Temperature Medicine Line"
    _inherit = ['mail.thread', 'mail.activity.mixin']
 

    date = fields.Datetime(string="Date and Time", default=fields.Datetime.now, required=True, tracking=True)
    flock_id = fields.Many2one('farm.layer.flock', string="Flock", tracking=True)
    created_by = fields.Many2one('res.users', string="Responsible Person", default=lambda self: self.env.user, readonly=True)
    product_id = fields.Many2one("product.product", string="Medicine", tracking=True)
    total_quantity = fields.Float(string="Available Quntity")
    consume_quantity = fields.Float(string="Consumed Quantity", tracking=True)
    remaining_quantity = fields.Float(string="Remaining Quantity")
    medicine_cost = fields.Float(string="Medicine Cost", related='product_id.standard_price', tracking=True)
    cost = fields.Float(string="Total Cost", compute="_compute_medicine_cost", store=True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], string="Status", default='draft', tracking=True)
    daily_temperature_id = fields.Many2one('temperature.details.data', string="Temperature Data", ondelete='cascade', required=False, tracking=True)
    farmboy_request_add_line_ids = fields.One2many('farmboy.request.add.line','farmboy_request_id',string="Request Add Lines")

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
        print("Total Quantity",self.total_quantity)

    
    @api.depends('consume_quantity', 'medicine_cost')
    def _compute_medicine_cost(self):

        for record in self:
            record.cost = (record.medicine_cost or 0.0) * (record.consume_quantity or 0.0)

    def action_done(self):

        request_data = self.env['farm.boy.request.data'].search([('date', '=', self.date)], limit=1)
        if request_data:
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
                    'consume_quantity':self.consume_quantity,
                    'daily_temperature_id': self.daily_temperature_id.id,
                    'flock_id': self.daily_temperature_id.flock_id.id if self.daily_temperature_id.flock_id else False,
                })

            self.state = 'done'

    def action_draft(self):
        if self.state =="draft":
            return 
        self.state =="draft"
    






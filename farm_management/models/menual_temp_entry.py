from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import logging
_logger = logging.getLogger(__name__)

class MenualTemperatureEntry(models.Model):
    _name = "menual.temperature.entry"
    _description = "Manual Temperature Entry for Tunnel Ventilation"
    _inherit = ['mail.thread', 'mail.activity.mixin']
 

    name = fields.Char(string="Reference", default="New", readonly=True, tracking=True)
    
    daily_temperature_ids = fields.One2many('today.hourly.temperature', 'menual_temperature_entry_id', string="Hourly Temperatures")
    date = fields.Date(string="Date", default=fields.Date.context_today, tracking=True)
    time = fields.Float(string="Time (Hours)", tracking=True)
    temperature = fields.Float(string="Temperature (°C)", tracking=True)
    created_by = fields.Many2one('res.users', string="Created By", default=lambda self: self.env.user, readonly=True, tracking=True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Confirm')], default='draft', string="Status", tracking=True)

    ##Flock Realted Fields .
    flock_id = fields.Many2one(
        "farm.layer.flock", string="Flock Name", required=True, ondelete="cascade"
    )
    flock_opening_bird = fields.Integer(string="Opening Birds", tracking=True)
    flock_starting_date = fields.Date(string="Starting Date")
    flock_ending_date = fields.Date(string="Ending Date")
    current_birds = fields.Integer(string="Current Birds")
    age_in_days = fields.Integer(string="Age in Days")
    current_age_display = fields.Char(string="Age in Weeks", tracking=True)

    @api.onchange('flock_id')
    def _onchange_get_flock_data(self):
        if self.flock_id:
            self.flock_opening_bird = self.flock_id.opening_bird_count
            self.flock_ending_date = self.flock_id.end_date
            self.flock_starting_date = self.flock_id.start_date
            self.current_birds = self.flock_id.total_qty
            self.age_in_days = self.flock_id.current_age_in_days
            self.current_age_display = self.flock_id.current_age_display

    @api.model
    def create(self, vals):
        if 'date' in vals:
            existing = self.search([('date', '=', vals['date'])])
            if existing:
                raise ValidationError("A temperature entry for this day already exists.")
            
        if vals.get('name', 'New') == 'New':
            today_str = datetime.today().strftime('%d-%m-%Y')
            last_record = self.search(
                [('name', 'like', f'MTE/{today_str}/%')],
                order='id desc', limit=1
            )
            if last_record:
                last_seq = int(last_record.name.split('/')[-1])
                next_seq = str(last_seq + 1).zfill(5)
            else:
                next_seq = '00001'
            vals['name'] = f"MTE/{today_str}/{next_seq}"
        return super(MenualTemperatureEntry, self).create(vals)
    def action_done(self):
        if self.state == "done":
            return 
        self.state = 'done'
    def action_draft(self):
        if self.state == "draft":
            return 
        self.state = 'draft'


class TodayHourlyTemperature(models.Model):
    _name = "today.hourly.temperature"
    _description = "Today's Hourly Temperature Records"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    

    

    date = fields.Date(string="Date", default=fields.Date.context_today, tracking=True)
    menual_temperature_entry_id = fields.Many2one('menual.temperature.entry', string="Manual Temperature Entry", tracking=True)

    def _get_current_time_ampm(self):
        now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        return now.strftime("%I:%M %p")
    
    time_now = fields.Char(
        string="Time",
        default=_get_current_time_ampm,
        readonly=False,
        tracking=True,
    )
    temperature = fields.Float(string="Temperature (°C)", tracking=True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Confirm')], default='draft', string="Status", tracking=True)
    matched_level_line_id = fields.Many2one(
    'farm.ventilation.level.line',
    string="Matched Level",
    compute="_compute_matched_level",
    store=False
    )


    
    def action_draft(self):
        if self.state == "done":
            return 
        self.state = 'done'

    def action_done(self):
        if self.state == "draft":
            return 
        self.state = 'draft'
    

    @api.depends('temperature', 'menual_temperature_entry_id.flock_id')
    def _compute_matched_level(self):
        for rec in self:
            rec.matched_level_line_id = False

            if rec.temperature and rec.menual_temperature_entry_id.flock_id:
                flock = rec.menual_temperature_entry_id.flock_id

                data = self.env['farm.ventilation.level.line'].search([
                    ('min_temperature', '<=', rec.temperature),
                    ('max_temperature', '>=', rec.temperature),
                    ('ventilation_farm_id.flock_id', '=', flock.id)
                ], limit=1)

                rec.matched_level_line_id = data.id

    def action_open_level_line(self):

        if not self.matched_level_line_id:
            raise UserError("No Ventilation matches this temperature!")
        
        return {
            'name': 'Matched Ventilation Level',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'farm.ventilation.level.line',
            'res_id': self.matched_level_line_id.id,
            'target': 'current',
        }

from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date
from datetime import datetime
class FarmWaterIntake(models.Model):

    _name = "farm.water.intake"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Daily Water Intake per Flock/Bird"
    

    date = fields.Date(string="Date", default=fields.Date.context_today)
    flock_id = fields.Many2one("farm.layer.flock", string="Flock",tracking =True)
    created_by = fields.Many2one('res.users', string="Responsible Person", default=lambda self: self.env.user, readonly=True,tracking =True)
    providing_category = fields.Selection(
    selection=[
        ('half_day', 'Morning (3,000 L)'),
        ('one_time', 'Late Morning (3,000 L)'),
        ('afternoon', 'Afternoon (3,000 L)'),
        ('full_day', 'Evening (3,000 L)'),
    ],
    string='Water Intake Type',
    tracking=True
    )

    current_birds = fields.Integer(string="Current Birds")
    bird_type = fields.Selection([('layer','Layer'),('broiler','Broiler')],string="Bird Type" ,tracking =True)
    current_age_display = fields.Char(string="Current Age in Weeks", tracking=True)
    current_age_days = fields.Integer(string="Current Age in Days", tracking=True)
    name = fields.Char(string="Reference", default="New", readonly=True ,tracking =True)
    water_lit = fields.Float(string="Water intake (Liters)",compute="_compute_water_for_total_birds",inverse="_set_water_lit", required=True ,tracking =True)
    water_ml_per_bird = fields.Float(string="Water (ml/bird/day)", compute="_compute_water_ml_per_bird",inverse="_set_water_lit",store=True ,tracking =True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Confirm')], default='draft', string="Status",tracking=True)
    cumulative_water = fields.Float(
    string="Cumulative Water Intake (Liters)",
    compute="_compute_cumulative_water",
    store=True,
    readonly=True,
    tracking=True
     )
    user_id = fields.Many2one('res.users',string='Farm Boy',help="Wakter intake",default=lambda self: self.env.user,tracking=True)
    note_html = fields.Html(string="Notes (HTML)")

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            today_str = datetime.today().strftime('%d-%m-%Y')
            last_record = self.search(
                [('name', 'like', f'W/I/{today_str}/%')],
                order='id desc', limit=1
            )
            if last_record:
                last_seq = int(last_record.name.split('/')[-1])
                next_seq = str(last_seq + 1).zfill(5)
            else:
                next_seq = '00001'
            vals['name'] = f"W/I/{today_str}"
        return super(FarmWaterIntake, self).create(vals)


    @api.onchange('water_lit')
    def _compute_water_ml_per_bird(self):
            if self.flock_id and self.flock_id.total_qty:
                self.water_ml_per_bird = round((self.water_lit * 1000) / self.flock_id.total_qty, 2)
            else:
                self.water_ml_per_bird = 0
    
    @api.onchange('providing_category')
    def _compute_water_for_total_birds(self):
        for record in self:
            if record.providing_category == 'half_day':
                record.water_lit = 3000
            elif record.providing_category == 'one_time':
                record.water_lit = 3000
            elif record.providing_category == 'full_day':
                record.water_lit = 3000
            elif record.providing_category == 'afternoon':
                record.water_lit = 3000
            else:
                record.water_lit = 0
        
    def _set_water_lit(self):
        for record in self:
            record = record.with_context(manual_entry=True)

    def action_confirm(self):
        if self.state =="done":
            return 
        self.state = "done"


    def action_draft(self):
        if self.state =="draft":
            return 
        self.state = "draft"
    
    def unlink(self):
        for rec in self:
            if rec.state == 'done':
                raise UserError("Record can't be deleted because it is marked as Done!")
            if not self.env.user.has_group('base.group_system'):
                raise UserError("Only Settings users can delete records!")
        return super(FarmWaterIntake, self).unlink()
    
    @api.onchange("flock_id")
    def _get_date(self):
        self.current_birds = self.flock_id.total_qty
        self.bird_type = self.flock_id.bird_type
        self.current_age_display = self.flock_id.current_age_display
        self.current_age_days = self.flock_id.current_age_in_days
    
    @api.depends('water_lit', 'flock_id', 'date')

    def _compute_cumulative_water(self):
        for record in self:
            if record.flock_id and record.date:
                previous_records = self.search([
                    ('flock_id', '=', record.flock_id.id),
                    ('date', '<=', record.date)
                ])

                record.cumulative_water = sum(previous_records.mapped('water_lit'))
            else:
                record.cumulative_water = 0

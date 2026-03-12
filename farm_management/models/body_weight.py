from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date
from datetime import datetime
from odoo.exceptions import ValidationError
MAX_INT_32 = 2**32

class FlockBodyWeight(models.Model):
    _name = "flock.body.weight"
    _description = "Flock Body Weight Records"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "age_in_days asc"
    
    
    date = fields.Date(string="Date", default=fields.Date.today,tracking =True)
    created_by = fields.Many2one('res.users', string="Created By", default=lambda self: self.env.user, readonly=True)
    name = fields.Char(string="Reference", default="New", readonly=True )
    state = fields.Selection([('draft','Draft'),('done','Confirm')],string="Status", default='draft', tracking=True)
    age_in_days = fields.Integer(string="Age (Days)", required=True, tracking=True)

    act_weight = fields.Float(string="Actual Weight (g)",tracking=True)
    std_weight = fields.Float(string="Standard Range (g)",tracking=True)
    min_weight = fields.Float(string="Min Weight (g)",tracking=True)
    max_weight = fields.Float(string="Max Weight (g)",tracking=True)
    note_html = fields.Html(string="Notes (HTML)")

    flock_id = fields.Many2one("farm.layer.flock", string="Flock", tracking=True)
    current_birds = fields.Integer(string="Current Birds" ,tracking=True)
    birds_type = fields.Selection([
        ('broiler', 'Broiler'),
        ('layer', 'Layer'),
        ('duck', 'Duck'),
    ], string="Birds Type", tracking=True)
    age_in_days = fields.Integer(string="Age in Days")
    age_in_weeks = fields.Char(string="Age in Weeks")

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            last_record = self.search([('name', 'like', 'B/W/%')], 
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
            vals['name'] = f"B/W/{today_str}"

        return super(FlockBodyWeight, self).create(vals)
    
    @api.constrains('act_weight', 'min_weight', 'max_weight')
    def _check_weight_limits(self):
        for rec in self:
         
            weight_fields = {
                'Actual Weight': rec.act_weight,
                'Minimum Weight': rec.min_weight,
                'Maximum Weight': rec.max_weight,
            }

            for field_name, value in weight_fields.items():
                if value is not None:
                 
                    if value <= 0:
                        raise ValidationError(f"{field_name} must be a positive value.")

                   
                    if value > MAX_INT_32:
                        raise ValidationError(
                            f"{field_name} cannot exceed {MAX_INT_32} (2^32 limit)."
                        )
    

    @api.onchange("flock_id")
    def get_flock_data(self):
        self.birds_type = self.flock_id.bird_type
        self.age_in_days = self.flock_id.current_age_in_days
        self.age_in_weeks = self.flock_id.current_age_display
        self.current_birds = self.flock_id.total_qty


    @api.depends('act_weight', 'min_weight', 'max_weight')
    def _compute_status(self):
        for rec in self:
            if not rec.act_weight or not rec.min_weight or not rec.max_weight:
                rec.status = False
            elif rec.act_weight < rec.min_weight:
                rec.status = 'low'
            elif rec.act_weight > rec.max_weight:
                rec.status = 'high'
            else:
                rec.status = 'normal'

    def action_draft(self):
        if self.state =="draft":
            return 
        self.state = 'draft'

    def action_confirm(self):
        if self.state =="done":
            return 
        self.state = 'done'
    
    

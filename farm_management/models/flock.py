
import secrets
from odoo import models, fields, api
from datetime import date
from datetime import datetime
from odoo.exceptions import UserError
from odoo import models
from odoo.exceptions import UserError
from odoo import models, fields
from odoo.exceptions import ValidationError

import logging

class LayerFlock(models.Model):
    
    _name = "farm.layer.flock"
    _description = "Layer / Broiler Flock Information"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
  
    name = fields.Char(string="Flock Name", required=True,tracking =True)
    reference = fields.Char(string="Reference", default="New", readonly=True)
    created_by = fields.Many2one('res.users', string="Responsible Person", default=lambda self: self.env.user, readonly=True)
    bird_type = fields.Selection([('layer','Layer'),('broiler','Broiler')],string="Birds Type" ,tracking =True )
    date = fields.Date(string="Date", default=fields.Date.today,tracking =True)
    start_date = fields.Date(string="Starting Date",tracking =True)
    end_date = fields.Date(string="End Date",tracking =True)
    opening_bird_count = fields.Integer(string="Opening Brids",tracking =True)
    age_in_days = fields.Integer(string="Starting Age in Days")
    age_in_weeks = fields.Integer(string="Starting Age in Weeks", compute="_compute_age_weeks", store=True,tracking =True)

    current_age_in_days =fields.Integer(string="Current Age in Days",compute="_compute_current_age_days", store=True,tracking=True)
    current_age_in_weeks = fields.Integer(string="Current Age in Weeks", compute="_compute_current_age_weeks", store=True)
    current_extra_days = fields.Integer(string="Current Extra Days", compute="_compute_current_extra_days", store=True)
    temp_days = fields.Integer(string="Temp store")
    current_age_display = fields.Char(string="Current Age in Weeks", compute="_compute_current_age_display", tracking=True)


    age_display = fields.Char(string="Starting Age in Week", compute="_compute_age_display",tracking =True)
    extra_days = fields.Integer(string="Days",compute ="_extra_days",store =True,readonly=True,tracking =True)
    product_id = fields.Many2one('product.product', string="Birds",tracking =True)
    total_qty = fields.Float(string="Current Birds",related='product_id.qty_available',tracking =True)
    opening_bird_id = fields.Many2one('product.product')
    note_html = fields.Html(string="Notes (HTML)")
    mortality_ids = fields.One2many("farm.mortality.details", "flock_id", string="Mortality Details",tracking =True)
    opening_flag = fields.Boolean(default=False)
    state = fields.Selection([('draft','Draft'),('done','Confirm')],string="Status", default='draft', tracking=True)
    share_token = fields.Char(string="Share Token", copy=False, readonly=True)
    preview_html = fields.Html(string="Email Preview", readonly=True)


    @api.depends('age_in_days')
    def _compute_age_weeks(self):
        for rec in self:
            rec.age_in_weeks = rec.age_in_days /7 
    
    @api.depends("age_in_days")
    def _extra_days(self):
        for rec in self:
            rec.extra_days = rec.age_in_days % 7 

    @api.depends("start_date", "age_in_days")
    def _compute_current_age_days(self):
        for rec in self:
            if rec.start_date:
                temp_days = (date.today() - rec.start_date).days
            else:
                temp_days = 0
            rec.current_age_in_days = (rec.age_in_days or 0) + temp_days

    @api.depends('current_age_in_days')
    def _compute_current_age_weeks(self):
        for rec in self:
            rec.current_age_in_weeks = rec.current_age_in_days // 7
    

    @api.depends('current_age_in_days')
    def _compute_current_extra_days(self):
        for rec in self:
            rec.current_extra_days = rec.current_age_in_days % 7

    @api.depends('age_in_weeks', 'extra_days')
    def _compute_age_display(self):
        for rec in self:
            rec.age_display = f"{rec.age_in_weeks}  weeks  {rec.extra_days} days"
    
    @api.depends('current_age_in_weeks', 'current_extra_days')
    def _compute_current_age_display(self):
        for rec in self:
            rec.current_age_display = f"{rec.current_age_in_weeks} weeks {rec.current_extra_days} days"


    def _cron_update_current_age(self):
        flocks = self.search([])
        for rec in flocks:
            if rec.start_date:
                temp_days = (date.today() - rec.start_date).days
                rec.current_age_in_days = (rec.age_in_days or 0) + temp_days
                rec.current_age_in_weeks = rec.current_age_in_days // 7
                rec.current_extra_days = rec.current_age_in_days % 7
                rec.current_age_display = f"{rec.current_age_in_weeks} weeks {rec.current_extra_days} days"


    @api.onchange('product_id')
    def _onchange_product_id(self):
        self.opening_bird_id = self.product_id
        self.opening_bird_count = self.product_id.qty_available
        self.opening_flag=True
        if self.opening_flag:
            if self.product_id.id != self.opening_bird_id.id:
                self.opening_bird_count = self.product_id.qty_available


    def unlink(self):
        if not self.env.user.has_group('base.group_system'):
            raise UserError("Only Settings users can delete records!")
        return super(LayerFlock, self).unlink()
    
    @api.model
    def create(self, vals):
        if vals.get('reference', 'New') == 'New':
            today_str = datetime.today().strftime('%d-%m-%Y')
            last_record = self.search(
                [('reference', 'like', f'Flock/Details/{today_str}/')],
                order='id desc', limit=1
            )
            if last_record and last_record.reference:
                try:
                    last_seq = int(last_record.reference.split('/')[-1])
                    next_seq = str(last_seq + 1).zfill(5) 
                except:
                    next_seq = '00001'
            else:
                next_seq = '00001'

            vals['reference'] = f"F/S/{next_seq}"

        if 'product_id' in vals and vals['product_id'] and not vals.get('opening_bird_count'):
            product = self.env['product.product'].browse(vals['product_id'])
            vals['opening_bird_count'] = product.qty_available
        record = super(LayerFlock, self).create(vals)

        if not record.share_token:
            record.share_token = secrets.token_urlsafe(16)
            print("Generated Share Token:", record.share_token)

        return record

    def action_draft(self):
        if self.state =="draft":
            return 
        self.state = 'draft'

    def action_confirm(self):
        if self.state =="done":
            return 
        self.state = 'done'
    
    def action_send_flock_mail(self):
        """Send Flock details email"""
        self.ensure_one()
        template = self.env.ref('your_module_name.mail_template_flock_details', raise_if_not_found=False)
        if not template:
            raise UserError("Email Template not found. Please check the XML ID.")
        template.send_mail(self.id, force_send=True)
        return True
    
    def unlink(self):
        for rec in self:
            if rec.state == 'done':
                raise UserError("Record can't be deleted because it is linked with a picking!")
            if not self.env.user.has_group('base.group_system'):
                raise UserError("Only Settings users can delete records!")
        return super(LayerFlock, self).unlink()
    
    @api.constrains('name')
    def _check_unique_flock_name(self):
        for rec in self:
            existing = self.search([('name', '=', rec.name), ('id', '!=', rec.id)])
            if existing:
                raise ValidationError(f"A flock with the name '{rec.name}' already exists!")

    
    def send_mail(self):

        Mail = self.env['mail.mail']
        partners = self.env['res.partner'].search([])

        for partner in partners:
            html_content = ""

            flocks = self.env['farm.layer.flock'].search([])

            for flock in flocks:
                today = datetime.today().date()
                production_records = self.env['farm.production.details'].search([
                    ('flock_id', '=', flock.id),
                    ('date', '=', self.date or date.today())
                ])

                mortality_records = self.env["farm.mortality.details"].search([
                    ('flock_id', '=', flock.id),
                    ('date', '=', self.date or date.today())
                ])

                feed_records = self.env["feed.details"].search([
                    ('flock_id', '=', flock.id)
                    ,('datetime','=',fields.Date.today())
                 ])
                
                water_intake_records = self.env["farm.water.intake"].search([
                    ('date', '=', today),
                    ('flock_id', '=', flock.id),
                ])
                
              
                body_weight_records = self.env["flock.body.weight"].search([
                    ('date', '=', today),
                    ('flock_id', '=',flock.id),
                ])


                requests = self.env['farm.boy.request.data'].search([
                
                ])

                current_birds = production_records[0].current_birds if production_records else flock.opening_bird_count
                html_content += f"""
                <div style="font-family: Arial, sans-serif; color: #333; padding: 20px; background-color: #f8f9fa; margin-bottom: 20px;">
                    <div style="background-color: #714B67; color: white; padding: 18px 18px; border-radius: 5px 5px 0 0;">
                        <h2 style="margin: 0; color: #FFFFFF;"> Shed <strong> <span style="color: #FFFFFF;">{flock.name} </span></strong> Of Overview & Key Insights</h2>
                    </div>
                    <div style="background: white; border: 1px solid #ddd; border-top: none; border-radius: 0 0 5px 5px; padding: 20px;">
                        
                    
                        <p> {today} ,<br><strong>Dear Sir</strong>,<br>
                            Kindly review the summary of today’s details provided below.
                        </p>

                        <table style="width: 100%; border-collapse: collapse; margin-top: 15px; border: 1px solid #000;">
                            <tr style="background-color: #f2f2f2;">
                                <th style="padding: 4px; text-align: left; border: 1px solid #000;">Field</th>
                                <th style="padding: 4px; text-align: left; border: 1px solid #000;">Value</th>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Shed Name</td>
                                <td style="padding: 4px; border: 1px solid #000;">{flock.name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Birds Type</td>
                                <td style="padding: 4px; border: 1px solid #000;">{flock.bird_type or ''}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Starting Date</td>
                                <td style="padding: 4px; border: 1px solid #000;">{flock.start_date or ''}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Current Age</td>
                                <td style="padding: 4px; border: 1px solid #000;">{flock.current_age_display or ''}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Opening Birds</td>
                                <td style="padding: 4px; border: 1px solid #000;">{flock.opening_bird_count or 0}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Current Birds</td>
                                <td style="padding: 4px; border: 1px solid #000;">{current_birds}</td>
                            </tr>
                        </table>
                """
                if not production_records:
                    html_content += f"""

                        <div style="display: flex; gap: 20px; margin-top: 15px;">
                    
                            <table style="width: 50%; margin-right: 10px; border-collapse: collapse; margin-top: 15px; border: 1px solid #000;">
                            <tr style="background-color: #f9f9f9;">
                                <th colspan="2" style=" text-align: center;  background-color: #017E84; /* professional green background */ color: white; /* white text for contrast */  font-weight: bold;font-size: 16px; padding: 10px; "> Today's Production Summary </th>
                            </tr>

                            <tr style="background-color: #f9f9f9;">
                                <td style="padding: 4px; border: 1px solid #000;">Reference Name </td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;"> Responsible Person</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total Small Egg</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total Medium Egg</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total High Medium Egg</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total High Egg</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total Double Yolk Egg</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total Broken Egg</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total White Egg</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total Damage Egg</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total Egg </td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Production Percentage</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                        </table>
                    """

                for production in production_records:
                    html_content += f"""

                        <div style="display: flex; gap:20px; margin-top: 15px;">
                    
                            <table style="width: 50%; border-collapse: collapse; margin-top: 15px; border: 1px solid #000;margin-right: 10px;">
                            <tr style="background-color: #f9f9f9;">
                                <th colspan="2" style=" text-align: center;  background-color: #017E84; /* professional green background */ color: white; /* white text for contrast */  font-weight: bold;font-size: 16px; padding: 10px;"> Today's Production Summary </th>
                            </tr>

                            <tr style="background-color: #f9f9f9;">
                                <td style="padding: 4px; border: 1px solid #000;">Reference Name </td>
                                <td style="padding: 4px; border: 1px solid #000;">{production.name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;"> Responsible Person</td>
                                <td style="padding: 4px; border: 1px solid #000;">{production.created_by.name if production.created_by else ''}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total Small Egg</td>
                                <td style="padding: 4px; border: 1px solid #000;">{production.total_small}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total Medium Egg</td>
                                <td style="padding: 4px; border: 1px solid #000;">{production.total_medium}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total High Medium Egg</td>
                                <td style="padding: 4px; border: 1px solid #000;">{production.total_high_medium}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total High Egg</td>
                                <td style="padding: 4px; border: 1px solid #000;">{production.total_high}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total Double Yolk Egg</td>
                                <td style="padding: 4px; border: 1px solid #000;">{production.total_double_yolk}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total Broken Egg</td>
                                <td style="padding: 4px; border: 1px solid #000;">{production.total_broken}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total White Egg</td>
                                <td style="padding: 4px; border: 1px solid #000;">{production.total_white}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total Damage Egg</td>
                                <td style="padding: 4px; border: 1px solid #000;">{production.total_damage}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total Egg</td>
                                <td style="padding: 4px; border: 1px solid #000;">{production.total_egg}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;"> Production Percentage  </td>
                                <td style="padding: 4px; border: 1px solid #000;">{production.percentage}%</td>
                            </tr>
                        </table>
                    """

                """" name, flock_id, date, state, created_by, product_id, flock_opening_bird, flock_starting_date, flock_ending_date, current_birds, 
                age_in_days, total_qty, breakdown_ids, total_mortality, today_overall_mortality_percentage, normal_cause_mortality, culled_cause_mortality,
                vaccine_reaction_mortality, prolapse_mortality, heat_stress_mortality, mechanical_mortality, injury_mortality, other_cause_mortality, 
                cumaletive_mortality, comalitive_mortality_normal, comalitive_mortality_culled, comalitive_mortality_vaccine, comalitive_mortality_prolapse,
                    comalitive_mortality_heat_stress, comalitive_mortality_mechanical, comalitive_mortality_injury, comalitive_mortality_other, 
                    cause_percentage_normal, cause_percentage_culled, cause_percentage_vaccine,
                cause_percentage_prolapse, cause_percentage_heat_stress, cause_percentage_mechanical, cause_percentage_injury, cause_percentage_other """
                
                if not mortality_records:
                    
                    html_content += f"""
                            <table style="width: 50%; border-collapse: collapse; margin-top: 15px; border: 1px solid #000;">
                            <tr style="background-color: #f9f9f9;">
                                <th colspan="2" style=" text-align: center;  background-color: #017E84; /* professional green background */ color: white; /* white text for contrast */  font-weight: bold;font-size: 16px; padding: 10px; "> Today's Mortality Summary </th>
                            </tr>
                            <tr style="background-color: #f9f9f9;">
                                <td style="padding: 4px; border: 1px solid #000;">Reference Name</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Responsible Person</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Normal Cause Mortality</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Culled Cause Mortality</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Vaccine Reaction Cause Mortality</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Prolapse Cause Mortality </td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Heat Streess Cause Mortality</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Mechanical Cause Mortality</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Injury Cause Mortality</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Other's Cause Mortality</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total Mortality</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Today Mortality Percentage </td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                        </table>
                        </div>
                    """

                for mortality in mortality_records:
                    html_content += f"""
                            <table style="width: 50%; border-collapse: collapse; margin-top: 15px; border: 1px solid #000;">
                            <tr style="background-color: #f9f9f9;">
                                <th colspan="2" style=" text-align: center;  background-color: #017E84; /* professional green background */ color: white; /* white text for contrast */  font-weight: bold;font-size: 16px; padding: 10px; "> Today's Mortality Summary </th>
                            </tr>
                            <tr style="background-color: #f9f9f9;">
                                <td style="padding: 4px; border: 1px solid #000;">Reference Name</td>
                                <td style="padding: 4px; border: 1px solid #000;">{mortality.name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Responsible Person</td>
                                <td style="padding: 4px; border: 1px solid #000;">{mortality.created_by.name if mortality.created_by else ''}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Normal Cause Mortality</td>
                                <td style="padding: 4px; border: 1px solid #000;">{mortality.normal_cause_mortality}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Culled Cause Mortality</td>
                                <td style="padding: 4px; border: 1px solid #000;">{mortality.culled_cause_mortality}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Vaccine Reaction Cause Mortality</td>
                                <td style="padding: 4px; border: 1px solid #000;">{mortality.vaccine_reaction_mortality}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Prolapse Cause Mortality </td>
                                <td style="padding: 4px; border: 1px solid #000;">{mortality.prolapse_mortality}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Heat Streess Cause Mortality</td>
                                <td style="padding: 4px; border: 1px solid #000;">{mortality.heat_stress_mortality}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Mechanical Cause Mortality</td>
                                <td style="padding: 4px; border: 1px solid #000;">{mortality.mechanical_mortality}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Injury Cause Mortality</td>
                                <td style="padding: 4px; border: 1px solid #000;">{mortality.injury_mortality}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Other's Cause Mortality</td>
                                <td style="padding: 4px; border: 1px solid #000;">{mortality.other_cause_mortality}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total Mortality</td>
                                <td style="padding: 4px; border: 1px solid #000;">{mortality.total_mortality}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Today Mortality Percentage </td>
                                <td style="padding: 4px; border: 1px solid #000;">{mortality.today_overall_mortality_percentage}%</td>
                            </tr>
                        </table>
                        </div>
                    """

                    # feed details fields . 

                    """datetime, name, flock_id, created_by, current_bird, current_age_days, feed_per_bird, 
                    feed_product_id, product_id, on_hand_qty, feed_kg, cumm_feed, status, state, description_html, feed_time"""

                if not feed_records:
                    
                    html_content += f"""
                        <div style="display: flex; gap: 20px; margin-top: 15px;">
                            <table style="width: 50%; border-collapse: collapse; margin-top: 15px; border: 1px solid #000;margin-right: 10px;">
                            <tr style="background-color: #f9f9f9;">
                                <th colspan="2" style=" text-align: center;  background-color: #017E84; /* professional green background */ color: white; /* white text for contrast */  font-weight: bold;font-size: 16px; padding: 10px; "> Today's Feed  Summary </th>
                            </tr>
                            <tr style="background-color: #f9f9f9;">
                                <td style="padding: 4px; border: 1px solid #000;">Reference Name</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Responsible Person</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Feed Time</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Feed Per Birds</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>

                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Product Name</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">On Hand Quantity</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Consume quantity</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>

                        </table>
                    
                    """

                for feed in feed_records:
                    html_content += f"""
                        <div style="display: flex; gap: 20px; margin-top: 15px;">
                            <table style="width: 50%; border-collapse: collapse; margin-top: 15px; border: 1px solid #000;margin-right: 10px;">
                            <tr style="background-color: #f9f9f9;">
                                <th colspan="2" style=" text-align: center;  background-color: #017E84; /* professional green background */ color: white; /* white text for contrast */  font-weight: bold;font-size: 16px; padding: 10px;"> Today's Feed  Summary </th>
                            </tr>
                            <tr style="background-color: #f9f9f9;">
                                <td style="padding: 4px; border: 1px solid #000;">Reference Name</td>
                                <td style="padding: 4px; border: 1px solid #000;">{feed.name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Responsible Person</td>
                                <td style="padding: 4px; border: 1px solid #000;">{feed.created_by.name if feed.created_by else ''}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Feed Time</td>
                                <td style="padding: 4px; border: 1px solid #000;">{feed.feed_time}</td>
                            </tr>

                             <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Product Name</td>
                                <td style="padding: 4px; border: 1px solid #000;">{feed.feed_product_id.name}</td>
                            </tr>

                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Feed Per Birds</td>
                                <td style="padding: 4px; border: 1px solid #000;">{feed.feed_per_bird}(g)</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">On Hand Quantity</td>
                                <td style="padding: 4px; border: 1px solid #000;">{feed.on_hand_qty}(Kg)</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Consume quantity</td>
                                <td style="padding: 4px; border: 1px solid #000;">{feed.feed_kg}(Kg)</td>
                            </tr>

                        </table>
                    
                    """
                    
                """date, flock_id, created_by, providing_category, current_birds, 
                bird_type, current_age_display, name, water_lit, water_ml_per_bird, state, cumulative_water, user_id, note_html"""
                if not water_intake_records:
                    html_content += f"""
                            <table style="width: 50%; border-collapse: collapse; margin-top: 15px; border: 1px solid #000;">
                            <tr style="background-color: #f9f9f9;">
                                <th colspan="2" style=" text-align: center;  background-color: #017E84; /* professional green background */ color: white; /* white text for contrast */  font-weight: bold;font-size: 16px; padding: 4px 8px;"> Today's Water Intake Summary </th>
                            </tr>
                            <tr style="background-color: #f9f9f9;">
                                <td style="padding: 4px; border: 1px solid #000;">Reference Name</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Responsible Person</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Providing Category </td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;"> Water Per bird (ml)</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total Provided Water(L)</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                        
                        </table>
                        </div>
                    """

                for water in water_intake_records:
                    html_content += f"""
                            <table style="width: 50%; border-collapse: collapse; margin-top: 15px; border: 1px solid #000;">
                            <tr style="background-color: #f9f9f9;">
                                <th colspan="2" style=" text-align: center;  background-color: #017E84; /* professional green background */ color: white; /* white text for contrast */  font-weight: bold;font-size: 16px; padding: 10px;"> Today's Water Intake Summary </th>
                            </tr>
                            <tr style="background-color: #f9f9f9;">
                                <td style="padding: 4px; border: 1px solid #000;">Reference Name</td>
                                <td style="padding: 4px; border: 1px solid #000;">{water.name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Responsible Person</td>
                                <td style="padding: 4px; border: 1px solid #000;">{water.created_by.name if water.created_by else ''}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Providing Category </td>
                                <td style="padding: 4px; border: 1px solid #000;">{water.providing_category}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;"> Water Per bird (ml)</td>
                                <td style="padding: 4px; border: 1px solid #000;">{water.water_ml_per_bird}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Total Provided Water(L)</td>
                                <td style="padding: 4px; border: 1px solid #000;">{water.water_lit}</td>
                            </tr>
                        
                        </table>
                        </div>
                    """
                    """date, created_by, name, state, age_in_days, 
                    act_weight, std_weight, min_weight, max_weight, note_html, flock_id, current_birds, birds_type, age_in_weeks"""

                if not body_weight_records:
                    html_content += f"""
                        <div style="display: flex; gap: 20px; margin-top: 15px;">
                            <table style="width: 50%; border-collapse: collapse; margin-top: 15px; border: 1px solid #000;margin-right: 10px;">
                            <tr style="background-color: #f9f9f9;">
                                <th colspan="2" style=" text-align: center;  background-color: #017E84; /* professional green background */ color: white; /* white text for contrast */  font-weight: bold;font-size: 16px; padding: 10px; "> Today's Body Weight Summary </th>
                            </tr>
                            <tr style="background-color: #f9f9f9;">
                                <td style="padding: 4px; border: 1px solid #000;">Reference Name</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Responsible Person</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Standard Weight </td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Minimum Weight</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Maximum Weight</td>
                                <td style="padding: 4px; border: 1px solid #000;">N/A</td>
                            </tr>
                        
                        </table>
                    
                    """

                for weight in body_weight_records:
                    
                
                    html_content += f"""
                        <div style="display: flex; gap: 20px; margin-top: 15px;">

                            <table style="width: 50%; border-collapse: collapse; margin-top: 15px; border: 1px solid #000; margin-right: 10px;">
                            <tr style="background-color: #f9f9f9;">
                                <th colspan="2" style=" text-align: center;  background-color: #017E84; /* professional green background */ color: white; /* white text for contrast */  font-weight: bold;font-size: 16px; padding: 10px; "> Today's Body Weight Summary </th>
                            </tr>
                            <tr style="background-color: #f9f9f9;">
                                <td style="padding: 4px; border: 1px solid #000;">Reference Name</td>
                                <td style="padding: 4px; border: 1px solid #000;">{weight.name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Responsible Person</td>
                                <td style="padding: 4px; border: 1px solid #000;">{weight.created_by.name if weight.created_by else ''}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Standard Weight </td>
                                <td style="padding: 4px; border: 1px solid #000;">{weight.std_weight}(g)</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Minimum Weight</td>
                                <td style="padding: 4px; border: 1px solid #000;">{weight.min_weight}(g)</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px; border: 1px solid #000;">Maximum Weight</td>
                                <td style="padding: 4px; border: 1px solid #000;">{weight.max_weight}(g)</td>
                            </tr>
                        
                        </table>
                    
                    """
                    
                """product_id, flock_id, request_id, total_dose, dose_per_bird, bird_count, short_note, consume_quantity, 
                remaining_dose, cost_per_unit, total_cost, daily_temperature_id, farmboy_request_id, state, approval_id, request_date
                """
                
                for request in requests:

                    flock_lines = request.farmboy_request_line_ids.filtered(
                        lambda l: l.flock_id.id == flock.id
                    )
                    for line in flock_lines:
                        html_content += f"""
                                <table style="width: 50%; border-collapse: collapse; margin-top: 15px; border: 1px solid #000;">
                                <tr style="background-color: #f9f9f9;">
                                    <th colspan="2" style=" text-align: center;  background-color: #017E84; /* professional green background */ color: white; /* white text for contrast */  font-weight: bold;font-size: 16px; padding: 10px;"> Today's Medicine Summary </th>
                                </tr>
                                <tr style="background-color: #f9f9f9;">
                                    <td style="padding: 4px; border: 1px solid #000;">Reference Name</td>
                                    <td style="padding: 4px; border: 1px solid #000;">{line.product_id}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 4px; border: 1px solid #000;">Responsible Person</td>
                                    <td style="padding: 4px; border: 1px solid #000;">{line.remaining_dose or''}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 4px; border: 1px solid #000;">Standard Weight </td>
                                    <td style="padding: 4px; border: 1px solid #000;">{line.total_dose}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 4px; border: 1px solid #000;">Minimum Weight</td>
                                    <td style="padding: 4px; border: 1px solid #000;">{line.dose_per_bird}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 4px; border: 1px solid #000;">Maximum Weight</td>
                                    <td style="padding: 4px; border: 1px solid #000;">{line.consume_quantity}</td>
                                </tr>
                            
                            </table>
                            </div>
                        """

                html_content += """
                        
                    </div>
                </div>
                """

            self.preview_html = html_content
        
            mail_values = {
                'subject': f"Flock Summary:",
                'body_html': html_content,
                'email_to': partner.email,
                'email_from': "afzalkhan101.contact@gmail.com",
            }
            mail = Mail.create(mail_values)
            mail.send()

    



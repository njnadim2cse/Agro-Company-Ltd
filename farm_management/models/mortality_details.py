from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date
from datetime import datetime
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

class MortalityDetails(models.Model):

    _name = "farm.mortality.details"
    _description = "Mortality Details"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "date desc, id desc"
    


    name = fields.Char(string="Reference", default="New", readonly=True )
    flock_id = fields.Many2one(
        "farm.layer.flock", string="Flock Name", required=True, ondelete="cascade"
    )
    date = fields.Date(string="Date", required=True, default=fields.Date.today)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Confirm'),
    ], default='draft', tracking=True)
    created_by = fields.Many2one('res.users', string="Responsible Person", default=lambda self: self.env.user, readonly=True)
    product_id = fields.Many2one('product.product', string="Product", tracking=True)
    flock_opening_bird = fields.Integer(string="Opening Birds", tracking=True)
    flock_starting_date = fields.Date(string="Starting Date")
    flock_ending_date = fields.Date(string="Ending Date")
    current_birds = fields.Integer(string="Current Birds")
    age_in_days = fields.Integer(string="Age in Days")
    current_age_display = fields.Char(string="Age in Weeks", tracking=True)

    total_qty = fields.Float(string="Current Birds", related='product_id.qty_available', tracking=True)
    breakdown_ids = fields.One2many(
        'farm.mortality.breakdown', 'mortality_id', string="Mortality Breakdown"
    )

    total_mortality = fields.Integer(
        string="Total Mortality",
        compute="_compute_total_mortality",
        store=True
    )
    new_added_ = fields.Integer(string="New added Mortality", compute="_compute_new_added_mortality",store=True)
        # Overall Mortality Percentage
    today_overall_mortality_percentage = fields.Float( string="Overall Mortality Percentage", compute="_compute_overall_mortality_percentage", store=True )

    #individual total mortality fields can be added here if needed ###
    normal_cause_mortality = fields.Integer(string="Normal Cause Mortality", compute="_compute_total_mortality", store=True)
    culled_cause_mortality = fields.Integer(string="Culled Cause Mortality", compute="_compute_total_mortality", store=True)
    vaccine_reaction_mortality = fields.Integer(string="Vaccine Reaction Mortality", compute="_compute_total_mortality", store=True)
    prolapse_mortality = fields.Integer(string="Prolapse Mortality", compute="_compute_total_mortality", store=True)
    heat_stress_mortality = fields.Integer(string="Heat Stress Mortality", compute="_compute_total_mortality", store=True)
    mechanical_mortality = fields.Integer(string="Mechanical Mortality", compute="_compute_total_mortality", store=True)
    injury_mortality = fields.Integer(string="Injury Mortality", compute="_compute_total_mortality", store=True)
    other_cause_mortality = fields.Integer(string="Other Cause Mortality", compute="_compute_total_mortality", store=True)  
    #### new Added Mortality related fields . 

    normal_cause_mortality_new = fields.Integer(string="Normal Cause Mortality", compute="_compute_new_added_mortality", store=True)
    culled_cause_mortality_new = fields.Integer(string="Culled Cause Mortality", compute="_compute_new_added_mortality", store=True)
    vaccine_reaction_mortality_new = fields.Integer(string="Vaccine Reaction Mortality", compute="_compute_new_added_mortality", store=True)
    prolapse_mortality_new = fields.Integer(string="Prolapse Mortality", compute="_compute_new_added_mortality", store=True)
    heat_stress_mortality_new = fields.Integer(string="Heat Stress Mortality", compute="_compute_new_added_mortality", store=True)
    mechanical_mortality_new = fields.Integer(string="Mechanical Mortality", compute="_compute_new_added_mortality", store=True)
    injury_mortality_new = fields.Integer(string="Injury Mortality", compute="_compute_new_added_mortality", store=True)
    other_cause_mortality_new = fields.Integer(string="Other Cause Mortality", compute="_compute_new_added_mortality", store=True)  


    cumaletive_mortality = fields.Float( string="Cumulative Mortality", compute="_compute_cumaletive_mortality", store=True )

    ### cumalitive mortality fileds can be added here if needed ###
    comalitive_mortality_normal = fields.Float(string="Cumulative Normal Cause Mortality", compute="_compute_cumalitive_mortality_normal", store=True)
    comalitive_mortality_culled = fields.Float(string="Cumulative Culled Cause Mortality", compute="_compute_cumalitive_mortality_culled", store=True) 
    comalitive_mortality_vaccine = fields.Float(string="Cumulative Vaccine Reaction Mortality", compute="_compute_cumalitive_mortality_vaccine", store=True)
    comalitive_mortality_prolapse = fields.Float(string="Cumulative Prolapse Mortality", compute="_compute_cumalitive_mortality_prolapse", store=True)
    comalitive_mortality_heat_stress = fields.Float(string="Cumulative Heat Stress Mortality", compute="_compute_cumalitive_mortality_heat_stress", store=True)
    comalitive_mortality_mechanical = fields.Float(string="Cumulative Mechanical Mortality", compute="_compute_cumalitive_mortality_mechanical", store=True)
    comalitive_mortality_injury = fields.Float(string="Cumulative Injury Mortality", compute="_compute_cumalitive_mortality_injury", store=True)
    comalitive_mortality_other = fields.Float(string="Cumulative Other Cause Mortality", compute="_compute_cumalitive_mortality_other", store=True) 

    ### individual cause percentage fields can be added here if needed ###
    
    cause_percentage_normal = fields.Float(string="Normal Cause Percentage", compute="_compute_cause_percentage_normal", store=True)
    cause_percentage_culled = fields.Float(string="Culled Cause Percentage", compute="_compute_cause_percentage_culled", store=True)
    cause_percentage_vaccine = fields.Float(string="Vaccine Reaction Percentage", compute="_compute_cause_percentage_vaccine", store=True)
    cause_percentage_prolapse = fields.Float(string="Prolapse Percentage", compute="_compute_cause_percentage_prolapse", store=True)
    cause_percentage_heat_stress = fields.Float(string="Heat Stress Percentage", compute="_compute_cause_percentage_heat_stress", store=True)
    cause_percentage_mechanical = fields.Float(string="Mechanical Percentage", compute="_compute_cause_percentage_mechanical", store=True)
    cause_percentage_injury = fields.Float(string="Injury Percentage", compute="_compute_cause_percentage_injury", store=True)
    cause_percentage_other = fields.Float(string="Other Cause Percentage", compute="_compute_cause_percentage_other", store=True)
    ##### type wise total mortality 

    ### Compute Methods for cumalitive mortality ###
    @api.depends('breakdown_ids.count', 'date', 'flock_id')
    def _compute_cumalitive_mortality_normal(self):
        for rec in self:
            if rec.flock_id:
                previous_records = self.env['farm.mortality.details'].search([
                    ('flock_id', '=', rec.flock_id.id),
                    ('date', '<=', rec.date)
                ])
                normal_count = sum(previous_records.mapped('breakdown_ids').filtered(lambda b: b.type == 'normal').mapped('count'))
                rec.comalitive_mortality_normal = normal_count
            else:
                rec.comalitive_mortality_normal = 0
    @api.depends('breakdown_ids.count', 'date', 'flock_id')
    def _compute_cumalitive_mortality_culled(self):
        for rec in self:
            if rec.flock_id:
                previous_records = self.env['farm.mortality.details'].search([
                    ('flock_id', '=', rec.flock_id.id),
                    ('date', '<=', rec.date)
                ])
                culled_count = sum(previous_records.mapped('breakdown_ids').filtered(lambda b: b.type == 'culled').mapped('count'))
                rec.comalitive_mortality_culled = culled_count
            else:
                rec.comalitive_mortality_culled = 0
    @api.depends('breakdown_ids.count', 'date', 'flock_id')
    def _compute_cumalitive_mortality_vaccine(self):
        for rec in self:
            if rec.flock_id:
                previous_records = self.env['farm.mortality.details'].search([
                    ('flock_id', '=', rec.flock_id.id),
                    ('date', '<=', rec.date)
                ])
                vaccine_count = sum(previous_records.mapped('breakdown_ids').filtered(lambda b: b.type == 'vaccine').mapped('count'))
                rec.comalitive_mortality_vaccine = vaccine_count
            else:
                rec.comalitive_mortality_vaccine = 0
    @api.depends('breakdown_ids.count', 'date', 'flock_id')
    def _compute_cumalitive_mortality_prolapse(self):
        for rec in self:
            if rec.flock_id:
                previous_records = self.env['farm.mortality.details'].search([
                    ('flock_id', '=', rec.flock_id.id),
                    ('date', '<=', rec.date)
                ])
                prolapse_count = sum(previous_records.mapped('breakdown_ids').filtered(lambda b: b.type == 'prolapse').mapped('count'))
                rec.comalitive_mortality_prolapse = prolapse_count
            else:
                rec.comalitive_mortality_prolapse = 0
    @api.depends('breakdown_ids.count', 'date', 'flock_id')
    def _compute_cumalitive_mortality_heat_stress(self):
        for rec in self:
            if rec.flock_id:
                previous_records = self.env['farm.mortality.details'].search([
                    ('flock_id', '=', rec.flock_id.id),
                    ('date', '<=', rec.date)
                ])
                heat_stress_count = sum(previous_records.mapped('breakdown_ids').filtered(lambda b: b.type == 'heat_stress').mapped('count'))
                rec.comalitive_mortality_heat_stress = heat_stress_count
            else:
                rec.comalitive_mortality_heat_stress = 0
    @api.depends('breakdown_ids.count', 'date', 'flock_id')
    def _compute_cumalitive_mortality_mechanical(self):
        for rec in self:
            if rec.flock_id:
                previous_records = self.env['farm.mortality.details'].search([
                    ('flock_id', '=', rec.flock_id.id),
                    ('date', '<=', rec.date)
                ])
                mechanical_count = sum(previous_records.mapped('breakdown_ids').filtered(lambda b: b.type == 'mechanical').mapped('count'))
                rec.comalitive_mortality_mechanical = mechanical_count
            else:
                rec.comalitive_mortality_mechanical = 0
    @api.depends('breakdown_ids.count', 'date', 'flock_id')
    def _compute_cumalitive_mortality_injury(self):
        for rec in self:
            if rec.flock_id:
                previous_records = self.env['farm.mortality.details'].search([
                    ('flock_id', '=', rec.flock_id.id),
                    ('date', '<=', rec.date)
                ])
                injury_count = sum(previous_records.mapped('breakdown_ids').filtered(lambda b: b.type == 'injury').mapped('count'))
                rec.comalitive_mortality_injury = injury_count
            else:
                rec.comalitive_mortality_injury = 0
    @api.depends('breakdown_ids.count', 'date', 'flock_id')
    def _compute_cumalitive_mortality_other(self):
        for rec in self:
            if rec.flock_id:
                previous_records = self.env['farm.mortality.details'].search([
                    ('flock_id', '=', rec.flock_id.id),
                    ('date', '<=', rec.date)
                ])
                other_count = sum(previous_records.mapped('breakdown_ids').filtered(lambda b: b.type == 'other').mapped('count'))
                rec.comalitive_mortality_other = other_count
            else:
                rec.comalitive_mortality_other = 0 

   
    @api.depends('breakdown_ids.count', 'total_mortality')
    def _compute_cause_percentage_normal(self):
        for rec in self:
            normal_count = sum(rec.breakdown_ids.filtered(lambda b: b.type == 'normal').mapped('count'))
            if rec.total_mortality > 0:
                rec.cause_percentage_normal = (normal_count / rec.total_mortality) * 100
            else:
                rec.cause_percentage_normal = 0 


    @api.depends('breakdown_ids.count', 'total_mortality')
    def _compute_cause_percentage_culled(self):
        for rec in self:
            culled_count = sum(rec.breakdown_ids.filtered(lambda b: b.type == 'culled').mapped('count'))
            if rec.total_mortality > 0:
                rec.cause_percentage_culled = (culled_count / rec.total_mortality) * 100
            else:
                rec.cause_percentage_culled = 0

    @api.depends('breakdown_ids.count', 'total_mortality')
    def _compute_cause_percentage_vaccine(self):    
        for rec in self:
            vaccine_count = sum(rec.breakdown_ids.filtered(lambda b: b.type == 'vaccine').mapped('count'))
            if rec.total_mortality > 0:
                rec.cause_percentage_vaccine = (vaccine_count / rec.total_mortality) * 100
            else:
                rec.cause_percentage_vaccine = 0
    @api.depends('breakdown_ids.count', 'total_mortality')
    def _compute_cause_percentage_prolapse(self):
        for rec in self:
            prolapse_count = sum(rec.breakdown_ids.filtered(lambda b: b.type == 'prolapse').mapped('count'))
            if rec.total_mortality > 0:
                rec.cause_percentage_prolapse = (prolapse_count / rec.total_mortality) * 100
            else:
                rec.cause_percentage_prolapse = 0
    @api.depends('breakdown_ids.count', 'total_mortality')
    def _compute_cause_percentage_heat_stress(self):
        for rec in self:
            heat_stress_count = sum(rec.breakdown_ids.filtered(lambda b: b.type == 'heat_stress').mapped('count'))
            if rec.total_mortality > 0:
                rec.cause_percentage_heat_stress = (heat_stress_count / rec.total_mortality) * 100
            else:
                rec.cause_percentage_heat_stress = 0
    @api.depends('breakdown_ids.count', 'total_mortality')
    def _compute_cause_percentage_mechanical(self):
        for rec in self:
            mechanical_count = sum(rec.breakdown_ids.filtered(lambda b: b.type == 'mechanical').mapped('count'))
            if rec.total_mortality > 0:
                rec.cause_percentage_mechanical = (mechanical_count / rec.total_mortality) * 100
            else:
                rec.cause_percentage_mechanical = 0
    @api.depends('breakdown_ids.count', 'total_mortality')
    def _compute_cause_percentage_injury(self):
        for rec in self:
            injury_count = sum(rec.breakdown_ids.filtered(lambda b: b.type == 'injury').mapped('count'))
            if rec.total_mortality > 0:
                rec.cause_percentage_injury = (injury_count / rec.total_mortality) * 100
            else:
                rec.cause_percentage_injury = 0
    @api.depends('breakdown_ids.count', 'total_mortality')
    def _compute_cause_percentage_other(self):
        for rec in self:
            other_count = sum(rec.breakdown_ids.filtered(lambda b: b.type == 'other').mapped('count'))
            if rec.total_mortality > 0:
                rec.cause_percentage_other = (other_count / rec.total_mortality) * 100
            else:
                rec.cause_percentage_other = 0
    
    @api.depends('total_mortality', 'flock_opening_bird')
    def _compute_overall_mortality_percentage(self):
        for rec in self:
            if rec.flock_opening_bird > 0:
                rec.today_overall_mortality_percentage = (rec.total_mortality / rec.flock_opening_bird) * 100
            else:
                rec.today_overall_mortality_percentage = 0

    @api.depends('total_mortality', 'date', 'flock_id')
    def _compute_cumaletive_mortality(self):
        for rec in self:
            if rec.flock_id:
                previous_records = self.env['farm.mortality.details'].search([
                    ('flock_id', '=', rec.flock_id.id),
                    ('date', '<=', rec.date)
                ])
                rec.cumaletive_mortality = sum(previous_records.mapped('total_mortality'))

            else:
                rec.cumaletive_mortality = 0


    @api.depends('breakdown_ids.count')
    def _compute_total_mortality(self):
        for record in self:
            record.total_mortality = sum(record.breakdown_ids.mapped('count'))
            record.normal_cause_mortality = sum(
                record.breakdown_ids.filtered(lambda b: b.type == 'normal').mapped('count')
            )
            record.culled_cause_mortality = sum(
                record.breakdown_ids.filtered(lambda b: b.type == 'culled').mapped('count')
            )
            record.vaccine_reaction_mortality = sum(
                record.breakdown_ids.filtered(lambda b: b.type == 'vaccine').mapped('count')
            )
            record.prolapse_mortality = sum(
                record.breakdown_ids.filtered(lambda b: b.type == 'prolapse').mapped('count')
            )
            record.heat_stress_mortality = sum(
                record.breakdown_ids.filtered(lambda b: b.type == 'heat_stress').mapped('count')
            )
            record.mechanical_mortality = sum(
                record.breakdown_ids.filtered(lambda b: b.type == 'mechanical').mapped('count')
            )
            record.injury_mortality = sum(
                record.breakdown_ids.filtered(lambda b: b.type == 'injury').mapped('count')
            )
            record.other_cause_mortality = sum(
                record.breakdown_ids.filtered(lambda b: b.type == 'other').mapped('count')
            )
          
            
    @api.depends("breakdown_ids.count", "state")
    def _compute_new_added_mortality(self):
        for rec in self:
            
            if rec.state == "done":
                rec.new_added_ = 0
                rec.normal_cause_mortality_new = 0
                rec.culled_cause_mortality_new = 0
                rec.vaccine_reaction_mortality_new = 0
                rec.prolapse_mortality_new = 0
                rec.heat_stress_mortality_new = 0
                rec.mechanical_mortality_new = 0
                rec.injury_mortality_new = 0
                rec.other_cause_mortality_new = 0
                continue

            draft_lines = rec.breakdown_ids.filtered(lambda b: b.state == 'draft')
            rec.new_added_ = sum(draft_lines.mapped('count'))
            rec.normal_cause_mortality_new = sum(
                draft_lines.filtered(lambda b: b.type == 'normal').mapped('count')
            )
            rec.culled_cause_mortality_new = sum(
                draft_lines.filtered(lambda b: b.type == 'culled').mapped('count')
            )
            rec.vaccine_reaction_mortality_new = sum(
                draft_lines.filtered(lambda b: b.type == 'vaccine').mapped('count')
            )
            rec.prolapse_mortality_new = sum(
                draft_lines.filtered(lambda b: b.type == 'prolapse').mapped('count')
            )
            rec.heat_stress_mortality_new = sum(
                draft_lines.filtered(lambda b: b.type == 'heat_stress').mapped('count')
            )
            rec.mechanical_mortality_new = sum(
                draft_lines.filtered(lambda b: b.type == 'mechanical').mapped('count')
            )
            rec.injury_mortality_new = sum(
                draft_lines.filtered(lambda b: b.type == 'injury').mapped('count')
            )
            rec.other_cause_mortality_new = sum(
                draft_lines.filtered(lambda b: b.type == 'other').mapped('count')
            )


    @api.model
    def create(self, vals):

        # record_date = vals.get('date') or fields.Date.context_today(self)
        # flock_id = vals.get('flock_id')

        # if record_date and flock_id:
        #     count = self.search_count([
        #         ('date', '=', record_date),
        #         ('flock_id', '=', flock_id)
        #     ])

        #     if count >= 2:
        #         raise UserError(
        #             f"For this flock on {record_date}, only 2 entries are allowed. "
        #             "You cannot create more than 2 records."
        #         )
            
        if vals.get('name', 'New') == 'New':
            last_record = self.search([('name', 'like', 'Daily/M/D/%')], 
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
            vals['name'] = f"M/D/{today_str}"

        return super(MortalityDetails, self).create(vals)
    

    @api.onchange('flock_id')
    def _onchange_get_flock_data(self):
        if self.flock_id:
            self.flock_opening_bird = self.flock_id.opening_bird_count
            self.flock_ending_date = self.flock_id.end_date
            self.flock_starting_date = self.flock_id.start_date
            self.current_birds = self.flock_id.total_qty
            self.age_in_days = self.flock_id.current_age_in_days
            self.current_age_display = self.flock_id.current_age_display

    def action_draft(self):

        if self.state =='draft':
            return
        self.state = 'draft'
       

    def action_confirm(self):
        
        if self.state =="done":
            return 
        else:
            for record in self:
                if not record.flock_id:
                    raise UserError("Flock not assigned!")
                product = record.flock_id.product_id
                if not product:
                    raise UserError("No bird product linked with this flock!")
                if record.new_added_ <= 0:
                    record.state = "done"
                    record.message_post(body="Mortality is zero. No birds removed.")
                    continue 
                
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', product.id),
                    ('location_id.usage', '=', 'internal'),
                    ('quantity', '>', 0)
                ], order='quantity desc')
                total_available = sum(q.quantity for q in quants)
                if total_available < record.new_added_:
                    raise UserError(
                        f"Not enough birds in stock to remove mortality!\nAvailable: {total_available}, Required: {record.total_mortality}"
                    )
                qty_to_remove = record.new_added_
                for quant in quants:
                    if qty_to_remove <0:
                        break
                    remove_qty = min(quant.quantity, qty_to_remove)
                    scrap = self.env['stock.scrap'].create({
                        'product_id': product.id,
                        'scrap_qty': remove_qty,
                        'location_id': quant.location_id.id,
                        'company_id': self.env.company.id,
                        'origin': f"Mortality Record {record.name} - Flock {record.flock_id.name}"
                    })
                    scrap.action_validate()
                qty_to_remove -= remove_qty
                record.current_birds = max(record.flock_opening_bird - record.new_added_, 0)
                record.message_post(body=f"Removed {record.new_added_} birds from flock due to mortality.")
                _logger.info("Mortality removed for flock %s: %s birds", record.flock_id.name, record.new_added_)
                self.current_birds = self.flock_id.total_qty
                if record.breakdown_ids:
                    record.breakdown_ids.write({'state': 'done'})
        self.state = 'done'
    

class MortalityBreakdown(models.Model):
    _name = "farm.mortality.breakdown"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    

    

    mortality_id = fields.Many2one(
        'farm.mortality.details', 
        string="Mortality Reference", 
        ondelete="cascade"
    )
    type = fields.Selection([
        ('normal', 'Normal'),
        ('culled', 'Culled'),
        ('vaccine', 'Vaccine Reaction'),
        ('prolapse', 'Prolapse'),
        ('heat_stress', 'Heat Stress'),
        ('mechanical', 'Mechanical'),
        ('injury', 'Injury'),
        ('other', 'Other'),
    ], string="Cause", required=True, tracking=True)

    count = fields.Integer(string="Quantity", required=True, default=0, tracking=True,)
    date = fields.Date(string="Date", required=True, default=fields.Date.today)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
    ], default='draft', tracking=True)

      
    def action_done(self):
        for line in self:
            line.state = 'done'
        self.state =="done"

    def unlink(self):
        """Prevent deletion if record is in 'done' state."""
        for record in self:
            if record.state == 'done':
                raise UserError("You cannot delete a mortality breakdown marked as Done!")
        return super().unlink()
    

    def _format_plain_message(self, action, changes=None, previous_state=None):
        
        msg_lines = [
            f"{action}",
            f"Updated By      : {self.env.user.name}",
            f"Flock           : {self.mortality_id.flock_id.name if self.mortality_id.flock_id else 'N/A'}",
            f"Date of Record  : {self.date or 'N/A'}",
            f"Cause           : {self.type or 'N/A'}",
            f"Quantity        : {self.count or 0}",
        ]
        if previous_state:
            msg_lines.append(f"Previous State  : {previous_state}")
        if changes:
            msg_lines.append(f"Changes         : {'; '.join(changes)}")
        return "\n".join(msg_lines)

    def write(self, vals):
        tracked_fields = ['type', 'count', 'date', 'state']
        messages_by_mortality = {}
        for line in self:
            changes = []
            previous_state = line.state
            for field in tracked_fields:
                if field in vals:
                    old_val = line[field]
                    new_val = vals[field]

                    if isinstance(line._fields[field], fields.Many2one):
                        comodel = line._fields[field].comodel_name
                        new_val_display = self.env[comodel].browse(new_val).name if new_val else False
                        old_val_display = old_val.name if old_val else False
                    else:
                        new_val_display = new_val
                        old_val_display = old_val

                    if old_val_display != new_val_display:
                        changes.append(f"{field.replace('_', ' ').title()}: '{old_val_display}' → '{new_val_display}'")

            res = super(MortalityBreakdown, self).write(vals)

            if changes and line.mortality_id:
                msg = line._format_plain_message(
                    action="Mortality Breakdown Updated",
                    changes=changes,
                    previous_state=previous_state
                )
                line.mortality_id.message_post(body=msg)

        return res

    @api.model
    def create(self, vals):
        record = super(MortalityBreakdown, self).create(vals)
        if record.mortality_id:
            msg = record._format_plain_message(
                action="New Mortality Breakdown Created"
            )
            record.mortality_id.message_post(body=msg)
        return record

    def unlink(self):
        for record in self:
            if record.state == 'done':
                raise UserError("You cannot delete a mortality breakdown marked as Done!")
            if record.mortality_id:
                msg = record._format_plain_message(
                    action="Mortality Breakdown Deleted"
                )
                record.mortality_id.message_post(body=msg)
        return super(MortalityBreakdown, self).unlink()
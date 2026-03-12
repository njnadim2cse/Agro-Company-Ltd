from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import UserError
import logging

class VentilationFarmDetails(models.Model):
    _name = "ventilation.farm.details"
    _description = "Ventilation Farm Details"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'reference'
    

    

    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Confirmed')
    ], string="Status", default='draft', tracking=True)

    reference = fields.Char(string="Reference", default="New", readonly=True, tracking=True)
    created_by = fields.Many2one(
        'res.users', string="Responsible Person",
        default=lambda self: self.env.user, readonly=True
    )

    name = fields.Char(string="Farm Name", tracking=True)

    target_temperature = fields.Float(
        string="Target Temp(°C)",
        tracking=True,
        default=None,
        digits=(16, 2),
    )

    description = fields.Html(string="Farm Description", tracking=True)

    flock_id = fields.Many2one(
        "farm.layer.flock", string="Flock Name",
        required=True, ondelete="cascade"
    )

    farm_ventilation_level_line_ids = fields.One2many(
        'farm.ventilation.level.line',
        'ventilation_farm_id',
        string="Ventilation Levels"
    )

    date = fields.Date(string="Date", default=fields.Date.today, tracking=True)

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

    def action_confirm(self):
        if self.state == "done":
            return
        if self.farm_ventilation_level_line_ids:
            self.farm_ventilation_level_line_ids.write({'state': 'done'})
        self.state = "done"

    def action_draft(self):
        if self.state == "draft":
            return
        self.state = 'draft'

    @api.model
    def create(self, vals):
        flock_id = vals.get('flock_id')
        target_temp = vals.get('target_temperature')

        if flock_id and target_temp:
            existing = self.search([
                ('flock_id', '=', flock_id),
                ('target_temperature', '=', target_temp)
            ], limit=1)
            if existing:
                raise UserError("This target temperature already exists for this flock!")

        if vals.get('reference', 'New') == 'New':
            today_str = datetime.today().strftime('%d-%m-%Y')

            last_record = self.search(
                [('reference', 'like', f'Fv/{today_str}/%')],
                order='id desc', limit=1
            )

            if last_record:
                last_seq = int(last_record.reference.split('/')[-1])
                next_seq = str(last_seq + 1).zfill(5)
            else:
                next_seq = '00001'

            vals['reference'] = f"Fv/{next_seq}"

        return super(VentilationFarmDetails, self).create(vals)


class FarmVentilationLevelLine(models.Model):
    _name = "farm.ventilation.level.line"
    _description = "Farm Ventilation Level Line"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    level_id = fields.Many2one(
        'ventilation.level',
        string="Ventilation Level",
        tracking=True,
        ondelete='cascade'
    )

    max_temperature = fields.Float(string="Max Temp(°C)", tracking=True)
    min_temperature = fields.Float(string="Min Temp(°C)", tracking=True)

    fan_ids = fields.Many2many(
        'ventilation.fans',
        'fan_level_rel',
        'level_line_id',
        'fan_id',
        string="Fans",
        tracking=True
    )

    ventilation_farm_id = fields.Many2one(
        'ventilation.farm.details',
        string="Ventilation Farm",
        tracking=True,
        ondelete='cascade'
    )

    state = fields.Selection(
        [('draft', 'Draft'), ('done', 'Confirmed')],
        string="Status", default='draft', tracking=True
    )

    target_temperature = fields.Float(string="Target Temperature")

    fan_count = fields.Integer(
        string="Fan Count",
        compute="_compute_fan_count",
        store=False
    )

    # Curtain selection generation
    L_values = ['1/2', '1/3', '0']
    R_values = ['1/2', '1/3', '0']
    F_values = ['0']

    LRF_combinations = []

    for l in L_values:
        LRF_combinations.append((f'L-{l}', f'L-{l}'))

    for r in R_values:
        LRF_combinations.append((f'R-{r}', f'R-{r}'))

    for f in F_values:
        LRF_combinations.append((f'F-{f}', f'F-{f}'))

    for l in L_values:
        for r in R_values:
            LRF_combinations.append((f'L-{l}_R-{r}', f'L-{l} / R-{r}'))

    for l in L_values:
        for r in R_values:
            for f in F_values:
                LRF_combinations.append((f'L-{l}_R-{r}_F-{f}', f'L-{l} / R-{r} / F-{f}'))

    LRF_value = fields.Selection(
        LRF_combinations,
        string="Curtain Close",
        tracking=True
    )

    @api.constrains('target_temperature')
    def _check_target_temperature(self):
        if self.target_temperature is not None and self.target_temperature <= 0.0:
            raise UserError("Target Temperature must be greater than 0. Zero or negative values are not allowed.")

    # -----------------------------------------------------
    #   FIXED: CUMULATIVE FAN COUNT
    # -----------------------------------------------------
    @api.depends('fan_ids',
                 'ventilation_farm_id.farm_ventilation_level_line_ids.fan_ids')
    def _compute_fan_count(self):
        for rec in self:
            cumulative_count = 0

            if rec.ventilation_farm_id and rec.level_id:

                all_lines = rec.ventilation_farm_id.farm_ventilation_level_line_ids

                # Requires sequence in ventilation.level
                sorted_lines = all_lines.sorted(lambda l: l.level_id.sequence)

                for line in sorted_lines:
                    cumulative_count += len(line.fan_ids)
                    if line.id == rec.id:
                        break

            rec.fan_count = cumulative_count

    def action_confirm(self):
        if self.state == "done":
            return
        self.state = 'done'

    def action_draft(self):
        if self.state == "draft":
            return
        self.state = 'draft'

    @api.onchange('level_id')
    def _onchange_target_temperature(self):
        if self.ventilation_farm_id:
            self.target_temperature = self.ventilation_farm_id.target_temperature

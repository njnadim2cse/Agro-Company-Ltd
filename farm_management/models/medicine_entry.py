from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime


class AddMedicineByLiveTemperature(models.Model):
    _name = "add.medicine.by.live.temperature"
    _description = "Temperature-based Medicine Record"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "create_date desc"
 

    selection_type = fields.Selection([
        ('age', 'Age'),
        ('temp', 'Temperature'),
        ('age_temp', 'Age & Temperature'),
    ], string="Selection Type", required=True, default='temp', tracking=True)
    min_age = fields.Integer(string="Min Age (Days)")
    max_age = fields.Integer(string="Max Age (Days)")
    min_temp = fields.Float(string="Min Temperature (°C)")
    max_temp = fields.Float(string="Max Temperature (°C)")
    medicine_line_ids = fields.One2many(
        'add.medicine.temperature.line', 'temperature_id', string="Medicine Lines"
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('done', 'Done')],
        string="Status", default='draft', tracking=True
    )
    name = fields.Char(string="Reference", default="New", readonly=True)
    date = fields.Datetime(string="Date", default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', string="Responsible", default=lambda self: self.env.user)
    note_html = fields.Html(string='HTML Description', sanitize_attributes=False)
    @api.onchange('selection_type')
    def _onchange_selection_type(self):
        for record in self:
            if record.medicine_line_ids:
                for line in record.medicine_line_ids:
                    line.selection_type = record.selection_type

    @api.constrains('min_age', 'max_age', 'min_temp', 'max_temp')
    def _check_ranges(self):
        for record in self:
            if record.selection_type in ['age', 'age_temp']:
                if record.min_age and record.max_age and record.min_age >= record.max_age:
                    raise ValidationError("Minimum age must be less than maximum age.")
            if record.selection_type in ['temp', 'age_temp']:
                if record.min_temp and record.max_temp and record.min_temp >= record.max_temp:
                    raise ValidationError("Minimum temperature must be less than maximum temperature.")
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            today_str = datetime.today().strftime('%d-%m-%Y')
            last_record = self.search(
                [('name', 'like', f'MED/{today_str}/%')],
                order='id desc', limit=1
            )
            if last_record:
                last_seq = int(last_record.name.split('/')[-1])
                next_seq = str(last_seq + 1).zfill(5)
            else:
                next_seq = '00001'
            vals['name'] = f"MED/{today_str}/{next_seq}"
        return super(AddMedicineByLiveTemperature, self).create(vals)

    def action_draft(self):
        if self.state == "draft":
            return
        self.state = 'draft'

    def action_confirm(self):
        """Set parent and all child lines to done"""
        for record in self:
            record.state = 'done'
            if record.medicine_line_ids:
                record.medicine_line_ids.write({'state': 'done'})

    def get_selection_type_display(self):
        """Get display name for selection type"""
        selection_dict = dict(self._fields['selection_type'].selection)
        return selection_dict.get(self.selection_type, '')


class AddMedicineTemperatureLine(models.Model):
    _name = "add.medicine.temperature.line"
    _description = "Medicine Line for Temperature"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    temperature_id = fields.Many2one('add.medicine.by.live.temperature', string="Temperature Record")
    selection_type = fields.Selection(related='temperature_id.selection_type', string="Selection Type", store=True,tracking=True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], string="Status", default='draft', tracking=True)
    product_id = fields.Many2one(
        'product.product',
        string="Medicine Name",
        domain="[('is_medicine', '=', True)]",
        tracking=True,
        required=True
    )
    user_id = fields.Many2one("res.users", string="Suggested By", default=lambda self: self.env.user, tracking=True)
    dose_per_water_liter = fields.Float(string="Per Water Liter", tracking=True,required=True)
    selection_display = fields.Char(string="Selection Criteria", compute='_compute_selection_display',tracking=True)
    uom_id = fields.Many2one('uom.uom', string="Unit of Measure", readonly=True)


    @api.depends('temperature_id.selection_type', 'temperature_id.min_age', 'temperature_id.max_age',
                 'temperature_id.min_temp', 'temperature_id.max_temp')
    def _compute_selection_display(self):
        """Compute display string for selection criteria"""
        for record in self:
            if not record.temperature_id:
                record.selection_display = ""
                continue
            temp = record.temperature_id
            parts = []
            if temp.selection_type in ['age', 'age_temp']:
                if temp.min_age and temp.max_age:
                    parts.append(f"Age: {temp.min_age}-{temp.max_age} days")
            if temp.selection_type in ['temp', 'age_temp']:
                if temp.min_temp and temp.max_temp:
                    parts.append(f"Temp: {temp.min_temp}-{temp.max_temp}°C")
            record.selection_display = " | ".join(parts)

    @api.constrains('dose_per_water_liter', 'product_id', 'temperature_id')
    def _check_positive_values(self):
        for record in self:
            if record.dose_per_water_liter <= 0:
                raise ValidationError("Dose Per Water Liter must be greater than zero.")
            duplicate = self.search([
                ('id', '!=', record.id),
                ('temperature_id', '=', record.temperature_id.id),
                ('product_id', '=', record.product_id.id)
            ])
            if duplicate:
                raise ValidationError(f"The medicine '{record.product_id.name}' is already added for this temperature record.")

    def action_done(self):
        if self.state == "done":
            return
        self.state = 'done'

    def action_draft(self):
        if self.state == "draft":
            return
        self.state = 'draft'

    @api.onchange('product_id')
    def get_uom(self):
  
        for record in self:
            if record.product_id:
                record.uom_id = record.product_id.uom_id
  



class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    is_medicine = fields.Boolean(string="Is Medicine")
    egg_type = fields.Selection([
        ('layer', 'Layer'),
        ('broiler', 'Broiler'),
        ('duck', 'Duck'),
    ], string="Egg Type")

    medicine_type = fields.Selection([
        ('general', 'General'),
        ('age_specific', 'Age Specific'),
        ('temp_specific', 'Temperature Specific'),
        ('all', 'All Types')
    ], string="Medicine Type", default='general')
    is_feed = fields.Boolean(string="Is Feed")

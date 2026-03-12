from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class VentilationFans(models.Model):

    """
    Model to store ventilation fan details.
    Features Key:"Ventilation Fans Model"
    Related Model: Ventilation level line
    Purpose: Store details of ventilation fans used in farm ventilation systems.
    -name : Reference name of the ventilation fan.
    -date : Date of installation or record. 
    """
    _name = "ventilation.fans"
    _description = "Ventilation Fans Details"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    

    

    reference = fields.Char(string="Reference", default="New", readonly=True, tracking=True)
    name = fields.Char(string="Fan ID", tracking=True)
    date = fields.Date(string="Date", default=fields.Date.context_today, tracking=True)
    created_by = fields.Many2one('res.users', string="Responsible Person", default=lambda self: self.env.user, readonly=True)
    description = fields.Text(string="Description", tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Confirmed')
    ], string="Status", default='draft', tracking=True)

    # Many2many relation
    
    ventilation_level_line_ids = fields.Many2many(
        'farm.ventilation.level.line',
        'fan_level_rel',          
        'fan_id',                
        'level_line_id',          
        string="Associated Ventilation Levels",
        tracking=True
    )

    def action_draft(self):
        if self.state == "draft":
            return
        self.state = 'draft'

    def action_confirm(self):
        if self.state == "done":
            return
        self.state = 'done'

    @api.model
    def create(self, vals):
        if vals.get('reference', 'New') == 'New':
            today_str = datetime.today().strftime('%d-%m-%Y')
            last_record = self.search(
                [('reference', 'like', f'VF/{today_str}/%')],
                order='id desc', limit=1
            )
            if last_record:
                last_seq = int(last_record.reference.split('/')[-1])
                next_seq = str(last_seq + 1).zfill(5)
            else:
                next_seq = '00001'
            vals['reference'] = f"VF/{today_str}/{next_seq}"
        return super(VentilationFans, self).create(vals)
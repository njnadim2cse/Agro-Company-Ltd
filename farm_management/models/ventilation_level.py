from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class VentilationLevel(models.Model):
    """
    Model to store ventilation level details.
    """
    _name = "ventilation.level"
    _description = "Ventilation Level Details"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
  
    reference = fields.Char(string="Reference", tracking=True)
    name = fields.Char(string="Level Name", required=True, tracking=True)
    description = fields.Text(string="Description", tracking=True)
    created_by = fields.Many2one('res.users', string="Responsible Person", default=lambda self: self.env.user, readonly=True)
    sequence = fields.Integer(string="Sequence", default=10)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Confirmed')
    ], string="Status", default='draft', tracking=True)
    farm_ventilation_level_line_ids = fields.One2many(
        'farm.ventilation.level.line',
        'level_id',
        string="Associated Farm Levels",
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
                [('reference', 'like', f'VL/{today_str}/%')],
                order='id desc', limit=1
            )
            if last_record:
                last_seq = int(last_record.reference.split('/')[-1])
                next_seq = str(last_seq + 1).zfill(5)
            else:
                next_seq = '00001'
            vals['reference'] = f"VL/{today_str}/{next_seq}"
        return super(VentilationLevel, self).create(vals)
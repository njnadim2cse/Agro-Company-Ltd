from odoo import models, fields, api
from odoo.exceptions import UserError

class GatePassApprovalWizard(models.TransientModel):
    _name = 'gatepass.approval.wizard'
    _description = 'Gate Pass Approval Wizard'
    
    gatepass_id = fields.Many2one('gatepass.gatepass', string='Gate Pass', required=True)
    approval_notes = fields.Text(string='Approval Notes')
    
    def action_approve(self):
        self.gatepass_id.action_approve()
        if self.approval_notes:
            self.gatepass_id.message_post(body=f'Approval Notes: {self.approval_notes}')
        return {'type': 'ir.actions.act_window_close'}
    
    def action_reject(self):
        self.gatepass_id.action_reject()
        if self.approval_notes:
            self.gatepass_id.message_post(body=f'Rejection Notes: {self.approval_notes}')
        return {'type': 'ir.actions.act_window_close'}
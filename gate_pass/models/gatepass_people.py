from odoo import models, fields, api

class GatePassPeople(models.Model):
    _name = 'gatepass.people'
    _description = 'People details for gate pass'
    
    gatepass_id = fields.Many2one('gatepass.gatepass', string='Gate Pass', required=True, ondelete='cascade')
    name = fields.Char(string='Name', required=True)
    id_type = fields.Selection([
        ('nid', 'National ID'),
        ('passport', 'Passport'),
        ('driving_license', 'Driving License'),
        ('company_id', 'Company ID')
    ], string='ID Type')
    id_number = fields.Char(string='ID Number')
    mobile = fields.Char(string='Mobile Number')
    
    # Compute vehicle type context for UI
    request_type = fields.Selection(related='gatepass_id.request_type', string='Request Type', store=False)
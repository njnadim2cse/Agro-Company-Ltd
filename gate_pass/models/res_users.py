from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'
    
    is_gate_staff = fields.Boolean(string='Is Gate Staff', default=False)
    is_head_office = fields.Boolean(string='Is Head Office', default=False)
    is_security_admin = fields.Boolean(string='Is Security Admin', default=False)
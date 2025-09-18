from odoo import models, fields, api
from odoo.exceptions import AccessError

class GateConfig(models.Model):
    _name = 'gatepass.gate.config'
    _description = 'Gate Configuration'
    _order = 'gate_number'
    
    gate_number = fields.Char(string='Gate Number', required=True)
    name = fields.Char(string='Gate Name', required=True)
    location = fields.Selection([
        ('north', 'North'),
        ('south', 'South'), 
        ('east', 'East'),
        ('west', 'West')
    ], string='Gate Location', required=True)

    gate_incharge_ids = fields.Many2many(
        'hr.employee', string='Gate Incharge/Staff'
    )

    active = fields.Boolean(string='Active', default=True)
    
    _sql_constraints = [
        ('gate_number_unique', 'unique(gate_number)', 'Gate number must be unique!'),
    ]
    
    def name_get(self):
        result = []
        for gate in self:
            name = f"{gate.gate_number} - {gate.name}"
            result.append((gate.id, name))
        return result
    
    @api.model
    def check_config_access(self):
        """Check if user has access to configuration"""
        if not (self.env.user.is_head_office or self.env.user.is_security_admin):
            raise AccessError(("You don't have access to configuration settings."))
    
    def write(self, vals):
        self.check_config_access()
        return super().write(vals)
    
    def unlink(self):
        self.check_config_access()
        return super().unlink()
    
    @api.model
    def create(self, vals):
        self.check_config_access()
        return super().create(vals)


class PurposeConfig(models.Model):
    _name = 'gatepass.purpose.config'
    _description = 'Purpose Configuration'
    _order = 'name'
    
    name = fields.Char(string='Purpose Name', required=True)
    assign_for = fields.Selection([
        ('vehicle', 'Vehicle'),
        ('visitor', 'Visitor'),
        ('both', 'Both')
    ], string='Type', required=True, default='both')
    active = fields.Boolean(string='Active', default=True)
    
    _sql_constraints = [
        ('purpose_name_unique', 'unique(name)', 'Purpose name must be unique!'),
    ]
    
    @api.model
    def check_config_access(self):
        """Check if user has access to configuration"""
        if not (self.env.user.is_head_office or self.env.user.is_security_admin):
            raise AccessError(("You don't have access to configuration settings."))
    
    def write(self, vals):
        self.check_config_access()
        return super().write(vals)
    
    def unlink(self):
        self.check_config_access()
        return super().unlink()
    
    @api.model
    def create(self, vals):
        self.check_config_access()
        return super().create(vals)

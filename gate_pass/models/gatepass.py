from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError
import logging

_logger = logging.getLogger(__name__)

class GatePass(models.Model):
    _name = 'gatepass.gatepass'
    _description = 'Gate Pass Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'), tracking=True)
    request_type = fields.Selection([
        ('vehicle', 'Vehicle'),
        ('visitor', 'Visitor')
    ], string='Request Type', required=True, default='vehicle', tracking=True)
    
    # Common fields
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent for Approval'),
        ('approved', 'Approved'),
        ('in', 'In'),
        ('out', 'Out'),
        ('completed', 'Completed')
    ], string='Status', default='draft', tracking=True)
    
    gate_number = fields.Selection([
        ('gate1', 'Gate 1'),
        ('gate2', 'Gate 2'),
        ('gate3', 'Gate 3')
    ], string='Gate Number', required=True, tracking=True)
    
    purpose = fields.Selection([
        ('feed', 'Feed Delivery'),
        ('raw_material', 'Raw Material'),
        ('packaging', 'Packaging'),
        ('maintenance', 'Maintenance'),
        ('meeting', 'Meeting'),
        ('inspection', 'Inspection'),
        ('other', 'Other')
    ], string='Purpose', required=True, tracking=True)
    
    people_count = fields.Integer(string='People Count', default=1, tracking=True)
    notes = fields.Text(string='Notes')
    entry_time = fields.Datetime(string='Entry Time')
    exit_time = fields.Datetime(string='Exit Time')
    approval_date = fields.Datetime(string='Approval Date')
    
    # Vehicle-specific fields
    vehicle_number = fields.Char(string='Vehicle Number', tracking=True)
    vehicle_type = fields.Selection([
        ('truck', 'Truck'),
        ('pickup', 'Pickup'),
        ('car', 'Car'),
        ('motorcycle', 'Motorcycle'),
        ('other', 'Other')
    ], string='Vehicle Type', tracking=True)
    
    # Visitor-specific fields
    visitor_purpose = fields.Text(string='Visitor Purpose Details')
    
    # Photo fields
    entry_photo = fields.Binary(string='Entry Photo', attachment=True, help="Capture photo using device camera")
    exit_photo = fields.Binary(string='Exit Photo', attachment=True, help="Capture photo using device camera")
    entry_photo_filename = fields.Char(string='Entry Photo Filename')
    exit_photo_filename = fields.Char(string='Exit Photo Filename')
    
    # Related documents
    sale_order_id = fields.Many2one('sale.order', string='Related Sales Order')
    delivery_order_id = fields.Many2one('stock.picking', string='Related Delivery Order')
    
    # People details (one2many)
    people_ids = fields.One2many('gatepass.people', 'gatepass_id', string='People Details')
    
    # Approval
    approved_by = fields.Many2one('res.users', string='Approved By')
    requested_by = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user)
    
    # ========== SECURITY METHODS ==========
    def _check_gate_staff_access(self):
        """Check if current user has gate staff access"""
        try:
            # Check if the field exists in the database
            if hasattr(self.env.user, 'is_gate_staff'):
                if not self.env.user.is_gate_staff and not self.env.user.is_security_admin:
                    raise AccessError(_("You don't have Gate Staff access rights."))
            else:
                # Field doesn't exist yet, allow access during development
                _logger.warning("Gate Staff field not found, allowing access")
        
        except Exception as e:
            _logger.warning("Error checking gate staff access: %s", str(e))
            # Allow access during development
            pass

    def _check_head_office_access(self):
        """Check if current user has head office access"""
        try:
            # Check if the field exists in the database
            if hasattr(self.env.user, 'is_head_office'):
                if not self.env.user.is_head_office and not self.env.user.is_security_admin:
                    raise AccessError(_("You don't have Head Office access rights."))
            else:
                # Field doesn't exist yet, allow access during development
                _logger.warning("Head Office field not found, allowing access")
        
        except Exception as e:
            _logger.warning("Error checking head office access: %s", str(e))
            # Allow access during development
            pass

    def _check_security_admin_access(self):
        """Check if current user has security admin access"""
        try:
            # Check if the field exists in the database
            if hasattr(self.env.user, 'is_security_admin'):
                if not self.env.user.is_security_admin:
                    raise AccessError(_("You don't have Security Admin access rights."))
            else:
                # Field doesn't exist yet, allow access during development
                _logger.warning("Security Admin field not found, allowing access")
        
        except Exception as e:
            _logger.warning("Error checking security admin access: %s", str(e))
            # Allow access during development
            pass
    # ========== END SECURITY METHODS ==========
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('gatepass.gatepass') or _('New')
        return super(GatePass, self).create(vals)
    
    @api.onchange('request_type')
    def _onchange_request_type(self):
        """Reset fields when request type changes"""
        if self.request_type == 'vehicle':
            self.visitor_purpose = False
        else:
            self.vehicle_number = False
            self.vehicle_type = False
    
    @api.onchange('people_count')
    def _onchange_people_count(self):
        """Update people records when count changes"""
        if self.people_count < len(self.people_ids):
            # Remove extra people
            self.people_ids = [(2, people.id) for people in self.people_ids[self.people_count:]]
        elif self.people_count > len(self.people_ids):
            # Add new people
            new_people = []
            for i in range(len(self.people_ids), self.people_count):
                new_people.append((0, 0, {'name': f'Person {i+1}'}))
            self.people_ids = new_people
    
    def action_send_for_approval(self):
        """Send gate pass for approval - Gate Staff & Admin only"""
        self._check_gate_staff_access()  # Add this security check
        
        if not self.people_ids:
            raise UserError(_('Please add people details before sending for approval.'))
        
        if self.request_type == 'vehicle' and not self.vehicle_number:
            raise UserError(_('Please enter vehicle number for vehicle gate pass.'))
        
        if self.request_type == 'visitor' and not self.visitor_purpose:
            raise UserError(_('Please enter visitor purpose details for visitor gate pass.'))
        print('Env USER:  ',self.env.user.name)
        user_id = self.env.user
        if user_id.is_gate_staff:
            self.write({'state': 'sent'})
            self._send_approval_notification()
        
        # Add this message post
            self.message_post(
                body=_('Gate pass sent for approval to Head Office'),
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )
            return True
    
    def _send_approval_notification(self):
        """Send approval notification to Head Office users"""
        try:
            # Check if the field exists
        
            # Find Head Office users by boolean field
            head_office_users = self.env['res.users'].search([
                ('is_head_office', 'in', True),
                ('active', 'in', True)
            ])
            
                
            # Fallback to security admins if no head office users found
            # if not head_office_users:
            #     head_office_users = self.env['res.users'].search([
            #         ('is_security_admin', '=', True),
            #         ('active', '=', True)
            #     ], limit=5)
            # else:
            #     # Fallback to old method if fields don't exist yet
            #     head_office_users = self.env['res.users'].search([
            #         ('groups_id.name', 'ilike', 'Head Office'),
            #         ('active', '=', True)
            #     ], limit=5)
            
            for user in head_office_users:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_('Gate Pass Approval Required'),
                    note=_('Gate Pass %s requires your approval') % self.name,
                    user_id=user.id
                )
                
        except Exception as e:
            _logger.warning("Failed to send approval notification: %s", str(e))
    
    def action_approve(self):
        """Approve gate pass - Head Office & Admin only"""
        self._check_head_office_access()  # Add this security check
        
        self.write({
            'state': 'approved',
            'approval_date': fields.Datetime.now(),
            'approved_by': self.env.user.id
        })
        
        # Notify gate staff
        self._send_approval_confirmation()
        
        # Post approval message to chatter
        self.message_post(
            body=_('Gate pass approved by %s') % self.env.user.name,
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
        
        return True
    
    def _send_approval_confirmation(self):
        """Send approval confirmation to requester"""
        try:
            # Complete any pending activities for this record (SIMPLIFIED)
            activities = self.activity_search([('res_id', '=', self.id)])
            if activities:
                activities.action_feedback()
                
        except Exception as e:
            _logger.warning("Failed to send approval confirmation: %s", str(e))
    
    def action_reject(self):
        """Reject gate pass - Head Office & Admin only"""
        self._check_head_office_access()  # Add this security check
        
        self.write({'state': 'draft'})
        
        # Post rejection message to chatter
        self.message_post(
            body=_('Gate pass rejected by %s') % self.env.user.name,
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
        
        try:
            # Complete any pending activities (SIMPLIFIED)
            activities = self.activity_search([('res_id', '=', self.id)])
            if activities:
                activities.action_feedback()
        except Exception as e:
            _logger.warning("Failed to update activities on rejection: %s", str(e))
        return True
    
    def action_mark_in(self):
        """Mark entry with timestamp and photo - Gate Staff & Admin only"""
        self._check_gate_staff_access()  # Add this security check
        
        if not self.entry_photo:
            raise UserError(_('Please capture entry photo before marking entry.'))
            
        self.write({
            'state': 'in',
            'entry_time': fields.Datetime.now()
        })
        
        # Post entry message to chatter
        self.message_post(
            body=_('Vehicle/Visitor entered at %s') % fields.Datetime.now(),
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
        return True
    
    def action_mark_out(self):
        """Mark exit with timestamp and photo - Head Office & Admin only"""
        self._check_head_office_access()  # Add this security check
        
        if not self.exit_photo:
            raise UserError(_('Please capture exit photo before marking exit.'))
            
        self.write({
            'state': 'out',
            'exit_time': fields.Datetime.now()
        })
        
        # Post exit message to chatter
        self.message_post(
            body=_('Vehicle/Visitor exited at %s') % fields.Datetime.now(),
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
        return True
    
    def action_complete(self):
        """Complete the gate pass - Head Office & Admin only"""
        self._check_head_office_access()  # Add this security check
        
        self.write({'state': 'completed'})
        
        # Post completion message to chatter
        self.message_post(
            body=_('Gate pass completed'),
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
        return True
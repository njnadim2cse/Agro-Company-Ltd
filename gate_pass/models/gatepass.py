from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError
import logging

_logger = logging.getLogger(__name__)

class GatePass(models.Model):
    _name = 'gatepass.gatepass'
    _description = 'Gate Pass Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # Add computed fields for UI visibility
    user_is_gate_staff = fields.Boolean(string='User is Gate Staff', compute='_compute_user_access')
    user_is_head_office = fields.Boolean(string='User is Head Office', compute='_compute_user_access')
    user_is_security_admin = fields.Boolean(string='User is Security Admin', compute='_compute_user_access')

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
        ('completed', 'Completed'),
    ], string="Status", default='draft')

    
    gate_number = fields.Selection(selection='_get_gate_numbers', string='Gate Number', required=True, tracking=True)
    purpose_id = fields.Many2one('gatepass.purpose.config', string='Purpose', required=True)
    # purpose = fields.Selection(selection='_get_purposes', string='Purpose', required=True, tracking=True)
    
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
    main_person_id = fields.Many2one(
        "gatepass.people",
        string="People",
        compute="_compute_main_person",
        store=True
    )

    # ========== SECURITY METHODS ==========
    def _check_gate_staff_access(self):
        """Check if current user has gate staff access"""
        if not (self.env.user.is_gate_staff or self.env.user.is_security_admin):
            raise AccessError(_("You don't have Gate Staff access rights."))

    def _check_head_office_access(self):
        """Check if current user has head office access"""
        if not (self.env.user.is_head_office or self.env.user.is_security_admin):
            raise AccessError(_("You don't have Head Office access rights."))

    def _check_security_admin_access(self):
        """Check if current user has security admin access"""
        if not self.env.user.is_security_admin:
            raise AccessError(_("You don't have Security Admin access rights."))
    # ========== END SECURITY METHODS ==========
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('gatepass.gatepass') or _('New')
        return super(GatePass, self).create(vals)
    
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
    
    @api.depends()
    def _compute_user_access(self):
        """Compute user access fields for UI visibility"""
        for record in self:
            try:
                record.user_is_gate_staff = self.env.user.is_gate_staff
                record.user_is_head_office = self.env.user.is_head_office
                record.user_is_security_admin = self.env.user.is_security_admin
            except:
                # Fallback if fields don't exist yet
                record.user_is_gate_staff = False
                record.user_is_head_office = False
                record.user_is_security_admin = False

    def action_send_for_approval(self):
        """Send gate pass for approval - Gate Staff & Admin only"""
        self._check_gate_staff_access()
        
        if not self.people_ids:
            raise UserError(_('Please add people details before sending for approval.'))
        
        if self.request_type == 'vehicle' and not self.vehicle_number:
            raise UserError(_('Please enter vehicle number for vehicle gate pass.'))
        
        if self.request_type == 'visitor' and not self.visitor_purpose:
            raise UserError(_('Please enter visitor purpose details for visitor gate pass.'))
        
        self.write({'state': 'sent'})
        self._send_approval_notification()
        
        self.message_post(
            body=_('Gate pass sent for approval to Head Office'),
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
        return True
    
    def _send_approval_notification(self):
        """Send approval notification to Head Office users"""
        try:
            # Find Head Office users
            head_office_users = self.env['res.users'].search([
                ('is_head_office', '=', True),
                ('active', '=', True)
            ])
            
            # Also include security admins
            security_admin_users = self.env['res.users'].search([
                ('is_security_admin', '=', True),
                ('active', '=', True),
                ('id', 'not in', head_office_users.ids)  # Avoid duplicates
            ])
            
            # Combine both lists
            all_approvers = head_office_users | security_admin_users
            
            # Fallback if no approvers found
            if not all_approvers:
                all_approvers = self.env['res.users'].search([
                    ('groups_id.name', 'ilike', 'Administrator'),
                    ('active', '=', True)
                ], limit=5)
            
            for user in all_approvers:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_('Gate Pass Approval Required'),
                    note=_('Gate Pass %s requires your approval') % self.name,
                    user_id=user.id
                )
                
            # Log notification
            _logger.info("Approval notification sent to %s users for gate pass %s", 
                        len(all_approvers), self.name)
                
        except Exception as e:
            _logger.error("Failed to send approval notification: %s", str(e))
    
    def action_approve(self):
        """Approve gate pass - Head Office & Admin only"""
        self._check_head_office_access()
        
        self.write({
            'state': 'approved',
            'approval_date': fields.Datetime.now(),
            'approved_by': self.env.user.id
        })
        
        # Post approval message to chatter
        self.message_post(
            body=_('Gate pass approved by %s') % self.env.user.name,
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
        
        return True
    
    def action_reject(self):
        """Reject gate pass - Head Office & Admin only"""
        self._check_head_office_access()
        
        self.write({'state': 'draft'})
        
        # Post rejection message to chatter
        self.message_post(
            body=_('Gate pass rejected by %s') % self.env.user.name,
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
        
        # Complete any pending activities
        try:
            activities = self.activity_search([('res_id', '=', self.id)])
            if activities:
                activities.action_feedback()
        except Exception as e:
            _logger.warning("Failed to update activities on rejection: %s", str(e))
            
        return True
    
    def action_mark_in(self):
        """Mark entry with timestamp and photo - Gate Staff & Admin only"""
        self._check_gate_staff_access()
        
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
        """Mark exit with timestamp and photo - Gate Staff & Admin only"""
        self._check_gate_staff_access()
        
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
        """Complete the gate pass - Gate Staff & Admin only"""
        self._check_gate_staff_access()
        
        self.write({'state': 'completed'})
        
        # Post completion message to chatter
        self.message_post(
            body=_('Gate pass completed'),
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
        return True
    
    @api.model
    def _get_gate_numbers(self):
        """Get gate numbers from configuration"""
        try:
            gates = self.env['gatepass.gate.config'].sudo().search([('active', '=', True)])
            return [(gate.gate_number, f"{gate.gate_number} - {gate.name}") for gate in gates]
        except AccessError:
            # If user doesn't have access to config, return empty list
            return []
        except Exception:
            # If model doesn't exist yet, return empty list
            return []

    @api.onchange('request_type')
    def _onchange_request_type(self):
        domain = [('active', '=', True)]
        if self.request_type == 'vehicle':
            domain.append(('assign_for', 'in', ['vehicle', 'both']))
            self.visitor_purpose = False
            self.purpose_id = False
        elif self.request_type == 'visitor':
            domain.append(('assign_for', 'in', ['visitor', 'both']))
            self.vehicle_number = False
            self.vehicle_type = False
            self.purpose_id = False
        return {'domain': {'purpose_id': domain}}
    
    @api.depends("people_ids")
    def _compute_main_person(self):
        for rec in self:
            rec.main_person_id = rec.people_ids[:1].id if rec.people_ids else False
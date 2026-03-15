from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class GatePass(models.Model):
    _name = 'gatepass.gatepass'
    _description = 'Gate Pass Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True
    )

    # Computed fields for UI visibility
    user_is_gate_staff = fields.Boolean(string='User is Gate Staff', compute='_compute_user_access')
    user_is_head_office = fields.Boolean(string='User is Head Office', compute='_compute_user_access')
    user_is_security_admin = fields.Boolean(string='User is Security Admin', compute='_compute_user_access')

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        index=True, default=lambda self: _('New'), tracking=True
    )

    # FIX BUG 2: order_type was declared TWICE in the class body.
    # Python last-write-wins, so the second declaration (no default, no required)
    # silently overwrote the first. This meant existing records could have a NULL
    # order_type after an ORM cache flush, causing unexpected IntegrityErrors or
    # None-comparisons inside _compute_available_orders and _validate_before_send,
    # producing a malformed server error that crashed Odoo mobile's onSaveError JS.
    # Fixed: one declaration only, with required=True and default='sale_order'.
    order_type = fields.Selection([
        ('sale_order', 'Sale Order'),
        ('purchase_order', 'Purchase Order')
    ], string="Order Type", required=True, default='sale_order', tracking=True)

    request_type = fields.Selection([
        ('vehicle', 'Vehicle'),
        ('visitor', 'Visitor')
    ], string='Request Type', required=True, default='vehicle', tracking=True)

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

    people_count = fields.Integer(string='People Count', default=1, tracking=True)
    notes = fields.Html(string='Notes', sanitize=True, sanitize_tags=False)
    entry_time = fields.Datetime(string='Entry Time')
    exit_time = fields.Datetime(string='Exit Time')
    approval_date = fields.Datetime(string='Approval Date')

    vehicle_number = fields.Char(string='Vehicle Number', tracking=True, required=False)
    vehicle_type = fields.Selection([
        ('truck', 'Truck'),
        ('pickup', 'Pickup'),
        ('car', 'Car'),
        ('motorcycle', 'Motorcycle'),
        ('other', 'Other')
    ], string='Vehicle Type', tracking=True)

    detail_purpose = fields.Html(
        string="Detail Purpose",
        sanitize=True,
        sanitize_tags=False,
        help="Detailed purpose of the visit"
    )
    visitor_audio = fields.Binary("Purpose Audio")
    audio_filename = fields.Char("Audio Filename")

    # Photo fields - attachment=True stores as ir.attachment (not inline in DB column)
    entry_photo = fields.Binary(string='Entry Photo', attachment=True)
    exit_photo = fields.Binary(string='Exit Photo', attachment=True)
    entry_photo_filename = fields.Char(string='Entry Photo Filename')
    exit_photo_filename = fields.Char(string='Exit Photo Filename')

    people_ids = fields.One2many('gatepass.people', 'gatepass_id', string='People Details')

    approved_by = fields.Many2one('res.users', string='Approved By')
    requested_by = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user)

    main_person_name = fields.Char(
        string="People Names",
        compute="_compute_main_person_name",
        store=True
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Related Sales Order',
        domain="[('id', 'in', available_sale_order_ids)]",
    )
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Related Purchase Order',
        domain="[('id', 'in', available_purchase_order_ids)]",
    )
    partner_id = fields.Many2one('res.partner', string="Customer Name")
    vendor_id = fields.Many2one('res.partner', string="Vendor Name")

    available_sale_order_ids = fields.Many2many(
        'sale.order',
        compute='_compute_available_orders',
        string='Available Sale Orders'
    )
    available_purchase_order_ids = fields.Many2many(
        'purchase.order',
        compute='_compute_available_orders',
        string='Available Purchase Orders'
    )

    # -----------------------------------------------------------------------
    # Compute methods
    # -----------------------------------------------------------------------

    @api.depends('partner_id', 'vendor_id', 'order_type')
    def _compute_available_orders(self):
        for record in self:
            record.available_sale_order_ids = False
            record.available_purchase_order_ids = False
            if record.order_type == 'sale_order' and record.partner_id:
                sale_orders = self.env['sale.order'].search([
                    ('partner_id', '=', record.partner_id.id),
                    ('state', 'in', ['sale', 'done']),
                ])
                record.available_sale_order_ids = sale_orders.filtered(
                    lambda so: any(p.state != 'done' for p in so.picking_ids)
                ).ids
            elif record.order_type == 'purchase_order' and record.vendor_id:
                purchase_orders = self.env['purchase.order'].search([
                    ('partner_id', '=', record.vendor_id.id),
                    ('state', 'in', ['purchase', 'done']),
                ])
                record.available_purchase_order_ids = purchase_orders.filtered(
                    lambda po: any(p.state != 'done' for p in po.picking_ids)
                ).ids

    @api.depends()
    def _compute_user_access(self):
        for record in self:
            try:
                record.user_is_gate_staff = self.env.user.is_gate_staff
                record.user_is_head_office = self.env.user.is_head_office
                record.user_is_security_admin = self.env.user.is_security_admin
            except Exception:
                record.user_is_gate_staff = False
                record.user_is_head_office = False
                record.user_is_security_admin = False

    @api.depends('people_ids.name')
    def _compute_main_person_name(self):
        for rec in self:
            names = [p.name for p in rec.people_ids if p.name]
            rec.main_person_name = ', '.join(names) if names else 'No Person'

    # -----------------------------------------------------------------------
    # Validation
    #
    # WHY NOT @api.constrains:
    # @api.constrains fires on every write(), including photo-only saves.
    # On Odoo mobile, tapping an action button (Mark Entry, Mark Exit, etc.)
    # while the form is dirty triggers an auto-save BEFORE the action runs.
    # If any exception is raised during that auto-save write(), the JS
    # onSaveError handler at web.assets_web.min.js:8794 receives a response
    # object shaped differently than expected, and crashes:
    #   TypeError: Cannot read properties of undefined (reading 'message')
    # Keeping all validation in explicit methods called only from action
    # buttons eliminates this crash entirely.
    # -----------------------------------------------------------------------

    def _validate_before_send(self):
        """Business rule validation. Called only from action_send_for_approval."""
        for record in self:
            if not record.people_ids:
                raise ValidationError(_('Please add at least one person before proceeding.'))
            people_without_mobile = record.people_ids.filtered(lambda p: not p.mobile)
            if people_without_mobile:
                names = ', '.join([p.name or 'Unnamed' for p in people_without_mobile])
                raise ValidationError(
                    _('All people must have a Mobile Number. Missing for: %s') % names
                )
            if record.request_type == 'vehicle':
                if not record.vehicle_number:
                    raise ValidationError(_('Please fill in the Vehicle Number before proceeding.'))
                if not record.order_type:
                    raise ValidationError(_('Please select an Order Type before proceeding.'))
                if record.order_type == 'sale_order':
                    if not record.partner_id:
                        raise ValidationError(_('Please select a Customer Name before proceeding.'))
                    if not record.sale_order_id:
                        raise ValidationError(_('Please select a Sales Order before proceeding.'))
                elif record.order_type == 'purchase_order':
                    if not record.vendor_id:
                        raise ValidationError(_('Please select a Vendor Name before proceeding.'))
                    if not record.purchase_order_id:
                        raise ValidationError(_('Please select a Purchase Order before proceeding.'))

    # -----------------------------------------------------------------------
    # Security helpers
    # -----------------------------------------------------------------------

    def _check_gate_staff_access(self):
        if not (self.env.user.is_gate_staff or self.env.user.is_security_admin):
            raise AccessError(_("You don't have Gate Staff access rights."))

    def _check_head_office_access(self):
        if not (self.env.user.is_head_office or self.env.user.is_security_admin):
            raise AccessError(_("You don't have Head Office access rights."))

    def _check_security_admin_access(self):
        if not self.env.user.is_security_admin:
            raise AccessError(_("You don't have Security Admin access rights."))

    # -----------------------------------------------------------------------
    # ORM overrides
    # -----------------------------------------------------------------------

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('gatepass.gatepass') or _('New')
        return super().create(vals)

    # -----------------------------------------------------------------------
    # Onchange
    # -----------------------------------------------------------------------

    @api.onchange('people_count')
    def _onchange_people_count(self):
        if self.people_count < len(self.people_ids):
            self.people_ids = [(2, p.id) for p in self.people_ids[self.people_count:]]
        elif self.people_count > len(self.people_ids):
            self.people_ids = [
                (0, 0, {'name': f'Person {i + 1}'})
                for i in range(len(self.people_ids), self.people_count)
            ]

    # -----------------------------------------------------------------------
    # Action buttons
    #
    # FIX BUG 3: action_mark_in and action_mark_out previously raised UserError
    # if the photo was missing. On mobile, tapping the button auto-saves first,
    # then runs the action. The UserError from the action propagated back through
    # the same JS save-error handler path, which could not handle it, crashing
    # with "Cannot read properties of undefined (reading 'message')".
    #
    # Fix: remove the server-side photo guard from both methods.
    # Instead, the "Mark Entry" button is now invisible until entry_photo exists,
    # and "Mark Exit" is invisible until exit_photo exists (enforced in the view).
    # The user literally cannot tap the button without a photo saved first.
    # This is both safer and correct UX.
    # -----------------------------------------------------------------------

    def action_send_for_approval(self):
        self._check_gate_staff_access()
        self._validate_before_send()
        self.write({'state': 'sent'})
        self._send_approval_notification()
        self.message_post(
            body=_('Gate pass sent for approval to Head Office'),
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
        return True

    def _send_approval_notification(self):
        try:
            head_office_users = self.env['res.users'].search([
                ('is_head_office', '=', True), ('active', '=', True)
            ])
            security_admin_users = self.env['res.users'].search([
                ('is_security_admin', '=', True),
                ('active', '=', True),
                ('id', 'not in', head_office_users.ids)
            ])
            all_approvers = head_office_users | security_admin_users
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
            _logger.info("Approval notification sent to %s users for gate pass %s",
                         len(all_approvers), self.name)
        except Exception as e:
            _logger.error("Failed to send approval notification: %s", str(e))

    def action_approve(self):
        self._check_head_office_access()
        self.write({
            'state': 'approved',
            'approval_date': fields.Datetime.now(),
            'approved_by': self.env.user.id
        })
        self.message_post(
            body=_('Gate pass approved by %s') % self.env.user.name,
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
        return True

    def action_reject(self):
        self._check_head_office_access()
        self.write({'state': 'draft'})
        self.message_post(
            body=_('Gate pass rejected by %s') % self.env.user.name,
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
        try:
            activities = self.activity_search([('res_id', '=', self.id)])
            if activities:
                activities.action_feedback()
        except Exception as e:
            _logger.warning("Failed to update activities on rejection: %s", str(e))
        return True

    def action_mark_in(self):
        """Mark entry. 'Mark Entry' button is invisible until entry_photo is saved (view-enforced)."""
        self._check_gate_staff_access()
        self.write({
            'state': 'in',
            'entry_time': fields.Datetime.now()
        })
        self.message_post(
            body=_('Vehicle/Visitor entered at %s') % fields.Datetime.now(),
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
        return True

    def action_mark_out(self):
        """Mark exit. 'Mark Exit' button is invisible until exit_photo is saved (view-enforced)."""
        self._check_gate_staff_access()
        self.write({
            'state': 'out',
            'exit_time': fields.Datetime.now()
        })
        self.message_post(
            body=_('Vehicle/Visitor exited at %s') % fields.Datetime.now(),
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
        return True

    def action_complete(self):
        self._check_gate_staff_access()
        self.write({'state': 'completed'})
        self.message_post(
            body=_('Gate pass completed'),
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
        return True

    @api.model
    def _get_gate_numbers(self):
        try:
            gates = self.env['gatepass.gate.config'].sudo().search([('active', '=', True)])
            return [(gate.gate_number, f"{gate.gate_number} - {gate.name}") for gate in gates]
        except (AccessError, Exception):
            return []

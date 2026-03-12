# farm_medicine_approval/models/farm_medicine_approval.py
from datetime import date
from datetime import datetime
from odoo import models, fields, api
from odoo.exceptions import UserError

class FarmMedicineApproval(models.Model):
    _name = "farm.medicine.approval"
    _description = "Farm Medicine Approval"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    
    name = fields.Char(string="Reference", required=True, default="New")
    request_date = fields.Datetime(string="Request Date", default=fields.Datetime.now)
    rejected_by = fields.Many2one("res.users", string="Rejected By") 
    rejection_reason = fields.Text(string="Rejection Reason")
    
    flock_id = fields.Many2one("farm.layer.flock", string="Flock", required=True, tracking=True)
    current_birds = fields.Integer(string="Current Birds", tracking=True)
    current_age_display = fields.Char(string="Current Age in Weeks", tracking=True)
    bird_type = fields.Selection([('layer','Layer'),('broiler','Broiler')],string="Bird Type" ,tracking =True)
    current_birds = fields.Integer(string="Current Birds", tracking=True)
    current_age_display = fields.Char(string="Current Age in Weeks", tracking=True)
    bird_type = fields.Selection([
        ('layer', 'Layer'),
        ('broiler', 'Broiler')
    ], string="Bird Type", tracking=True)

    @api.onchange("flock_id")
    def get_flock_data(self):
        self.current_birds = self.flock_id.total_qty 
        self.current_age_display = self.flock_id.current_age_display 
        self.bird_type = self.flock_id.bird_type 


    state = fields.Selection([
        ('draft', 'To Submit'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('refused', 'Rejected') 
      
    ], string="Status", default='draft', tracking=True)
    
    approved_by = fields.Many2one("res.users", string="Approved By")
    approval_date = fields.Datetime(string="Approval Date")
    approval_line_ids = fields.One2many(
        "farm.medicine.approval.line", 
        "approval_id", 
        string="Medicine Items"
    )
    requested_by = fields.Many2one(
        'res.users', 
        string="Requested By", 
        required=True,
        default=lambda self: self.env.user,
        tracking=True
    )

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            today_str = datetime.today().strftime('%d-%m-%Y')
            last_record = self.search(
                [('name', 'like', f'M/S/{today_str}/%')],
                order='id desc', limit=1
            )
            if last_record:
                last_seq = int(last_record.name.split('/')[-1])
                next_seq = str(last_seq + 1).zfill(5)
            else:
                next_seq = '00001'
            vals['name'] = f"M/S/{today_str}/{next_seq}"
        return super(FarmMedicineApproval, self).create(vals)
  

    
    def action_submit(self):

        for approval in self:
            if approval.state != 'draft':
                raise UserError("Only draft approvals can be submitted!")
            approval.write({'state': 'submitted'})
    

    def action_approve(self):

        for approval in self:
            if approval.state != 'submitted':
                raise UserError("Only submitted requests can be approved!")
            
            approval.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approval_date': fields.Datetime.now()
            })
            
         
            for line in approval.approval_line_ids:
                if line.farm_boy_request_id:
                 
                    line.farm_boy_request_id.write({
                        'state': 'approved'
                    })
                    
                    line.farm_boy_request_id.message_post(
                        body=f"Medicine request approved by {self.env.user.name}",
                        message_type="comment",
                        subtype_xmlid="mail.mt_comment"
                    )
            
            approval.message_post(
                body=f"Approval completed by {self.env.user.name}. All medicine requests have been approved.",
                message_type="comment",
                subtype_xmlid="mail.mt_comment"
            )
    
    def action_reject(self):
    
        self.ensure_one()

        # ❌ Block rejection if already approved
        if self.state == 'approved':
            raise UserError("You cannot reject an already approved request.")

        # Optionally block if refused also
        if self.state == 'refused':
            raise UserError("This request is already rejected.")

        # Otherwise open wizard
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reject Medicine Request',
            'res_model': 'farm.medicine.rejection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_approval_id': self.id}
        }


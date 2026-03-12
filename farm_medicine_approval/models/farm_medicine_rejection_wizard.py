from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class FarmMedicineRejectionWizard(models.Model):
    _name = "farm.medicine.rejection.wizard"
    _description = "Farm Medicine Rejection Wizard"

    approval_id = fields.Many2one("farm.medicine.approval", string="Approval", required=True)
    rejection_reason = fields.Text(string="Rejection Reason", required=True)

    def action_confirm_rejection(self):
        """Confirm rejection with reason"""
        self.ensure_one()
        
        if not self.rejection_reason.strip():
            raise UserError("Please provide a rejection reason!")

        self.approval_id.with_context(tracking_disable=True).write({
            'state': 'refused',
            'rejected_by': self.env.user.id,
            'rejection_reason': self.rejection_reason
        })
      
        rejected_lines_count = 0
    
        for i, approval_line in enumerate(self.approval_id.approval_line_ids):
            _logger.info(f"--- Processing Approval Line {i+1} ---")
            _logger.info(f"Approval Line ID: {approval_line.id}")
            _logger.info(f"Farm Boy Request ID: {approval_line.farm_boy_request_id.id if approval_line.farm_boy_request_id else 'None'}")
            
            if approval_line.farm_boy_request_id:
                farmboy_record = approval_line.farm_boy_request_id
            
                try:
                    
                    farmboy_record.with_context(tracking_disable=True).write({
                        'state': 'refused'
                    })
                    
                    farmboy_record.message_post(
                        body=f"❌ Medicine request rejected by {self.env.user.name}. Reason: {self.rejection_reason}",
                        message_type="comment",
                        subtype_xmlid="mail.mt_comment"
                    )
                    
                    rejected_lines_count += 1
                 
                    
                except Exception as e:
                    _logger.error(f"❌ Error updating farmboy record {farmboy_record.id}: {str(e)}")
            else:
                _logger.warning("⚠️ No farmboy record linked to this approval line")


        self.approval_id.message_post(
            body=f"❌ Request rejected by {self.env.user.name}. Reason: {self.rejection_reason}. {rejected_lines_count} line(s) updated.",
            message_type="comment",
            subtype_xmlid="mail.mt_comment"
        )
        
        if rejected_lines_count > 0:
            message = f"✅ Request rejected successfully! {rejected_lines_count} medicine line(s) updated to 'refused' state."
        else:
            message = "⚠️ Approval rejected but no linked farmboy records were found to update."
            
        return {
            'type': 'ir.actions.act_window_close',
            'effect': {
                'fadeout': 'slow',
                'message': message,
                'type': 'rainbow_man',
            }
        }
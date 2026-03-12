from odoo import models, fields

class ResCompany(models.Model):
    _inherit = "res.company"

    enable_gate_pass = fields.Boolean("Enable Gate Pass")

    def _sync_feature_groups(self):
        """Sync groups based on company-specific module access"""
        mapping = {
            "enable_gate_pass": "gate_pass.group_gate_pass_user",
        }

        # Get all users from all affected companies
        all_users = self.mapped('user_ids')
        
        for user in all_users:
            # Get all companies the user has access to
            user_companies = user.company_ids
            
            for field_name, group_xml in mapping.items():
                group = self.env.ref(group_xml, raise_if_not_found=False)
                if not group:
                    continue
                
                # Check if module is enabled in ANY of user's companies
                module_enabled = False
                for company in user_companies:
                    if getattr(company, field_name):
                        module_enabled = True
                        break
                
                # Add or remove group based on module access in any company
                if module_enabled:
                    if group not in user.groups_id:
                        user.write({"groups_id": [(4, group.id)]})
                else:
                    if group in user.groups_id:
                        user.write({"groups_id": [(3, group.id)]})

    def write(self, vals):
        res = super().write(vals)
        self._sync_feature_groups()
        return res
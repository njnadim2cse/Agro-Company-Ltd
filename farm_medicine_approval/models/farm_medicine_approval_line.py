# farm_medicine_approval/models/farm_medicine_approval_line.py

from odoo import models, fields, api

class FarmMedicineApprovalLine(models.Model):
    _name = "farm.medicine.approval.line"
    _description = "Farm Medicine Approval Line"

    approval_id = fields.Many2one("farm.medicine.approval", string="Approval", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Medicine")
    requested_quantity = fields.Float(string="Requested Quantity")
    farm_boy_request_id = fields.Many2one("farmboy.request.add.line", string="Farm Boy Request")
    dose_per_bird = fields.Float(string="Dose Per Bird (ml)")
    remaining_dose = fields.Float(string="Remaining Dose (ml)")
    requested_quantity = fields.Float(string="Available Quantity (ml)")
    bird_count = fields.Integer(string="Number of Birds")
    consume_quantity = fields.Float(string="Consumed Quantity")
    total_dose = fields.Float(string="Available Quantity")
    total_cost = fields.Float(string="Total Cost")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('refused', 'Rejected')
    ], string="Status", default='draft', tracking=True)
   
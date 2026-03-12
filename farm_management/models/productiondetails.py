from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

class ProductionDetails(models.Model):
    _name = "farm.production.details"
    _description = "Production Details"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "id desc"
    

    name = fields.Char(string="Reference", default="New", readonly=True)
    egg_line_ids = fields.One2many("farm.egg.line", "production_id", string="Egg Categories", default=lambda self: [])
    created_by = fields.Many2one('res.users', string="Responsible Person", default=lambda self: self.env.user, readonly=True)

    total_small = fields.Integer(string="Total Small", compute="_compute_egg_totals", store=True, tracking=True)
    total_medium = fields.Integer(string="Total Medium", compute="_compute_egg_totals", store=True, tracking=True)
    total_high_medium = fields.Integer(string="Total High Medium", compute="_compute_egg_totals", store=True, tracking=True)
    total_high = fields.Integer(string="Total High", compute="_compute_egg_totals", store=True, tracking=True)
    total_double_yolk = fields.Integer(string="Total Double Yolk", compute="_compute_egg_totals", store=True, tracking=True)
    total_broken = fields.Integer(string="Total Broken", compute="_compute_egg_totals", store=True, tracking=True)
    total_white = fields.Integer(string="Total White", compute="_compute_egg_totals", store=True, tracking=True)
    total_damage = fields.Integer(string="Total Damage", compute="_compute_egg_totals", store=True, tracking=True)
    total_egg = fields.Integer(string="Total Egg", compute="_compute_egg_totals", store=True, tracking=True)

    percentage = fields.Float(string="Production Percentage", compute="_compute_percentage", store=True, tracking=True)
    cumulative_egg = fields.Integer(string="Cumulative Egg", compute="_compute_cumulative", store=True, tracking=True)

    egg_weight = fields.Float(string="Egg Weight (gm)", tracking=True)
    act = fields.Integer(string="Act", tracking=True)
    date = fields.Date(string="Date", default=fields.Date.context_today, tracking=True)
    flock_id = fields.Many2one("farm.layer.flock", string="Flock Name", tracking=True)
    current_birds = fields.Integer(string="Current Birds", tracking=True)
    bird_type = fields.Selection([('layer','Layer'),('broiler','Broiler')],string="Bird Type" ,tracking =True)
    current_age_display = fields.Char(string="Current Age in Weeks", tracking=True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Confirm')], string="Status", default='draft', tracking=True)

    small_percentage = fields.Float(string="Small Egg %", compute="_compute_category_percentage", store=True, tracking=True)
    medium_percentage = fields.Float(string="Medium Egg %", compute="_compute_category_percentage", store=True, tracking=True)
    high_medium_percentage = fields.Float(string="High Medium Egg %", compute="_compute_category_percentage", store=True, tracking=True)
    high_percentage = fields.Float(string="High Egg %", compute="_compute_category_percentage", store=True, tracking=True)
    double_yolk_percentage = fields.Float(string="Double Yolk %", compute="_compute_category_percentage", store=True, tracking=True)
    broken_percentage = fields.Float(string="Broken %", compute="_compute_category_percentage", store=True, tracking=True)
    white_percentage = fields.Float(string="White %", compute="_compute_category_percentage", store=True, tracking=True)
    damage_percentage = fields.Float(string="Damage %", compute="_compute_category_percentage", store=True, tracking=True)


    small_cumulative = fields.Float(string="Small Egg Cumulative", compute="_compute_cumulative", store=True, tracking=True)
    medium_cumulative = fields.Float(string="Medium Egg Cumulative", compute="_compute_cumulative", store=True, tracking=True)
    high_medium_cumulative = fields.Float(string="High Medium Egg Cumulative", compute="_compute_cumulative", store=True, tracking=True)
    high_cumulative = fields.Float(string="High Egg Cumulative", compute="_compute_cumulative", store=True, tracking=True)
    double_yolk_cumulative = fields.Float(string="Double Yolk Cumulative", compute="_compute_cumulative", store=True, tracking=True)
    broken_cumulative = fields.Float(string="Broken Cumulative", compute="_compute_cumulative", store=True, tracking=True)
    white_cumulative = fields.Float(string="White Cumulative", compute="_compute_cumulative", store=True, tracking=True)
    damage_cumulative = fields.Float(string="Damage Cumulative", compute="_compute_cumulative", store=True, tracking=True)

    ### Egg production Warehouse locations

    picking_type_id = fields.Many2one(
    'stock.picking.type',
    string="Operation Type",
    required=True,
    default=lambda self: self.env['stock.picking.type'].search(
        [
            ('is_for_production_egg', '=', True),
            ('company_id', '=', self.env.company.id)
        ],
        limit=1
      )
    )

    location_id = fields.Many2one(
        'stock.location',
        string="Source Location",
        required=True 
    )
    location_dest_id = fields.Many2one(
        'stock.location',
        string="Destination Location",
        required=True
    )

    @api.onchange('picking_type_id')
    def _onchange_picking_type_id(self):
        if self.picking_type_id:
            self.location_id = self.picking_type_id.default_location_src_id
            self.location_dest_id = self.picking_type_id.default_location_dest_id


    @api.depends("total_egg", "current_birds")
    def _compute_cumulative(self):
        all_records = self.search([])
        for rec in self:
            rec.small_cumulative = sum(all_records.mapped("total_small"))
            rec.medium_cumulative = sum(all_records.mapped("total_medium"))
            rec.high_medium_cumulative = sum(all_records.mapped("total_high_medium"))
            rec.high_cumulative = sum(all_records.mapped("total_high"))
            rec.double_yolk_cumulative = sum(all_records.mapped("total_double_yolk"))
            rec.broken_cumulative = sum(all_records.mapped("total_broken"))
            rec.white_cumulative = sum(all_records.mapped("total_white"))
            rec.damage_cumulative = sum(all_records.mapped("total_damage"))

    @api.depends("total_egg")
    def _compute_category_percentage(self):
        for record in self:
            record.small_percentage = (record.total_small / record.total_egg) * 100 if record.total_egg else 0.0
            record.medium_percentage = (record.total_medium / record.total_egg) * 100 if record.total_egg else 0.0
            record.high_medium_percentage = (record.total_high_medium / record.total_egg) * 100 if record.total_egg else 0.0
            record.high_percentage = (record.total_high / record.total_egg) * 100 if record.total_egg else 0.0
            record.double_yolk_percentage = (record.total_double_yolk / record.total_egg) * 100 if record.total_egg else 0.0
            record.broken_percentage = (record.total_broken / record.total_egg) * 100 if record.total_egg else 0.0
            record.white_percentage = (record.total_white / record.total_egg) * 100 if record.total_egg else 0.0
            record.damage_percentage = (record.total_damage / record.total_egg) * 100 if record.total_egg else 0.0

    @api.onchange("flock_id")
    def _onchange_get_flock_data(self):
        self.current_birds = self.flock_id.total_qty
        self.current_age_display = self.flock_id.current_age_display
        self.bird_type = self.flock_id.bird_type


    @api.model
    def create(self, vals):

        # record_date = vals.get('date') or fields.Date.context_today(self)
        # flock_id = vals.get('flock_id')
        # if record_date and flock_id:
        #     count = self.search_count([
        #         ('date', '=', record_date),
        #         ('flock_id', '=', flock_id)
        #     ])
        #     if count >= 2:
        #         raise UserError(
        #             f"For this flock on {record_date}, only 2 entries are allowed. "
        #             "You cannot create more than 2 records."
        #         )
        
        if vals.get('name', 'New') == 'New':
            today_str = datetime.today().strftime('%d-%m-%Y')
            vals['name'] = f"P/D/{today_str}"
        return super(ProductionDetails, self).create(vals)

    @api.depends("egg_line_ids.egg_type", "egg_line_ids.value")
    def _compute_egg_totals(self):
        for rec in self:
            rec.total_small = sum(line.value for line in rec.egg_line_ids if line.egg_type == "small")
            rec.total_medium = sum(line.value for line in rec.egg_line_ids if line.egg_type == "medium")
            rec.total_high_medium = sum(line.value for line in rec.egg_line_ids if line.egg_type == "high_medium")
            rec.total_high = sum(line.value for line in rec.egg_line_ids if line.egg_type == "high")
            rec.total_double_yolk = sum(line.value for line in rec.egg_line_ids if line.egg_type == "double_yolk")
            rec.total_broken = sum(line.value for line in rec.egg_line_ids if line.egg_type == "broken")
            rec.total_white = sum(line.value for line in rec.egg_line_ids if line.egg_type == "white")
            rec.total_damage = sum(line.value for line in rec.egg_line_ids if line.egg_type == "damage")

            rec.total_egg = (
                rec.total_small + rec.total_medium + rec.total_high_medium +
                rec.total_high + rec.total_double_yolk + rec.total_broken +
                rec.total_white + rec.total_damage
            )

        all_records = self.search([])
        total_sum = sum(all_records.mapped("total_egg"))
        for rec in self:
            rec.cumulative_egg = total_sum

    @api.depends("total_egg", "current_birds")
    def _compute_percentage(self):
        for record in self:
            record.percentage = (record.total_egg / record.current_birds) * 100 if record.current_birds else 0.0

    def action_draft(self):
        if self.state != "draft":
            self.state = 'draft'
            self.message_post(body="Production moved to Draft state.")

    def action_confirm(self):
        if self.state != "done":
            self.state = 'done'
            self.message_post(body="Production marked as Done state.")
            if self.egg_line_ids:
                    self.egg_line_ids.action_done()
                    self.egg_line_ids.write({'state': 'done'})


class EggInventoryProcess(models.Model):
    _name = "egg.inventory.process"
    _description = "Egg Inventory Processing"
    

    

    name = fields.Char(string="Name", required=True)
    egg_type = fields.Selection([
        ("small", "Small"),
        ("medium", "Medium"),
        ("high_medium", "High Medium"),
        ("high", "High"),
        ("double_yolk", "Double Yolk"),
        ("broken", "Broken"),
        ("white", "White"),
        ("damage", "Damage"),
        ('misshaped','Misshaped'),
        ('liquid' ,'Liquid')
    ], string="Egg Type", required=True)

    product_id = fields.Many2one(
        'product.template',
        string="Product",
        domain="[('egg_type', '=', egg_type)]",  
        required=True
    )
    quantity = fields.Float(string="Quantity", required=True)

    @api.onchange('egg_type')
    def _onchange_egg_type(self):
        for record in self: 
            if record.egg_type:
                product = self.env['product.template'].search([('egg_type', '=', record.egg_type)], limit=1)
                if product:
                    record.product_id = product.id
                else:
                    record.product_id = False


class EggLine(models.Model):
    _name = "farm.egg.line"
    _description = "Egg Line"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    production_id = fields.Many2one(
        "farm.production.details",
        string="Production",
        ondelete="cascade",
        tracking=True
    )
    date = fields.Datetime(
        string="Date",
        default=fields.Datetime.now,
        tracking=True
    )

    egg_type = fields.Selection([
        ("small", "Small"),
        ("medium", "Medium"),
        ("high_medium", "High Medium"),
        ("high", "High"),
        ("double_yolk", "Double Yolk"),
        ("broken", "Broken"),
        ("white", "White"),
        ("damage", "Damage"),
        ('misshaped','Misshaped'),
        ('liquid' ,'Liquid')
    ], string="Egg Type", required=True, tracking=True)

    product_id = fields.Many2one("product.template", string="Product")
    value = fields.Integer(string="Number of Eggs", required=True, tracking=True)
    short_description = fields.Char(string="Short Description", tracking=True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], string="Status", default="draft", readonly=True, tracking=True)

    @api.constrains('value')
    def _check_value_positive(self):
        for rec in self:
            if rec.value <= 0:
                raise ValidationError("Quantity must be greater than zero!")

    def _format_plain_message(self, action, changes=None, previous_state=None):
        msg_lines = [
            f"{action}",
            f"Updated By      : {self.env.user.name}",
            f"Production      : {self.production_id.name if self.production_id else 'N/A'}",
            f"Date of Record  : {self.date or 'N/A'}",
            f"Egg Type        : {self.egg_type or 'N/A'}",
            f"Quantity        : {self.value or 0}",
        ]
        if previous_state:
            msg_lines.append(f"Previous State  : {previous_state}")
        if changes:
            msg_lines.append(f"Changes         : {'; '.join(changes)}")
        return "\n".join(msg_lines)
    

    def action_done(self):

        for line in self:
            if line.state == 'done':
                continue
            production = line.production_id
            if not production:
                raise UserError("Production record not found!")
            if not production.picking_type_id:
                raise UserError("Operation Type is required in Production Details.")
            if not production.location_id:
                raise UserError("Source Location is required in Production Details.")
            if not production.location_dest_id:
                raise UserError("Destination Location is required in Production Details.")
            previous_state = line.state
            line.state = 'done'
            product = self.env['product.product'].sudo().search(
                [('product_tmpl_id.egg_type', '=', line.egg_type)],
                limit=1
            )
            if not product:
                raise UserError(f"No product found for egg type {line.egg_type}")
            

            picking = self.env['stock.picking'].sudo().create({
                'picking_type_id': production.picking_type_id.id,
                'location_id': production.location_id.id,
                'location_dest_id': production.location_dest_id.id,
                'origin': production.name,
                'scheduled_date': line.date,
                'company_id': self.env.company.id,
            })

            move = self.env['stock.move'].sudo().create({
                'name': f"Egg {line.egg_type}",
                'product_id': product.id,
                'product_uom_qty': line.value,
                'product_uom': product.uom_id.id,
                'picking_id': picking.id,
                'location_id': production.location_id.id,
                'location_dest_id': production.location_dest_id.id,
                'company_id': self.env.company.id,
                'date': line.date, 
            })

            picking.action_confirm()

            self.env['stock.move.line'].sudo().create({
                'move_id': move.id,
                'picking_id': picking.id,
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'qty_done': line.value,
                'location_id': production.location_id.id,
                'location_dest_id': production.location_dest_id.id,
                'company_id': self.env.company.id,
            })
            
            picking.with_context(force_period_date=line.date).button_validate()
            picking.sudo().write({
                'date_done': line.date,
            })
            
            move.sudo().write({
                'date': line.date,
            })

            msg = line._format_plain_message(
                action="Egg Line Marked as Done",
                previous_state=previous_state
            )
            production.message_post(body=msg)


    def unlink(self):
        for record in self:
            if record.state == 'done':
                raise UserError("You cannot delete an Egg Line marked as Done!")
            if record.production_id:
                msg = record._format_plain_message(action="Egg Line Deleted")
                record.production_id.message_post(body=msg)
        return super(EggLine, self).unlink()

    def write(self, vals):
        tracked_fields = ['egg_type', 'value', 'date', 'state', 'product_id', 'short_description']
        for line in self:
            changes = []
            previous_state = line.state
            for field in tracked_fields:
                if field in vals:
                    old_val = line[field]
                    new_val = vals[field]

                    if isinstance(line._fields[field], fields.Many2one):
                        comodel = line._fields[field].comodel_name
                        new_val_display = self.env[comodel].browse(new_val).name if new_val else False
                        old_val_display = old_val.name if old_val else False
                    else:
                        new_val_display = new_val
                        old_val_display = old_val

                    if old_val_display != new_val_display:
                        changes.append(f"{field.replace('_', ' ').title()}: '{old_val_display}' → '{new_val_display}'")

            res = super(EggLine, self).write(vals)

            if changes and line.production_id:
                msg = line._format_plain_message(
                    action="Egg Line Updated",
                    changes=changes,
                    previous_state=previous_state
                )
                line.production_id.message_post(body=msg)

        return res

    @api.model
    def create(self, vals):
        record = super(EggLine, self).create(vals)
        if record.production_id:
            msg = record._format_plain_message(action="New Egg Line Created")
            record.production_id.message_post(body=msg)
        return record

    @api.onchange('egg_type')
    def _onchange_egg_type(self):
        for record in self:
            if record.egg_type:
                product = self.env['product.template'].search([('egg_type', '=', record.egg_type)], limit=1)
                record.product_id = product.id if product else False


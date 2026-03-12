import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

# -----------------------
# Setter Machine
# -----------------------
class SetterMachine(models.Model):
    _name = 'hatchery.setter.machine'
    _description = 'Setter Machine'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True, tracking=True)
    capacity = fields.Integer(default=100000, tracking=True)

    # Stages linked to this machine
    setter_stage_ids = fields.One2many(
        'hatchery.setter.stage',
        'machine_id',
        string="Setter Stages"
    )

    # Current batch assigned to this machine (auto-picked from latest stage)
    egg_batch_id = fields.Many2one(
        'hatchery.egg.batch',
        string="Egg Batch",
        tracking=True
    )

    # Total available eggs for this machine (sum of stage qty_available for the latest batch)
    available_qty = fields.Integer(
        compute="_compute_available_qty",
        store=True,
        string="Available Eggs"
    )

    # Racks generated dynamically for the latest batch
    rack_ids = fields.One2many(
        'hatchery.setter.stage.rack',
        'machine_id',
        string="Racks",
        store=True,
        compute="_compute_racks"
    )

    # -----------------------
    # Compute Methods
    # -----------------------
    @api.depends('setter_stage_ids.qty_available', 'setter_stage_ids.state', 'setter_stage_ids.batch_id')
    def _compute_available_qty(self):
      for machine in self:
        # Filter only active stages
        active_stages = machine.setter_stage_ids.filtered(
            lambda s: s.state in ['in_setter', 'ready_for_hatcher']
        )

        if not active_stages:
            # No active stages → reset machine
            machine.egg_batch_id = False
            machine.available_qty = 0
            # Remove all racks
            machine.rack_ids.unlink()
            continue

        # Pick the stage with the highest ID (latest created)
        latest_stage = max(active_stages, key=lambda s: s.id)
        new_batch = latest_stage.batch_id

        # If batch changed, delete previous batch racks
        if machine.egg_batch_id != new_batch:
            machine.rack_ids.unlink()

        machine.egg_batch_id = new_batch

        # Sum only stages for that batch and still active
        stages_for_batch = machine.setter_stage_ids.filtered(
            lambda s: s.batch_id == machine.egg_batch_id
            and s.state in ['in_setter', 'ready_for_hatcher']
        )
        machine.available_qty = sum(stages_for_batch.mapped('qty_available'))

        # Debug log - using batch_no since _rec_name is batch_no
        _logger.info(
            "Machine %s latest batch: %s, available_qty: %s",
            machine.name,
            machine.egg_batch_id.batch_no if machine.egg_batch_id else "None",
            machine.available_qty
        )


    @api.depends('available_qty', 'egg_batch_id')
    def _compute_racks(self):
        rack_capacity = 10000  # Eggs per rack
        for machine in self:
            total_eggs = machine.available_qty or 0

            # Delete only racks for the current batch
            if machine.egg_batch_id:
                machine.rack_ids.filtered(
                    lambda r: r.batch_id == machine.egg_batch_id
                ).unlink()

            racks_to_create = []
            if total_eggs > 0:
                full_racks = total_eggs // rack_capacity
                remainder = total_eggs % rack_capacity

                # Create full racks
                for i in range(full_racks):
                    racks_to_create.append({
                        'rack_no': f'Rack {i + 1}',
                        'qty': rack_capacity,
                        'machine_id': machine.id,
                        'batch_id': machine.egg_batch_id.id
                    })

                # Create partial rack if remainder exists
                if remainder > 0:
                    racks_to_create.append({
                        'rack_no': f'Rack {full_racks + 1}',
                        'qty': remainder,
                        'machine_id': machine.id,
                        'batch_id': machine.egg_batch_id.id
                    })

                # Create racks in DB
                self.env['hatchery.setter.stage.rack'].create(racks_to_create)


# -----------------------
# Setter Stage Rack
# -----------------------
class SetterStageRack(models.Model):
    _name = 'hatchery.setter.stage.rack'
    _description = 'Setter Stage Rack'

    rack_no = fields.Char(string="Rack No")
    machine_id = fields.Many2one('hatchery.setter.machine', string="Setter Machine")
    batch_id = fields.Many2one('hatchery.egg.batch', string="Egg Batch")
    qty = fields.Integer(string="Egg Quantity")
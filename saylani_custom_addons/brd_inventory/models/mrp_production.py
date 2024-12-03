from odoo import fields, api, models

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    user_id = fields.Many2one(string='Preparer', readonly=True)
    inventory_code = fields.Char(string='Inventory Code')
    unit_id = fields.Many2one('uom.uom',string='Unit of Measure')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'HOD Approval'),
        ('confirmed', 'Approved'),
        ('progress', 'In Progress'),
        ('to_close', 'To Close'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')], string='State',
        compute='_compute_state', copy=False, index=True, readonly=True,
        store=True, tracking=True,
        help=" * Draft: The MO is not confirmed yet.\n"
             " * HOD Approval: HOD Approval is Pending.\n"
             " * Approved: The MO is confirmed, the stock rules and the reordering of the components are trigerred.\n"
             " * In Progress: The production has started (on the MO or on the WO).\n"
             " * To Close: The production is done, the MO has to be closed.\n"
             " * Done: The MO is closed, the stock moves are posted. \n"
             " * Cancelled: The MO has been cancelled, can't be confirmed anymore.")


    @api.onchange('product_id')
    def onchange_product_id(self):
        self.inventory_code = self.product_id.default_code
        self.unit_id = self.product_id.uom_id


    def action_hod_approval(self):
        self.write({'state': 'to_approve'})

    def action_confirm(self):
        res = super(MrpProduction, self).action_confirm()

        # quant_vals = {
        #     'location_id': self.warehouse_loc_id.id,
        #     'product_id': self.product_id.id,
        #     'product_uom_id': self.unit_id.id,
        #     'company_id': self.company_id.id,
        # }
        #
        # existing_quant = self.env['stock.quant'].search(quant_vals, limit=1)
        #
        # if existing_quant:
        #     existing_quant.sudo().write({'quantity': existing_quant.quantity + self.product_qty})
        # else:
        #     quant_vals['quantity'] = self.product_qty
        #     self.env['stock.quant'].create(quant_vals)

        self.write({'state': 'confirmed'})
        return res

    # def action_confirm(self):
    #     res = super(MrpProduction, self).action_confirm()
    #
    #     quant_vals = {
    #         'location_id': self.warehouse_loc_id.id,
    #         'product_id': self.product_id.id,
    #         'product_uom_id': self.unit_id.id,
    #         'company_id': self.company_id.id,
    #         'quantity': self.product_qty,
    #     }
    #
    #     self.env['stock.quant'].create(quant_vals)
    #     self.write({'state': 'confirmed'})
    #     return res

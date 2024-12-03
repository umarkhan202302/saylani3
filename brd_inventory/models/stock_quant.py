from odoo import fields, api, models

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    is_pr_required = fields.Boolean(compute='_calculate_pr_required')

    def _calculate_pr_required(self):
        for rec in self:
            if rec.available_quantity < 0:
                rec.is_pr_required = True
            else:
                rec.is_pr_required = False

    def button_purchase_request(self):

        default_values = {
            'description': 'This is a default description for the purchase request.',
            'product_id': self.product_id.id,
            'product_desc': self.product_id.name,
            'product_qty': abs(self.available_quantity),
            'product_uom_id': self.product_id.uom_id.id
        }
        default_line = [(0, 0, {
            'product_id': default_values['product_id'],
            'name': default_values['product_desc'],
            'product_qty': default_values['product_qty'],
            'product_uom_id': default_values['product_uom_id']
        })]

        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Request',
            'res_model': 'purchase.request',
            'view_mode': 'form',
            'view_type': 'form',
            'context': {
                'default_description': default_values.get('description'),
                'default_line_ids': default_line
            },
            'target': 'current',
        }
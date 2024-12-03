from odoo import models, fields, api

category_type = [
    ('livestock_vendor', 'Livestock Vendor'),
    ('food_vendor', 'Food & Ration Vendor'),
    ('medical_vendor', 'Medicine & Medical Accessories Vendor'),
    ('contract_vendor', 'Service providers / Contractors'),
    ('capex_vendor', 'CAPEX Vendor'),
    ('other_vendor', 'Other')
]

class ResPartner(models.Model):
    _inherit = 'res.partner'

    category_type = fields.Selection(selection=category_type, string='Type', default='livestock_vendor')

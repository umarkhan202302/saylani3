from odoo import fields, api, models,_
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError


class MfdLoanRequest(models.Model):
    _name = 'mfd.loan.request'
    _description = 'Microfinance Loan Request'

    name = fields.Char(string="Name", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    asset_type = fields.Selection([('cash', 'Cash'), ('asset', 'Asset')], string='Asset Type', default='cash')
    customer_id = fields.Many2one('res.partner', 'Customer')
    product_id = fields.Many2one('product.product', string='Asset')
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id.id)
    amount = fields.Monetary('Amount', currency_field='currency_id')
    disbursement_date = fields.Date('Disbursement Date')
    installment_period = fields.Integer('Installment Period (in Months)', default=1, help="Total duration of the installment plan in months")
    asset_availability = fields.Selection([('not_available', 'Not Available'), ('available', 'Available')], compute='_compute_asset_availablity', string='Asset Availability')
    warehouse_loc_id = fields.Many2one('stock.location', 'Warehouse/Location')
    loan_reqeust_lines = fields.One2many('mfd.loan.request.line', 'loan_request_id')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'HOD Approval'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('rejected', 'Rejected')],
        string='State',
        default='draft',
        compute='_compute_state', copy=False, index=True, readonly=True,
        store=True, tracking=True,
        help=" * Draft: The MFD Loan is not confirmed yet.\n"
             " * HOD Approval: HOD Approval is Pending.\n"
             " * Approved: The MFD Loan is approved, handover of asset to customer is Pending.\n"
             " * Done: Asset Hand Overed to customer\n"
             " * Done: MFD Loan Approval Rejected\n")

    def _compute_asset_availablity(self):
        if self.product_id:
            available_qty = self.product_id.qty_available
            if available_qty > 0:
                self.asset_availability = 'available'
            else:
                self.asset_availability = 'not_available'
        else:
            self.asset_availability = 'not_available'

    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('mfd.loan.request') or ('New')
        return super().create(vals)


    @api.onchange('product_id')
    def onchange_product(self):
        self.amount = self.product_id.lst_price

        available_qty = self.product_id.qty_available

        if available_qty > 0:
            self.asset_availability = 'available'
        else:
            self.asset_availability = 'not_available'

    def action_to_approve(self):
        if self.asset_type == 'asset' and self.asset_availability == 'not_available':
            raise UserError('Asset is not Available')
        else:
            self.write({'state': 'to_approve'})

    def action_approved(self):
        self.write({'state': 'approved'})

    def action_done(self):
        if self.asset_type == 'asset':
            product_quantity = self.product_id.qty_available
            if product_quantity > 0:
                stock_quant = self.env['stock.quant'].search([
                    ('location_id', '=', self.warehouse_loc_id.id),
                    ('product_id', '=',  self.product_id.id),
                    ('inventory_quantity_auto_apply', '>', 0)
                ], limit=1)

                if not stock_quant:
                    raise UserError('Stock is not available in that location. Kindly select another location')
                else:
                    stock_move = self.env['stock.move'].create({
                        'name': f'Decrease stock for Loan {self.name}',
                        'product_id': self.product_id.id,
                        'product_uom': self.product_id.uom_id.id,
                        'product_uom_qty': 1,  # Decrease 1 unit
                        'location_id': self.warehouse_loc_id.id,  # Source location (stock)
                        'location_dest_id': self.env.ref('stock.stock_location_customers').id,
                        'state': 'draft',  # Initial state is draft
                    })
                    picking = self.env['stock.picking'].create({
                        'partner_id': self.customer_id.id,  # Link to customer
                        'picking_type_id': self.env.ref('stock.picking_type_out').id,  # Outgoing picking type
                        'move_ids_without_package': [(6, 0, [stock_move.id])],  # Associate the stock move with the picking
                        'origin': self.name
                    })
                    stock_move._action_confirm()
                    stock_move._action_assign()
                    picking.action_confirm()
                    picking.button_validate()

            else:
                self.write({'asset_availability': 'not_available'})
                raise UserError('Not enough stock available')
        self.write({'state': 'done'})

    def action_rejected(self):
        self.write({'state': 'rejected'})

    def compute_installment(self):
        if self.amount <= 0 or self.installment_period <= 0:
            return False

        self.loan_reqeust_lines.unlink()

        monthly_amount = self.amount / self.installment_period

        for i in range(self.installment_period):
            due_date = self.disbursement_date + relativedelta(months=i + 1)
            self.env['mfd.loan.request.line'].create({
                'loan_request_id': self.id,
                'installment_number': i + 1,
                'installment_id': str(self.name) + '/00' + str(i+1),
                'due_date': due_date,
                'amount': monthly_amount,
            })



class MfdLoanRequestInstallment(models.Model):
    _name = 'mfd.loan.request.line'
    _description = 'Microfinance Loan Request Installment'

    loan_request_id = fields.Many2one('mfd.loan.request', string='Loan Id', required=True, ondelete='cascade')
    loan_state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'HOD Approval'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('rejected', 'Rejected')], related='loan_request_id.state')
    installment_number = fields.Integer('Installment Number', required=True)
    installment_id = fields.Char('Installment Id', required=True)
    due_date = fields.Date('Due Date', required=True)
    amount = fields.Monetary('Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', 'Currency', related='loan_request_id.currency_id', readonly=True)
    state = fields.Selection([
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid')],
        string='Status', default='unpaid', help=" * Unpaid: The installment is not paid yet.\n * Paid: The installment is paid.\n * Overdue: The installment is overdue.")
    payment_id = fields.Many2one('account.payment', string='Payment ID')
    is_payment_done = fields.Boolean(compute='_compute_check_payment_id')

    def create_pir(self):
        action = self.env.ref('microfinance_loan.action_mfd_pir_receipt').read()[0]
        form_view_id = self.env.ref('microfinance_loan.mfd_pir_receipt_form').id
        action['views'] = [
            [form_view_id, 'form']
        ]
        action['context'] = {
                'default_partner_id':  self.loan_request_id.customer_id.id,
                'default_amount': self.amount,
                'default_is_mfd_loan': True,
                'default_ref': self.installment_id
        }
        return action
        #
        # view_id = self.env.ref('microfinance_loan.mfd_pir_receipt_form').id
        # return {
        #     'type': 'ir.actions.act_window',
        #     'name': 'Installment Receipt',
        #     'res_model': 'account.payment',
        #     'view_mode': 'form',
        #     'view_type': 'form',
        #     'view_id': view_id,
        #     'context': {
        #         'default_partner_id':  self.loan_request_id.customer_id.id,
        #         'default_amount': self.amount,
        #         'default_is_mfd_loan': True,
        #         'default_ref': self.installment_id
        #     },
        #     'target': 'current',
        # }

    def go_to_pir(self):
        action = self.env.ref('microfinance_loan.action_mfd_pir_receipt').read()[0]
        tree_view_id = self.env.ref('microfinance_loan.mfd_pir_receipt_tree').id
        form_view_id = self.env.ref('microfinance_loan.mfd_pir_receipt_form').id
        action['views'] = [
            [tree_view_id, 'tree'],
            [form_view_id, 'form']
        ]
        action['domain'] = [('ref', '=', self.installment_id)]
        return action


    def _compute_check_payment_id(self):
        for rec in self:
            payment = self.env['account.payment'].search([
                ('ref', '=' , rec.installment_id)
            ], limit=1)
            if payment:
                rec.is_payment_done = True
                rec.payment_id = payment.id
            else:
                rec.is_payment_done = False



class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_mfd_loan = fields.Boolean()
    payment_choice = fields.Selection([('cash', 'Cash'), ('cheque', 'Cheque')], string='Payment Type', default='cash')
    mfd_bank_id = fields.Many2one('mfd.bank', string='Bank Name')
    account_number = fields.Char(string='Account Number')
    cheque_number = fields.Char(string='Cheque Number')
    cheque_date = fields.Date(string='Cheque Date')
    status = fields.Selection([
        ('draft', 'Draft'),
        ('cheque_pending', 'Pending'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled'),
        ('cheque_bounced', 'Bounced')],
        string='Status',
        default='draft',
        copy=False, index=True, readonly=True,
        store=True, tracking=True,
        help=" * Draft: The MFD Loan is not confirmed yet.\n"
             " * HOD Approval: HOD Approval is Pending.\n"
             " * Approved: The MFD Loan is approved, handover of asset to customer is Pending.\n"
             " * Done: Asset Hand Overed to customer\n"
             " * Done: MFD Loan Approval Rejected\n")


    def action_cheque_pending(self):
        self.write({'status': 'cheque_pending'})

    def action_cheque_bounced(self):
        self.action_cancel()
        self.write({'status': 'cheque_bounced'})

    def confirm_payment(self):
        for rec in self:
            installment = self.env['mfd.loan.request.line'].search([
                ('installment_id', '=', rec.ref)
            ], limit=1)
            if installment:
                installment.state = 'paid'
        self.action_post()
        self.write({'status': 'posted'})

    def action_cancel(self):
        res = super(AccountPayment, self).action_cancel()
        self.write({'status': 'cancel'})
        return res

    def action_redeposit_cheque(self):
        action = self.env.ref('microfinance_loan.action_mfd_pir_receipt').read()[0]
        form_view_id = self.env.ref('microfinance_loan.mfd_pir_receipt_form').id
        action['views'] = [
            [form_view_id, 'form']
        ]
        action['context'] = {
            'default_partner_id': self.partner_id.id,
            'default_amount': self.amount,
            'default_is_mfd_loan': True,
            'default_ref': self.ref,
            'default_payment_choice': self.payment_choice
        }
        return action
        # view_id = self.env.ref('microfinance_loan.mfd_pir_receipt_form').id
        # return {
        #     'type': 'ir.actions.act_window',
        #     'name': 'Installment Receipt',
        #     'res_model': 'account.payment',
        #     'view_mode': 'form',
        #     'view_type': 'form',
        #     'view_id': view_id,
        #     'context': {
        #         'default_partner_id': self.partner_id.id,
        #         'default_amount': self.amount,
        #         'default_is_mfd_loan': True,
        #         'default_ref': self.ref,
        #         'default_payment_choice': self.payment_choice
        #     },
        #     'target': 'current',
        # }



class MfdBank(models.Model):
    _name  = 'mfd.bank'

    name = fields.Char(string='Name')
    is_active = fields.Boolean(string='Active')



from odoo import models, fields, api, _


class HRAttendance(models.Model):
    _inherit = 'hr.attendance'

    # Adding a new field to store the employee's ID in the biometric device
    hikvision_id = fields.Many2one('hr.hikvision', string='Hikvision Device', help='Hikvision Device ID', related='employee_id.hikvision_id', readonly=True)
    biometric_id = fields.Char(string='Biometric ID', help='ID of the employee in the biometric device', related='employee_id.biometric_id', store=True, readonly=True)
    check_in_time = fields.Char(string='Check In', compute='_compute_check_in_time')
    check_out_time = fields.Char(string='Check Out', compute='_compute_check_out_time')
    check_in_visible = fields.Char(string="Check In", compute='_compute_check_in_visible',store = False)
    show_check_in = fields.Boolean(string='check in box', readonly=True, default=True)
    check_in = fields.Datetime(string='Check In', help='Check In time', required=False, index=True, copy=False)

    @api.depends('check_in')
    def _compute_check_in_time(self):
        for record in self:
            if record.check_in:
                # Convertir a la zona horaria del usuario
                local_time = fields.Datetime.context_timestamp(record, record.check_in)
                record.check_in_time = local_time.strftime('%H:%M:%S')  # Formato de hora: %H:%M:%S
            else:
                record.check_in_time = ''
    @api.depends('check_out')
    def _compute_check_out_time(self):
        for record in self:
            if record.check_out:
                # Convertir a la zona horaria del usuario
                local_time = fields.Datetime.context_timestamp(record, record.check_out)
                record.check_out_time = local_time.strftime('%H:%M:%S')  # Formato de hora: %H:%M:%S
            else:
                record.check_out_time = ''

    @api.depends('show_check_in','check_in')
    def _compute_check_in_visible(self):
         for record in self:
            if record.show_check_in:
                local_time = fields.Datetime.context_timestamp(record, record.check_in)
                record.check_in_visible = local_time.strftime('%H:%M:%S')
            else:
                record.check_in_visible = ''

    def _check_validity(self):
        # Sobrescribir y NO hacer nada
        pass
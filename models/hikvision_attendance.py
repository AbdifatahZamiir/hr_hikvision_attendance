import odoo
from odoo import models, fields, api

class HikvisionAttendance(models.Model):
    """Model to hold data from the Hikvision attendance device"""
    _name = 'hr.hikvision.attendance'
    _description = 'Hikvision Attendance'
    _inherit = 'hr.attendance'

    @api.constrains('check_in', 'check_out', 'employee_id')
    def _check_validity(self):
        """Overriding the __check_validity function for employee attendance."""
        pass
    
    device_id = fields.Many2one('hr.hikvision', string='Hikvision Device',
                                help="The Hikvision device that recorded the attendance",
                                ondelete='set null')
    device_id_num = fields.Char(string='Hikvision Device ID',
                                help="The ID of the Hikvision Device")
    punch_type = fields.Char(string='Punch Type',
                             help="The type of punch (Check In/Check Out)")
    employee_id = fields.Many2one('hr.employee', string='Employee',
                                   help="The employee who punched in/out")
    attendance_type = fields.Char(string='Attendance Type',
                                  help="The type of attendance (Finger/Face/Password/Card)")
    punching_time = fields.Datetime(string='Punching Time',
                                    help="The time of the punch")
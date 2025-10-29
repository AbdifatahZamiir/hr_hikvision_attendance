### -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# © 2023 Grupo SIRYT (http://www.siryt.com)
import logging
from datetime import datetime, time, timedelta
from dateutil import parser
from odoo import models, fields, _
from odoo.exceptions import UserError
import pytz
from ..services.hikvision import Hikvision

_logger = logging.getLogger(__name__)

class HikvisionDownloadWizard(models.TransientModel):
    """
    This class defines a wizard for downloading attendance data from Hikvision devices.
    It allows the user to select a date range and download attendance records in Excel format.
    """
    _name = 'hikvision.download.wizard'
    _description = 'Hikvision Download Wizard'

    date_start = fields.Datetime(string='Start Date', required=True)
    date_end = fields.Datetime(string='End Date', required=True)

    device_ip = fields.Char(string="IP", readonly=True)
    device_port = fields.Integer(string="Port", readonly=True)
    device_user = fields.Char(string="User", readonly=True)
    device_password = fields.Char(string="Password", readonly=True)


    def action_get_attendance(self):
        _logger.info("==========Trying to get attendance from Hikvision device==========")

        if not self.date_start or not self.date_end:
            raise UserError(_('Please fill in all required fields.'))
        if self.date_start >= self.date_end:
            raise UserError(_('From date must be less than to date.'))
        if not self.device_ip or not self.device_port or not self.device_password or not self.device_user:
            raise UserError(_('Please fill in all required fields.'))

        conn = Hikvision(self.device_ip, self.device_port, self.device_user, self.device_password)
        attendance_d = self.env['hr.hikvision.attendance']
        hr_att = self.env['hr.attendance']
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')

        from_local = self.date_start + timedelta(hours=3)
        to_local = self.date_end + timedelta(hours=3)
        formatted_local_f = from_local.strftime("%Y-%m-%dT%H:%M:%S")
        formatted_local_t = to_local.strftime("%Y-%m-%dT%H:%M:%S")

        if not conn.connect():
            raise UserError(_('Failed to connect to the device.'))

        attendance = conn.get_attendance(from_date=formatted_local_f, to_date=formatted_local_t)
        if not attendance:
            raise UserError(_('No attendance found for the given dates.'))
        _logger.info(f"INICIOOO: {formatted_local_f}")
        _logger.info(f"FIIIINNN: {formatted_local_t}")

        _logger.info(f"Total attendance records: {len(attendance)}")

        for each in attendance:
            time_a = each.get("time")
            local_dt = parser.isoparse(time_a)

            biometric_id = each["employeeNoString"]
            employee = self.env['hr.employee'].search([('biometric_id', '=', biometric_id)], limit=1)

            if not employee:
                device_id = self.env['hr.hikvision'].search([
                    ('is_public', '=', True),
                    ('local_ip', '=', self.device_ip)
                ], limit=1) or self.env['hr.hikvision'].search([('device_ip', '=', self.device_ip)], limit=1)
                employee = self.env['hr.employee'].create({
                    'name': each["name"],
                    'hikvision_id': device_id.id,
                    'biometric_id': biometric_id
                })

            employee_tz = pytz.timezone(employee.tz or 'UTC')
            local_dt = local_dt.astimezone(employee_tz)
            utc_dt = local_dt.astimezone(pytz.utc)
            time_a_str = fields.Datetime.to_string(utc_dt)

            metod = "Face" if "FaceRect" in each else "Fingerprint"

            # Evitar duplicados cercanos
            tolerance = timedelta(minutes=10)
            range_start = local_dt - tolerance
            range_end = local_dt + tolerance

            nearby_raw = attendance_d.search([
                ('employee_id', '=', employee.id),
                ('punching_time', '>=', fields.Datetime.to_string(range_start.astimezone(pytz.utc))),
                ('punching_time', '<=', fields.Datetime.to_string(range_end.astimezone(pytz.utc))),
            ], limit=1)

            if nearby_raw:
                _logger.info(f"[IGNORED] Attendance close or duplicated for {employee.name} at {time_a_str}")
                continue

            # Guardar asistencia cruda
            attendance_d.create({
                'device_id': employee.hikvision_id.id,
                'device_id_num': biometric_id,
                'employee_id': employee.id,
                'punch_type': "Unknown",
                'attendance_type': metod,
                'punching_time': time_a_str
            })

            # === Lógica de check_in / check_out estricta ===
            calendar = employee.resource_calendar_id
            if not calendar:
                _logger.warning(f"[WITHOUT CALENDAR] The employee {employee.name} doesen't have resource.calendar assigned")
                continue

            day_of_week = str(local_dt.weekday())
            attendances = calendar.attendance_ids.filtered(lambda a: a.dayofweek == day_of_week)

            work_intervals = []
            for att in attendances:
                hour_from = int(att.hour_from)
                min_from = int((att.hour_from - hour_from) * 60)
                hour_to = int(att.hour_to)
                min_to = int((att.hour_to - hour_to) * 60)

                start_dt = local_dt.replace(hour=hour_from, minute=min_from, second=0, microsecond=0)
                end_dt = local_dt.replace(hour=hour_to, minute=min_to, second=0, microsecond=0)

                if att.hour_to < att.hour_from:
                    end_dt += timedelta(days=1)

                work_intervals.append((start_dt, end_dt))

            inside_work = any(start <= local_dt <= end for start, end in work_intervals)
            event_day = local_dt.date()

            # Buscar check_in existente en ese día LOCAL
            start_day_local = employee_tz.localize(datetime.combine(event_day, time.min))
            end_day_local = employee_tz.localize(datetime.combine(event_day, time.max))

            check_in_same_day = hr_att.search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', fields.Datetime.to_string(start_day_local.astimezone(pytz.utc))),
                ('check_in', '<=', fields.Datetime.to_string(end_day_local.astimezone(pytz.utc))),
            ], limit=1)

            open_attendance = hr_att.search([
                ('employee_id', '=', employee.id),
                ('check_out', '=', False)
            ], order='check_in desc', limit=1)

            if inside_work:
                if not check_in_same_day:
                    _logger.info(f"[CHECK IN] {employee.name} at {time_a_str}")
                    hr_att.create({
                        'employee_id': employee.id,
                        'check_in': time_a_str
                    })
                else:
                    _logger.info(f"[IGNORED] Duplicate check_in in same work day for {employee.name}")
            else:
                if open_attendance:
                    check_in_local = open_attendance.check_in.astimezone(employee_tz)
                    check_in_day = check_in_local.date()

                    # Aceptar check_out si es el mismo día o máximo al día siguiente antes de X hora
                    if event_day == check_in_day:
                        _logger.info(f"[CHECK OUT] {employee.name} at {time_a_str}")
                        open_attendance.write({'check_out': time_a_str})
                    else:
                        # Permitir check_out hasta 5am del día siguiente si fue un turno largo
                        if event_day == (check_in_day + timedelta(days=1)) and local_dt.time() <= time(5, 0):
                            _logger.info(f"[LATE CHECK OUT] {employee.name} at {time_a_str} (previous day's session)")
                            open_attendance.write({'check_out': time_a_str})
                        else:
                            _logger.warning(f"[IGNORED] check_out not matching check_in day for {employee.name}")
                else:
                    _logger.info(f"[IGNORED] No open attendance to close for {employee.name}")

        return True


    def convert_to_utc_datetime(self, dt, user_tz_name):
        """
        Convert a datetime object to UTC timezone.
        :param dt: datetime object
        :param user_tz_name: string name of the user's timezone
        :return: datetime object in UTC timezone
        """
        user_tz = pytz.timezone(user_tz_name or 'UTC')

        if isinstance(dt, str):
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")

        if dt.tzinfo is not None:
            dt = user_tz.localize(dt)
        else:
            dt = dt.astimezone(user_tz)
        return dt

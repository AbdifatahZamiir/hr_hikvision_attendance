import logging
import json
import pytz
from dateutil import parser
from odoo import http, fields, _
from odoo.fields import Datetime
from odoo.http import request, Response
import base64
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from ..services.hikvision import Hikvision
from datetime import datetime, time, timedelta

TOKEN_EXPIRATION = 10 ## seconds
_logger = logging.getLogger(__name__)

class FaceImageController(http.Controller):

    @http.route('/face/image/<token>', auth='public', type='http', cors='*')
    def get_face_image(self, token, **kwargs):
        """
        
        This method retrieves the face image of an employee based on the provided token.
        The token is expected to be a URL-safe, timed serializer token that contains the employee ID.

        """
        secret_key = kwargs.get('secret_key')
        if not secret_key:
            return Response("Token faltante", status=403)

        try:
            serializer = URLSafeTimedSerializer(secret_key)
            employee_id = serializer.loads(token, max_age=TOKEN_EXPIRATION)
            employee = request.env['hr.employee'].sudo().browse(int(employee_id))
            if employee.exists() and employee.image_1920:
                image_data = base64.b64decode(employee.image_1920)
                return Response(image_data, headers=[('Content-Type', 'image/jpg')])
        except SignatureExpired:
            return Response("Token expirado", status=403)
        except BadSignature:
            return Response("Token inválido", status=403)

        return Response(status=404)

class HikvisionController(http.Controller):
    """
    Controller for handling Hikvision attendance-related requests.
    """

    @http.route('/event', type='http', auth='public', methods=['POST'], csrf=False)
    def receive_event(self, **kwargs):
        """
        This method receives attendance events from Hikvision devices.
        It expects a POST request with a JSON payload containing the event data.
        """
        req = request.httprequest
        # Extraer el campo del formulario que contiene el JSON como string
        if req.form.get('AccessControllerEvent'):
            raw_event = req.form.get('AccessControllerEvent')
        elif req.form.get('event_log'):
            raw_event = req.form.get('event_log')
        else:
            _logger.error("No valid event data found in the request")
            return Response("No valid event data found", status=400)

        try:
            if json.loads(raw_event) and json.loads(raw_event).get('AccessControllerEvent') and \
            (json.loads(raw_event).get('AccessControllerEvent').get('FaceRect') or \
            json.loads(raw_event).get('AccessControllerEvent').get('label')):
                data = json.loads(raw_event)
                ip_device = data.get('ipAddress')
                nested_event = data.get('AccessControllerEvent', {})
                date_time = data.get('dateTime')
                name = nested_event.get('name')
                employee_no = nested_event.get('employeeNoString')
                face_rect = nested_event.get('FaceRect', {})
                label = nested_event.get('label')
                local_t = parser.isoparse(date_time)
                utc_t = local_t.astimezone(pytz.utc)
                time_a = fields.Datetime.to_string(utc_t)
                method = ""
                is_public = request.env['hr.hikvision'].sudo().search([('is_public', '=', True)])
                if is_public:
                    for device in is_public:
                        if device.local_ip == ip_device:
                            device_id = device
                            break
                else:
                    device_id = request.env['hr.hikvision'].sudo().search([('device_ip', '=', ip_device)], limit=1)
                attendance_d = request.env['hr.hikvision.attendance'].sudo()
                hr_att = request.env['hr.attendance'].sudo()
                employees = request.env['hr.employee'].sudo()
                conn = Hikvision(device_id.device_ip, device_id.port, device_id.device_user, device_id.device_password)
                if conn:
                    if face_rect:
                        method = "Face"
                    employee = employees.search([
                        ('biometric_id', '=', employee_no)], limit=1)
                    if employee:
                        atten_duplicate_ids = attendance_d.search([
                            ('device_id_num', '=', employee.id),
                            ('punching_time', '=', time_a)])
                        if not atten_duplicate_ids:
                            dt_with_tz = parser.isoparse(time_a)  # time_a es string con tzinfo
                            user_tz = pytz.timezone(request.env.user.tz or 'UTC')
                            local_dt = dt_with_tz.astimezone(user_tz)
                            local_date = local_dt.date()
                            if local_dt.time() < time(4, 0):
                                # Si la hora es antes de las 04:00, consideramos el día anterior
                                local_date = local_date - timedelta(days=1)
                            start_day_local = datetime.combine(local_date, time(0, 0))
                            end_day_local = datetime.combine(local_date, time(23, 59, 59))
                            start_day_utc = user_tz.localize(start_day_local).astimezone(pytz.utc)
                            end_day_utc = user_tz.localize(end_day_local).astimezone(pytz.utc)
                            check_in_record = hr_att.search([
                                    ('employee_id', '=', employee.id),
                                    ('check_in', '>=', fields.Datetime.to_string(start_day_utc)),
                                    ('check_in', '<=', fields.Datetime.to_string(end_day_utc)),
                                ], limit=1)
                            if label == "Check In" or label == "Check Out":
                            # Crear o actualizar el registro de asistencia
                                attendance_d.create({
                                    'device_id': device_id.id,
                                    'device_id_num': employee_no,
                                    'employee_id': employee.id,
                                    'punch_type': label,
                                    'attendance_type': "Face" if method == "Face" else "finger",
                                    'punching_time': time_a
                                })
                            if label == "Check In":
                                if not check_in_record:
                                    hr_att.create({
                                        'employee_id': employee.id,
                                        'check_in': time_a,
                                    })
                                _logger.info("Attendance event processed successfully")
                                return "Event processed successfully"
                            if label == "Check Out":
                                # Buscar check_in sin check_out para el mismo día
                                check_ino_record = hr_att.search([
                                    ('employee_id', '=', employee.id),
                                    ('check_in', '>=', fields.Datetime.to_string(start_day_utc)),
                                    ('check_in', '<=', fields.Datetime.to_string(end_day_utc)),
                                    ('check_out', '=', False),
                                ], limit=1)
                                check_out_record = hr_att.search([
                                    ('employee_id', '=', employee.id),
                                    ('check_out', '>=', fields.Datetime.to_string(start_day_utc)),
                                    ('check_out', '<=', fields.Datetime.to_string(end_day_utc)),
                                ], limit=1)
                                if check_ino_record:
                                    # Si hay check_in del mismo día sin check_out, lo actualizamos
                                    check_in_record.write({
                                        'check_out': dt_with_tz.astimezone(pytz.utc).replace(tzinfo=None),
                                    })
                                    _logger.info("Check out agregado a asistencia existente del mismo día sin check_out")
                                elif not check_out_record or not check_ino_record:
                                    # No existe check_in ese día y tampoco no encuentra check_out's de ese mismo día, crear automático a las 08:00
                                    default_checkin_local = datetime.combine(local_date, time(8, 0))
                                    default_checkin_utc = user_tz.localize(default_checkin_local).astimezone(pytz.utc)

                                    hr_att.create({
                                        'employee_id': employee.id,
                                        'check_in': default_checkin_utc.replace(tzinfo=None),
                                        'check_out': dt_with_tz.astimezone(pytz.utc).replace(tzinfo=None),
                                        'show_check_in': False,
                                    })
                                    _logger.info("Check in automático creado a las 08:00 y check out agregado")
                    else:
                        if label == "Check In" or label == "Check Out":
                            employee = employees.create({
                                'hikvision_id': device_id.id,
                                'name': name,
                                'biometric_id': employee_no
                            })
                            attendance_d.create({
                                'device_id': employee.hikvision_id.id,
                                'device_id_num': employee_no,
                                'employee_id': employee.id,
                                'punch_type': label,
                                'attendance_type': "Face" if face_rect else "finger",
                                'punching_time': time_a
                            })
                            hr_att.create({
                                'employee_id': employee.id,
                                'check_in': time_a,
                            })
                            _logger.info("Attendance event processed successfully")
                            return "Event processed successfully"
                else:
                    _logger.error("Failed to connect to Hikvision device at %s", ip_device)
                    return "Failed to connect to device"
        except json.JSONDecodeError as e:
            _logger.error("Failed to parse JSON: %s", e)
            return "Invalid JSON format"


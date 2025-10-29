###
#
# EGPerezR
#
###
import logging
import secrets
from datetime import timedelta, datetime
import requests

from itsdangerous import URLSafeTimedSerializer
import pytz
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from ..services.hikvision import Hikvision

_logger = logging.getLogger(__name__)

class HikvisionDeviceDetails(models.Model):
    """ Model Device Specifications"""

    _name = 'hr.hikvision'
    _description = 'Hikvision Device Details'

    name = fields.Char(required=True, help='Name of the device', store=True)
    device_ip = fields.Char(string='Device IP',
                            required=True, default='127.0.0.1', store=True)
    local_ip = fields.Char(string='Local IP',
                            required=False, default='0.0.0.0', store=True)
    port= fields.Integer(string='Port',
                        required=True,
                        default=80,
                        help='Port of the device', store=True)
    is_public = fields.Boolean(string='Is Public',
                            required=False,
                            default=False,
                            help='Is the device public?', store=True)
    device_user = fields.Char(string='Device User',
                            required=True,
                            help='User for the device', store=True)
    device_password = fields.Char(string='Device Password',
                                required=True,
                                help='Password for the device', store=True)
    ubication = fields.Char(string='Ubication',
                            required=False,
                            help='Ubication of the device', store=True)
    from_date = fields.Datetime(string="From date",
                                required=False,
                                help='From what date begging the search')
    to_date = fields.Datetime(string="To date",
                            required=False,
                            help='To what date begging the search')

    @api.onchange('device_ip', 'port', 'device_user', 'device_password')
    def _onchange(self):
        """
        This method is triggered when any of the specified fields are changed.
        It can be used to validate or update other fields based on the changes.
        """
        if self.device_ip and not self.device_ip.strip():
            raise ValidationError(_("Device IP cannot be empty or whitespace."))
        if self.port and (self.port <= 0 or self.port > 65535):
            raise ValidationError(_("Port must be between 1 and 65535."))

    def action_device_connect(self):
        """
        Action to test the connection to the device.
        """
        if not self.device_ip or not self.port or not self.device_password or not self.device_user:
            raise UserError(_('Please fill in all required fields.'))
        hv = Hikvision(self.device_ip, self.port, self.device_user, self.device_password)
        try:
            if hv.connect():
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Successful'),
                        'message': 'Device connected successfully.',
                        'type': 'success',
                        'sticky': False
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Failed'),
                        'message': 'Failed to connect to the device. Please check the device data.',
                        'type': 'warning',
                        'sticky': False
                    }
                }
        except requests.exceptions.RequestException as error:
            _logger.info("Error: %s", error)
            return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Error'),
                        'message': 'Check the device data and try again. \n'
                                   f'device_ip: {self.device_ip} \n'
                                   f'port: {self.port}',
                        'type': 'warning',
                        'sticky': False
                    }
                }

    def validate_user(self, employee):
        """ Validate user to see if is already upload """
        if not self.device_ip or not self.port or not self.device_password or not self.device_user:
            conn = Hikvision(employee.hikvision_id.device_ip,
                            employee.hikvision_id.port,
                            employee.hikvision_id.device_user,
                            employee.hikvision_id.device_password)
        else:
            conn = Hikvision(self.device_ip, self.port, self.device_user, self.device_password)

        if conn:
            end_point = 'AccessControl/UserInfo/Search?format=json'
            search_user = {
                    "UserInfoSearchCond":{
                        "SearchID":"1",
                        "searchResultPosition":0,
                        "maxresults":32,
                        "EmployeeNoList":[
                            {
                                "employeeNo":str(employee.biometric_id)
                            }
                        ]
                    }
            }
            response = conn.user_exist(end_point,search_user)
            if response:
                return True
            else:
                return False

    def generate_general_token(self, employee_id, secret_key):
        """
        Generate a token for the employee.
        This token is used to access the employee's face image.
        """
        serializer = URLSafeTimedSerializer(secret_key)
        token = serializer.dumps(str(employee_id))
        return token

    def upload_user(self,employee):
        """ Function to upload each user to device """
        if not self.device_ip or not self.port or not self.device_password or not self.device_user:
            conn = Hikvision(employee.hikvision_id.device_ip,
                            employee.hikvision_id.port,
                            employee.hikvision_id.device_user,
                            employee.hikvision_id.device_password)
        else:
            conn = Hikvision(self.device_ip, self.port, self.device_user, self.device_password)
        base_url = 'AccessControl/UserInfo/Record?format=json'
        try:
            user_tz = self.env.context.get(
                        'tz') or self.env.user.tz or 'UTC'
            user_timezone_time = pytz.utc.localize(fields.Datetime.now())
            user_timezone_time = user_timezone_time.astimezone(
                pytz.timezone(user_tz))
            formatd = user_timezone_time.strftime("%Y-%m-%d")
            three = user_timezone_time + timedelta(days=3*365)
            formath = user_timezone_time.strftime("%H:%M:%S")
        except NameError as exc:
            raise UserError("Pyzk module not Found. Please install it"
                "with 'pip3 install pyzk'.") from exc
        if conn:
            user_image = employee.avatar_1920
            data = {
                "UserInfo":{
                    "employeeNo":str(employee.biometric_id),
                    "name":str(employee.name),
                    "userType":"normal",
                    "Valid": {
                        "enable": True,
                        "beginTime":_("%sT%s",formatd, formath),
                        "endTime":_("%sT%s",three.strftime("%Y-%m-%d"), formath),
                        "timeType":"local"
                    },
                    "doorRight": "1",
                    "RightPlan": [{"doorNo": 1, "planTemplateNo": "1"}],
                    "numOfFace":1,
                    "belonGroup":"",
                    "gender":str(employee.gender),
                    "groupId":employee.department_id.id
                }
            }
            response = conn.post_mode(base_url, data)
            if response:
                if user_image:
                    base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                    token = secrets.token_hex(16)
                    endpoint = 'Intelligent/FDLib/FaceDataRecord?format=json'
                    g_token = self.generate_general_token(employee.id, token)
                    j_face = {
                        "faceLibType":"blackFD",
                        "FDID":"1",
                        "FPID":str(employee.biometric_id),
                        "faceURL":str(base_url + "/face/image/" + g_token + "?secret_key=" + token),
                    }
                    try:
                        # Upload the image to the device
                        conn.upload_photo(endpoint, j_face)

                    except Exception as error:
                        _logger.error("Error: %s", error)
                        raise UserError(_('Failed to upload user image: %s') % (str(error))) from error
                return True
            else: return False

    def action_upload_users(self):
        """ Action to upload all the users from de hr.employee model """
        error_messajes = []
        success = 0
        _logger.info("==========Tring upload users to Hikvision device==========")
        employees = self.env['hr.employee'].search([])
        max_users = employees.search_count([])
        # Assuming we have a method to get the users to upload
        try:
            for employee in employees:
                if employee.biometric_id and employee.hikvision_id:
                    if self.validate_user(employee):
                        if self.upload_user(employee):
                            employee.write({
                                'hikvision_id': self.id
                            })
                            _logger.info(_("User: %s uploaded successfully"), employee.name)
                            success += 1
                        else:
                            _logger.info(_("User: %s can't be uploaded"), employee.name)
                    else:
                        _logger.info(_("User: %s already exists."), employee.name)
                        error_messajes.append(employee.name)
                else:
                    _logger.info(_("User: %s has no biometric_id or hikvision_id"), employee.name)
                    error_messajes.append(employee.name)
        except Exception as error:
            _logger.error("Error uploading user %s: %s",
                        employee.name, error)
            raise UserError(_('Failed to upload user %s: %s') % 
                        (employee.name, str(error))) from error
        if success > 0 and not error_messajes:
            _logger.info("All users uploaded successfully")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message':'All the users has been upload',
                    'type': 'success',
                    'sticky': False
                }
            }
        if error_messajes:
            _logger.info("Error uploading users")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Uploaded with users duplicated'),
                    'message': f'{error_messajes}\n',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        if success < max_users and success > 0:
            _logger.info("Not all users were uploaded")
            return [
                {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Warning'),
                        'message':'Not all the users were uploaded',
                        'type': 'warning',
                        'sticky': False
                    }
                },
                {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Usuarios duplicados'),
                        'message': '\n'.join(error_messajes),
                        'type': 'warning',
                        'sticky': False,
                    }
                }
            ]
        if success == 0:
            _logger.info("No users were uploaded")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Warning'),
                    'message':'No users were uploaded, probably all the users are already uploaded',
                    'type': 'warning',
                    'sticky': False
                }
            }

    def action_open_wizard(self):
        """
        Action to open the wizard for getting attendance.
        """
        return {
            'name': _('Get Attendance'),
            'view_mode': 'form',
            'res_model': 'hikvision.download.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {
                'default_device_ip': self.device_ip,
                'default_device_user': self.device_user,
                'default_device_password': self.device_password,
                'default_device_port': self.port,
            }
        }
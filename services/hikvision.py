import logging
import requests
from odoo.exceptions import UserError
from odoo import _


_logger = logging.getLogger(__name__)

class Hikvision():
    """
    Hikvision class to manipulate and make petitions the Hikvision device.
    """
    def __init__(self, device_ip, port, device_user, device_password):
        self.device_ip = device_ip
        self.port = port
        self.device_user = device_user
        self.device_password = device_password

    def connect(self):
        """
        Connect to the device and return the connection object.
        """
        url = f'http://{self.device_ip}:{self.port}/ISAPI/System/deviceInfo'
        auth = requests.auth.HTTPDigestAuth(self.device_user, self.device_password)
        try:
            response = requests.get(url, auth=auth,timeout=30)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException as error:
            _logger.info("Error: %s", error)
            return False

    def get_mode(self, endpoint):
        """
        Send a GET request to the device.
        """
        url = f'http://{self.device_ip}:{self.port}/ISAPI/{endpoint}'
        auth = requests.auth.HTTPDigestAuth(self.device_user, self.device_password)
        try:
            response = requests.get(url, auth=auth, timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                _logger.info("Error: %s", response.status_code)
                return None
        except requests.exceptions.RequestException as error:
            _logger.info("Error: %s", error)
            return None

    def post_mode(self, endpoint, data):
        """
        Send a POST request to the device.
        """
        url = f'http://{self.device_ip}:{self.port}/ISAPI/{endpoint}'
        auth = requests.auth.HTTPDigestAuth(self.device_user, self.device_password)
        try:
            response = requests.post(url, json=data, auth=auth, timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except requests.exceptions.RequestException as error:
            _logger.info("Error: %s", error)
            return None

    def get_users(self):
        """
        Get all users from the device.
        """
        url = f'http://{self.device_ip}:{self.port}/ISAPI/AccessControl/UserInfo/Search?format=json'
        auth = requests.auth.HTTPDigestAuth(self.device_user, self.device_password)
        all_users = []
        begin = 0
        limit = 30
        while True:
            search_user = {
                "UserInfoSearchCond": {
                    "SearchID": "1",
                    "searchResultPosition": begin,
                    "maxresults": limit
                }
            }
            response = requests.post(url=url, json=search_user, auth=auth, timeout=30)
            data = response.json()
            users = data.get("UserInfoSearch", {}).get("UserInfo", [])
            if not users:
                break
            all_users.extend(users)
            begin += len(users)

            if len(users) < limit:
                break

        return all_users

    def get_attendance(self, from_date, to_date):
        """
        Get all attendance records from the device.
        """
        url = f'http://{self.device_ip}:{self.port}/ISAPI/AccessControl/AcsEvent?format=json'
        auth = requests.auth.HTTPDigestAuth(self.device_user, self.device_password)
        all_attendance = []
        from_date = from_date + "-00:00"
        to_date = to_date + "-00:00"

        _logger.info(f"FECHA INICIOOO: {from_date}")
        _logger.info(f"FECHA FIIINNNN: {to_date}")

        def fetch_events(major, minor):
            begin = 0
            limit = 30
            events = []

            while True:
                condition = {
                    "AcsEventCond": {
                        "searchID": "3",
                        "searchResultPosition": begin,
                        "maxResults": limit,
                        "major": major,
                        "minor": minor,
                        "startTime": from_date,
                        "endTime": to_date
                    }
                }
                try:
                    response = requests.post(url=url, json=condition, auth=auth, timeout=30)
                    response.raise_for_status()
                    datos = response.json()
                except Exception as e:
                    _logger.warning(f"Error al consultar eventos major {major}, minor {minor}: {e}")
                    break

                attendance_raw = datos.get("AcsEvent", {}).get("InfoList", [])
                _logger.info(f"[PAGINATION] Major {major} Minor {minor} | Pos {begin} | Received: {len(attendance_raw)}")

                if not attendance_raw:
                    break

                events.extend(attendance_raw)
                begin += limit  # ✅ usar limit fijo, no length real

                if len(attendance_raw) < limit:
                    break

            return events

        # Obtener eventos normales (major 5, minor 75)
        all_attendance.extend(fetch_events(major=5, minor=75))

        # Obtener eventos por huella (major 5, minor 38)
        all_attendance.extend(fetch_events(major=5, minor=38))

        return all_attendance

    def user_exist(self, endpoint, data):
        """
        Check if a user exists in the device.
        """
        url = f'http://{self.device_ip}:{self.port}/ISAPI/{endpoint}'
        auth = requests.auth.HTTPDigestAuth(self.device_user, self.device_password)
        try:
            response = requests.post(url, json=data, auth=auth, timeout=30)
            match_status = response.json()
            if match_status['UserInfoSearch']['responseStatusStrg'] == "NO MATCH":
                return True
            else:
                return False
        except requests.exceptions.RequestException as error:
            _logger.info("Error: %s", error)
            return None

    def upload_photo(self,endpoint,data):
        """
        Upload a photo to the device.
        """
        url = f'http://{self.device_ip}:{self.port}/ISAPI/{endpoint}'
        auth = requests.auth.HTTPDigestAuth(self.device_user, self.device_password)

        try:
            response = requests.post(url, json=data, auth=auth, timeout=30)
            if response.status_code == 200:
                return True

        except Exception as error:
            _logger.error("Error: %s", error)
            raise UserError(_('Failed to upload user image: %s') % (str(error))) from error

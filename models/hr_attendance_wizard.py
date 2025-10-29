import logging
import io
import base64
from datetime import timedelta
import pytz
import xlsxwriter
from odoo import models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
class HRAttendanceWizard(models.TransientModel):
    """
    This class defines a wizard for generating attendance reports in Excel format.
    It allows the user to select a date range and generates an Excel file with attendance records.
    """
    _name = 'hr.attendance.wizard'
    _description = 'Attendance Wizard'

    date_start = fields.Datetime(string='Start Date', required=True)
    date_end = fields.Datetime(string='End Date', required=True)
    device_id = fields.Many2one('hr.hikvision', string='Hikvision Device', required=True, help='Select the Hikvision device to generate the report.')

    def action_search_attendance(self):
        """
        This method generates the attendance report as an Excel file for the selected date range.
        """
        # Validate the date range
        if self.date_start > self.date_end:
            raise UserError('The start date must be before the end date.')

        # Get the current user's timezone
        user_timezone = self.env.user.tz or 'UTC'
        local_tz = pytz.timezone(user_timezone)

        # Convert the start and end dates to the user's timezone
        _logger.info("Start date: %s", self.date_start)
        _logger.info("End date: %s", self.date_end)

        # Create an output stream for the Excel file
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Attendance Records')

        # Define formats for the Excel file
        S_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'bold': True,
            'border': 1,
            'font_size': 11,
            'bg_color': '#e7e6e6',
            'pattern': 1
        })
        date_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'font_size': 10
        })
        checks_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'bold': True,
            'border': 1,
            'font_size': 10,
            'bg_color': '#e7e6e6',
        })

        # Set the headers for CODE and NAME columns
        worksheet.merge_range('B1:B2', 'NAME', S_format)
        worksheet.set_column_pixels('B:B', 310)
        worksheet.merge_range('A1:A2', 'CODE', S_format)
        worksheet.set_column_pixels('A:A', 58)

        # Create the dictionary to store employee rows
        empleados_filas = {}

        # Get attendance records in the selected date range
        attendance_records = self.env['hr.attendance'].search([
            ('check_in', '>=', self.date_start),
            ('check_in', '<=', self.date_end),
            ('hikvision_id', '=', self.device_id.id)
        ])

        # Prepare the list of unique employees (to avoid duplicates)
        employees = []
        for record in attendance_records:
            if record.employee_id not in employees:
                employees.append(record.employee_id)

        # Fill the employee rows (starting from row 2 in the worksheet)
        row = 2  # Start from the third row (row 2 is for employees)
        for employee in employees:
            worksheet.write(row, 0, employee.biometric_id, date_format)
            worksheet.write(row, 1, employee.name, date_format)
            empleados_filas[employee.id] = row
            row += 1

        # Create a column for each date in the range (Starting from column 2 for dates)
        column = 2
        current_date = self.date_start
        while current_date <= self.date_end:
            # Create headers for the dates with merged cells
            worksheet.merge_range(0, column, 0, column + 1, current_date.strftime('%A %Y/%m/%d'), S_format)
            worksheet.set_column_pixels(column, column + 1, 80)

            # Add "Check In" and "Check Out" labels below the date headers
            worksheet.write(1, column, 'Check In', checks_format)
            worksheet.write(1, column + 1, 'Check Out', checks_format)
            column += 2  # Move to the next pair of columns for the next date

            # Move to the next date
            current_date += timedelta(days=1)

        # Fill in the attendance data for each employee and date
        for record in attendance_records:
            # Convert the check-in time to the user's local timezone
            check_in_local = record.check_in.astimezone(local_tz)

            # Get the row for the employee using the employee ID from the dictionary
            employee_row = empleados_filas.get(record.employee_id.id)
            if employee_row:
                # Get the column index for the date
                days_diff = (check_in_local.date() - self.date_start.date()).days
                date_column = 2 + days_diff * 2  # Adjusted column for the date
                if record.show_check_in:
                    worksheet.write(employee_row, date_column, record.check_in_time)  # Check-in time
                else:
                    worksheet.write(employee_row, date_column, record.check_in_visible)
                worksheet.write(employee_row, date_column + 1, record.check_out_time)  # Check-out time

        # Close the workbook to write the file
        workbook.close()
        output.seek(0)

        # Encode the file data to base64
        file_data = base64.b64encode(output.read())

        # Create an attachment for the generated Excel file
        attachment = self.env['ir.attachment'].create({
            'name': 'Reporte de Asistencia.xlsx',
            'type': 'binary',
            'datas': file_data,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return a URL to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

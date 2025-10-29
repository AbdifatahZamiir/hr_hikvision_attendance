import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class HREmployee(models.Model):
    """ inherit model from hr.employee"""
    _inherit = 'hr.employee'

    # Adding a new field to store the employee's ID in the biometric device
    biometric_id = fields.Char(string='Biometric ID',help='ID of the employee in the biometric device', store=True)
    hikvision_id = fields.Many2one('hr.hikvision', string='Hikvision Device', help='Hikvision Device ID', store=True)
    hikvision_register = fields.Boolean(string='registred in hikvision device', compute='_compute_hikvision_registered', store=False)

    @api.depends('biometric_id')
    def _compute_hikvision_registered(self):
        """ Check if the employee is registered in the Hikvision device """

        for employee in self:
            if not employee.biometric_id or not employee.hikvision_id:
                employee.hikvision_register = False
            else:
                employee.hikvision_register = not employee.hikvision_id.validate_user(employee)

    def action_create_user(self):

        """ 
        Upload One User to the Hikvision device.
        
         """

        for employee in self:
            if not employee.biometric_id or not employee.hikvision_id:
                return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('User Error'),
                            'message': 'Verify biometric id or device',
                            'type': 'warning',
                            'sticky': False
                        }
                    }
            else:
                if not employee.hikvision_id.validate_user(employee):
                    _logger.info("User: %s already exists.", employee.name)
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('User Error'),
                            'message': f'User: {employee.name} already exists',
                            'type': 'warning',
                            'sticky': False
                        }
                    }
                else:
                    if employee.hikvision_id.upload_user(employee):
                        _logger.info("User: %s uploaded successfully.", employee.name)
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': _('Success'),
                                'message': f'{employee.name}: uploaded successfuly',
                                'type': 'success',
                                'sticky': False
                            }
                        }
                    else:
                        _logger.info("User: %s can't be uploaded", employee.name)
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': _('Error'),
                                'message': f"{employee.name}: can't be uploaded",
                                'type': 'warning',
                                'sticky': False
                            }
                        }
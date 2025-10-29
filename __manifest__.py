{
    'name': 'Hikvision Biometric Device Integration',
    'version': '1.0.1',
    'category': 'Human Resources',
    'summary': "Integrating Biometric Device (ISAPI technology) With HR "
               "Attendance, with real-time synchronization",
    'description': "This module integrates Odoo with the biometric "
                   "hikvision device, Odoo 18, hr, attendance",
    'author': 'Emmanuel Perez (EGPerezR)',
    'price': 150.0,
    'currency': 'USD',
    'images': ['static/description/banner.png'],
    'support': 'emmanuel.pero.2001@gmail.com',
    'depends': ['base', 'hr_attendance','hr'],
    'external_dependencies': {
        'python': ['pyzk','itsdangerous']},
    'data': [
        'views/hikvision_device_details_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_attendance_actions.xml',
        'views/hr_attendance_views.xml',
        'views/hr_attendance_wizard_view.xml',
        'views/hikvision_attendance_views.xml',
        'views/hikvision_download_wizard_view.xml',
        'views/hikvision_device_attendance_Menus.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
    ],
    'license': 'OPL-1',
    'installable': True,
    'application': False,
    'auto_install': False,
}

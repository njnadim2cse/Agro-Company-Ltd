
{
    'name': 'A4 Half Paper Format',
    'version': '1.0',
    'category': '',
    'summary': 'Adds A4-half paper format for reports',
    'description': """
Adds a custom paper format (A4-half) for invoices, quotations, and other reports.
""",
    'author': 'Afzal khan',
    'website': 'https://yourwebsite.com',
    'depends': ['base', 'account','sale'],  
    'data': [
        'data/paperformat.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

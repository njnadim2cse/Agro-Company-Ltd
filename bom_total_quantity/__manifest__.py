{
    'name': 'BOM Total Quantity',
    'version': '18.0.1.0',
    'category': 'Agro Modules',
    'summary': 'Adds total BOM quantity calculation in KG',
    'description': """
        This module adds a total quantity field at the bottom of BOM components
        showing the sum of all component quantities in KG.
    """,
    'author': 'Anwar',
    'website': 'https://www.yourcompany.com',
    'depends': ['mrp'],
    'data': [
        'views/mrp_bom_view.xml',
       
    ],
    
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
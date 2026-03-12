
{
    'name': 'Farm Medicine Approval',
    'version': '1.0',
    'summary': 'Farm Medicine Approval System',
    'category': 'Agro Modules',
    'author':'Ayesha Chowdhury',
    'depends': ['base', 'mail', 'farm_management'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/farm_medicine_approval_views.xml',
        'views/farm_medicine_approval_line_views.xml',
        'views/farm_medicine_rejection_wizard_views.xml',
    ],
    
    'installable': True,
    'application': True,
}
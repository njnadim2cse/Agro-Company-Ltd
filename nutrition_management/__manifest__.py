{
    'name': 'Nutrition Management',
    'version': '18.0.1.0',
    'category': 'Agro Modules',
    'summary': 'Integrated Nutrition Management for Feed Manufacturing',
    'description': """
Comprehensive Nutrition Management Module integrated with Odoo Manufacturing
================================================================================

Features:
---------
- Nutrition Master with standards (min/max/actual)
- Ingredients linked to Raw Material products
- Formulas with automatic BOM integration
- Nutrition Standards management
- Real-time nutrition status checking
- Detailed reporting (Ingredients & Nutrients)
- Manufacturing integration with nutrition validation

Key Integration Points:
-----------------------
- Automatic ingredient creation from BOM lines
- Real-time nutrition status in BOM and Manufacturing Orders
- Nutrition validation before production confirmation
- Per kg standardization for batch scaling
- Cost calculation and nutrient tracking
""",
    'author': 'Your Company',
    'license': 'LGPL-3',
    'depends': [
        'base', 
        'product', 
        'mrp', 
        'stock',
        'mail',
        'web',
        'farm_management',
        'agro_core',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/nutrition_views.xml',
        'views/ingredient_views.xml',
        'views/feed_ingredient_nutrient_views.xml',
        'views/formula_views.xml',
        'views/nutrition_standard_views.xml',
        'views/mrp_views.xml',
        'views/mrp_production_views.xml',
        'views/report_wizard_views.xml',
        'views/menu_views.xml',
        'report/templates.xml',
        'report/actions.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
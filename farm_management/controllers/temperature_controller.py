from odoo import http
from odoo.http import request
import logging
import json

_logger = logging.getLogger(__name__)

class TemperatureController(http.Controller):

    @http.route('/get/live-temperature', type='json', auth='user', methods=['POST'])
    def get_live_temperature(self, record_id=None):

        try:
            Temperature = request.env['temperature.details.data'].sudo()
            if record_id:
                record = Temperature.browse(int(record_id))
            else:
                record = Temperature.search([], order='id desc', limit=1)
            if not record:
                return {'success': False, 'error': 'No temperature record found.'}
            result = record.action_fetch_live_temperature()

            weather_data = None
            if isinstance(result, dict):
                if result.get('context') and result['context'].get('weather_data'):
                    weather_data = result['context']['weather_data']
                elif result.get('weather_data'):
                    weather_data = result['weather_data']
                elif result.get('data_1h'):
                    weather_data = result
                elif result.get('context'):
                    for key, value in result['context'].items():
                        if any(term in key.lower() for term in ['weather', 'temperature', 'data_1h', 'hourly']):
                            weather_data = value
                            break
            if weather_data:
                return {
                    'success': True,
                    'data': weather_data
                }
            else:
                return {
                    'success': True,
                    'data': result,
                    'raw_action': True  
                }
            
        except Exception as e:
            _logger.exception("Error fetching live temperature")
            return {'success': False, 'error': str(e)}

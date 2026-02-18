import requests
from flask import Blueprint, request, jsonify, session
from ..config import Config

proxy_bp = Blueprint('proxy', __name__)

@proxy_bp.route('/api-proxy/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_proxy(path):
    """
    Proxy requests to the backend API.
    This avoids CORS issues and keeps the API URL hidden from the client if needed.
    """
    url = f"{Config.API_BASE_URL}/{path}"
    
    # Forward the method and json data
    method = request.method
    data = request.get_json() if request.is_json else None
    params = request.args
    
    # Forward authorization header
    headers = {
        'Content-Type': 'application/json'
    }
    
    # Get token from session if available
    token = session.get('token')
    if token:
        headers['Authorization'] = f'Bearer {token}'
        
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, params=params, timeout=10)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data, params=params, timeout=10)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=data, params=params, timeout=10)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers, params=params, timeout=10)
        else:
            return jsonify({'error': 'Method not supported'}), 405
            
        # Return the response from the API
        # Handle 204 No Content
        if response.status_code == 204:
            return '', 204
            
        try:
            return jsonify(response.json()), response.status_code
        except:
            return response.content, response.status_code
            
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Cannot connect to backend API'}), 503
    except Exception as e:
        return jsonify({'error': str(e)}), 500

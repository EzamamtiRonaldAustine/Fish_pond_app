# dashboard/api_client.py
import requests
from flask import session
from .config import Config

def call_api(endpoint, method='GET', data=None, token=None):
    """
    Wrapper function to call the backend API.
    
    Args:
        endpoint: API endpoint (e.g., '/current-readings')
        method: HTTP method ('GET', 'POST', etc.)
        data: Request payload for POST/PUT
        token: JWT token for authenticated endpoints
    
    Returns:
        dict: API response data or error dict
    """
    url = f"{Config.API_BASE_URL}{endpoint}"
    headers = {'Content-Type': 'application/json'}
    
    if token:
        headers['Authorization'] = f'Bearer {token}'
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, timeout=10)
        elif method == 'POST':
            response = requests.post(url, json=data, headers=headers, timeout=10)
        elif method == 'PUT':
            response = requests.put(url, json=data, headers=headers, timeout=10)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers, timeout=10)
        else:
            return {'error': 'Unsupported HTTP method'}
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 201:
            return response.json()
        elif response.status_code == 401:
            # Clear session on authentication failure
            session.clear()
            return {'error': 'Authentication required. Please login.', 'auth_required': True}
        elif response.status_code == 403:
            return {'error': 'Access denied. Insufficient permissions.', 'status_code': 403}
        else:
            return {'error': f'API returned status {response.status_code}', 'details': response.text}
    
    except requests.exceptions.ConnectionError:
        return {'error': 'Cannot connect to API. Is the API server running?'}
    except requests.exceptions.Timeout:
        return {'error': 'API request timed out'}
    except Exception as e:
        return {'error': f'API call failed: {str(e)}'}

def login_api(username, password):
    """Authenticate user and get JWT token."""
    return call_api('/auth/login', method='POST', data={
        'username': username,
        'password': password
    })


def signup_api(username, password, email, full_name, organization_id):
    """Public signup for farmer accounts."""
    return call_api('/auth/signup', method='POST', data={
        'username': username,
        'password': password,
        'email': email,
        'full_name': full_name,
        'organization_id': organization_id,
    })

def google_login_api(credential):
    """Authenticate via Google OAuth."""
    return call_api('/auth/google', method='POST', data={
        'credential': credential
    })
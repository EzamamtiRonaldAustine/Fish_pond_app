import sys
import os
import io

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dashboard import create_app

def test_ml_route():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False # Disable CSRF for testing
    client = app.test_client()

    print("Testing GET /ml-analysis...")
    response = client.get('/ml-analysis')
    if response.status_code == 200:
        print("PASS: GET request successful.")
    else:
        print(f"FAIL: GET request failed with status {response.status_code}")
        return

    print("\nTesting POST /ml-analysis with IoTPond6.xlsx...")
    
    # Path to the dataset
    data_path = os.path.join(os.path.dirname(__file__), '..', 'ml', 'data', 'IoTPond6.xlsx')
    
    if not os.path.exists(data_path):
        print(f"FAIL: Data file not found at {data_path}")
        return

    with open(data_path, 'rb') as f:
        data = {
            'file': (f, 'IoTPond6.xlsx')
        }
        response = client.post('/ml-analysis', data=data, content_type='multipart/form-data', follow_redirects=True)
    
    if response.status_code == 200:
        # Check if "Analysis Results" or the predicted level is present in value
        response_text = response.get_data(as_text=True)
        if "Analysis Results" in response_text or "Risk Level" in response_text:
             print("PASS: POST request successful and results displayed.")
        else:
             print("FAIL: POST request successful but results not found in response.")
             # print(response_text[:500]) # Debug
    else:
        print(f"FAIL: POST request failed with status {response.status_code}")

if __name__ == "__main__":
    test_ml_route()

import requests
import urllib3

# Suppress warnings if we test verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_connection(url):
    print(f"\n--- Testing: {url} ---")
    
    # 1. Standard secure request
    print("1. Standard HTTPS request...")
    try:
        r = requests.get(url, timeout=10)
        print(f"   Success! Status: {r.status_code}")
        return
    except Exception as e:
        print(f"   FAILED: {e}")

    # 2. Request without certificate verification
    print("2. HTTPS request (verify=False)...")
    try:
        r = requests.get(url, timeout=10, verify=False)
        print(f"   Success (but insecure)! Status: {r.status_code}")
        print("   TIP: This means your Pi's root certificates are outdated.")
        return
    except Exception as e:
        print(f"   FAILED: {e}")

    # 3. Check if it's a protocol issue
    print("3. Checking if it's an SNI/Handshake issue...")
    print("   (Try updating your Pi with: sudo apt update && sudo apt install ca-certificates)")

if __name__ == "__main__":
    target = "https://fish-pond-api.up.railway.app/api/health"
    test_connection(target)

import requests
import sys

# Test endpoint
url = "http://localhost:8000/api/user-stories/project/8"

# Get token from environment or use a test one
# For now, let's test without token to see if server responds
try:
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

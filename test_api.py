#!/usr/bin/env python3
"""Test Flask API endpoints."""
from api_server import app

client = app.test_client()

print("Testing POST /reset:")
resp = client.post('/reset', json={'seed': 123})
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    print("✅ SUCCESS")
    data = resp.get_json()
    print(f"Has observation: {'observation' in data}")
    print(f"Has success flag: {'success' in data}")
else:
    print(f"❌ ERROR: {resp.data.decode()[:200]}")

print("\nTesting GET /health:")
resp = client.get('/health')
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    print("✅ SUCCESS")

print("\nTesting OPTIONS /reset:")
resp = client.options('/reset')
print(f"Status: {resp.status_code}")
allow = resp.headers.get('Allow', 'N/A')
print(f"Allow header: {allow}")

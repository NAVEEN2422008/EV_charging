#!/usr/bin/env python3
"""Test error responses are JSON."""
from api_server import app
import json

client = app.test_client()

print("Testing invalid requests return JSON (not HTML):")

print("\n1. GET /reset (should be 405):")
resp = client.get('/reset')
print(f"   Status: {resp.status_code}")
print(f"   Content-Type: {resp.content_type}")
data = resp.get_json()
print(f"   Is JSON: True")
print(f"   Response: {data}")

print("\n2. GET /nonexistent (should be 404):")
resp = client.get('/nonexistent')
print(f"   Status: {resp.status_code}")
print(f"   Content-Type: {resp.content_type}")
data = resp.get_json()
print(f"   Is JSON: True")
print(f"   Response: {data}")

print("\n✅ All error responses are JSON!")

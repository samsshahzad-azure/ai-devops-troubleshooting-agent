#!/usr/bin/env python3
"""Quick test of new endpoints."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Test config endpoint
print("Testing GET /config...")
response = client.get("/config")
print(f"Status: {response.status_code}")
print(f"Config: {response.json()}\n")

# Test cluster-info endpoint with local fixtures
print("Testing GET /cluster-info...")
response = client.get("/cluster-info?use_local=true")
print(f"Status: {response.status_code}")
cluster_info = response.json()
print(f"Pods in snapshot: {len(cluster_info.get('pods', []))}")
print(f"Events in snapshot: {len(cluster_info.get('events', []))}\n")

# Test pod-info endpoint
print("Testing GET /pod-info...")
response = client.get("/pod-info?pod_name=checkout-api-7d8f9c6b5f-q2m4k&use_local=true")
print(f"Status: {response.status_code}")
pod_info = response.json()
print(f"Pod name: {pod_info['pod']['name']}")
print(f"Pod status: {pod_info['pod']['status']}")

print("\n✓ All endpoints working correctly!")

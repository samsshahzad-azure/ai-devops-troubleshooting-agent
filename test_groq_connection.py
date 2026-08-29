#!/usr/bin/env python3
"""Test script to diagnose Groq API connection."""

from app.config import settings
from groq import Groq

print(f"API Key loaded: {'Yes' if settings.groq_api_key else 'No'}")
if settings.groq_api_key:
    print(f"API Key starts with: {settings.groq_api_key[:20]}...")
    print(f"API Key length: {len(settings.groq_api_key)}")

print(f"Model: {settings.groq_model}")

try:
    print("\nConnecting to Groq API...")
    client = Groq(api_key=settings.groq_api_key)
    
    print("Sending test request...")
    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=[{"role": "user", "content": "Hi"}],
        max_tokens=10
    )
    print("✓ Groq API connection successful!")
    print(f"Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

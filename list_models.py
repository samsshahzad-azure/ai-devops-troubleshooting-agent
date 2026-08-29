#!/usr/bin/env python3
"""List available Groq models."""

from app.config import settings
from groq import Groq

try:
    client = Groq(api_key=settings.groq_api_key)
    models = client.models.list()
    print("Available models:")
    for model in models.data:
        print(f"  - {model.id}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

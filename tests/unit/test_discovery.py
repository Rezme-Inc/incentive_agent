#!/usr/bin/env python3
"""Quick test of discovery agent"""

import os
from dotenv import load_dotenv
from agents import DiscoveryAgent

load_dotenv()

print("Testing Discovery Agent...")
print("=" * 60)

discovery = DiscoveryAgent()
print(f"Model: {discovery.model}")
print(f"Temperature: {discovery.temperature}")

# Test with a very short prompt to verify it works
print("\nMaking test API call...")
try:
    result = discovery.discover_programs(
        jurisdiction="Illinois",
        state="Illinois",
        cities=[],
        counties=[]
    )
    print(f"✓ Success! Got {len(result)} characters of output")
    print(f"First 200 chars: {result[:200]}...")
except Exception as e:
    print(f"✗ Error: {str(e)[:300]}")


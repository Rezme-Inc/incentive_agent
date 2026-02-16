#!/usr/bin/env python3
"""
Test script to diagnose Anthropic API model issues
"""

import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

def test_api_connection():
    """Test basic API connection"""
    print("=" * 60)
    print("TEST 1: API Connection")
    print("=" * 60)
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not found in environment")
        return False
    
    print(f"✓ API key found: {api_key[:10]}...{api_key[-4:]}")
    return True

def test_model_names():
    """Test various model name formats"""
    print("\n" + "=" * 60)
    print("TEST 2: Model Name Formats")
    print("=" * 60)
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ No API key")
        return
    
    client = Anthropic(api_key=api_key)
    
    # List of model names to try
    models_to_test = [
        "claude-3-5-sonnet-20240620",
        "claude-3-5-sonnet",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
        "claude-3-5-haiku-20241022",
        "claude-3-5-opus-20241022",
    ]
    
    print("Testing model names...")
    for model in models_to_test:
        try:
            print(f"\n  Testing: {model}")
            response = client.messages.create(
                model=model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Say 'test'"}]
            )
            print(f"  ✓ SUCCESS: {model} works!")
            return model
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg or "not_found" in error_msg.lower():
                print(f"  ✗ Not found: {model}")
            else:
                print(f"  ✗ Error: {error_msg[:100]}")
    
    return None

def test_thinking_parameter(working_model):
    """Test if thinking parameter works"""
    print("\n" + "=" * 60)
    print("TEST 3: Extended Thinking Support")
    print("=" * 60)
    
    if not working_model:
        print("❌ No working model found, skipping thinking test")
        return False
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = Anthropic(api_key=api_key)
    
    try:
        print(f"Testing thinking parameter with: {working_model}")
        response = client.messages.create(
            model=working_model,
            max_tokens=50,
            thinking={
                "type": "enabled",
                "budget_tokens": 100
            },
            messages=[{"role": "user", "content": "Say 'test'"}]
        )
        print("✓ Extended thinking works!")
        
        # Check response structure
        if response.content:
            for block in response.content:
                print(f"  Block type: {block.type}")
                if hasattr(block, 'text'):
                    print(f"  Text length: {len(block.text)}")
        return True
    except Exception as e:
        print(f"✗ Thinking parameter error: {str(e)[:200]}")
        return False

def test_simple_call(working_model):
    """Test a simple API call"""
    print("\n" + "=" * 60)
    print("TEST 4: Simple API Call")
    print("=" * 60)
    
    if not working_model:
        print("❌ No working model found")
        return False
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = Anthropic(api_key=api_key)
    
    try:
        print(f"Making simple call with: {working_model}")
        response = client.messages.create(
            model=working_model,
            max_tokens=100,
            messages=[{"role": "user", "content": "What is 2+2? Answer in one word."}]
        )
        
        if response.content:
            text = response.content[0].text
            print(f"✓ Response received: {text}")
            print(f"✓ Usage: {response.usage}")
            return True
    except Exception as e:
        print(f"✗ Error: {str(e)[:200]}")
        return False

def main():
    print("\n" + "=" * 60)
    print("ANTHROPIC API DIAGNOSTIC TESTS")
    print("=" * 60)
    
    # Test 1: API Connection
    if not test_api_connection():
        print("\n❌ Cannot proceed without API key")
        return
    
    # Test 2: Find working model
    working_model = test_model_names()
    
    if not working_model:
        print("\n❌ No working model found. Possible issues:")
        print("  1. API key doesn't have access to Claude models")
        print("  2. API key is invalid")
        print("  3. Account needs to be upgraded")
        return
    
    print(f"\n✓ Found working model: {working_model}")
    
    # Test 3: Extended thinking
    thinking_works = test_thinking_parameter(working_model)
    
    # Test 4: Simple call
    test_simple_call(working_model)
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Working model: {working_model}")
    print(f"Extended thinking: {'✓ Works' if thinking_works else '✗ Not supported'}")
    print(f"\nRecommendation: Update all agents to use: {working_model}")

if __name__ == "__main__":
    main()


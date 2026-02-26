#!/usr/bin/env python3
"""
Test script for ALICE remote access functionality.
Run this to test the remote access server locally before trying on mobile.
"""

import requests
import json
import time
import sys

def test_remote_access():
    """Test the remote access server functionality."""
    base_url = "http://127.0.0.1:8765"
    token = None

    print("🧪 Testing ALICE Remote Access Server")
    print("=" * 50)

    # Test 1: Ping endpoint
    try:
        print("1. Testing server health (ping)...")
        response = requests.get(f"{base_url}/ping", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Server responding (time: {data.get('time', 'unknown')})")
        else:
            print(f"   ❌ Ping failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Ping error: {e}")
        return False

    # Test 2: Get token
    try:
        print("2. Testing token retrieval...")
        response = requests.get(f"{base_url}/token", timeout=5)
        if response.status_code == 200:
            data = response.json()
            token = data.get('token')
            print(f"   ✅ Token retrieved: {token[:8]}...")
        else:
            print(f"   ❌ Token retrieval failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Token error: {e}")
        return False

    if not token:
        print("   ❌ No token received")
        return False

    # Test 3: Test client page
    try:
        print("3. Testing client page...")
        response = requests.get(f"{base_url}/client?token={token}", timeout=5)
        if response.status_code == 200:
            print("   ✅ Client page loads successfully")
            if "ALICE Remote Client" in response.text:
                print("   ✅ Client page contains expected content")
            else:
                print("   ⚠️  Client page loaded but content may be incomplete")
        else:
            print(f"   ❌ Client page failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Client page error: {e}")
        return False

    # Test 4: Test voice command endpoint
    try:
        print("4. Testing voice command endpoint...")
        payload = {
            "token": token,
            "text": "test command from test script"
        }
        response = requests.post(f"{base_url}/voice-command",
                               json=payload,
                               timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('ok') and data.get('queued'):
                print("   ✅ Voice command endpoint working")
                print(f"   📝 Command queued: {data.get('command', 'unknown')}")
            else:
                print(f"   ⚠️  Voice command response: {data}")
        else:
            print(f"   ❌ Voice command failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Voice command error: {e}")
        return False

    # Test 5: Test push notification (optional)
    try:
        print("5. Testing push notification endpoint...")
        payload = {
            "token": token,
            "title": "Test",
            "body": "Test message from test script"
        }
        response = requests.post(f"{base_url}/pushnotify",
                               json=payload,
                               timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Push notification test: {data}")
        else:
            print(f"   ⚠️  Push notification failed: {response.status_code} (may be normal if no subscriptions)")
    except Exception as e:
        print(f"   ⚠️  Push notification error: {e} (may be normal)")

    print("\n" + "=" * 50)
    print("🎉 All basic tests passed!")
    print("\n📱 For mobile testing:")
    print("1. Open this URL in your mobile browser:")
    print(f"   http://100.79.99.39:8765/client?token={token}")
    print("2. Tap '🎙️ Microphone Permission' and allow access")
    print("3. Tap '🎤 Start Voice' and try saying 'Hey Alice, test'")
    print("4. Or use the text input: type 'test' and tap '📤 Send'")
    print("\n🔧 Troubleshooting:")
    print("- If microphone doesn't work, check browser settings")
    print("- Make sure both devices are on the same Tailscale network")
    print("- Try refreshing the page if connection fails")

    return True

if __name__ == "__main__":
    success = test_remote_access()
    sys.exit(0 if success else 1)
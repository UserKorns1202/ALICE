#!/usr/bin/env python3
"""
Setup script for ALICE remote access with Tailscale
"""

import os
import subprocess
import sys

def check_tailscale():
    """Check if Tailscale is installed and running"""
    try:
        result = subprocess.run(['tailscale', 'status'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ Tailscale is installed and running")
            return True
        else:
            print("❌ Tailscale is installed but not running")
            return False
    except FileNotFoundError:
        print("❌ Tailscale is not installed")
        return False

def get_tailscale_ip():
    """Get the Tailscale IP address"""
    try:
        result = subprocess.run(['tailscale', 'ip'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            ip = result.stdout.strip().split('\n')[0]
            print(f"📱 Your Tailscale IP: {ip}")
            return ip
        else:
            print("❌ Could not get Tailscale IP")
            return None
    except Exception as e:
        print(f"❌ Error getting Tailscale IP: {e}")
        return None

def setup_remote_access():
    """Setup remote access configuration"""
    print("🚀 Setting up ALICE Remote Access")
    print("=" * 40)

    # Check Tailscale
    if not check_tailscale():
        print("\n📋 To install Tailscale:")
        print("1. Go to https://tailscale.com/download")
        print("2. Download and install Tailscale for your platform")
        print("3. Run 'tailscale login' to authenticate")
        print("4. Run this setup script again")
        return

    # Get Tailscale IP
    tailscale_ip = get_tailscale_ip()
    if not tailscale_ip:
        print("\n❌ Please ensure Tailscale is properly configured")
        return

    # Get token
    try:
        import remote_access
        token = remote_access.get_token()
        print(f"🔑 Your access token: {token}")
    except Exception as e:
        print(f"❌ Error getting access token: {e}")
        return

    print("\n" + "=" * 40)
    print("🎯 REMOTE ACCESS SETUP COMPLETE!")
    print("=" * 40)
    print(f"🌐 Access URL: http://{tailscale_ip}:8765/client?token={token}")
    print("\n📱 On your phone:")
    print("1. Open the URL above in your mobile browser")
    print("2. Grant microphone permissions when prompted")
    print("3. Click '🎤 Start Voice' to begin voice commands")
    print("4. Say 'Hey Alice' or 'Hey Virgil' followed by your command")
    print("\n🎙️ Voice Commands Examples:")
    print("- 'Hey Alice, what's the weather?'")
    print("- 'Hey Virgil, open Chrome'")
    print("- 'Hey Alice, set a timer for 5 minutes'")
    print("- 'Hey Virgil, check my emails'")
    print("\n🔒 Security Notes:")
    print("- Only devices on your Tailscale network can access")
    print("- All communication is encrypted")
    print("- Voice processing happens locally on your phone")
    print("- Commands are securely transmitted to your PC")

    # Test server startup
    print("\n🧪 Testing server startup...")
    try:
        remote_access.start_server()
        print("✅ Remote access server started successfully!")
        print("🎉 You're all set! Access ALICE from your phone using the URL above.")
    except Exception as e:
        print(f"❌ Server startup failed: {e}")

if __name__ == "__main__":
    setup_remote_access()
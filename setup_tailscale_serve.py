#!/usr/bin/env python3
"""
Manual Tailscale Serve Setup for ALICE Remote Access
Run this if you want to enable external access to ALICE from outside your tailnet.
"""

import subprocess
import sys
import time

def setup_tailscale_serve():
    """Manually set up Tailscale serve for external access."""
    print("🔧 Setting up Tailscale Serve for external access...")
    print("This will make ALICE accessible from the internet via Tailscale Funnel")
    print()

    # Check if tailscale is available
    try:
        result = subprocess.run(['tailscale', 'version'], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            print("❌ Tailscale CLI not found. Please install Tailscale first.")
            return False
    except FileNotFoundError:
        print("❌ Tailscale CLI not found. Please install Tailscale first.")
        return False

    # Check current serve status
    print("📊 Checking current serve status...")
    result = subprocess.run(['tailscale', 'serve', 'status'], capture_output=True, text=True, timeout=10)

    if result.returncode == 0 and '8765' in result.stdout:
        print("✅ Serve rule already exists for port 8765")
        print("🌐 Your ALICE remote access should be available at:")
        print("   https://desktop-t5lfomm.tail8c3cd9.ts.net/")
        return True

    # Set up serve
    print("🚀 Setting up serve rule for port 8765...")
    try:
        # Run tailscale serve in background
        process = subprocess.Popen(['tailscale', 'serve', '8765'],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 text=True)

        # Wait a moment for it to start
        time.sleep(3)

        if process.poll() is None:
            print("✅ Serve rule created successfully!")
            print("🌐 Your ALICE remote access is now available at:")
            print("   https://desktop-t5lfomm.tail8c3cd9.ts.net/")
            print()
            print("📝 Note: The tailscale serve process is running in the background.")
            print("   It will continue until you stop it manually with: tailscale serve reset")
            return True
        else:
            stdout, stderr = process.communicate()
            print(f"❌ Failed to create serve rule: {stderr}")
            return False

    except Exception as e:
        print(f"❌ Error setting up serve: {e}")
        return False

def main():
    print("ALICE Remote Access - Manual Tailscale Serve Setup")
    print("=" * 55)

    # Confirm with user
    response = input("This will enable external access to ALICE via the internet. Continue? (y/N): ").strip().lower()

    if response not in ['y', 'yes']:
        print("Setup cancelled.")
        return

    success = setup_tailscale_serve()

    if success:
        print("\n🎉 Setup complete!")
        print("You can now access ALICE from anywhere using the URL above.")
        print("Make sure to use HTTPS for security.")
    else:
        print("\n❌ Setup failed. Check the error messages above.")

if __name__ == "__main__":
    main()
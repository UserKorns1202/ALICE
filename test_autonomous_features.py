#!/usr/bin/env python3
"""
Test script for ALICE's autonomous features
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from dynamic_response import DynamicResponseHandler
from user_memory import UserMemory

def test_communication_hub():
    """Test the communication hub functionality"""
    print("=== Testing Communication Hub ===")

    memory = UserMemory()
    handler = DynamicResponseHandler(memory)

    # Test communication hub (will show warnings for missing credentials)
    alerts = handler.manage_communication_hub()
    print(f"Communication alerts: {alerts}")

def test_security_guardian():
    """Test the security guardian functionality"""
    print("\n=== Testing Security Guardian ===")

    memory = UserMemory()
    handler = DynamicResponseHandler(memory)

    # Test security guardian
    status = handler.manage_security_guardian()
    print(f"Security status: {status}")

def test_file_organization():
    """Test file organization (safe test)"""
    print("\n=== Testing File Organization ===")

    memory = UserMemory()
    handler = DynamicResponseHandler(memory)

    # Test file organization (will scan but not move files in test)
    result = handler.organize_files_autonomously()
    print(f"File organization result: {result}")

if __name__ == "__main__":
    print("ALICE Autonomous Features Test")
    print("=" * 40)

    try:
        test_communication_hub()
        test_security_guardian()
        test_file_organization()

        print("\n" + "=" * 40)
        print("✅ All tests completed successfully!")
        print("\nNext steps:")
        print("1. Set up credentials for email/SMS monitoring")
        print("2. Configure urgent contacts in user_memory")
        print("3. Add background threads to ALICE.py for autonomous operation")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
#!/usr/bin/env python3
"""
Setup script for ALICE autonomous features
Configures credentials and settings for communication hub and security guardian
"""

import os
import getpass

def setup_email_credentials():
    """Set up Gmail IMAP credentials"""
    print("\n=== Email Setup (Gmail IMAP) ===")
    print("Note: Use Gmail App Password, not regular password")
    print("Enable 2FA and generate App Password at: https://myaccount.google.com/apppasswords")

    try:
        import keyring
        email = input("Enter your Gmail address: ").strip()
        if email:
            app_password = getpass.getpass("Enter Gmail App Password: ")
            keyring.set_password("alice_email", "username", email)
            keyring.set_password("alice_email", "password", app_password)
            print("✅ Email credentials saved securely")
        else:
            print("⚠️ Email setup skipped")
    except ImportError:
        print("❌ Keyring not available - secure credential storage disabled")

def setup_sms_credentials():
    """Set up Twilio SMS credentials"""
    print("\n=== SMS Setup (Twilio) ===")
    print("Get credentials from: https://console.twilio.com/")

    try:
        import keyring
        sid = input("Enter Twilio Account SID: ").strip()
        if sid:
            token = getpass.getpass("Enter Twilio Auth Token: ")
            number = input("Enter your Twilio phone number (+1234567890): ").strip()

            keyring.set_password("alice_twilio", "sid", sid)
            keyring.set_password("alice_twilio", "token", token)
            keyring.set_password("alice_twilio", "number", number)
            print("✅ SMS credentials saved securely")
        else:
            print("⚠️ SMS setup skipped")
    except ImportError:
        print("❌ Keyring not available - secure credential storage disabled")

def setup_urgent_contacts():
    """Set up urgent contacts for communication prioritization"""
    print("\n=== Urgent Contacts Setup ===")
    print("Enter email addresses that should be treated as high priority:")

    contacts = []
    while True:
        contact = input("Enter urgent contact email (or press Enter to finish): ").strip()
        if not contact:
            break
        contacts.append(contact)

    if contacts:
        # Save to user_memory
        try:
            from user_memory import UserMemory
            memory = UserMemory()
            patterns = memory.get_learned_patterns()
            patterns['urgent_contacts'] = contacts
            memory.update_learned_patterns(patterns)
            print(f"✅ Added {len(contacts)} urgent contacts")
        except Exception as e:
            print(f"❌ Failed to save urgent contacts: {e}")
    else:
        print("⚠️ No urgent contacts configured")

def show_status():
    """Show current setup status"""
    print("\n=== Current Setup Status ===")

    # Check libraries
    libraries = {
        'imapclient': 'Email monitoring',
        'keyring': 'Secure credentials',
        'scapy': 'Network monitoring',
        'twilio': 'SMS monitoring',
        'pyautogui': 'Device control',
        'schedule': 'Task scheduling'
    }

    print("📚 Library Status:")
    for lib, desc in libraries.items():
        try:
            __import__(lib)
            print(f"  ✅ {desc}")
        except ImportError:
            print(f"  ❌ {desc} - {lib} not installed")

    # Check credentials
    print("\n🔐 Credentials Status:")
    try:
        import keyring
        services = {
            'alice_email': ['username', 'password'],
            'alice_twilio': ['sid', 'token', 'number']
        }

        for service, keys in services.items():
            configured = sum(1 for key in keys if keyring.get_password(service, key))
            total = len(keys)
            status = "✅" if configured == total else f"⚠️ ({configured}/{total})"
            print(f"  {status} {service.replace('alice_', '').title()}")
    except ImportError:
        print("  ❌ Secure credential storage unavailable")

    # Check user memory
    print("\n🧠 Learning Status:")
    try:
        from user_memory import UserMemory
        memory = UserMemory()
        patterns = memory.get_learned_patterns()
        urgent_count = len(patterns.get('urgent_contacts', []))
        print(f"  📧 {urgent_count} urgent contacts configured")
    except Exception as e:
        print(f"  ❌ User memory error: {e}")

def main():
    print("ALICE Autonomous Features Setup")
    print("=" * 40)
    print("This will help you configure:")
    print("• Email monitoring (Gmail IMAP)")
    print("• SMS monitoring (Twilio)")
    print("• Urgent contact prioritization")
    print("• Security and communication preferences")

    show_status()

    choice = input("\nWhat would you like to set up? (email/sms/contacts/status/quit): ").strip().lower()

    if choice == 'email':
        setup_email_credentials()
    elif choice == 'sms':
        setup_sms_credentials()
    elif choice == 'contacts':
        setup_urgent_contacts()
    elif choice == 'status':
        pass  # Already shown
    elif choice == 'quit':
        return
    else:
        print("Invalid choice")

    # Show final status
    show_status()

    print("\n🎉 Setup complete!")
    print("Run ALICE to start autonomous operation:")
    print("  python ALICE.py")
    print("\nTest features with:")
    print("  python test_autonomous_features.py")

if __name__ == "__main__":
    main()
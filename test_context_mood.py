import requests
import json

# Test context-aware mood detection for ALICE
def test_context_mood():
    base_url = "http://localhost:5000"

    # Test cases for different contexts
    test_cases = [
        {
            "message": "I need help with my Python homework assignment",
            "expected_context": "homework_study"
        },
        {
            "message": "How do I optimize this database query?",
            "expected_context": "technical_professional"
        },
        {
            "message": "What's up? How's it going?",
            "expected_context": "casual_chat"
        },
        {
            "message": "Let's play a game or tell a joke",
            "expected_context": "fun_playful"
        },
        {
            "message": "I'm really struggling with this problem",
            "expected_context": "serious_help"
        }
    ]

    print("Testing context-aware mood detection for ALICE...")
    print("=" * 50)

    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['message'][:50]}...")
        print(f"Expected context: {test_case['expected_context']}")

        try:
            # Test with ALICE personality (should trigger context analysis)
            response = requests.post(
                f"{base_url}/query",
                json={
                    "text": test_case["message"],
                    "personality": "helpful"
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                print(f"Response received: {result.get('response', '')[:100]}...")
                print("✓ ALICE request successful")
            else:
                print(f"✗ ALICE request failed: {response.status_code}")

        except Exception as e:
            print(f"✗ Error testing ALICE: {e}")

        try:
            # Test with VRGL personality (should NOT trigger context analysis)
            response = requests.post(
                f"{base_url}/chat",
                json={
                    "message": test_case["message"],
                    "personality": "minimal"
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                print(f"VRGL Response: {result.get('response', '')[:50]}...")
                print("✓ VRGL request successful (should be consistent)")
            else:
                print(f"✗ VRGL request failed: {response.status_code}")

        except Exception as e:
            print(f"✗ Error testing VRGL: {e}")

        print("-" * 30)

if __name__ == "__main__":
    test_context_mood()
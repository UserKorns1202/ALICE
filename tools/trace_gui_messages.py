import asyncio
import json

# Import ALICE_v2 from current workspace
import ALICE_v2

class FakeRequest:
    def __init__(self, body):
        self._body = body
    async def json(self):
        return self._body

async def run_test():
    tests = [
        (
            "compact_open",
            {"system": "Amica persona: be friendly.", "user": "[neutral] open calculator"},
        ),
        (
            "compact_hello",
            {"system": "Amica persona: be friendly.", "user": "hello"},
        ),
        (
            "legacy_messages_cmd",
            {
                "system": "Amica persona: be friendly.",
                "messages": [
                    {"role": "system", "content": "Amica persona: be friendly."},
                    {"role": "user", "content": "open calculator"},
                    {"role": "assistant", "content": "ok"},
                ],
            },
        ),
        (
            "legacy_messages_chat",
            {
                "system": "Amica persona: be friendly.",
                "messages": [
                    {"role": "system", "content": "Amica persona: be friendly."},
                    {"role": "user", "content": "hello there"},
                ],
            },
        ),
        (
            "raw_text_combined",
            {"text": "system: Amica persona be friendly\nuser: open calculator"},
        ),
        (
            "ambiguous_history",
            {
                # Simulate a history where previous KEVIN assistant reply might confuse routing
                "messages": [
                    {"role": "system", "content": "Amica persona"},
                    {"role": "user", "content": "open calculator"},
                    {"role": "assistant", "content": "Please provide the instruction."},
                    {"role": "user", "content": "hello"},
                ]
            }
        )
    ]

    for name, body in tests:
        print('\n' + '='*10 + f' TEST: {name} ' + '='*10)
        req = FakeRequest(body)
        try:
            resp = await ALICE_v2.gui_input(req)
        except Exception as e:
            print(f"gui_input raised exception: {e}")
            continue

        # Try to read JSONResponse body
        try:
            status = getattr(resp, 'status_code', None) or getattr(resp, 'status', None) or '??'
            body_bytes = getattr(resp, 'body', None)
            if body_bytes:
                decoded = body_bytes.decode('utf-8', errors='replace')
                try:
                    parsed = json.loads(decoded)
                    print('STATUS:', status)
                    print('RESPONSE JSON:', json.dumps(parsed, indent=2))
                except Exception:
                    print('STATUS:', status)
                    print('RESPONSE (raw):', decoded)
            else:
                # fallback: try .media or .body
                if hasattr(resp, 'media'):
                    print('STATUS:', status)
                    print('RESPONSE media:', resp.media)
                else:
                    print('STATUS:', status)
                    print('RESPONSE object:', resp)
        except Exception as e:
            print('Error reading response:', e)

if __name__ == '__main__':
    asyncio.run(run_test())

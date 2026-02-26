import os
import asyncio
import json

import amica_alice_bridge as bridge

class FakeReq:
    def __init__(self, headers=None, query_params=None):
        self.headers = headers or {}
        self.query_params = query_params or {}
    async def json(self):
        return self._body

# ensure module's BRIDGE_API_KEY is used
req = FakeReq(headers={'x-bridge-api-key': bridge.BRIDGE_API_KEY}, query_params={})

async def run_test():
    # Provide a body with 'open calculator' and confirm True
    body = {'text': 'open calculator', 'confirm': True}
    # attach body to fake request to satisfy any .json() calls
    req._body = body
    try:
        res = await bridge.bridge_alice(req, body)
        print('bridge_alice result:', res)
    except Exception as e:
        print('bridge_alice raised:', e)

if __name__ == '__main__':
    asyncio.run(run_test())

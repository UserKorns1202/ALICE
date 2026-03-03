"""Test runner for the OCR service scaffold.

Starts the local bus, starts the OCR worker stub, subscribes to messages and
prints them to stdout. Publishes several test capture messages to simulate
activity. This produces the same JSON-like messages `ALICE` would receive.
"""
import threading
import time
from .bus import BusServer, subscribe_forever
from .ocr_worker import run_worker
from .capture import capture_and_publish
from .integration import start_integration


def _printer_callback(msg: dict):
    try:
        topic = msg.get('topic')
        payload = msg.get('payload')
    except Exception:
        return
    print(f"RECV TOPIC={topic} PAYLOAD={payload}")


def main(run_seconds: float = 4.0):
    stop_event = threading.Event()

    # Start the bus server
    server = BusServer()
    server.start()
    print('BusServer started')

    # Start OCR worker in a background thread
    worker_thread = threading.Thread(target=run_worker, kwargs={'stop_event': stop_event}, daemon=True)
    worker_thread.start()
    print('OCR worker started')

    # Start a subscriber that prints received messages
    subscriber_thread = threading.Thread(target=subscribe_forever, args=(server.host, server.port, _printer_callback, stop_event), daemon=True)
    subscriber_thread.start()
    print('Subscriber started (printing incoming messages)')

    # Start integration service and a simple ALICE callback that prints decisions
    def alice_callback(decision: dict):
        action = decision.get('action')
        score = decision.get('score')
        payload = decision.get('payload')
        print(f"ALICE_DECISION action={action} score={score:.2f} app={payload.get('app')} text={payload.get('text')}")

    integration = start_integration(alice_callback, host=server.host, port=server.port)
    print('Integration service started (decision engine)')

    # Publish a few test capture events
    for i in range(3):
        time.sleep(0.5)
        try:
            p = capture_and_publish(server.host, server.port)
            print('Sent capture:', p)
        except Exception as e:
            print('Capture failed:', e)

    # Allow time for worker responses
    time.sleep(run_seconds)

    # Shutdown
    stop_event.set()
    integration.stop()
    server.stop()
    print('Stopped bus and worker. Exiting test runner.')


if __name__ == '__main__':
    main()

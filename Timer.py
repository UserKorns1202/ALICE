import threading
import time

class TimerThread(threading.Thread):
    def __init__(self, duration, callback):
        threading.Thread.__init__(self)
        self.duration = duration
        self.callback = callback

    def run(self):
        print(f"Timer started for {self.duration} seconds.")
        time.sleep(self.duration)
        print("\n\nTimer finished.\n")
        self.callback()

def timer_callback():
    print("Your timer has finished")

def set_timer(duration):
    timer_thread = TimerThread(duration, timer_callback)
    timer_thread.start()

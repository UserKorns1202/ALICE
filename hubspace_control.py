# hubspace_control.py
from hubspace import login, get_devices, set_on

class HubspaceController:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.devices = get_devices(login(username, password))

    def control(self, name, turn_on=True):
        name = name.lower()
        for dev in self.devices:
            if dev['name'].lower() == name:
                try:
                    set_on(dev, turn_on)
                    return f"{'Powered on' if turn_on else 'Powered off'} '{name}'."
                except Exception as e:
                    return f"Error: {e}"
        return f"Device '{name}' not found."

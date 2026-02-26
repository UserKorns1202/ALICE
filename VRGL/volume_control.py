from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
import sys

class VolumeControl:
    def __init__(self):
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        self.volume = cast(interface, POINTER(IAudioEndpointVolume))

    def set_volume(self, level):
        """Sets the volume to the specified level (0.0 to 1.0)"""
        if 0.0 <= level <= 1.0:
            self.volume.SetMasterVolumeLevelScalar(level, None)
            print(f"Volume set to {level * 100}%")
        else:
            print("Volume level must be between 0.0 and 1.0")

    def get_volume(self):
        """Returns the current volume level"""
        current_volume = self.volume.GetMasterVolumeLevelScalar()
        print(f"Current volume is {current_volume * 100}%")
        return current_volume

if __name__ == "__main__":
    vol_control = VolumeControl()
    
    if len(sys.argv) != 2:
        print("Usage: python ALICE_volume_control.py <volume_level>")
        print("Volume level should be between 0.0 and 1.0")
    else:
        try:
            volume_level = float(sys.argv[1])
            vol_control.set_volume(volume_level)
        except ValueError:
            print("Please enter a valid number between 0.0 and 1.0")

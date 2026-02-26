from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
import sys
from com_utils import com_init


class VolumeControl:
    """Volume control helper that performs COM activation per-call

    Creating COM objects once and letting them be garbage-collected can
    trigger comtypes destructor races on shutdown. To avoid that, create
    and release the COM interface inside each method while ensuring
    CoInitialize/CoUninitialize are called on the current thread.
    """

    def _with_volume(self, func):
        """Helper: activate endpoint, run func(volume), then clean up."""
        with com_init():
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            try:
                return func(volume)
            finally:
                try:
                    # Remove references promptly so comtypes destructor runs here
                    del volume
                    del interface
                    del devices
                except Exception:
                    pass

    def set_volume(self, level):
        """Sets the volume to the specified level (0.0 to 1.0)"""
        if not (0.0 <= level <= 1.0):
            print("Volume level must be between 0.0 and 1.0")
            return

        def _do(vol):
            vol.SetMasterVolumeLevelScalar(level, None)
            return None

        self._with_volume(_do)
        print(f"Volume set to {level * 100}%")

    def get_volume(self):
        """Returns the current volume level"""
        def _do(vol):
            return vol.GetMasterVolumeLevelScalar()

        current_volume = self._with_volume(_do)
        try:
            print(f"Current volume is {current_volume * 100}%")
        except Exception:
            pass
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

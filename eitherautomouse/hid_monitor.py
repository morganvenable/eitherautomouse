"""
HID Device Monitoring for EitherAutoMouse.

Provides functionality to:
- Enumerate connected HID devices (mice, trackballs, keyboards)
- Monitor for device changes
- Filter devices by VID/PID pairs

Note: On Windows, mice claimed by the OS cannot be directly read via hidapi.
This module provides device enumeration for UI and filtering purposes.
Mouse activity detection is handled via pynput in the keyboard module.
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple
import logging
import threading
import time

logger = logging.getLogger(__name__)

# Try to import hidapi
try:
    import hid
    HID_AVAILABLE = True
except ImportError:
    HID_AVAILABLE = False
    logger.warning("hidapi not available - device enumeration disabled")

# HID Usage Page and Usage constants
USAGE_PAGE_GENERIC_DESKTOP = 0x01
USAGE_MOUSE = 0x02
USAGE_KEYBOARD = 0x06
USAGE_POINTER = 0x01
USAGE_JOYSTICK = 0x04
USAGE_GAMEPAD = 0x05


@dataclass
class HIDDevice:
    """Represents a HID device with its properties."""
    vendor_id: int
    product_id: int
    path: bytes
    manufacturer: str
    product: str
    serial: str
    usage_page: int
    usage: int
    interface_number: int

    @property
    def vid_pid(self) -> Tuple[int, int]:
        """Return (vendor_id, product_id) tuple."""
        return (self.vendor_id, self.product_id)

    @property
    def is_pointing_device(self) -> bool:
        """Check if this device is a mouse or trackball."""
        if self.usage_page != USAGE_PAGE_GENERIC_DESKTOP:
            return False
        return self.usage in (USAGE_MOUSE, USAGE_POINTER)

    @property
    def is_keyboard(self) -> bool:
        """Check if this device is a keyboard."""
        return (self.usage_page == USAGE_PAGE_GENERIC_DESKTOP and
                self.usage == USAGE_KEYBOARD)

    @property
    def display_name(self) -> str:
        """Get a human-readable name for the device."""
        if self.product:
            return self.product
        if self.manufacturer:
            return f"{self.manufacturer} Device"
        return f"Device {self.vendor_id:04X}:{self.product_id:04X}"

    def __hash__(self):
        return hash(self.path)

    def __eq__(self, other):
        if not isinstance(other, HIDDevice):
            return False
        return self.path == other.path


def enumerate_all_devices() -> List[HIDDevice]:
    """
    Enumerate all connected HID devices.

    Returns an empty list if hidapi is not available.
    """
    if not HID_AVAILABLE:
        return []

    devices = []
    try:
        for dev in hid.enumerate():
            devices.append(HIDDevice(
                vendor_id=dev.get("vendor_id", 0),
                product_id=dev.get("product_id", 0),
                path=dev.get("path", b""),
                manufacturer=dev.get("manufacturer_string", "") or "",
                product=dev.get("product_string", "") or "",
                serial=dev.get("serial_number", "") or "",
                usage_page=dev.get("usage_page", 0),
                usage=dev.get("usage", 0),
                interface_number=dev.get("interface_number", -1),
            ))
    except Exception as e:
        logger.error(f"Error enumerating HID devices: {e}")

    return devices


def enumerate_pointing_devices() -> List[HIDDevice]:
    """Get a list of all connected pointing devices (mice, trackballs)."""
    return [d for d in enumerate_all_devices() if d.is_pointing_device]


def enumerate_keyboards() -> List[HIDDevice]:
    """Get a list of all connected keyboards."""
    return [d for d in enumerate_all_devices() if d.is_keyboard]


class HIDMonitor:
    """
    Monitors HID devices and notifies on changes.

    This class runs a background thread that periodically checks for
    device connection/disconnection events.
    """

    def __init__(
        self,
        poll_interval: float = 1.0,
        target_vids_pids: Optional[Set[Tuple[int, int]]] = None
    ):
        """
        Initialize the HID monitor.

        Args:
            poll_interval: How often to check for device changes (seconds)
            target_vids_pids: Optional set of (vid, pid) tuples to filter for
        """
        self.poll_interval = poll_interval
        self.target_vids_pids = target_vids_pids
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._known_devices: Dict[bytes, HIDDevice] = {}

        # Callbacks
        self._on_device_added: Optional[Callable[[HIDDevice], None]] = None
        self._on_device_removed: Optional[Callable[[HIDDevice], None]] = None

    def set_callbacks(
        self,
        on_added: Optional[Callable[[HIDDevice], None]] = None,
        on_removed: Optional[Callable[[HIDDevice], None]] = None
    ):
        """Set callbacks for device events."""
        self._on_device_added = on_added
        self._on_device_removed = on_removed

    def start(self):
        """Start monitoring for device changes."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("HID monitor started")

    def stop(self):
        """Stop monitoring for device changes."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("HID monitor stopped")

    def get_pointing_devices(self) -> List[HIDDevice]:
        """Get current list of pointing devices."""
        with self._lock:
            return [d for d in self._known_devices.values() if d.is_pointing_device]

    def get_keyboards(self) -> List[HIDDevice]:
        """Get current list of keyboards."""
        with self._lock:
            return [d for d in self._known_devices.values() if d.is_keyboard]

    def _should_track(self, device: HIDDevice) -> bool:
        """Check if we should track this device."""
        # Only track pointing devices and keyboards
        if not (device.is_pointing_device or device.is_keyboard):
            return False

        # If we have a filter, apply it
        if self.target_vids_pids:
            return device.vid_pid in self.target_vids_pids

        return True

    def _monitor_loop(self):
        """Background thread that monitors for device changes."""
        # Initial enumeration
        self._update_devices()

        while self._running:
            time.sleep(self.poll_interval)
            if self._running:
                self._update_devices()

    def _update_devices(self):
        """Check for device changes and notify callbacks."""
        try:
            current_devices = {
                d.path: d for d in enumerate_all_devices()
                if self._should_track(d)
            }
        except Exception as e:
            logger.error(f"Error updating devices: {e}")
            return

        with self._lock:
            # Find added devices
            for path, device in current_devices.items():
                if path not in self._known_devices:
                    self._known_devices[path] = device
                    if self._on_device_added:
                        threading.Thread(
                            target=self._on_device_added,
                            args=(device,),
                            daemon=True
                        ).start()
                    logger.info(f"Device added: {device.display_name}")

            # Find removed devices
            removed_paths = set(self._known_devices.keys()) - set(current_devices.keys())
            for path in removed_paths:
                device = self._known_devices.pop(path)
                if self._on_device_removed:
                    threading.Thread(
                        target=self._on_device_removed,
                        args=(device,),
                        daemon=True
                    ).start()
                logger.info(f"Device removed: {device.display_name}")


def get_device_info_table() -> List[Dict]:
    """
    Get device information as a list of dictionaries for display.

    Returns a list suitable for displaying in a UI table.
    """
    devices = enumerate_all_devices()
    table = []

    for dev in devices:
        if dev.is_pointing_device or dev.is_keyboard:
            table.append({
                "name": dev.display_name,
                "type": "Mouse" if dev.is_pointing_device else "Keyboard",
                "vid": f"0x{dev.vendor_id:04X}",
                "pid": f"0x{dev.product_id:04X}",
                "manufacturer": dev.manufacturer,
            })

    return table

"""
Main Application for EitherAutoMouse.

Ties together all components:
- Configuration loading
- HID device monitoring
- Layer state machine
- Keyboard controller with mouse actions
- System tray icon for status and control
"""

import logging
import os
import platform
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Import our modules
from .config import (
    Config, load_config, save_config, get_config_path,
    ensure_config_exists, create_default_config
)
from .hid_monitor import HIDMonitor, get_device_info_table, HID_AVAILABLE
from .state import LayerStateMachine, LayerState
from .keyboard import KeyboardController, install_unmapped_key_hook

# Import system tray and image libraries
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    logger.warning("pystray or Pillow not available - no system tray icon")


def create_icon_image(active: bool = False, size: int = 64) -> "Image":
    """
    Create a simple mouse icon for the system tray.

    Args:
        active: If True, icon is green (layer active). Otherwise gray.
        size: Icon size in pixels.
    """
    # Colors
    if active:
        bg_color = (46, 204, 113)  # Green
        fg_color = (255, 255, 255)  # White
    else:
        bg_color = (149, 165, 166)  # Gray
        fg_color = (255, 255, 255)  # White

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw mouse body (rounded rectangle approximation)
    margin = size // 8
    body_left = margin
    body_right = size - margin
    body_top = size // 4
    body_bottom = size - margin

    # Mouse body
    draw.ellipse([body_left, body_top, body_right, body_bottom], fill=bg_color)
    draw.rectangle([body_left, body_top + (body_bottom - body_top) // 3,
                    body_right, body_bottom - (body_bottom - body_top) // 4],
                   fill=bg_color)

    # Mouse wheel (center line)
    center_x = size // 2
    wheel_top = body_top + margin
    wheel_bottom = body_top + (body_bottom - body_top) // 3
    draw.rectangle([center_x - 2, wheel_top, center_x + 2, wheel_bottom], fill=fg_color)

    # Mouse buttons divider
    draw.line([center_x, body_top, center_x, wheel_bottom], fill=fg_color, width=1)

    return img


def show_device_dialog():
    """Show a dialog listing connected HID devices."""
    if not HID_AVAILABLE:
        logger.warning("Cannot show device dialog - hidapi not available")
        return

    devices = get_device_info_table()

    # Create Tkinter window
    root = tk.Tk()
    root.title("EitherAutoMouse - Connected Devices")
    root.geometry("600x400")

    # Create treeview
    columns = ("name", "type", "vid", "pid", "manufacturer")
    tree = ttk.Treeview(root, columns=columns, show="headings")

    tree.heading("name", text="Device Name")
    tree.heading("type", text="Type")
    tree.heading("vid", text="Vendor ID")
    tree.heading("pid", text="Product ID")
    tree.heading("manufacturer", text="Manufacturer")

    tree.column("name", width=200)
    tree.column("type", width=80)
    tree.column("vid", width=80)
    tree.column("pid", width=80)
    tree.column("manufacturer", width=150)

    for dev in devices:
        tree.insert("", tk.END, values=(
            dev["name"],
            dev["type"],
            dev["vid"],
            dev["pid"],
            dev["manufacturer"]
        ))

    tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Close button
    close_btn = ttk.Button(root, text="Close", command=root.destroy)
    close_btn.pack(pady=10)

    root.mainloop()


class EitherAutoMouse:
    """Main application controller."""

    def __init__(self):
        """Initialize the application."""
        self.config: Optional[Config] = None
        self.state_machine: Optional[LayerStateMachine] = None
        self.keyboard_controller: Optional[KeyboardController] = None
        self.hid_monitor: Optional[HIDMonitor] = None
        self.tray_icon: Optional["pystray.Icon"] = None
        self._unmapped_key_unhook: Optional[callable] = None
        self._running = False

    def load_configuration(self):
        """Load configuration from file."""
        ensure_config_exists()
        self.config = load_config()
        logger.info(f"Loaded configuration from {get_config_path()}")
        logger.info(f"Layer timeout: {self.config.layer.timeout_ms}ms")
        logger.info(f"Key mappings: {list(self.config.layer.mappings.keys())}")

    def reload_configuration(self):
        """Reload configuration from file."""
        self.load_configuration()

        # Update state machine
        if self.state_machine:
            self.state_machine.timeout_ms = self.config.layer.timeout_ms
            self.state_machine.exit_on_other_key = self.config.layer.exit_on_other_key

        # Update keyboard controller mappings
        if self.keyboard_controller:
            self.keyboard_controller.set_mappings(self.config.layer.mappings)

            # Reinstall unmapped key hook
            if self._unmapped_key_unhook:
                self._unmapped_key_unhook()
            self._setup_unmapped_key_hook()

        logger.info("Configuration reloaded")

    def _setup_unmapped_key_hook(self):
        """Set up hook for unmapped key detection."""
        if self.state_machine and self.keyboard_controller:
            mapped_keys = self.keyboard_controller.get_mapped_keys()
            self._unmapped_key_unhook = install_unmapped_key_hook(
                mapped_keys,
                self.state_machine.on_unmapped_key
            )

    def _on_state_change(self, new_state: LayerState):
        """Handle layer state changes."""
        is_active = new_state != LayerState.NORMAL

        # Update keyboard controller
        if self.keyboard_controller:
            self.keyboard_controller.set_layer_active(is_active)

        # Update tray icon
        self._update_tray_icon(is_active)

        logger.info(f"Layer state: {new_state.name}")

    def _update_tray_icon(self, active: bool):
        """Update the system tray icon to reflect current state."""
        if self.tray_icon and TRAY_AVAILABLE:
            self.tray_icon.icon = create_icon_image(active)

    def _create_tray_menu(self) -> "pystray.Menu":
        """Create the system tray context menu."""
        def get_status(item):
            # pystray passes the menu item as argument to dynamic text functions
            if self.state_machine:
                return f"Status: {self.state_machine.state.name}"
            return "Status: Unknown"

        return pystray.Menu(
            pystray.MenuItem(
                get_status,
                None,
                enabled=False
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Toggle Latch",
                lambda: self.state_machine.toggle_latch() if self.state_machine else None
            ),
            pystray.MenuItem(
                "Exit Layer",
                lambda: self.state_machine.exit_layer() if self.state_machine else None
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Show Devices",
                lambda: threading.Thread(target=show_device_dialog, daemon=True).start()
            ),
            pystray.MenuItem(
                "Open Config File",
                self._open_config_file
            ),
            pystray.MenuItem(
                "Reload Config",
                lambda: self.reload_configuration()
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Exit",
                self.stop
            )
        )

    def _open_config_file(self):
        """Open the configuration file in the default editor."""
        config_path = get_config_path()

        try:
            if platform.system() == "Windows":
                os.startfile(str(config_path))
            elif platform.system() == "Darwin":
                subprocess.run(["open", str(config_path)])
            else:
                subprocess.run(["xdg-open", str(config_path)])
        except Exception as e:
            logger.error(f"Failed to open config file: {e}")

    def start(self):
        """Start the application."""
        if self._running:
            return

        self._running = True
        logger.info("Starting EitherAutoMouse...")

        # Load configuration
        self.load_configuration()

        # Initialize state machine
        self.state_machine = LayerStateMachine(
            timeout_ms=self.config.layer.timeout_ms,
            exit_on_other_key=self.config.layer.exit_on_other_key
        )
        self.state_machine.add_listener(self._on_state_change)

        # Initialize keyboard controller
        self.keyboard_controller = KeyboardController()
        self.keyboard_controller.set_mappings(self.config.layer.mappings)
        self.keyboard_controller.set_callbacks(
            on_mouse_activity=self.state_machine.on_mouse_activity,
            on_mapped_key=self.state_machine.on_mapped_key
        )
        self.keyboard_controller.start()

        # Setup unmapped key hook
        self._setup_unmapped_key_hook()

        # Initialize HID monitor (optional, for device enumeration)
        if HID_AVAILABLE:
            self.hid_monitor = HIDMonitor()
            self.hid_monitor.start()

        # Create system tray icon
        if TRAY_AVAILABLE:
            self.tray_icon = pystray.Icon(
                "EitherAutoMouse",
                create_icon_image(False),
                "EitherAutoMouse",
                self._create_tray_menu()
            )
            logger.info("Starting system tray icon...")
            self.tray_icon.run()  # This blocks until stop is called
        else:
            # No tray available, just run in console mode
            logger.info("Running in console mode (no system tray)")
            try:
                while self._running:
                    import time
                    time.sleep(0.1)
            except KeyboardInterrupt:
                pass

    def stop(self):
        """Stop the application and clean up resources."""
        logger.info("Stopping EitherAutoMouse...")
        self._running = False

        # Stop keyboard controller
        if self.keyboard_controller:
            self.keyboard_controller.stop()
            self.keyboard_controller = None

        # Stop state machine
        if self.state_machine:
            self.state_machine.stop()
            self.state_machine = None

        # Stop HID monitor
        if self.hid_monitor:
            self.hid_monitor.stop()
            self.hid_monitor = None

        # Remove unmapped key hook
        if self._unmapped_key_unhook:
            try:
                self._unmapped_key_unhook()
            except Exception:
                pass
            self._unmapped_key_unhook = None

        # Stop tray icon
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None

        logger.info("EitherAutoMouse stopped")


def main():
    """Entry point for the application."""
    # Check platform
    if platform.system() != "Windows":
        logger.warning(
            "EitherAutoMouse is designed for Windows. "
            "Some features may not work on other platforms."
        )

    # Create and start application
    app = EitherAutoMouse()

    try:
        app.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        app.stop()


if __name__ == "__main__":
    main()

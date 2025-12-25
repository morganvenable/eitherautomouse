"""
Keyboard and Mouse Controller for EitherAutoMouse.

Handles:
- Keyboard hook installation for mapped keys
- Mouse action execution (clicks, scrolls)
- Mouse movement monitoring to detect activity
- Clipboard shortcut execution
"""

from enum import Enum, auto
from typing import Callable, Dict, Optional, Set
import logging
import queue
import threading

logger = logging.getLogger(__name__)

# Import keyboard library for hooking
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    logger.warning("keyboard library not available")

# Import pynput for mouse control and monitoring
try:
    from pynput import mouse
    from pynput.mouse import Button, Controller as MouseController
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    logger.warning("pynput not available")


class MouseAction(Enum):
    """Possible mouse actions that can be triggered."""
    LEFT_CLICK = auto()
    RIGHT_CLICK = auto()
    MIDDLE_CLICK = auto()
    SCROLL_UP = auto()
    SCROLL_DOWN = auto()
    SCROLL_LEFT = auto()
    SCROLL_RIGHT = auto()


# Map string names to MouseAction enum
ACTION_MAP: Dict[str, MouseAction] = {
    "left_click": MouseAction.LEFT_CLICK,
    "right_click": MouseAction.RIGHT_CLICK,
    "middle_click": MouseAction.MIDDLE_CLICK,
    "scroll_up": MouseAction.SCROLL_UP,
    "scroll_down": MouseAction.SCROLL_DOWN,
    "scroll_left": MouseAction.SCROLL_LEFT,
    "scroll_right": MouseAction.SCROLL_RIGHT,
}


class KeyboardController:
    """
    Manages keyboard hooks and mouse action execution.

    When the layer is active, intercepts configured keys and translates
    them to mouse actions. Also monitors mouse movement to detect activity.
    """

    def __init__(self):
        """Initialize the keyboard controller."""
        self._mappings: Dict[str, str] = {}  # key -> action string
        self._active = False
        self._running = False
        self._lock = threading.Lock()

        # Action queue for thread-safe mouse operations
        self._action_queue: queue.Queue = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None

        # Mouse controller and listener
        self._mouse: Optional[MouseController] = None
        self._mouse_listener: Optional[mouse.Listener] = None

        # Registered hotkey handlers
        self._hotkeys: Set[str] = set()

        # Callbacks
        self._on_mouse_activity: Optional[Callable[[], None]] = None
        self._on_mapped_key: Optional[Callable[[], None]] = None
        self._on_unmapped_key: Optional[Callable[[], None]] = None

        # Track pressed keys for proper release
        self._pressed_buttons: Set[Button] = set()

        # Last mouse position for movement detection
        self._last_mouse_pos: Optional[tuple] = None

    def set_callbacks(
        self,
        on_mouse_activity: Optional[Callable[[], None]] = None,
        on_mapped_key: Optional[Callable[[], None]] = None,
        on_unmapped_key: Optional[Callable[[], None]] = None
    ):
        """Set callbacks for various events."""
        self._on_mouse_activity = on_mouse_activity
        self._on_mapped_key = on_mapped_key
        self._on_unmapped_key = on_unmapped_key

    def set_mappings(self, mappings: Dict[str, str]):
        """
        Set the key-to-action mappings.

        Args:
            mappings: Dictionary of key names to action strings
                     (e.g., {"f": "left_click", "e": "scroll_up"})
        """
        with self._lock:
            self._mappings = mappings.copy()
            logger.info(f"Mappings set: {list(mappings.keys())}")

    def set_layer_active(self, active: bool):
        """
        Enable or disable the keyboard layer.

        When active, mapped keys are intercepted and converted to mouse actions.
        When inactive, keys work normally.
        """
        with self._lock:
            if active == self._active:
                return

            self._active = active
            if active:
                self._register_hotkeys()
                logger.info("Layer activated - hotkeys registered")
            else:
                self._unregister_hotkeys()
                self._release_all_buttons()
                logger.info("Layer deactivated - hotkeys unregistered")

    def start(self):
        """Start the controller (mouse listener and action worker)."""
        if self._running:
            return

        self._running = True

        # Initialize mouse controller
        if PYNPUT_AVAILABLE:
            self._mouse = MouseController()

            # Start mouse listener for movement detection
            self._mouse_listener = mouse.Listener(
                on_move=self._on_mouse_move,
                on_click=self._on_mouse_click,
                on_scroll=self._on_mouse_scroll
            )
            self._mouse_listener.start()

        # Start action worker thread
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

        logger.info("Keyboard controller started")

    def stop(self):
        """Stop the controller and clean up resources."""
        self._running = False

        # Unregister hotkeys
        self._unregister_hotkeys()
        self._release_all_buttons()

        # Stop mouse listener
        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None

        # Stop worker thread
        self._action_queue.put(None)  # Sentinel to stop worker
        if self._worker_thread:
            self._worker_thread.join(timeout=1.0)
            self._worker_thread = None

        logger.info("Keyboard controller stopped")

    def _register_hotkeys(self):
        """Register keyboard hooks for mapped keys."""
        if not KEYBOARD_AVAILABLE:
            return

        self._unregister_hotkeys()  # Clear any existing

        for key, action in self._mappings.items():
            # Skip modifier combination shortcuts (handled separately)
            if "+" in action and action not in ACTION_MAP:
                self._register_shortcut_key(key, action)
            else:
                self._register_mouse_key(key, action)

    def _register_mouse_key(self, key: str, action: str):
        """Register a key that maps to a mouse action."""
        if action not in ACTION_MAP:
            logger.warning(f"Unknown action '{action}' for key '{key}'")
            return

        mouse_action = ACTION_MAP[action]

        try:
            # Use keyboard library to hook the key
            keyboard.on_press_key(key, lambda e, a=mouse_action: self._on_mapped_press(a), suppress=True)
            keyboard.on_release_key(key, lambda e, a=mouse_action: self._on_mapped_release(a), suppress=True)
            self._hotkeys.add(key)
        except Exception as e:
            logger.error(f"Failed to register hotkey '{key}': {e}")

    def _register_shortcut_key(self, key: str, shortcut: str):
        """Register a key that triggers a keyboard shortcut."""
        try:
            keyboard.on_press_key(key, lambda e, s=shortcut: self._on_shortcut_press(s), suppress=True)
            keyboard.on_release_key(key, lambda e, s=shortcut: self._on_shortcut_release(s), suppress=True)
            self._hotkeys.add(key)
        except Exception as e:
            logger.error(f"Failed to register shortcut key '{key}': {e}")

    def _unregister_hotkeys(self):
        """Unregister all keyboard hooks."""
        if not KEYBOARD_AVAILABLE:
            return

        for key in self._hotkeys:
            try:
                keyboard.unhook_key(key)
            except Exception as e:
                logger.debug(f"Error unhooking key '{key}': {e}")

        self._hotkeys.clear()

    def _on_mapped_press(self, action: MouseAction):
        """Handle press of a mapped key."""
        if not self._active:
            return

        # Notify callback
        if self._on_mapped_key:
            self._on_mapped_key()

        # Queue the action
        self._action_queue.put(("press", action))

    def _on_mapped_release(self, action: MouseAction):
        """Handle release of a mapped key."""
        if not self._active:
            return

        self._action_queue.put(("release", action))

    def _on_shortcut_press(self, shortcut: str):
        """Handle press of a shortcut key."""
        if not self._active:
            return

        if self._on_mapped_key:
            self._on_mapped_key()

        # Execute the shortcut
        try:
            keyboard.press(shortcut)
        except Exception as e:
            logger.error(f"Failed to press shortcut '{shortcut}': {e}")

    def _on_shortcut_release(self, shortcut: str):
        """Handle release of a shortcut key."""
        if not self._active:
            return

        try:
            keyboard.release(shortcut)
        except Exception as e:
            logger.error(f"Failed to release shortcut '{shortcut}': {e}")

    def _worker_loop(self):
        """Background thread that processes queued mouse actions."""
        while self._running:
            try:
                item = self._action_queue.get(timeout=0.1)
                if item is None:  # Sentinel
                    break

                event_type, action = item
                self._do_mouse_action(event_type, action)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in action worker: {e}")

    def _do_mouse_action(self, event_type: str, action: MouseAction):
        """Execute a mouse action."""
        if not self._mouse:
            return

        try:
            if event_type == "press":
                if action == MouseAction.LEFT_CLICK:
                    self._mouse.press(Button.left)
                    self._pressed_buttons.add(Button.left)
                elif action == MouseAction.RIGHT_CLICK:
                    self._mouse.press(Button.right)
                    self._pressed_buttons.add(Button.right)
                elif action == MouseAction.MIDDLE_CLICK:
                    self._mouse.press(Button.middle)
                    self._pressed_buttons.add(Button.middle)
                elif action == MouseAction.SCROLL_UP:
                    self._mouse.scroll(0, 3)  # Scroll up
                elif action == MouseAction.SCROLL_DOWN:
                    self._mouse.scroll(0, -3)  # Scroll down
                elif action == MouseAction.SCROLL_LEFT:
                    self._mouse.scroll(-3, 0)
                elif action == MouseAction.SCROLL_RIGHT:
                    self._mouse.scroll(3, 0)

            elif event_type == "release":
                if action == MouseAction.LEFT_CLICK:
                    self._mouse.release(Button.left)
                    self._pressed_buttons.discard(Button.left)
                elif action == MouseAction.RIGHT_CLICK:
                    self._mouse.release(Button.right)
                    self._pressed_buttons.discard(Button.right)
                elif action == MouseAction.MIDDLE_CLICK:
                    self._mouse.release(Button.middle)
                    self._pressed_buttons.discard(Button.middle)
                # Scroll actions don't have release

        except Exception as e:
            logger.error(f"Error executing mouse action {action}: {e}")

    def _release_all_buttons(self):
        """Release any held mouse buttons."""
        if not self._mouse:
            return

        for button in list(self._pressed_buttons):
            try:
                self._mouse.release(button)
            except Exception:
                pass
        self._pressed_buttons.clear()

    def _on_mouse_move(self, x: int, y: int):
        """Called when mouse is moved."""
        # Check if this is actual movement (not just position polling)
        if self._last_mouse_pos is not None:
            if (x, y) != self._last_mouse_pos:
                if self._on_mouse_activity:
                    self._on_mouse_activity()
        self._last_mouse_pos = (x, y)

    def _on_mouse_click(self, x: int, y: int, button: Button, pressed: bool):
        """Called when mouse button is clicked."""
        # Only count actual mouse clicks, not our simulated ones
        if button not in self._pressed_buttons:
            if self._on_mouse_activity:
                self._on_mouse_activity()

    def _on_mouse_scroll(self, x: int, y: int, dx: int, dy: int):
        """Called when mouse wheel is scrolled."""
        if self._on_mouse_activity:
            self._on_mouse_activity()

    def get_mapped_keys(self) -> Set[str]:
        """Get the set of currently mapped keys."""
        with self._lock:
            return set(self._mappings.keys())


def install_unmapped_key_hook(
    mapped_keys: Set[str],
    callback: Callable[[], None]
) -> Optional[Callable]:
    """
    Install a hook that calls the callback when any unmapped key is pressed.

    Returns a function to uninstall the hook, or None if failed.
    """
    if not KEYBOARD_AVAILABLE:
        return None

    def on_key(event):
        if event.event_type == "down" and event.name not in mapped_keys:
            # Ignore modifier keys
            if event.name not in ("shift", "ctrl", "alt", "cmd", "windows"):
                callback()

    try:
        keyboard.hook(on_key)
        return lambda: keyboard.unhook(on_key)
    except Exception as e:
        logger.error(f"Failed to install unmapped key hook: {e}")
        return None

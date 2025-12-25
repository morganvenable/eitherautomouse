"""
State Machine for EitherAutoMouse Layer Management.

Manages the layer state transitions:
- NORMAL: Default state, keyboard works normally
- MOUSE_LAYER_ACTIVE: Mouse activity detected, layer is temporarily active
- LATCHED: Layer is persistent until explicitly exited

The layer activates when mouse movement is detected and deactivates after
a timeout period of inactivity or when an unmapped key is pressed.
"""

from enum import Enum, auto
from typing import Callable, List, Optional
import logging
import threading
import time

logger = logging.getLogger(__name__)


class LayerState(Enum):
    """Possible states for the mouse layer."""
    NORMAL = auto()           # Layer inactive, keyboard works normally
    MOUSE_LAYER_ACTIVE = auto()  # Layer temporarily active
    LATCHED = auto()          # Layer locked active until explicit exit


class LayerStateMachine:
    """
    Manages the mouse layer state with timeout and latch support.

    The state machine responds to:
    - Mouse activity (activates/refreshes layer)
    - Mapped key events (keeps layer active)
    - Unmapped key events (exits layer if configured)
    - Explicit latch/unlatch commands
    - Timeout (returns to normal after inactivity)
    """

    def __init__(self, timeout_ms: int = 500, exit_on_other_key: bool = True):
        """
        Initialize the state machine.

        Args:
            timeout_ms: Milliseconds of inactivity before layer deactivates
            exit_on_other_key: Whether unmapped keys should exit the layer
        """
        self._state = LayerState.NORMAL
        self._timeout_ms = timeout_ms
        self._exit_on_other_key = exit_on_other_key
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None
        self._listeners: List[Callable[[LayerState], None]] = []
        self._last_activity: float = 0

    @property
    def state(self) -> LayerState:
        """Get the current layer state."""
        with self._lock:
            return self._state

    @property
    def is_active(self) -> bool:
        """Check if the layer is currently active (either active or latched)."""
        with self._lock:
            return self._state != LayerState.NORMAL

    @property
    def timeout_ms(self) -> int:
        """Get the current timeout value in milliseconds."""
        return self._timeout_ms

    @timeout_ms.setter
    def timeout_ms(self, value: int):
        """Set the timeout value in milliseconds."""
        self._timeout_ms = max(100, value)  # Minimum 100ms

    @property
    def exit_on_other_key(self) -> bool:
        """Check if unmapped keys should exit the layer."""
        return self._exit_on_other_key

    @exit_on_other_key.setter
    def exit_on_other_key(self, value: bool):
        """Set whether unmapped keys should exit the layer."""
        self._exit_on_other_key = value

    def add_listener(self, callback: Callable[[LayerState], None]):
        """
        Add a listener to be notified of state changes.

        The callback will be called on a separate thread.
        """
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[LayerState], None]):
        """Remove a state change listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self, new_state: LayerState):
        """Notify all listeners of a state change."""
        for listener in self._listeners:
            threading.Thread(
                target=listener,
                args=(new_state,),
                daemon=True
            ).start()

    def _cancel_timer(self):
        """Cancel any pending timeout timer."""
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _start_timer(self):
        """Start the inactivity timeout timer."""
        self._cancel_timer()
        timeout_sec = self._timeout_ms / 1000.0
        self._timer = threading.Timer(timeout_sec, self._on_timeout)
        self._timer.daemon = True
        self._timer.start()

    def _on_timeout(self):
        """Called when the inactivity timer expires."""
        with self._lock:
            if self._state == LayerState.MOUSE_LAYER_ACTIVE:
                logger.debug("Layer timeout - returning to normal")
                self._state = LayerState.NORMAL
                self._notify_listeners(LayerState.NORMAL)

    def _set_state(self, new_state: LayerState):
        """Set state and notify listeners (must hold lock)."""
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            logger.debug(f"State change: {old_state.name} -> {new_state.name}")
            self._notify_listeners(new_state)

    def on_mouse_activity(self):
        """
        Called when mouse movement or button activity is detected.

        Activates the layer if not already active, or refreshes the timeout.
        """
        with self._lock:
            self._last_activity = time.time()

            if self._state == LayerState.NORMAL:
                self._set_state(LayerState.MOUSE_LAYER_ACTIVE)
                self._start_timer()
            elif self._state == LayerState.MOUSE_LAYER_ACTIVE:
                # Refresh the timer
                self._start_timer()
            # If LATCHED, do nothing - layer stays active

    def on_mapped_key(self):
        """
        Called when a mapped key is pressed.

        This indicates the user is actively using the layer, so refresh timeout.
        """
        with self._lock:
            if self._state == LayerState.MOUSE_LAYER_ACTIVE:
                self._last_activity = time.time()
                self._start_timer()

    def on_unmapped_key(self):
        """
        Called when an unmapped key is pressed.

        If configured, this exits the layer back to normal mode.
        """
        if not self._exit_on_other_key:
            return

        with self._lock:
            if self._state == LayerState.MOUSE_LAYER_ACTIVE:
                logger.debug("Unmapped key pressed - exiting layer")
                self._cancel_timer()
                self._set_state(LayerState.NORMAL)

    def latch(self):
        """
        Latch the layer active.

        The layer will remain active until explicitly exited, regardless of
        timeout or unmapped keys.
        """
        with self._lock:
            self._cancel_timer()
            if self._state != LayerState.LATCHED:
                self._set_state(LayerState.LATCHED)
                logger.info("Layer latched")

    def unlatch(self):
        """
        Unlatch the layer.

        Returns to MOUSE_LAYER_ACTIVE with timeout, or NORMAL if no recent activity.
        """
        with self._lock:
            if self._state == LayerState.LATCHED:
                # Check if there was recent activity
                if time.time() - self._last_activity < (self._timeout_ms / 1000.0):
                    self._set_state(LayerState.MOUSE_LAYER_ACTIVE)
                    self._start_timer()
                else:
                    self._set_state(LayerState.NORMAL)
                logger.info("Layer unlatched")

    def exit_layer(self):
        """
        Explicitly exit the layer back to normal state.

        This works from both ACTIVE and LATCHED states.
        """
        with self._lock:
            self._cancel_timer()
            if self._state != LayerState.NORMAL:
                self._set_state(LayerState.NORMAL)
                logger.debug("Layer explicitly exited")

    def toggle_latch(self):
        """
        Toggle between latched and unlatched states.

        If normal or active, latch. If latched, unlatch.
        """
        with self._lock:
            if self._state == LayerState.LATCHED:
                self.unlatch()
            else:
                self.latch()

    def stop(self):
        """Clean up resources (cancel timers)."""
        self._cancel_timer()

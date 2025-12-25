"""
Configuration management for EitherAutoMouse.

Handles loading and saving of YAML configuration files, including:
- Device specifications (VID/PID pairs for mice and keyboards)
- Layer configuration (timeout, key mappings)
- Global settings
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
import os
import platform
import yaml

logger = logging.getLogger(__name__)


@dataclass
class DeviceConfig:
    """Configuration for a specific HID device."""
    vid: int  # Vendor ID
    pid: int  # Product ID
    role: str  # "mouse" or "keyboard"
    name: str = ""  # Human-readable name


@dataclass
class LayerConfig:
    """Configuration for the mouse layer behavior."""
    timeout_ms: int = 500  # Milliseconds of inactivity before layer deactivates
    exit_on_other_key: bool = True  # Exit layer when unmapped key is pressed
    mappings: Dict[str, str] = field(default_factory=dict)  # key -> action


@dataclass
class Config:
    """Main configuration container."""
    any_pointing_device: bool = True  # Accept any mouse/trackball
    any_keyboard: bool = True  # Apply to any keyboard
    devices: List[DeviceConfig] = field(default_factory=list)
    layer: LayerConfig = field(default_factory=LayerConfig)


def get_config_dir() -> Path:
    """Get the platform-appropriate configuration directory."""
    system = platform.system()

    if system == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return Path(base) / "EitherAutoMouse"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "EitherAutoMouse"
    else:
        # Linux and others - use XDG standard
        xdg_config = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        return Path(xdg_config) / "eitherautomouse"


def get_config_path() -> Path:
    """Get the full path to the configuration file."""
    return get_config_dir() / "config.yaml"


def parse_hex(value: str) -> int:
    """Parse a hex string (with or without 0x prefix) to int."""
    if isinstance(value, int):
        return value
    value = value.strip()
    if value.lower().startswith("0x"):
        return int(value, 16)
    return int(value, 16)


def load_config(path: Optional[Path] = None) -> Config:
    """
    Load configuration from YAML file.

    If no path is specified, uses the default config location.
    If the file doesn't exist, returns default configuration.
    """
    if path is None:
        path = get_config_path()

    if not path.exists():
        logger.info(f"No config file at {path}, using defaults")
        return create_default_config()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Failed to load config from {path}: {e}")
        return create_default_config()

    config = Config()

    # Global settings
    config.any_pointing_device = data.get("any_pointing_device", True)
    config.any_keyboard = data.get("any_keyboard", True)

    # Device list
    devices_data = data.get("devices", {})
    if isinstance(devices_data, dict):
        for name, dev in devices_data.items():
            if isinstance(dev, dict):
                try:
                    config.devices.append(DeviceConfig(
                        vid=parse_hex(dev.get("vid", "0")),
                        pid=parse_hex(dev.get("pid", "0")),
                        role=dev.get("role", "mouse"),
                        name=name
                    ))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid device config '{name}': {e}")

    # Layer configuration
    layer_data = data.get("layer", {})
    if isinstance(layer_data, dict):
        config.layer.timeout_ms = layer_data.get("timeout_ms", 500)
        config.layer.exit_on_other_key = layer_data.get("exit_on_other_key", True)
        config.layer.mappings = layer_data.get("mappings", {})

    # Ensure we have default mappings if none specified
    if not config.layer.mappings:
        config.layer.mappings = get_default_mappings()

    return config


def get_default_mappings() -> Dict[str, str]:
    """Return the default key-to-action mappings."""
    return {
        # Home row mouse buttons (left hand)
        "f": "left_click",
        "s": "right_click",
        "d": "middle_click",
        # Scroll actions
        "e": "scroll_up",
        "r": "scroll_down",
        # Clipboard shortcuts (convenient when using mouse)
        "x": "ctrl+x",
        "c": "ctrl+c",
        "v": "ctrl+v",
    }


def create_default_config() -> Config:
    """Create a configuration with sensible defaults."""
    return Config(
        any_pointing_device=True,
        any_keyboard=True,
        devices=[],
        layer=LayerConfig(
            timeout_ms=500,
            exit_on_other_key=True,
            mappings=get_default_mappings()
        )
    )


def save_config(config: Config, path: Optional[Path] = None) -> None:
    """
    Save configuration to YAML file.

    Creates the directory if it doesn't exist.
    """
    if path is None:
        path = get_config_path()

    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "any_pointing_device": config.any_pointing_device,
        "any_keyboard": config.any_keyboard,
        "devices": {},
        "layer": {
            "timeout_ms": config.layer.timeout_ms,
            "exit_on_other_key": config.layer.exit_on_other_key,
            "mappings": config.layer.mappings,
        }
    }

    # Add devices
    for dev in config.devices:
        data["devices"][dev.name or f"device_{dev.vid:04x}_{dev.pid:04x}"] = {
            "vid": f"0x{dev.vid:04X}",
            "pid": f"0x{dev.pid:04X}",
            "role": dev.role,
        }

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    logger.info(f"Configuration saved to {path}")


def ensure_config_exists() -> Path:
    """
    Ensure a configuration file exists, creating default if needed.

    Returns the path to the configuration file.
    """
    path = get_config_path()
    if not path.exists():
        config = create_default_config()
        save_config(config, path)
        logger.info(f"Created default configuration at {path}")
    return path

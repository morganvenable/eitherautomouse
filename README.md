# EitherAutoMouse

**Mouse-activated keyboard layer for mouse actions**

EitherAutoMouse combines the concepts from [EitherMouse](https://github.com/gwarble/EitherMouse) (per-device settings) and [AutoMouse](https://github.com/morganvenable/automouse) (keyboard layer activation on mouse movement) to provide a seamless way to perform mouse actions from the keyboard when a pointing device is active.

## How It Works

When you move your mouse or trackball, a temporary "layer" activates on your keyboard. While active, certain keys become mouse buttons:

| Key | Action |
|-----|--------|
| `F` | Left Click |
| `S` | Right Click |
| `D` | Middle Click |
| `E` | Scroll Up |
| `R` | Scroll Down |
| `X` | Cut (Ctrl+X) |
| `C` | Copy (Ctrl+C) |
| `V` | Paste (Ctrl+V) |

The layer automatically deactivates after 500ms of mouse inactivity, or immediately when you press any other key.

**Modifier keys work naturally!** Hold `Shift` while pressing `F` to drag-select, or `Ctrl+F` for a Ctrl+Click.

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/morganvenable/eitherautomouse.git
cd eitherautomouse

# Install dependencies
pip install -r requirements.txt

# Run
python -m eitherautomouse
```

### Using pip (coming soon)

```bash
pip install eitherautomouse
eitherautomouse
```

## Requirements

- Windows (primary platform)
- Python 3.9+
- Administrator privileges (required for keyboard hooks)

## Configuration

Configuration is stored in a YAML file:

- **Windows**: `%APPDATA%\EitherAutoMouse\config.yaml`
- **macOS**: `~/Library/Application Support/EitherAutoMouse/config.yaml`
- **Linux**: `~/.config/eitherautomouse/config.yaml`

A default configuration is created on first run. You can edit it to customize:

- **Key mappings**: Change which keys trigger which mouse actions
- **Timeout**: How long the layer stays active after mouse movement
- **Exit behavior**: Whether unmapped keys should deactivate the layer

### Example Configuration

```yaml
any_pointing_device: true
any_keyboard: true

layer:
  timeout_ms: 500
  exit_on_other_key: true

  mappings:
    f: left_click
    d: middle_click
    s: right_click
    e: scroll_up
    r: scroll_down
    x: ctrl+x
    c: ctrl+c
    v: ctrl+v
```

## System Tray

EitherAutoMouse runs in your system tray with a mouse icon:

- **Gray icon**: Layer inactive (normal keyboard operation)
- **Green icon**: Layer active (keys are mapped to mouse actions)

Right-click the icon for options:
- Toggle Latch (keep layer active until explicitly disabled)
- Exit Layer
- Show connected devices
- Open/reload configuration
- Exit application

## Use Cases

- **Reduce hand movement**: Keep your hands on the keyboard while navigating
- **RSI prevention**: Minimize switching between mouse and keyboard
- **Trackball users**: Natural integration with thumb-operated trackballs
- **Accessibility**: Alternative input method for those who find mice difficult

## Dependencies

- `pynput` - Mouse control and monitoring
- `keyboard` - Keyboard hooking and control
- `hidapi` - HID device enumeration
- `pystray` - System tray integration
- `Pillow` - Icon generation
- `PyYAML` - Configuration file parsing

## License

MIT License - See [LICENSE](LICENSE) for details.

## Acknowledgments

- [EitherMouse](https://github.com/gwarble/EitherMouse) by Steffen Software - Inspiration for per-device mouse settings
- [AutoMouse](https://github.com/morganvenable/automouse) - Original keyboard layer concept

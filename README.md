# EitherAutoMouse

**EitherMouse + AutoMouse: Per-mouse settings with keyboard layer activation**

EitherAutoMouse extends [EitherMouse](https://github.com/gwarble/EitherMouse)'s per-device mouse management with [AutoMouse](https://github.com/morganvenable/automouse)'s keyboard layer functionality.

## What It Does

When you move your mouse, a temporary keyboard "layer" activates that turns home-row keys into mouse actions:

| Key | Action |
|-----|--------|
| `F` | Left Click |
| `D` | Middle Click |
| `S` | Right Click |
| `E` | Scroll Up |
| `R` | Scroll Down |
| `X` | Cut (Ctrl+X) |
| `C` | Copy (Ctrl+C) |
| `V` | Paste (Ctrl+V) |

The layer automatically deactivates after 500ms of mouse inactivity, or immediately when you press any unmapped key.

**Modifiers work naturally!** Hold `Shift` while pressing `F` to drag-select.

## Features

### From EitherMouse
- **RawInput mouse detection** - Identifies individual mice by hardware handle
- **Per-mouse settings** - Each mouse can have its own configuration
- **Registry persistence** - Settings survive restarts

### From AutoMouse
- **Keyboard layer activation** - Mouse movement triggers the layer
- **Configurable timeout** - Layer auto-deactivates after inactivity
- **Exit on unmapped key** - Typing normal keys exits the layer
- **Latch mode** - Lock the layer active until explicitly disabled

### Combined
- **Per-mouse layer enable** - Enable/disable the keyboard layer for each mouse independently
- **Settings GUI** - Configure everything through a graphical interface
- **System tray** - Status icon and quick controls

## Installation

### Requirements
- Windows 7/8/10/11
- [AutoHotkey v1.1+](https://www.autohotkey.com/)

### Setup
1. Install AutoHotkey
2. Download `EitherAutoMouse.ahk`
3. Double-click to run, or right-click → "Run as Administrator" for full functionality
4. (Optional) Add to Startup folder for auto-launch

### Compile to EXE
```
Right-click EitherAutoMouse.ahk → Compile Script
```

## Usage

### Tray Icon
- **Gray**: Layer inactive (normal keyboard)
- **Green/Check**: Layer active (keys mapped to mouse actions)
- **Lock**: Layer latched (stays active until Escape)

### Tray Menu
- **Toggle Latch** - Lock/unlock the layer
- **Exit Layer** - Immediately deactivate the layer
- **Settings** - Open configuration GUI
- **Reload** - Restart the script
- **Exit** - Close the application

### Keyboard Shortcuts
- `Escape` - Exit the layer (works even when latched)

## Configuration

Right-click tray icon → **Settings** to configure:

### Layer Settings
- **Timeout (ms)**: How long until layer deactivates (default: 500)
- **Exit on unmapped key**: Whether pressing unmapped keys exits the layer

### Key Mappings
Edit mappings in format `key = action`:
```
f = left
d = middle
s = right
e = scrollup
r = scrolldown
x = ^x
c = ^c
v = ^v
```

**Available actions:**
- `left`, `right`, `middle` - Mouse buttons
- `scrollup`, `scrolldown`, `scrollleft`, `scrollright` - Scroll wheel
- `^c`, `^v`, `^x`, etc. - Keyboard shortcuts (^ = Ctrl)

### Per-Mouse Enable
Enable or disable the keyboard layer for each detected mouse individually. Useful if you want the layer only for your trackball but not your regular mouse.

## Registry

Settings are stored in:
```
HKEY_CURRENT_USER\Software\EitherAutoMouse
```

## Architecture

```
EitherAutoMouse.ahk
├── RawInput Mouse Detection
│   └── WM_INPUT handler detects mouse movement
├── Layer State Machine
│   ├── NORMAL (0) - Keyboard works normally
│   ├── ACTIVE (1) - Keys mapped to mouse actions, timeout active
│   └── LATCHED (2) - Keys mapped, no timeout
├── Hotkey Management
│   ├── Register/unregister based on state
│   └── Per-key action execution
├── Per-Mouse Configuration
│   └── Enable/disable layer per device
├── Settings GUI
│   └── Tkinter-style configuration panel
└── Registry Persistence
    └── Save/load settings on startup
```

## Credits

- [EitherMouse](https://github.com/gwarble/EitherMouse) by Steffen Software - RawInput mouse detection, per-device architecture
- [AutoMouse](https://github.com/morganvenable/automouse) by morganvenable - Keyboard layer concept

## License

MIT License - See [LICENSE](LICENSE) for details.

# EitherAutoMouse

**EitherMouse + AutoMouse: Multiple mice with individual settings AND keyboard layer on mouse activity**

This is a fork of [EitherMouse](https://github.com/gwarble/EitherMouse) that adds keyboard layer functionality inspired by [AutoMouse](https://github.com/morganvenable/automouse).

## Features

### Original EitherMouse Features (all preserved)
- **Per-mouse settings** - Each mouse can have its own configuration
- **Swap mouse buttons** - Left-handed mode per mouse
- **Mirror cursors** - Flip cursor appearance per mouse
- **Mouse speed** - Individual speed settings per mouse
- **Double-click speed** - Per mouse
- **Scroll wheel speed** - Per mouse
- **Navigation button swap** - Swap XButton1/XButton2
- **Reverse scroll** - Per mouse (vertical and horizontal)
- **Click lock** - Per mouse
- **Snap to default button** - Per mouse
- **Disable wheel click** - Per mouse
- **Multi-cursor display** - Show cursor for each mouse
- **Tray icon options** - Logo, numbered, or per-mouse icons

### New: Keyboard Layer (AutoMouse)
When you move your mouse, a keyboard layer activates that turns keys into mouse actions:

| Key | Action |
|-----|--------|
| `F` | Left Click (hold for drag) |
| `D` | Middle Click |
| `S` | Right Click |
| `E` | Scroll Up |
| `R` | Scroll Down |
| `X` | Cut (Ctrl+X) |
| `C` | Copy (Ctrl+C) |
| `V` | Paste (Ctrl+V) |
| `Escape` | Exit layer |

- Layer auto-deactivates after 500ms of mouse inactivity
- **Per-mouse enable** - Enable/disable the layer for each mouse independently
- Modifiers work naturally (Shift+F to drag-select)

## Installation

1. Install [AutoHotkey v1.1+](https://www.autohotkey.com/)
2. Download `EitherAutoMouse.ahk`
3. Double-click to run

Or compile to standalone EXE:
```
Right-click EitherAutoMouse.ahk → Compile Script
```

## Usage

The GUI appears when you click the tray icon. All original EitherMouse settings are available, plus:

- **"Enable Keyboard Layer"** checkbox - Toggle the AutoMouse layer for each mouse

Settings are automatically saved to the Windows registry.

## Configuration

All settings are stored in:
```
HKEY_CURRENT_USER\Software\EitherAutoMouse
```

Layer settings:
- `Layer\Enabled` - Global layer enable (1/0)
- `Layer\Timeout` - Timeout in milliseconds (default: 500)
- `Mouse1\Layer`, `Mouse2\Layer`, etc. - Per-mouse layer enable

## Credits

- [EitherMouse](https://github.com/gwarble/EitherMouse) © 2009-2020 Steffen Software
- [AutoMouse](https://github.com/morganvenable/automouse) keyboard layer concept

## License

MIT License

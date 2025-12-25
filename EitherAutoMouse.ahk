;================================================================================
;==
    Name     =  EitherAutoMouse
    Version  =     0.1.0
;==
;=== EitherMouse + AutoMouse: Per-mouse settings with keyboard layer activation
;===== Based on EitherMouse © 2009 - 2020 Steffen Software
;===== AutoMouse layer functionality © 2025 morganvenable
;======  Combines: www.EitherMouse.com + github.com/morganvenable/automouse
;================================================================================

#SingleInstance Force
#NoEnv
#MaxHotkeysPerInterval 700
#HotkeyInterval 250
SetBatchLines, -1
SetWorkingDir %A_ScriptDir%
CoordMode, Mouse, Screen
SendMode Input

;===================================================================================
;=== Global Variables ==============================================================
;===================================================================================

; Application info
global AppName := "EitherAutoMouse"
global AppVersion := "0.1.0"

; Mouse tracking
global MouseCount := 0
global ActiveMouse := 0
global LastMouse := 0
global LastActiveMouse := 0

; Layer state: 0=Normal, 1=Active, 2=Latched
global LayerState := 0
global LayerTimeout := 500  ; ms
global LayerExitOnOtherKey := true
global LayerTimer := 0

; Per-mouse layer enable (default all enabled)
global Mouse1LayerEnabled := 1
global Mouse2LayerEnabled := 1
global Mouse3LayerEnabled := 1
global Mouse4LayerEnabled := 1
global Mouse5LayerEnabled := 1

; Key mappings (key -> action)
; Actions: "left", "right", "middle", "scrollup", "scrolldown", "scrollleft", "scrollright"
;          or keyboard shortcuts like "^c" for Ctrl+C
global KeyMappings := {}

; Track which keys are currently pressed (for proper release)
global PressedKeys := {}

; GUI state
global GuiShown := false
global SettingsKey := "HKCU\Software\EitherAutoMouse"

;===================================================================================
;=== Initialization ================================================================
;===================================================================================

Initialize:
    ; Set default key mappings
    SetDefaultMappings()

    ; Load settings from registry
    GoSub, LoadSettings

    ; Create tray menu
    GoSub, CreateTrayMenu

    ; Register for raw input (mouse detection)
    GoSub, RegisterMice

    ; Register window messages
    GoSub, RegisterMessages

    ; Show startup notification
    TrayTip, %AppName%, Started - Layer timeout: %LayerTimeout%ms, 2, 1
Return

;===================================================================================
;=== Default Key Mappings ==========================================================
;===================================================================================

SetDefaultMappings() {
    global KeyMappings

    ; Home row mouse buttons (left hand)
    KeyMappings["f"] := "left"
    KeyMappings["d"] := "middle"
    KeyMappings["s"] := "right"

    ; Scroll keys
    KeyMappings["e"] := "scrollup"
    KeyMappings["r"] := "scrolldown"

    ; Clipboard shortcuts
    KeyMappings["x"] := "^x"  ; Cut
    KeyMappings["c"] := "^c"  ; Copy
    KeyMappings["v"] := "^v"  ; Paste
}

;===================================================================================
;=== Raw Input - Mouse Detection ===================================================
;===================================================================================

RegisterMice:
    ; Get list of mice using RawInput
    VarSetCapacity(RID, 8 + A_PtrSize, 0)
    NumPut(1, RID, 0, "UShort")  ; UsagePage = 1 (Generic Desktop)
    NumPut(2, RID, 2, "UShort")  ; Usage = 2 (Mouse)
    NumPut(0x00000100, RID, 4, "UInt")  ; RIDEV_INPUTSINK
    NumPut(A_ScriptHwnd, RID, 8, "Ptr")  ; hwndTarget

    DllCall("RegisterRawInputDevices", "Ptr", &RID, "UInt", 1, "UInt", 8 + A_PtrSize)
Return

RegisterMessages:
    OnMessage(0x00FF, "WM_INPUT")  ; WM_INPUT
Return

WM_INPUT(wParam, lParam) {
    global MouseCount, ActiveMouse, LastMouse, LastActiveMouse
    global LayerState, LayerTimeout

    Critical

    ; Get raw input data size
    DllCall("GetRawInputData", "Ptr", lParam, "UInt", 0x10000003, "Ptr", 0, "UInt*", size, "UInt", 8 + A_PtrSize*2)
    VarSetCapacity(raw, size, 0)

    if (!DllCall("GetRawInputData", "Ptr", lParam, "UInt", 0x10000003, "Ptr", &raw, "UInt*", size, "UInt", 8 + A_PtrSize*2))
        return 0

    ; Get device handle
    ThisMouse := NumGet(raw, 8, "Ptr")

    if (ThisMouse = 0)
        return 0

    ; Mouse activity detected - activate layer if this mouse has it enabled
    mouseIndex := GetMouseIndex(ThisMouse)
    if (mouseIndex > 0) {
        layerEnabledVar := "Mouse" . mouseIndex . "LayerEnabled"
        if (%layerEnabledVar%) {
            ActivateLayer()
        }
    } else {
        ; New mouse - add it and activate layer
        AddNewMouse(ThisMouse)
        ActivateLayer()
    }

    ; Track mouse change for EitherMouse functionality
    if (LastMouse != ThisMouse) {
        LastActiveMouse := ActiveMouse
        ActiveMouse := GetMouseIndex(ThisMouse)
        LastMouse := ThisMouse

        ; Here you would apply per-mouse EitherMouse settings
        ; (button swap, speed, etc.) - omitted for clarity
        GoSub, OnMouseChange
    }

    return 0
}

GetMouseIndex(handle) {
    global MouseCount
    Loop, %MouseCount% {
        if (Mouse%A_Index%Handle = handle)
            return A_Index
    }
    return 0
}

GetMouseName(handle) {
    ; Get device name from handle
    size := 0
    DllCall("GetRawInputDeviceInfo", "Ptr", handle, "UInt", 0x20000007, "Ptr", 0, "UInt*", size)
    VarSetCapacity(name, size * 2, 0)
    DllCall("GetRawInputDeviceInfo", "Ptr", handle, "UInt", 0x20000007, "Str", name, "UInt*", size)
    return name
}

AddNewMouse(handle) {
    global MouseCount
    MouseCount++
    Mouse%MouseCount%Handle := handle
    Mouse%MouseCount%Name := GetMouseName(handle)
    Mouse%MouseCount%Nick := "Mouse " . MouseCount
    Mouse%MouseCount%LayerEnabled := 1

    ; Load per-mouse settings if they exist
    RegRead, nick, %SettingsKey%\Mouse%MouseCount%, Nick
    if (nick)
        Mouse%MouseCount%Nick := nick

    RegRead, layerEnabled, %SettingsKey%\Mouse%MouseCount%, LayerEnabled
    if (layerEnabled != "")
        Mouse%MouseCount%LayerEnabled := layerEnabled

    TrayTip, %AppName%, New mouse detected: %nick%, 2, 1
}

OnMouseChange:
    ; Placeholder for EitherMouse per-mouse settings application
    ; This is where button swap, cursor style, speed, etc. would be applied
    UpdateTrayIcon()
Return

;===================================================================================
;=== Layer State Machine ===========================================================
;===================================================================================

ActivateLayer() {
    global LayerState, LayerTimeout

    if (LayerState = 0) {
        ; Transition from Normal to Active
        LayerState := 1
        RegisterLayerHotkeys()
        UpdateTrayIcon()
    }

    ; Reset/start timeout timer (unless latched)
    if (LayerState = 1) {
        SetTimer, LayerTimeoutHandler, -%LayerTimeout%
    }
}

DeactivateLayer() {
    global LayerState, PressedKeys

    if (LayerState != 0) {
        LayerState := 0
        UnregisterLayerHotkeys()
        ReleaseAllButtons()
        UpdateTrayIcon()
        SetTimer, LayerTimeoutHandler, Off
    }
}

LatchLayer() {
    global LayerState

    if (LayerState != 2) {
        LayerState := 2
        RegisterLayerHotkeys()
        UpdateTrayIcon()
        SetTimer, LayerTimeoutHandler, Off
        TrayTip, %AppName%, Layer LATCHED - press Escape to exit, 2, 1
    }
}

UnlatchLayer() {
    global LayerState

    if (LayerState = 2) {
        DeactivateLayer()
    }
}

ToggleLatch() {
    global LayerState

    if (LayerState = 2) {
        UnlatchLayer()
    } else {
        LatchLayer()
    }
}

LayerTimeoutHandler:
    if (LayerState = 1) {
        DeactivateLayer()
    }
Return

;===================================================================================
;=== Keyboard Layer Hotkeys ========================================================
;===================================================================================

RegisterLayerHotkeys() {
    global KeyMappings

    for key, action in KeyMappings {
        ; Register key down
        fn := Func("OnLayerKeyDown").Bind(key, action)
        Hotkey, *%key%, %fn%, On

        ; Register key up
        fnUp := Func("OnLayerKeyUp").Bind(key, action)
        Hotkey, *%key% Up, %fnUp%, On
    }
}

UnregisterLayerHotkeys() {
    global KeyMappings

    for key, action in KeyMappings {
        try {
            Hotkey, *%key%, Off
            Hotkey, *%key% Up, Off
        }
    }
}

OnLayerKeyDown(key, action) {
    global LayerState, LayerTimeout, PressedKeys

    if (LayerState = 0)
        return

    ; Refresh timeout if active (not latched)
    if (LayerState = 1) {
        SetTimer, LayerTimeoutHandler, -%LayerTimeout%
    }

    ; Execute action
    if (action = "left") {
        Click, Down Left
        PressedKeys["left"] := true
    } else if (action = "right") {
        Click, Down Right
        PressedKeys["right"] := true
    } else if (action = "middle") {
        Click, Down Middle
        PressedKeys["middle"] := true
    } else if (action = "scrollup") {
        Click, WheelUp
    } else if (action = "scrolldown") {
        Click, WheelDown
    } else if (action = "scrollleft") {
        Click, WheelLeft
    } else if (action = "scrollright") {
        Click, WheelRight
    } else {
        ; It's a keyboard shortcut - send it
        Send, %action%
    }
}

OnLayerKeyUp(key, action) {
    global PressedKeys

    ; Release mouse button if it was pressed
    if (action = "left" && PressedKeys["left"]) {
        Click, Up Left
        PressedKeys.Delete("left")
    } else if (action = "right" && PressedKeys["right"]) {
        Click, Up Right
        PressedKeys.Delete("right")
    } else if (action = "middle" && PressedKeys["middle"]) {
        Click, Up Middle
        PressedKeys.Delete("middle")
    }
}

ReleaseAllButtons() {
    global PressedKeys

    if (PressedKeys["left"]) {
        Click, Up Left
    }
    if (PressedKeys["right"]) {
        Click, Up Right
    }
    if (PressedKeys["middle"]) {
        Click, Up Middle
    }
    PressedKeys := {}
}

;===================================================================================
;=== Unmapped Key Detection ========================================================
;===================================================================================

; This hook catches keys that are NOT in our mapping
; If LayerExitOnOtherKey is true, exit the layer
#If (LayerState = 1 && LayerExitOnOtherKey)
~*a::
~*b::
~*g::
~*h::
~*i::
~*j::
~*k::
~*l::
~*m::
~*n::
~*o::
~*p::
~*q::
~*t::
~*u::
~*w::
~*y::
~*z::
~*1::
~*2::
~*3::
~*4::
~*5::
~*6::
~*7::
~*8::
~*9::
~*0::
~*Space::
~*Enter::
~*Tab::
~*Backspace::
    DeactivateLayer()
return
#If

; Escape always exits layer (even when latched)
#If (LayerState > 0)
*Escape::
    DeactivateLayer()
return
#If

;===================================================================================
;=== Tray Menu & Icon ==============================================================
;===================================================================================

CreateTrayMenu:
    Menu, Tray, NoStandard
    Menu, Tray, Add, %AppName% v%AppVersion%, ShowAbout
    Menu, Tray, Default, %AppName% v%AppVersion%
    Menu, Tray, Add
    Menu, Tray, Add, Layer Status: NORMAL, ShowStatus
    Menu, Tray, Disable, Layer Status: NORMAL
    Menu, Tray, Add
    Menu, Tray, Add, Toggle Latch (keep layer active), ToggleLatchMenu
    Menu, Tray, Add, Exit Layer, ExitLayerMenu
    Menu, Tray, Add
    Menu, Tray, Add, Settings..., ShowSettings
    Menu, Tray, Add, Reload, ReloadScript
    Menu, Tray, Add
    Menu, Tray, Add, Exit, ExitApp

    Menu, Tray, Tip, %AppName% - Layer: NORMAL
    UpdateTrayIcon()
Return

UpdateTrayIcon() {
    global LayerState, AppName

    if (LayerState = 0) {
        ; Gray icon - normal
        Menu, Tray, Icon, Shell32.dll, 14  ; Gray mouse icon
        Menu, Tray, Tip, %AppName% - Layer: NORMAL
        try Menu, Tray, Rename, Layer Status:%, Layer Status: NORMAL
    } else if (LayerState = 1) {
        ; Green icon - active
        Menu, Tray, Icon, Shell32.dll, 3  ; Check/active icon
        Menu, Tray, Tip, %AppName% - Layer: ACTIVE
        try Menu, Tray, Rename, Layer Status:%, Layer Status: ACTIVE
    } else if (LayerState = 2) {
        ; Yellow/locked icon - latched
        Menu, Tray, Icon, Shell32.dll, 48  ; Lock icon
        Menu, Tray, Tip, %AppName% - Layer: LATCHED
        try Menu, Tray, Rename, Layer Status:%, Layer Status: LATCHED
    }
}

ShowAbout:
    MsgBox, 64, %AppName%,
    (
%AppName% v%AppVersion%

Combines EitherMouse per-device settings with AutoMouse keyboard layer.

When you move your mouse, a keyboard layer activates:
  F = Left Click
  D = Middle Click
  S = Right Click
  E = Scroll Up
  R = Scroll Down
  X/C/V = Cut/Copy/Paste

Layer times out after %LayerTimeout%ms of mouse inactivity.
Press Escape to exit the layer at any time.
    )
return

ShowStatus:
return

ToggleLatchMenu:
    ToggleLatch()
return

ExitLayerMenu:
    DeactivateLayer()
return

ReloadScript:
    Reload
return

ExitApp:
    ExitApp
return

;===================================================================================
;=== Settings GUI ==================================================================
;===================================================================================

ShowSettings:
    global GuiShown, LayerTimeout, LayerExitOnOtherKey, MouseCount

    if (GuiShown) {
        Gui, Settings:Show
        return
    }

    Gui, Settings:New, +Resize, %AppName% Settings
    Gui, Settings:Add, Text, x10 y10 w380 h20, Layer Settings
    Gui, Settings:Add, Text, x10 y35 w100 h20, Timeout (ms):
    Gui, Settings:Add, Edit, x120 y33 w80 h20 vLayerTimeoutEdit, %LayerTimeout%
    Gui, Settings:Add, CheckBox, x10 y60 w200 h20 vExitOnOtherKeyCheck Checked%LayerExitOnOtherKey%, Exit layer on unmapped key

    Gui, Settings:Add, Text, x10 y95 w380 h20, Key Mappings (key = action):

    ; Build mappings text
    mappingsText := ""
    for key, action in KeyMappings {
        mappingsText .= key . " = " . action . "`n"
    }
    Gui, Settings:Add, Edit, x10 y115 w380 h120 vMappingsEdit, %mappingsText%

    Gui, Settings:Add, Text, x10 y245 w380 h40,
    (
Actions: left, right, middle, scrollup, scrolldown, scrollleft, scrollright
Shortcuts: ^c (Ctrl+C), ^x (Ctrl+X), ^v (Ctrl+V), etc.
    )

    ; Per-mouse layer enable
    Gui, Settings:Add, Text, x10 y295 w380 h20, Per-Mouse Layer Enable:
    yPos := 315
    Loop, %MouseCount% {
        nick := Mouse%A_Index%Nick
        enabled := Mouse%A_Index%LayerEnabled
        Gui, Settings:Add, CheckBox, x10 y%yPos% w300 h20 vMouse%A_Index%LayerCheck Checked%enabled%, %nick% - Layer enabled
        yPos += 25
    }

    Gui, Settings:Add, Button, x10 y%yPos% w100 h30 gSaveSettings, Save
    Gui, Settings:Add, Button, x120 y%yPos% w100 h30 gCancelSettings, Cancel

    GuiShown := true
    Gui, Settings:Show, w400
return

SaveSettings:
    Gui, Settings:Submit, NoHide

    ; Update timeout
    if (LayerTimeoutEdit > 0) {
        LayerTimeout := LayerTimeoutEdit
    }

    ; Update exit on other key
    LayerExitOnOtherKey := ExitOnOtherKeyCheck

    ; Parse and update mappings
    KeyMappings := {}
    Loop, Parse, MappingsEdit, `n, `r
    {
        if (A_LoopField = "")
            continue
        parts := StrSplit(A_LoopField, "=")
        if (parts.Length() >= 2) {
            key := Trim(parts[1])
            action := Trim(parts[2])
            if (key && action) {
                KeyMappings[key] := action
            }
        }
    }

    ; Update per-mouse settings
    Loop, %MouseCount% {
        checkVar := "Mouse" . A_Index . "LayerCheck"
        Mouse%A_Index%LayerEnabled := %checkVar%
    }

    ; Re-register hotkeys if layer is active
    if (LayerState > 0) {
        UnregisterLayerHotkeys()
        RegisterLayerHotkeys()
    }

    ; Save to registry
    GoSub, SaveSettingsToRegistry

    Gui, Settings:Destroy
    GuiShown := false

    TrayTip, %AppName%, Settings saved, 2, 1
return

CancelSettings:
    Gui, Settings:Destroy
    GuiShown := false
return

SettingsGuiClose:
    Gui, Settings:Destroy
    GuiShown := false
return

;===================================================================================
;=== Settings Persistence (Registry) ===============================================
;===================================================================================

LoadSettings:
    global LayerTimeout, LayerExitOnOtherKey, KeyMappings, SettingsKey

    ; Load layer settings
    RegRead, timeout, %SettingsKey%, LayerTimeout
    if (timeout > 0)
        LayerTimeout := timeout

    RegRead, exitOnOther, %SettingsKey%, ExitOnOtherKey
    if (exitOnOther != "")
        LayerExitOnOtherKey := exitOnOther

    ; Load key mappings
    RegRead, mappingsStr, %SettingsKey%, KeyMappings
    if (mappingsStr) {
        KeyMappings := {}
        Loop, Parse, mappingsStr, |
        {
            parts := StrSplit(A_LoopField, ":")
            if (parts.Length() >= 2) {
                KeyMappings[parts[1]] := parts[2]
            }
        }
    }
Return

SaveSettingsToRegistry:
    global LayerTimeout, LayerExitOnOtherKey, KeyMappings, SettingsKey, MouseCount

    ; Save layer settings
    RegWrite, REG_DWORD, %SettingsKey%, LayerTimeout, %LayerTimeout%
    RegWrite, REG_DWORD, %SettingsKey%, ExitOnOtherKey, %LayerExitOnOtherKey%

    ; Save key mappings as pipe-separated string
    mappingsStr := ""
    for key, action in KeyMappings {
        if (mappingsStr)
            mappingsStr .= "|"
        mappingsStr .= key . ":" . action
    }
    RegWrite, REG_SZ, %SettingsKey%, KeyMappings, %mappingsStr%

    ; Save per-mouse settings
    Loop, %MouseCount% {
        nick := Mouse%A_Index%Nick
        layerEnabled := Mouse%A_Index%LayerEnabled
        RegWrite, REG_SZ, %SettingsKey%\Mouse%A_Index%, Nick, %nick%
        RegWrite, REG_DWORD, %SettingsKey%\Mouse%A_Index%, LayerEnabled, %layerEnabled%
    }
Return

;===================================================================================
;=== Startup =======================================================================
;===================================================================================

GoSub, Initialize
return

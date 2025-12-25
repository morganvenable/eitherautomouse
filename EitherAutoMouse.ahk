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
AppName := "EitherAutoMouse"
AppVersion := "0.1.0"

; Mouse tracking
MouseCount := 0
ActiveMouse := 0
LastMouse := 0
LastActiveMouse := 0

; Layer state: 0=Normal, 1=Active, 2=Latched
LayerState := 0
LayerTimeout := 500  ; ms
LayerExitOnOtherKey := 1

; Per-mouse layer enable (default all enabled)
Mouse1LayerEnabled := 1
Mouse2LayerEnabled := 1
Mouse3LayerEnabled := 1
Mouse4LayerEnabled := 1
Mouse5LayerEnabled := 1

; Track which mouse buttons are currently pressed
LeftPressed := 0
RightPressed := 0
MiddlePressed := 0

; GUI state
GuiShown := 0
SettingsKey := "HKCU\Software\EitherAutoMouse"

; Key mappings stored as parallel arrays (v1 compatible)
MapKeys := "f,d,s,e,r,x,c,v"
MapActions := "left,middle,right,scrollup,scrolldown,^x,^c,^v"

;===================================================================================
;=== Initialization ================================================================
;===================================================================================

GoSub, LoadSettings
GoSub, CreateTrayMenu
GoSub, RegisterMice
GoSub, RegisterMessages

TrayTip, %AppName%, Started - Layer timeout: %LayerTimeout%ms, 2, 1
Return

;===================================================================================
;=== Raw Input - Mouse Detection ===================================================
;===================================================================================

RegisterMice:
    ; Register for raw input from mice
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

WM_INPUT(wParam, lParam)
{
    global MouseCount, ActiveMouse, LastMouse, LastActiveMouse, LayerState, LayerTimeout

    Critical

    ; Get raw input data size
    DllCall("GetRawInputData", "Ptr", lParam, "UInt", 0x10000003, "Ptr", 0, "UInt*", size, "UInt", 8 + A_PtrSize*2)
    VarSetCapacity(raw, size, 0)

    result := DllCall("GetRawInputData", "Ptr", lParam, "UInt", 0x10000003, "Ptr", &raw, "UInt*", size, "UInt", 8 + A_PtrSize*2)
    if (!result)
        Return 0

    ; Get device handle
    ThisMouse := NumGet(raw, 8, "Ptr")

    if (ThisMouse = 0)
        Return 0

    ; Mouse activity detected - activate layer if this mouse has it enabled
    mouseIndex := GetMouseIndex(ThisMouse)
    if (mouseIndex > 0)
    {
        layerEnabled := Mouse%mouseIndex%LayerEnabled
        if (layerEnabled)
            ActivateLayer()
    }
    else
    {
        ; New mouse - add it and activate layer
        AddNewMouse(ThisMouse)
        ActivateLayer()
    }

    ; Track mouse change
    if (LastMouse != ThisMouse)
    {
        LastActiveMouse := ActiveMouse
        ActiveMouse := GetMouseIndex(ThisMouse)
        LastMouse := ThisMouse
        GoSub, OnMouseChange
    }

    Return 0
}

GetMouseIndex(handle)
{
    global MouseCount
    Loop, %MouseCount%
    {
        h := Mouse%A_Index%Handle
        if (h = handle)
            Return A_Index
    }
    Return 0
}

GetMouseName(handle)
{
    ; Get device name from handle
    size := 0
    DllCall("GetRawInputDeviceInfo", "Ptr", handle, "UInt", 0x20000007, "Ptr", 0, "UInt*", size)
    VarSetCapacity(name, size * 2, 0)
    DllCall("GetRawInputDeviceInfo", "Ptr", handle, "UInt", 0x20000007, "Str", name, "UInt*", size)
    Return name
}

AddNewMouse(handle)
{
    global MouseCount, SettingsKey, AppName
    MouseCount++
    Mouse%MouseCount%Handle := handle
    Mouse%MouseCount%Name := GetMouseName(handle)
    Mouse%MouseCount%Nick := "Mouse " . MouseCount
    Mouse%MouseCount%LayerEnabled := 1

    ; Load per-mouse settings if they exist
    RegRead, nick, %SettingsKey%\Mouse%MouseCount%, Nick
    if (!ErrorLevel && nick != "")
        Mouse%MouseCount%Nick := nick

    RegRead, layerEnabled, %SettingsKey%\Mouse%MouseCount%, LayerEnabled
    if (!ErrorLevel)
        Mouse%MouseCount%LayerEnabled := layerEnabled

    nick := Mouse%MouseCount%Nick
    TrayTip, %AppName%, New mouse detected: %nick%, 2, 1
}

OnMouseChange:
    UpdateTrayIcon()
Return

;===================================================================================
;=== Layer State Machine ===========================================================
;===================================================================================

ActivateLayer()
{
    global LayerState, LayerTimeout

    if (LayerState = 0)
    {
        ; Transition from Normal to Active
        LayerState := 1
        GoSub, EnableLayerHotkeys
        UpdateTrayIcon()
    }

    ; Reset/start timeout timer (unless latched)
    if (LayerState = 1)
        SetTimer, LayerTimeoutHandler, -%LayerTimeout%
}

DeactivateLayer()
{
    global LayerState

    if (LayerState != 0)
    {
        LayerState := 0
        GoSub, DisableLayerHotkeys
        ReleaseAllButtons()
        UpdateTrayIcon()
        SetTimer, LayerTimeoutHandler, Off
    }
}

LatchLayer()
{
    global LayerState, AppName

    if (LayerState != 2)
    {
        LayerState := 2
        GoSub, EnableLayerHotkeys
        UpdateTrayIcon()
        SetTimer, LayerTimeoutHandler, Off
        TrayTip, %AppName%, Layer LATCHED - press Escape to exit, 2, 1
    }
}

UnlatchLayer()
{
    global LayerState

    if (LayerState = 2)
        DeactivateLayer()
}

ToggleLatch()
{
    global LayerState

    if (LayerState = 2)
        UnlatchLayer()
    else
        LatchLayer()
}

LayerTimeoutHandler:
    if (LayerState = 1)
        DeactivateLayer()
Return

;===================================================================================
;=== Keyboard Layer Hotkeys (v1 compatible using labels) ===========================
;===================================================================================

EnableLayerHotkeys:
    Hotkey, *f, KeyF, On
    Hotkey, *f Up, KeyFUp, On
    Hotkey, *d, KeyD, On
    Hotkey, *d Up, KeyDUp, On
    Hotkey, *s, KeyS, On
    Hotkey, *s Up, KeySUp, On
    Hotkey, *e, KeyE, On
    Hotkey, *r, KeyR, On
    Hotkey, *x, KeyX, On
    Hotkey, *c, KeyC, On
    Hotkey, *v, KeyV, On
Return

DisableLayerHotkeys:
    Hotkey, *f, Off
    Hotkey, *f Up, Off
    Hotkey, *d, Off
    Hotkey, *d Up, Off
    Hotkey, *s, Off
    Hotkey, *s Up, Off
    Hotkey, *e, Off
    Hotkey, *r, Off
    Hotkey, *x, Off
    Hotkey, *c, Off
    Hotkey, *v, Off
Return

; Key handlers - F = Left Click
KeyF:
    if (LayerState = 0)
        Return
    RefreshLayerTimeout()
    Click, Down Left
    LeftPressed := 1
Return

KeyFUp:
    if (LeftPressed)
    {
        Click, Up Left
        LeftPressed := 0
    }
Return

; D = Middle Click
KeyD:
    if (LayerState = 0)
        Return
    RefreshLayerTimeout()
    Click, Down Middle
    MiddlePressed := 1
Return

KeyDUp:
    if (MiddlePressed)
    {
        Click, Up Middle
        MiddlePressed := 0
    }
Return

; S = Right Click
KeyS:
    if (LayerState = 0)
        Return
    RefreshLayerTimeout()
    Click, Down Right
    RightPressed := 1
Return

KeySUp:
    if (RightPressed)
    {
        Click, Up Right
        RightPressed := 0
    }
Return

; E = Scroll Up
KeyE:
    if (LayerState = 0)
        Return
    RefreshLayerTimeout()
    Click, WheelUp
Return

; R = Scroll Down
KeyR:
    if (LayerState = 0)
        Return
    RefreshLayerTimeout()
    Click, WheelDown
Return

; X = Cut (Ctrl+X)
KeyX:
    if (LayerState = 0)
        Return
    RefreshLayerTimeout()
    Send, ^x
Return

; C = Copy (Ctrl+C)
KeyC:
    if (LayerState = 0)
        Return
    RefreshLayerTimeout()
    Send, ^c
Return

; V = Paste (Ctrl+V)
KeyV:
    if (LayerState = 0)
        Return
    RefreshLayerTimeout()
    Send, ^v
Return

RefreshLayerTimeout()
{
    global LayerState, LayerTimeout
    if (LayerState = 1)
        SetTimer, LayerTimeoutHandler, -%LayerTimeout%
}

ReleaseAllButtons()
{
    global LeftPressed, RightPressed, MiddlePressed

    if (LeftPressed)
    {
        Click, Up Left
        LeftPressed := 0
    }
    if (RightPressed)
    {
        Click, Up Right
        RightPressed := 0
    }
    if (MiddlePressed)
    {
        Click, Up Middle
        MiddlePressed := 0
    }
}

;===================================================================================
;=== Unmapped Key Detection ========================================================
;===================================================================================

; Exit layer on unmapped keys (when active, not latched)
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
Return
#If

; Escape always exits layer (even when latched)
#If (LayerState > 0)
*Escape::
    DeactivateLayer()
Return
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

UpdateTrayIcon()
{
    global LayerState, AppName
    static lastStatus := "Layer Status: NORMAL"

    if (LayerState = 0)
    {
        Menu, Tray, Icon, Shell32.dll, 14
        Menu, Tray, Tip, %AppName% - Layer: NORMAL
        newStatus := "Layer Status: NORMAL"
    }
    else if (LayerState = 1)
    {
        Menu, Tray, Icon, Shell32.dll, 3
        Menu, Tray, Tip, %AppName% - Layer: ACTIVE
        newStatus := "Layer Status: ACTIVE"
    }
    else if (LayerState = 2)
    {
        Menu, Tray, Icon, Shell32.dll, 48
        Menu, Tray, Tip, %AppName% - Layer: LATCHED
        newStatus := "Layer Status: LATCHED"
    }

    ; Rename menu item if changed
    if (lastStatus != newStatus)
    {
        Menu, Tray, Rename, %lastStatus%, %newStatus%
        lastStatus := newStatus
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
Return

ShowStatus:
Return

ToggleLatchMenu:
    ToggleLatch()
Return

ExitLayerMenu:
    DeactivateLayer()
Return

ReloadScript:
    Reload
Return

ExitApp:
    ExitApp
Return

;===================================================================================
;=== Settings GUI ==================================================================
;===================================================================================

ShowSettings:
    global GuiShown, LayerTimeout, LayerExitOnOtherKey, MouseCount, AppName

    if (GuiShown)
    {
        Gui, Settings:Show
        Return
    }

    Gui, Settings:Destroy
    Gui, Settings:+Resize
    Gui, Settings:Add, Text, x10 y10 w380 h20, Layer Settings
    Gui, Settings:Add, Text, x10 y35 w100 h20, Timeout (ms):
    Gui, Settings:Add, Edit, x120 y33 w80 h20 vLayerTimeoutEdit, %LayerTimeout%
    Gui, Settings:Add, CheckBox, x10 y60 w200 h20 vExitOnOtherKeyCheck Checked%LayerExitOnOtherKey%, Exit layer on unmapped key

    Gui, Settings:Add, Text, x10 y95 w380 h20, Key Mappings:
    Gui, Settings:Add, Text, x10 y115 w380 h80,
    (
F = Left Click    D = Middle Click    S = Right Click
E = Scroll Up     R = Scroll Down
X = Cut           C = Copy            V = Paste

(Edit EitherAutoMouse.ahk to change mappings)
    )

    ; Per-mouse layer enable
    Gui, Settings:Add, Text, x10 y205 w380 h20, Per-Mouse Layer Enable:
    yPos := 225
    Loop, %MouseCount%
    {
        nick := Mouse%A_Index%Nick
        enabled := Mouse%A_Index%LayerEnabled
        Gui, Settings:Add, CheckBox, x10 y%yPos% w300 h20 vMouse%A_Index%LayerCheck Checked%enabled%, %nick% - Layer enabled
        yPos += 25
    }

    yPos += 10
    Gui, Settings:Add, Button, x10 y%yPos% w100 h30 gSaveSettings, Save
    Gui, Settings:Add, Button, x120 y%yPos% w100 h30 gCancelSettings, Cancel

    GuiShown := 1
    Gui, Settings:Show, w400, %AppName% Settings
Return

SaveSettings:
    Gui, Settings:Submit, NoHide

    ; Update timeout
    if (LayerTimeoutEdit > 0)
        LayerTimeout := LayerTimeoutEdit

    ; Update exit on other key
    LayerExitOnOtherKey := ExitOnOtherKeyCheck

    ; Update per-mouse settings
    Loop, %MouseCount%
    {
        GuiControlGet, checkVal,, Mouse%A_Index%LayerCheck
        Mouse%A_Index%LayerEnabled := checkVal
    }

    ; Save to registry
    GoSub, SaveSettingsToRegistry

    Gui, Settings:Destroy
    GuiShown := 0

    TrayTip, %AppName%, Settings saved, 2, 1
Return

CancelSettings:
SettingsGuiClose:
SettingsGuiEscape:
    Gui, Settings:Destroy
    GuiShown := 0
Return

;===================================================================================
;=== Settings Persistence (Registry) ===============================================
;===================================================================================

LoadSettings:
    global LayerTimeout, LayerExitOnOtherKey, SettingsKey

    ; Load layer settings
    RegRead, timeout, %SettingsKey%, LayerTimeout
    if (!ErrorLevel && timeout > 0)
        LayerTimeout := timeout

    RegRead, exitOnOther, %SettingsKey%, ExitOnOtherKey
    if (!ErrorLevel)
        LayerExitOnOtherKey := exitOnOther
Return

SaveSettingsToRegistry:
    global LayerTimeout, LayerExitOnOtherKey, SettingsKey, MouseCount

    ; Save layer settings
    RegWrite, REG_DWORD, %SettingsKey%, LayerTimeout, %LayerTimeout%
    RegWrite, REG_DWORD, %SettingsKey%, ExitOnOtherKey, %LayerExitOnOtherKey%

    ; Save per-mouse settings
    Loop, %MouseCount%
    {
        nick := Mouse%A_Index%Nick
        layerEnabled := Mouse%A_Index%LayerEnabled
        RegWrite, REG_SZ, %SettingsKey%\Mouse%A_Index%, Nick, %nick%
        RegWrite, REG_DWORD, %SettingsKey%\Mouse%A_Index%, LayerEnabled, %layerEnabled%
    }
Return

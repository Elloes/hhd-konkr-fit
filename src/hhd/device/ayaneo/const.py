from typing import Literal

from hhd.controller import Axis
from hhd.controller.physical.evdev import B, XBOX_BUTTON_MAP
from hhd.utils import hsb_to_rgb, rgb_to_hsb

AYA_GAMEPAD_BTN_MAPPINGS = {**XBOX_BUTTON_MAP, B("BTN_MODE"): "share"}

AYA3_AT_BTN_MAPPINGS = {B("KEY_F23"): "mode"}
AYA_NEXT2_AT_BTN_MAPPINGS = {}
KONKR_FIT_AT_BTN_MAPPINGS = {}

AYA3_BTN_MAPPINGS = {
    B("KEY_F24"): "keyboard",
    B("KEY_D"): "keyboard",
    B("KEY_F21"): "extra_l2",
    B("KEY_F22"): "extra_r2",
    B("KEY_L"): "extra_l1",
    B("KEY_R"): "extra_r1",
}

# Konkr Fit (Ayaneo sub-brand). Same composite keyboard as AYANEO 3
# (1c4f:0002) but a different physical button layout.
# F23 is the konkr logo button (right-bottom-left); the right-top button
# emits F23 with Ctrl held (handled by ChordGamepadEvdev). KEY_D is the
# right-bottom-right button and is user-remappable via konkr_buttons.yml.
KONKR_FIT_BTN_MAPPINGS = {
    B("KEY_F24"): "keyboard",
    B("KEY_D"): "share",
    B("KEY_F21"): "extra_l2",
    B("KEY_F22"): "extra_r2",
    B("KEY_L"): "extra_l1",
    B("KEY_R"): "extra_r1",
    B("KEY_F23"): "mode",
}

# Physical button assignments reported for NEXT 2; the device log has no key trace.
AYA_NEXT2_BTN_MAPPINGS = {
    B("KEY_F20"): "extra_r1",
    B("KEY_F19"): "extra_l1",
    B("KEY_F18"): "extra_r2",
    B("KEY_F17"): "extra_l2",
    B("KEY_F21"): "extra_l3",
    B("KEY_F22"): "extra_r3",
    B("KEY_F23"): "mode",
    B("KEY_D"): "share",
    B("KEY_F16"): "keyboard",
    B("KEY_VOLUMEUP"): "key_volumeup",
    B("KEY_VOLUMEDOWN"): "key_volumedown",
}

DEFAULT_MAPPINGS: dict[str, tuple[Axis, str | None, float, float | None]] = {
    "accel_x": ("accel_z", "accel", 1, None),
    "accel_y": ("accel_x", "accel", -1, None),
    "accel_z": ("accel_y", "accel", -1, None),
    "anglvel_x": ("gyro_z", "anglvel", 1, None),
    "anglvel_y": ("gyro_x", "anglvel", -1, None),
    "anglvel_z": ("gyro_y", "anglvel", -1, None),
    "timestamp": ("imu_ts", None, 1, None),
}

AYA_DEFAULT_CONF = {
    "hrtimer": True,
    "mapping": DEFAULT_MAPPINGS,
}

CONFS = {
    # Ayaneo
    "AYANEO 3": {
        "name": "AYANEO 3",
        "extra_buttons": "quad",
        "magic_modules": True,
        "rgb": True,
        "btn_mapping": AYA3_BTN_MAPPINGS,
        "at_btn_mapping": AYA3_AT_BTN_MAPPINGS,
        **AYA_DEFAULT_CONF,
    },
    "AB09": {
        "name": "AYANEO NEXT 2",
        "extra_buttons": "quad",
        "magic_modules": False,
        "rgb": True,
        "btn_mapping": AYA_NEXT2_BTN_MAPPINGS,
        "at_btn_mapping": AYA_NEXT2_AT_BTN_MAPPINGS,
        **AYA_DEFAULT_CONF,
    },
    "KONKR FIT": {
        "name": "KONKR FIT",
        "extra_buttons": "quad",
        "magic_modules": False,
        "rgb": True,
        # Konkr (Ayaneo sub-brand). Same controller hw as AYANEO 3
        # (1c4f:0002 composite + 045e:028e gamepad) but no detachable
        # modules (no ayaneo-ec EC interface). Four extra buttons (two rear
        # paddles + LC/RC) and BTN_MODE is the main button, so it acts as the
        # guide/Steam button rather than the QAM/overlay button.
        "mode_is_guide": True,
        # Expose per-button remap dropdowns for the six system/face buttons
        # (handled in base.py + konkr_buttons.yml). Gated so it never touches
        # the gamepad BTN_MODE/SELECT/START on other AYANEO devices.
        "face_remap": True,
        "btn_mapping": KONKR_FIT_BTN_MAPPINGS,
        "at_btn_mapping": KONKR_FIT_AT_BTN_MAPPINGS,
        **AYA_DEFAULT_CONF,
    },
}

AYA3_INIT = [
    # Configure controller
    "0000000b07000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b07010000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b07020000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b07030000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b07040000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b07050000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b07060000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b07070000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b07080000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b07090000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b070a0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b070b0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0068000b070c0000000000006800000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0069000b070d0000000000006900000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b070e0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b070f0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0070000b07100000000000007000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0071000b07110000000000007100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0011000b07120002000000000f00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0017000b07130002000000001500000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b07140000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b07150000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0072000b07160000000000007200000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0011000b07170002000008000700000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "006b000b07180000000000006b00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b07190000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b071a0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b071b0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b071c0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b071d0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b071e0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b071f0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    "0000000b07200000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
]


def pad(data: bytes | list[int], length: int = 65) -> bytes:
    return bytes(data).ljust(length, b"\x00")


def calculate_checksum_inplace(buf: bytes | list[int]):
    data = bytearray(buf)
    data[1:3] = sum(data[7:]).to_bytes(2, byteorder="little")
    return pad(data)


AYA_CHECK = pad([0x00, 0x00, 0x00, 0x00, 0x08])
AYA_CUSTOM = pad([0x00, 0x00, 0x00, 0x00, 0x0A, 0x02])
AYA_SAVE = pad([0x00, 0x00, 0x00, 0x00, 0x05])


def get_cfg_commands(
    rgb_mode: str,
    r,
    g,
    b,
    brightness: float,
    eject_left: bool = False,
    eject_right: bool = False,
    reset: bool = False,
    vibration: Literal["disabled", "low", "medium", "high"] = "medium",
):
    match rgb_mode:
        case "disabled":
            mode = 0xFF
        case "solid":
            mode = 1
        case "pulse":
            mode = 2
        case "rainbow":
            mode = 3
            # This has issues
            r, g, b = hsb_to_rgb(275, 100, min(int(brightness * 100), 100))
        case _:
            raise ValueError(f"Invalid RGB mode: {rgb_mode}")

    # Adjust hue slightly to color correct
    if rgb_mode in ["solid", "pulse"]:
        h, s, v = rgb_to_hsb(r, g, b)
        h = (h + 10) % 360
        r, g, b = hsb_to_rgb(h, s, v)

    ccmd = 0x00

    if reset:
        ccmd = 0x88
    if eject_left or eject_right:
        ccmd = (0x07 if eject_left else 0x00) + (0x70 if eject_right else 0x00)

    match vibration:
        case "low":
            c_vibration = 0x01
        case "medium":
            c_vibration = 0x02
        case "high":
            c_vibration = 0x03
        case _:  # "disabled":
            c_vibration = 0x04

    # Joystick sensitivity
    # 50-100-150% 1-3
    # Right, Left
    c_joysens = 0x22

    cmd = [
        # Report id
        0x00,
        # CRC
        0x00,
        0x00,
        # Command
        0x21,
        0x09,
        # Unknown
        0x00,
        0x00,
        0x00,
        # Right RGB, mode, color
        mode,
        r,
        g,
        b,
        # Left RGB, mode, color
        mode,
        r,
        g,
        b,
        # Unknown
        0x00,
        0x00,
        0x00,
        0x00,
        ccmd,
        0x00,
        0x33,
        c_joysens,
        c_vibration << 4,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x01,
        0x00,
        0x00,
        0x00,
        0x00,
        0x64,
        0x64,
    ]
    return [calculate_checksum_inplace(cmd)]


# Curated, user-friendly option list for the Konkr Button Map keyboard
# passthrough (see konkr_buttons.yml / AyaneoKonkr.settings()).
#
# Values are EV_KEY names so they can be used directly as passthrough button
# codes (base.py relies on `act.startswith("KEY_")` and
# `EC(act) in KEYBOARD_CAPABILITIES`). Labels are friendly display names.
#
# Keys of the form "hhd.section:<Group>" are UI-only entries: the patched
# hhd-ui renders them as section headers in the dropdown and never selects
# them. remap_action() in base.py treats them as "disabled" in case an
# unpatched UI saved one anyway.
#
# Every key here is part of the virtual keyboard capability set
# (KEYBOARD_CAPABILITIES in hhd.controller.virtual.uinput).
KONKR_KEY_OPTIONS = {
    "hhd.section:Alphabet": "Alphabet",
    "KEY_A": "A",
    "KEY_B": "B",
    "KEY_C": "C",
    "KEY_D": "D",
    "KEY_E": "E",
    "KEY_F": "F",
    "KEY_G": "G",
    "KEY_H": "H",
    "KEY_I": "I",
    "KEY_J": "J",
    "KEY_K": "K",
    "KEY_L": "L",
    "KEY_M": "M",
    "KEY_N": "N",
    "KEY_O": "O",
    "KEY_P": "P",
    "KEY_Q": "Q",
    "KEY_R": "R",
    "KEY_S": "S",
    "KEY_T": "T",
    "KEY_U": "U",
    "KEY_V": "V",
    "KEY_W": "W",
    "KEY_X": "X",
    "KEY_Y": "Y",
    "KEY_Z": "Z",
    "hhd.section:Numbers": "Numbers",
    "KEY_1": "1",
    "KEY_2": "2",
    "KEY_3": "3",
    "KEY_4": "4",
    "KEY_5": "5",
    "KEY_6": "6",
    "KEY_7": "7",
    "KEY_8": "8",
    "KEY_9": "9",
    "KEY_0": "0",
    "hhd.section:Function Keys": "Function Keys",
    "KEY_F1": "F1",
    "KEY_F2": "F2",
    "KEY_F3": "F3",
    "KEY_F4": "F4",
    "KEY_F5": "F5",
    "KEY_F6": "F6",
    "KEY_F7": "F7",
    "KEY_F8": "F8",
    "KEY_F9": "F9",
    "KEY_F10": "F10",
    "KEY_F11": "F11",
    "KEY_F12": "F12",
    "hhd.section:Navigation": "Navigation",
    "KEY_ESC": "Esc",
    "KEY_TAB": "Tab",
    "KEY_ENTER": "Enter",
    "KEY_BACKSPACE": "Backspace",
    "KEY_SPACE": "Space",
    "KEY_DELETE": "Delete",
    "KEY_INSERT": "Insert",
    "KEY_HOME": "Home",
    "KEY_END": "End",
    "KEY_PAGEUP": "Page Up",
    "KEY_PAGEDOWN": "Page Down",
    "KEY_UP": "Arrow Up",
    "KEY_DOWN": "Arrow Down",
    "KEY_LEFT": "Arrow Left",
    "KEY_RIGHT": "Arrow Right",
    "hhd.section:Modifiers": "Modifiers",
    "KEY_LEFTSHIFT": "Left Shift",
    "KEY_RIGHTSHIFT": "Right Shift",
    "KEY_LEFTCTRL": "Left Ctrl",
    "KEY_RIGHTCTRL": "Right Ctrl",
    "KEY_LEFTALT": "Left Alt",
    "KEY_RIGHTALT": "Right Alt",
    "KEY_LEFTMETA": "Left Win",
    "KEY_RIGHTMETA": "Right Win",
    "hhd.section:System": "System",
    "KEY_CAPSLOCK": "Caps Lock",
    "KEY_NUMLOCK": "Num Lock",
    "KEY_SCROLLLOCK": "Scroll Lock",
    "KEY_PAUSE": "Pause",
}

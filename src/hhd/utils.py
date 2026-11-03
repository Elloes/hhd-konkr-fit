import json
import logging
import os
import platform
import re
import urllib.request

from hhd.plugins.plugin import (
    Context,
    expanduser,
    get_context,
    refresh_is_steam_running,
    is_steam_gamepad_running,
    freeze_steam,
    save_priviledge,
    restore_priviledge,
    run_steam_command,
    switch_priviledge,
)

logger = logging.getLogger(__name__)

# This fork (hhd-konkr-fit) self-hosts its own update channel: the settings
# "Update" buttons pull hhd from the fork below instead of upstream
# hhd-dev/hhd (PyPI), so fork features (Konkr Fit support) survive updates.
FORK_REPO = "Elloes/hhd-konkr-fit"
GIT_HHD = f"git+https://github.com/{FORK_REPO}"
# The upstream hhd-dev/hhd release this fork is based on. Shown in the
# settings next to the fork version.
UPSTREAM_HHD_VERSION = "4.1.12"
HHD_RELEASES_API = f"https://api.github.com/repos/{FORK_REPO}/releases/latest"
# The gamescope overlay UI is a separate project, still published upstream.
HHD_UI_RELEASES_API = "https://api.github.com/repos/hhd-dev/hhd-ui/releases/latest"
HHD_DEV_DIR = "/run/hhd/dev"


def fork_latest_release_source(fallback: str | None = None) -> str:
    """Return a pip-installable git source pointing at the fork's latest release.

    Queries the fork's GitHub releases API for the newest tag and pins the
    git install to it. Falls back to the fork's default branch (``GIT_HHD``)
    when the API is unreachable or the fork has no published release yet.
    """
    if fallback is None:
        fallback = GIT_HHD
    try:
        with urllib.request.urlopen(HHD_RELEASES_API, timeout=15) as f:
            tag = json.load(f)["tag_name"]
        logger.info(f"Resolving hhd-konkr-fit stable update to release tag {tag}")
        return f"{GIT_HHD}@{tag}"
    except Exception as e:
        logger.warning(
            f"Could not resolve the latest hhd-konkr-fit release ({e}); "
            f"falling back to the fork's default branch."
        )
        return fallback

GIT_VERSION_RE = re.compile(r"^(.+\+git\.\d+)\.g?[0-9a-fA-F]+$")


def get_display_version(version: str) -> str:
    """Remove the commit hash from a version produced from a Git checkout."""
    match = GIT_VERSION_RE.fullmatch(version)
    return match.group(1) if match else version


def get_distro_color():
    match get_os():
        case "anatase":
            return 53
        case "arch":
            return 195
        case "ubuntu":
            return 340
        case "red_gold" | "red_gold_an":
            return 28
        case "blood_orange" | "blood_orange_an":
            return 18
        case _:
            return 30


def hsb_to_rgb(h: int, s: int | float, v: int | float):
    # https://www.rapidtables.com/convert/color/hsv-to-rgb.html
    if h >= 360:
        h = 359
    s = s / 100
    v = v / 100

    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c

    if h < 60:
        rgb = (c, x, 0)
    elif h < 120:
        rgb = (x, c, 0)
    elif h < 180:
        rgb = (0, c, x)
    elif h < 240:
        rgb = (0, x, c)
    elif h < 300:
        rgb = (x, 0, c)
    else:
        rgb = (c, 0, x)

    return [int((v + m) * 255) for v in rgb]

def rgb_to_hsb(r, g, b):
    r /= 255
    g /= 255
    b /= 255

    mx = max(r, g, b)
    mn = min(r, g, b)
    c = mx - mn

    if c == 0:
        h = 0
    elif mx == r:
        h = (60 * ((g - b) / c) + 360) % 360
    elif mx == g:
        h = (60 * ((b - r) / c) + 120) % 360
    else:
        h = (60 * ((r - g) / c) + 240) % 360

    s = 0 if mx == 0 else c / mx
    v = mx

    return [int(h), int(s * 100), int(v * 100)]

def get_os() -> str:
    if name := os.environ.get("HHD_DISTRO", None):
        logger.warning(f"Distro override using an environment variable to '{name}'.")
        return name.lower()

    try:
        name = platform.freedesktop_os_release()["NAME"]
    except Exception as e:
        logger.error(f"Could not read os information, error:\n{e}")
        return "ukn"

    distro = name.lower()
    logger.info(f"Running under Linux distro '{distro}'.")

    try:
        # Match just product name
        # if a device exists here its officially supported
        with open("/sys/devices/virtual/dmi/id/product_name") as f:
            dmi = f.read().strip()

        if "ONEXPLAYER F1 EVA-02" in dmi:
            if distro == "anatase":
                distro = "red_gold_an"
            else:
                distro = "red_gold"
    except Exception as e:
        logger.error(f"Could not read product name, error:\n{e}")

    return distro


def get_ac_status_fn() -> str | None:
    BASE_DIR = "/sys/class/power_supply"
    fn = None
    try:
        for name in os.listdir(BASE_DIR):
            if name.startswith("AC") or name.startswith("ADP"):
                fn = name
                break
        if fn is None:
            logger.error(
                f"Could not find AC status file. Power supply directory:\n{os.listdir(BASE_DIR)}"
            )
            return None

        return os.path.join(BASE_DIR, fn, "online")
    except Exception as e:
        logger.error(f"Could not read power supply directory, error:\n{e}")
        return None


def get_ac_status(fn: str | None) -> bool | None:
    if fn is None:
        return None
    if not os.path.exists(fn):
        return None
    try:
        with open(fn) as f:
            status = f.read().strip()
        if status == "1":
            return True
        if status == "0":
            return False
        logger.error(f"Invalid AC status '{status}' read from '{fn}'.")
        return None
    except Exception as e:
        logger.error(f"Could not read AC status file '{fn}', error:\n{e}")
        return None


__all__ = [
    "get_display_version",
    "get_os",
    "refresh_is_steam_running",
    "is_steam_gamepad_running",
    "freeze_steam",
    "expanduser",
    "save_priviledge",
    "restore_priviledge",
    "switch_priviledge",
    "get_context",
    "Context",
    "run_steam_command",
    "get_ac_status",
    "get_ac_status_fn",
]

import logging
from threading import Event, Thread
from typing import Sequence

from hhd.controller.virtual.uinput import KEYBOARD_CAPABILITIES
from hhd.plugins import (
    Config,
    Context,
    Emitter,
    HHDPlugin,
    get_gyro_config,
    get_outputs_config,
    load_relative_yaml,
)
from hhd.plugins.settings import HHDSettings

from .const import CONFS, DEFAULT_MAPPINGS

logger = logging.getLogger(__name__)


class AyaneoControllersPlugin(HHDPlugin):
    name = "ayaneo_controllers"
    priority = 18
    log = "ayac"

    def __init__(self, dmi: str, dconf: dict) -> None:
        self.t = None
        self.should_exit = None
        self.updated = Event()
        self.started = False
        self.t = None

        self.dmi = dmi
        self.dconf = dconf
        self.magic_modules = dconf.get("magic_modules", False)
        self.name = f"ayaneo_controllers@'{dconf.get('name', 'ukn')}'"

        self.config = Config()

    def open(
        self,
        emit: Emitter,
        context: Context,
    ):
        self.emit = emit
        self.context = context
        self.prev = None

    def settings(self) -> HHDSettings:
        if self.magic_modules:
            base = {
                "controllers": {
                    "ayaneo": load_relative_yaml("controllers.yml"),
                },
                "magic_modules": {
                    "magic_modules": load_relative_yaml("modules.yml"),
                },
            }
        else:
            base = {
                "controllers": {
                    "ayaneo": load_relative_yaml("controllers.yml"),
                }
            }

        base["controllers"]["ayaneo"]["children"]["controller_mode"].update(
            get_outputs_config(
                can_disable=True,
                has_leds=self.dconf.get("rgb", False),
                start_disabled=self.dconf.get("untested", False),
                extra_buttons=self.dconf.get("extra_buttons", "quad"),
                noob_default=False,
            )
        )

        if self.dconf.get("face_remap", False):
            children = base["controllers"]["ayaneo"]["children"]
            konkr = load_relative_yaml("konkr_buttons.yml")
            # Add raw keyboard keys (e.g. KEY_INSERT) to every button's
            # dropdown. The values are EV_KEY names so they can be used as
            # passthrough button codes; the labels are their display names.
            # The gamepad options from the yml keep priority when a name
            # collides (there are no collisions today).
            # B("EV_KEY", 1) is always the EV_KEY input event type, whose
            # value is 1 regardless of the runtime ecodes table. The list
            # holds key codes, so reverse them to names via ecodes.keys
            # (names are "KEY_*"; the label is the name without the prefix).
            from evdev import ecodes

            code_to_key = {
                code: name
                for name, code in ecodes.keys.items()
                if name.startswith("KEY_")
            }
            keyboard_options = {
                name.replace("KEY_", ""): name
                for name in (
                    code_to_key.get(code) for code in KEYBOARD_CAPABILITIES[1]
                )
                if name
            }
            for name, button in konkr["children"].items():
                # The rear paddles and LC/RC (btn_rear_* / btn_lc / btn_rc)
                # only offer paddle/face-button options, so they are skipped
                # here and keep the yml's own option set.
                if name in (
                    "btn_left_top",
                    "btn_left_select",
                    "btn_left_start",
                    "btn_right_top",
                    "btn_konkr",
                    "btn_right_bottom",
                ):
                    button["options"] = {**keyboard_options, **button["options"]}
            children["face_buttons"] = konkr
            # The per-button map supersedes the Aya Button Map (swap_guide),
            # so hide it to avoid two conflicting remap UIs.
            children.pop("swap_guide", None)

        if self.dconf.get("display_gyro", True):
            base["controllers"]["ayaneo"]["children"]["imu_axis"] = get_gyro_config(
                self.dconf.get("mapping", DEFAULT_MAPPINGS)
            )
        else:
            del base["controllers"]["ayaneo"]["children"]["imu_axis"]
            del base["controllers"]["ayaneo"]["children"]["imu"]

        return base

    def update(self, conf: Config):
        new_conf = conf["controllers.ayaneo"]

        if self.magic_modules:
            pop_both = conf.get_action("magic_modules.magic_modules.pop_both")
            pop_left = conf.get_action("magic_modules.magic_modules.pop_left")
            pop_right = conf.get_action("magic_modules.magic_modules.pop_right")
            reset = conf.get_action("magic_modules.magic_modules.reset")

            conf["magic_modules.magic_modules.info_right"] = self.config.get(
                "info_right", None
            )
            conf["magic_modules.magic_modules.info_left"] = self.config.get(
                "info_left", None
            )
        else:
            pop_both = False
            pop_left = False
            pop_right = False
            reset = False

        if (
            new_conf == self.prev
            and not pop_both
            and not pop_left
            and not pop_right
            and not reset
        ):
            return
        if self.prev is None:
            self.prev = new_conf
        else:
            self.prev.update(new_conf.conf)

        if pop_both:
            pop = "both"
        elif pop_left:
            pop = "left"
        elif pop_right:
            pop = "right"
        else:
            pop = None

        if pop_both or pop_left or pop_right or reset:
            self.started = False
        else:
            self.updated.set()
        self.start(self.prev, pop=pop, reset=reset)

    def start(self, conf, pop=None, reset=False):
        from .base import plugin_run

        if self.started:
            return
        self.started = True

        self.close()
        self.should_exit = Event()
        self.config["pop"] = pop
        self.config["reset"] = reset
        self.t = Thread(
            target=plugin_run,
            args=(
                conf,
                self.emit,
                self.context,
                self.should_exit,
                self.updated,
                self.dconf,
                self.config,
            ),
        )
        self.t.start()

    def close(self):
        if not self.should_exit or not self.t:
            return
        self.should_exit.set()
        self.t.join()
        self.should_exit = None
        self.t = None


def autodetect(existing: Sequence[HHDPlugin]) -> Sequence[HHDPlugin]:
    if len(existing):
        return existing

    # Match just product name
    # if a device exists here its officially supported
    with open("/sys/devices/virtual/dmi/id/product_name") as f:
        dmi = f.read().strip()

    dconf = CONFS.get(dmi, None)
    matched = dmi
    if dconf is None:
        # Some firmware builds report the DMI product name with slightly
        # different spelling (e.g. zero vs. letter O, or extra prefixes in
        # the Konkr Fit name). Fall back to case-insensitive, 0/O-equivalent
        # matching, with a "KONKR" substring match for the Konkr Fit.
        def norm(s: str) -> str:
            return s.upper().replace("0", "O")

        ndmi = norm(dmi)
        for name, conf in CONFS.items():
            nname = norm(name)
            if ndmi == nname or (nname == "KONKR FIT" and nname in ndmi):
                logger.warning(
                    f"DMI product name '{dmi}' matched device '{name}' "
                    f"via fuzzy matching."
                )
                dconf = conf
                matched = name
                break

    if dconf:
        return [AyaneoControllersPlugin(matched, dconf)]

    logger.warning(f"No AYANEO device found for DMI product name '{dmi}'.")
    return []

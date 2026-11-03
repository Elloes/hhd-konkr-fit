import unittest
from contextlib import ExitStack
from threading import Event
from unittest.mock import Mock, mock_open, patch

from hhd.controller.physical.evdev import B, ChordGamepadEvdev
from hhd.device.ayaneo import AyaneoControllersPlugin, autodetect, base
from hhd.device.ayaneo.const import CONFS
from hhd.plugins import Config


class AyaneoTest(unittest.TestCase):
    def setUp(self):
        self.conf = Config(
            {
                "controller_mode": {"mode": "xbox_elite"},
                "imu": False,
                "imu_hz": 400,
                "imu_axis": {"mode": "default"},
                "nintendo_mode": False,
            }
        )

    def test_ab09_detected_without_vendor_fallback(self):
        with patch("builtins.open", mock_open(read_data="AB09\n")):
            plugins = autodetect([])
        self.assertEqual(len(plugins), 1)
        self.assertIsInstance(plugins[0], AyaneoControllersPlugin)
        self.assertEqual(plugins[0].dconf["name"], "AYANEO NEXT 2")
        self.assertNotIn("magic_modules", plugins[0].settings())
        self.assertIn(
            "magic_modules",
            AyaneoControllersPlugin("AYANEO 3", CONFS["AYANEO 3"]).settings(),
        )

    def test_next2_never_touches_module_power_or_ejection(self):
        stop = Event()
        others = Config({"pop": "both", "reset": True})
        with ExitStack() as stack:
            hardware = [
                stack.enter_context(patch.object(base, name))
                for name in (
                    "read_modules", "read_power", "write_power", "Ayaneo3Hidraw",
                )
            ]
            stack.enter_context(
                patch.object(base, "enumerate_evs", return_value={1: {}})
            )
            loop = stack.enter_context(
                patch.object(base, "controller_loop", side_effect=lambda *a: stop.set())
            )
            stack.enter_context(patch.object(base, "unhide_all"))
            stack.enter_context(patch.object(base.UInputDevice, "close_volume_cached"))
            base.plugin_run(
                self.conf, Mock(), None, stop, Event(), CONFS["AB09"], others
            )
        loop.assert_called_once()
        for call in hardware:
            call.assert_not_called()

    def run_controller(self, product):
        stop = Event()
        stop.set()
        with ExitStack() as stack:
            inputs = stack.enter_context(patch.object(base, "GenericGamepadEvdev"))
            inputs.return_value.open.return_value = []
            vendor = stack.enter_context(patch.object(base, "Ayaneo3Hidraw"))
            vendor.return_value.open.return_value = []
            vendor.return_value.check.return_value = False
            volume = stack.enter_context(patch.object(base, "UInputDevice"))
            volume.return_value.open.return_value = []
            stack.enter_context(patch.object(base, "HrtimerTrigger"))
            outputs = stack.enter_context(
                patch.object(
                    base, "get_outputs", return_value=([], [], {"uses_motion": False})
                )
            )
            stack.enter_context(patch.object(base, "_reset", True))
            base.controller_loop(
                self.conf, stop, Event(), CONFS[product], Mock(), Config()
            )
        return inputs, vendor.return_value, volume.return_value, outputs

    def test_next2_uses_shared_core_without_module_initialization(self):
        inputs, vendor, volume, outputs = self.run_controller("AB09")
        keyboard = inputs.call_args_list[2].kwargs
        self.assertEqual(keyboard["vid"], [0x1C4F])
        self.assertEqual(keyboard["pid"], [0x0002])
        self.assertTrue(keyboard["required"])
        self.assertTrue(keyboard["grab"])
        self.assertEqual(keyboard["capabilities"], {B("EV_KEY"): [B("KEY_F21")]})
        self.assertEqual(keyboard["btn_map"][B("KEY_F21")], "extra_l3")
        self.assertEqual(keyboard["btn_map"][B("KEY_F20")], "extra_r1")
        self.assertEqual(keyboard["btn_map"][B("KEY_D")], "share")
        self.assertEqual(inputs.call_args_list[1].kwargs["btn_map"], {})
        for name in ("check", "init", "reset", "save"):
            getattr(vendor, name).assert_not_called()
        vendor.cfg.assert_called_once()
        volume.open.assert_called_once()
        self.assertIn("rainbow", outputs.call_args.kwargs["rgb_modes"])

    def test_aya3_keeps_existing_initialization_and_button_map(self):
        inputs, vendor, _, _ = self.run_controller("AYANEO 3")
        keyboard = inputs.call_args_list[2].kwargs["btn_map"]
        self.assertEqual(keyboard[B("KEY_F21")], "extra_l2")
        self.assertEqual(keyboard[B("KEY_L")], "extra_l1")
        self.assertEqual(
            inputs.call_args_list[1].kwargs["btn_map"], {B("KEY_F23"): "mode"}
        )
        for name in ("check", "init", "reset", "save"):
            getattr(vendor, name).assert_called_once()

    def test_konkr_settings_inject_button_map_and_hide_aya_map(self):
        s = AyaneoControllersPlugin("KONKR FIT", CONFS["KONKR FIT"]).settings()
        children = s["controllers"]["ayaneo"]["children"]
        self.assertIn("face_buttons", children)
        self.assertIn("btn_konkr", children["face_buttons"]["children"])
        self.assertNotIn("swap_guide", children)
        aya3 = AyaneoControllersPlugin("AYANEO 3", CONFS["AYANEO 3"]).settings()
        children3 = aya3["controllers"]["ayaneo"]["children"]
        self.assertIn("swap_guide", children3)
        self.assertNotIn("face_buttons", children3)

    def test_konkr_button_map_offers_virtual_keyboard_option(self):
        s = AyaneoControllersPlugin("KONKR FIT", CONFS["KONKR FIT"]).settings()
        options = s["controllers"]["ayaneo"]["children"]["face_buttons"]["children"][
            "btn_left_top"
        ]["options"]
        self.assertEqual(options["virtual_kbd"], "Virtual Keyboard")

    def test_virtual_kbd_prefers_steam_and_falls_back_to_system(self):
        from hhd.controller.base import Multiplexer

        for steam_ok, expect_fallback in ((True, False), (False, True)):
            steam_kbd = Mock(return_value=steam_ok)
            linux_kbd = Mock(return_value=True)
            m = Multiplexer(
                params={"steam_kbd": steam_kbd, "linux_kbd": linux_kbd}
            )
            out = m.process(
                [{"type": "button", "code": "virtual_kbd", "value": 1}]
            )
            steam_kbd.assert_called_once_with(True)
            if expect_fallback:
                linux_kbd.assert_called_once_with(True)
            else:
                linux_kbd.assert_not_called()
            # The special event is consumed and blanked before output.
            self.assertEqual(
                [o for o in out if o.get("code") == "virtual_kbd"], []
            )

    def test_virtual_kbd_release_opens_nothing(self):
        from hhd.controller.base import Multiplexer

        steam_kbd = Mock(return_value=True)
        linux_kbd = Mock(return_value=True)
        m = Multiplexer(params={"steam_kbd": steam_kbd, "linux_kbd": linux_kbd})
        m.process([{"type": "button", "code": "virtual_kbd", "value": 0}])
        steam_kbd.assert_not_called()
        linux_kbd.assert_not_called()

    def run_konkr(self, conf=None):
        stop = Event()
        stop.set()
        with ExitStack() as stack:
            inputs = stack.enter_context(patch.object(base, "GenericGamepadEvdev"))
            inputs.return_value.open.return_value = []
            chord = stack.enter_context(patch.object(base, "ChordGamepadEvdev"))
            chord.return_value.open.return_value = []
            vendor = stack.enter_context(patch.object(base, "Ayaneo3Hidraw"))
            vendor.return_value.open.return_value = []
            vendor.return_value.check.return_value = False
            volume = stack.enter_context(patch.object(base, "UInputDevice"))
            volume.return_value.open.return_value = []
            stack.enter_context(patch.object(base, "HrtimerTrigger"))
            stack.enter_context(
                patch.object(
                    base, "get_outputs", return_value=([], [], {"uses_motion": False})
                )
            )
            stack.enter_context(patch.object(base, "_reset", True))
            base.controller_loop(
                conf or self.conf, stop, Event(), CONFS["KONKR FIT"], Mock(), Config()
            )
        return inputs, chord

    def test_konkr_defaults_keep_guide_and_drop_unused_chord_buttons(self):
        inputs, chord = self.run_konkr()
        xmap = inputs.call_args_list[0].kwargs["btn_map"]
        self.assertEqual(xmap[B("BTN_MODE")], "mode")
        self.assertEqual(xmap[B("BTN_SELECT")], "select")
        self.assertEqual(xmap[B("BTN_START")], "start")
        chord.assert_called_once()
        args = chord.call_args.kwargs
        self.assertEqual(args["mod_code"], B("KEY_LEFTCTRL"))
        self.assertEqual(args["plain_code"], B("KEY_F23"))
        self.assertIsNone(args["mod_btn"])
        self.assertIsNone(args["plain_btn"])
        self.assertNotIn(B("KEY_F23"), args["btn_map"])
        self.assertEqual(args["btn_map"][B("KEY_D")], "hhd_qam")
        self.assertEqual(args["btn_map"][B("KEY_L")], "extra_l1")
        self.assertEqual(args["btn_map"][B("KEY_R")], "extra_r1")

    def test_konkr_face_remap_applies_dropdown_choices(self):
        conf = Config(
            {
                "controller_mode": {"mode": "xbox_elite"},
                "imu": False,
                "imu_hz": 400,
                "imu_axis": {"mode": "default"},
                "nintendo_mode": False,
                "face_buttons": {
                    "btn_left_top": "steam_qam",
                    "btn_left_select": "disabled",
                    "btn_konkr": "select",
                    "btn_right_top": "hhd_qam",
                    "btn_right_bottom": "disabled",
                },
            }
        )
        inputs, chord = self.run_konkr(conf)
        xmap = inputs.call_args_list[0].kwargs["btn_map"]
        self.assertEqual(xmap[B("BTN_MODE")], "steam_qam")
        self.assertNotIn(B("BTN_SELECT"), xmap)
        self.assertEqual(xmap[B("BTN_START")], "start")
        args = chord.call_args.kwargs
        self.assertEqual(args["mod_btn"], "hhd_qam")
        self.assertEqual(args["plain_btn"], "select")
        self.assertNotIn(B("KEY_D"), args["btn_map"])

    @staticmethod
    def key(code, value):
        return Mock(type=B("EV_KEY"), code=code, value=value)

    def test_chord_producer_latches_modifiers_on_press(self):
        ctrl, f23, f24 = B("KEY_LEFTCTRL"), B("KEY_F23"), B("KEY_F24")
        dev = Mock()
        dev.read.side_effect = [
            [self.key(ctrl, 1), self.key(f23, 1)],
            [self.key(ctrl, 0), self.key(f23, 0)],
            [self.key(f23, 1)],
            [self.key(f23, 0), self.key(f24, 1)],
        ]
        chord = ChordGamepadEvdev(
            [],
            [],
            btn_map={f24: "keyboard"},
            mod_code=ctrl,
            plain_code=f23,
            mod_btn="hhd_qam",
            plain_btn="select",
        )
        chord.dev = dev
        chord.fd = 1
        with patch(
            "hhd.controller.physical.evdev.can_read",
            side_effect=[True, True, True, True, False],
        ):
            self.assertEqual(
                chord.produce([1]),
                [
                    {"type": "button", "code": "hhd_qam", "value": True},
                    {"type": "button", "code": "hhd_qam", "value": False},
                    {"type": "button", "code": "select", "value": True},
                    {"type": "button", "code": "select", "value": False},
                    {"type": "button", "code": "keyboard", "value": True},
                ],
            )

    def test_chord_producer_ignores_unmapped_combinations(self):
        ctrl, f23 = B("KEY_LEFTCTRL"), B("KEY_F23")
        dev = Mock()
        dev.read.side_effect = [
            [self.key(ctrl, 1), self.key(f23, 1)],
            [self.key(ctrl, 0)],
            [self.key(f23, 1), self.key(f23, 0)],
        ]
        chord = ChordGamepadEvdev(
            [],
            [],
            btn_map={},
            mod_code=ctrl,
            plain_code=f23,
            mod_btn=None,
            plain_btn=None,
        )
        chord.dev = dev
        chord.fd = 1
        with patch(
            "hhd.controller.physical.evdev.can_read", side_effect=[True, True, True, False]
        ):
            self.assertEqual(chord.produce([1]), [])

    def test_shared_rgb_report_and_resume_reapply(self):
        for mode, expected_mode in (
            ("disabled", 0xFF), ("solid", 1), ("pulse", 2), ("rainbow", 3)
        ):
            with self.subTest(mode=mode), patch.dict(base._cfg, mode=None):
                vendor = base.Ayaneo3Hidraw(
                    vibration="medium", config=Config(), emit=Mock()
                )
                vendor.dev = Mock()
                vendor.dev.read.return_value = bytes(64)
                vendor.consume(
                    [{
                        "type": "led", "mode": mode,
                        "red": 0, "green": 0, "blue": 0, "brightness": 1,
                    }]
                )
                report = vendor.dev.write.call_args.args[0]
                self.assertEqual(len(report), 65)
                self.assertEqual(report[3:5], b"\x21\x09")
                self.assertEqual(
                    (report[8], report[12]), (expected_mode, expected_mode)
                )
                self.assertEqual(
                    int.from_bytes(report[1:3], "little"), sum(report[7:])
                )
                vendor.dev.reset_mock()
                vendor.cfg()
                vendor.dev.write.assert_called_once_with(report)


if __name__ == "__main__":
    unittest.main()

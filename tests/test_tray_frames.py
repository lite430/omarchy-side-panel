import importlib.util
from pathlib import Path
import unittest
from gi.repository import GLib

spec = importlib.util.spec_from_file_location("frames", Path(__file__).parents[1] / "monitor-tray-frames.py")
frames = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frames)
frames.GLib = GLib


class RawTrayFrames(unittest.TestCase):
    def pixels(self, *entries):
        return GLib.Variant("a(iiay)", entries)

    def properties(self, **changes):
        values = {"Id": GLib.Variant("s", "1"), "Title": GLib.Variant("s", "wechat"),
                  "ToolTip": GLib.Variant("(sa(iiay)ss)", ("", [], "微信", "")),
                  "IconPixmap": self.pixels((1, 1, bytes([255, 20, 80, 120])))}
        values.update(changes)
        return GLib.Variant("(a{sv})", (values,))

    def test_network_order_argb_and_invisible_rgb(self):
        blank = frames.fingerprint(self.pixels((1, 1, bytes([0, 255, 20, 30]))))
        self.assertEqual(blank, {"signature": "blank", "blank": True})
        self.assertEqual(blank, frames.fingerprint(self.pixels((1, 1, bytes([8, 10, 30, 20])))))
        opaque = self.pixels((1, 1, bytes([255, 20, 80, 120])))
        self.assertFalse(frames.fingerprint(opaque)["blank"])
        self.assertEqual(frames.fingerprint(opaque), frames.fingerprint(opaque))
        self.assertNotEqual(frames.fingerprint(opaque), frames.fingerprint(
            self.pixels((1, 1, bytes([255, 20, 80, 121])))))

    def test_empty_pixels_are_blank_but_named_file_only_icons_are_not(self):
        empty = self.pixels()
        self.assertTrue(frames.frame_record(self.properties(IconPixmap=empty))["frame"]["blank"])
        self.assertIsNone(frames.frame_record(self.properties(
            IconPixmap=empty, IconName=GLib.Variant("s", "crafted.png"),
            IconThemePath=GLib.Variant("s", "/untrusted/cache"))))

    def test_named_icons_with_raw_pixels_still_support_catlink_blinking(self):
        record = frames.frame_record(self.properties(IconName=GLib.Variant("s", "/untrusted/icon.png")))
        self.assertEqual(record["identity"], ["1", "wechat", "微信"])
        self.assertFalse(record["frame"]["blank"])

    def test_dimensions_and_byte_lengths_must_match_before_reading_pixels(self):
        for width, height, data in [(0, 1, b""), (-1, 1, b""), (257, 1, b"x" * 1028),
                                    (2147483647, 2147483647, b""), (2, 2, b"x" * 15)]:
            with self.subTest(width=width, height=height):
                self.assertIsNone(frames.fingerprint(self.pixels((width, height, data))))
        self.assertIsNone(frames.fingerprint(self.pixels(*[(1, 1, b"1234")] * 17)))
        self.assertIsNone(frames.fingerprint(GLib.Variant("s", "file:///untrusted/icon.png")))

    def test_oversized_variant_and_identity_are_rejected(self):
        self.assertIsNone(frames.frame_record(self.properties(IconName=GLib.Variant("s", "x" * frames.MAX_MESSAGE))))
        self.assertIsNone(frames.frame_record(self.properties(Id=GLib.Variant("s", "x" * 513))))

    def test_nearest_valid_size_and_alpha_normalization_are_stable(self):
        raw = bytes([255, 20, 80, 120]) * 32 * 32
        self.assertEqual(frames.fingerprint(self.pixels((32, 32, raw))), frames.fingerprint(
            self.pixels((10000, 10000, b""), (64, 64, b"x" * 64 * 64 * 4), (32, 32, raw))))
        self.assertEqual(frames.fingerprint(self.pixels((2, 1, b"\xff\x14\x50\x78\x00\xff\x20\x30"))),
                         frames.fingerprint(self.pixels((2, 1, b"\xff\x14\x50\x78\x00\x00\x00\x00"))))


if __name__ == "__main__":
    unittest.main()

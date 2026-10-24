#!/usr/bin/env python3
"""Fingerprint SNI raw ARGB pixels without opening or decoding icon files."""
import hashlib
import json
import resource
import sys

WATCHER = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"
ITEM_INTERFACE = "org.kde.StatusNotifierItem"
MAX_ITEMS = 64
MAX_MESSAGE = 2 * 1024 * 1024
MAX_EDGE = 256
MAX_PIXMAPS = 16


def fingerprint(pixmaps):
    """Reject oversized/malformed frames before copying any pixel data."""
    if pixmaps is None or not pixmaps.is_of_type(GLib.VariantType.new("a(iiay)")):
        return None
    count = pixmaps.n_children()
    if count > MAX_PIXMAPS or pixmaps.get_size() > MAX_MESSAGE:
        return None
    if not count:
        return {"signature": "blank", "blank": True}
    candidates = []
    for index in range(count):
        entry = pixmaps.get_child_value(index)
        width = entry.get_child_value(0).get_int32()
        height = entry.get_child_value(1).get_int32()
        pixels = entry.get_child_value(2)
        if not (0 < width <= MAX_EDGE and 0 < height <= MAX_EDGE):
            continue
        if pixels.n_children() != width * height * 4:
            continue
        candidates.append((abs(width - 32) + abs(height - 32), width, height, pixels))
    if not candidates:
        return None
    _, width, height, pixels = min(candidates, key=lambda candidate: candidate[0])
    data = bytearray(pixels.get_data_as_bytes().get_data())
    blank = True
    # SNI uses network-order ARGB, unlike Canvas's RGBA. Invisible RGB must
    # not turn repeated transparent frames into a spurious blink.
    for offset in range(0, len(data), 4):
        if data[offset] <= 8:
            data[offset:offset + 4] = b"\0\0\0\0"
        else:
            blank = False
    signature = "blank" if blank else hashlib.blake2s(
        width.to_bytes(2, "big") + height.to_bytes(2, "big") + data).hexdigest()
    return {"signature": signature, "blank": blank}


def frame_record(reply):
    if reply.get_size() > MAX_MESSAGE:
        return None
    properties = reply.get_child_value(0)

    def text(key):
        value = properties.lookup_value(key, GLib.VariantType.new("s"))
        return value.get_string() if value else ""

    # A named icon with no raw pixels is unsupported, not a blank frame.
    # In particular, never resolve IconThemePath, IconName or a file URL.
    pixmaps = properties.lookup_value("IconPixmap", GLib.VariantType.new("a(iiay)"))
    if pixmaps is None or (not pixmaps.n_children() and text("IconName")):
        return None
    frame = fingerprint(pixmaps)
    if frame is None:
        return None
    tooltip = properties.lookup_value("ToolTip", GLib.VariantType.new("(sa(iiay)ss)"))
    identity = [text("Id"), text("Title"), tooltip.get_child_value(2).get_string() if tooltip else ""]
    if not identity[0] or any(len(value) > 512 for value in identity):
        return None
    return {"identity": identity, "frame": frame}


class Monitor:
    def __init__(self):
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.items = {}
        self.generation = 0
        self.refreshing = False
        self.rescan = False
        self.bus.signal_subscribe(WATCHER, WATCHER, None, WATCHER_PATH, None,
                                  Gio.DBusSignalFlags.NONE, self.watcher_signal)
        self.bus.signal_subscribe(None, ITEM_INTERFACE, None, None, None,
                                  Gio.DBusSignalFlags.NONE, self.item_signal)
        Gio.bus_watch_name_on_connection(self.bus, WATCHER, Gio.BusNameWatcherFlags.NONE,
                                         self.watcher_appeared, self.watcher_vanished)
        GLib.timeout_add_seconds(30, self.reconcile)

    def watcher_appeared(self, *_):
        self.reconcile()

    def watcher_vanished(self, *_):
        self.generation += 1
        self.items.clear()

    def watcher_signal(self, *_):
        self.reconcile()

    def reconcile(self):
        if self.refreshing:
            self.rescan = True
            return True
        self.refreshing = True
        self.bus.call(WATCHER, WATCHER_PATH, "org.freedesktop.DBus.Properties", "Get",
                      GLib.Variant("(ss)", (WATCHER, "RegisteredStatusNotifierItems")),
                      GLib.VariantType.new("(v)"), Gio.DBusCallFlags.NO_AUTO_START, 1000,
                      None, self.listed, self.generation)
        return True

    def reconcile_once(self):
        self.reconcile()
        return False

    def listed(self, bus, result, generation):
        self.refreshing = False
        try:
            reply = bus.call_finish(result)
            if generation != self.generation:
                self.rescan = True
                return
            if reply.get_size() > 65536:
                return
            addresses = reply.unpack()[0]
            current = {}
            for address in addresses[:MAX_ITEMS]:
                service, separator, path = address.partition("/")
                path = "/" + path if separator else "/StatusNotifierItem"
                # Pin subsequent reads/signals to the current unique owner.
                try:
                    owner = bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus",
                        "org.freedesktop.DBus", "GetNameOwner", GLib.Variant("(s)", (service,)),
                        GLib.VariantType.new("(s)"), Gio.DBusCallFlags.NO_AUTO_START, 500, None).unpack()[0]
                except GLib.Error:
                    continue
                key = (owner, path)
                current[key] = self.items.get(key, {"busy": False, "queued": False, "last": None})
            self.items = current
            for key in current:
                self.queue(key)
        except GLib.Error:
            pass  # Watcher/app restarts are retried by signals and reconciliation.
        finally:
            if self.rescan:
                self.rescan = False
                GLib.idle_add(self.reconcile_once)

    def item_signal(self, bus, sender, path, interface, signal, parameters):
        if signal in ("NewIcon", "NewTitle", "NewToolTip"):
            self.queue((sender, path))

    def queue(self, key):
        item = self.items.get(key)
        if item is None:
            return
        item["queued"] = True
        if not item["busy"]:
            item["busy"] = True
            GLib.timeout_add(100, self.read, key, item, self.generation)

    def read(self, key, item, generation):
        if generation != self.generation or self.items.get(key) is not item:
            return False
        item["queued"] = False
        self.bus.call(key[0], key[1], "org.freedesktop.DBus.Properties", "GetAll",
                      GLib.Variant("(s)", (ITEM_INTERFACE,)), GLib.VariantType.new("(a{sv})"),
                      Gio.DBusCallFlags.NO_AUTO_START, 1000, None, self.received,
                      (key, item, generation))
        return False

    def received(self, bus, result, request):
        key, item, generation = request
        try:
            reply = bus.call_finish(result)
            if generation != self.generation or self.items.get(key) is not item:
                return
            record = frame_record(reply)
            if record and record != item["last"]:
                print(json.dumps(record, ensure_ascii=True, separators=(",", ":")), flush=True)
                item["last"] = record
        except GLib.Error:
            pass
        finally:
            item["busy"] = False
            if item["queued"]:
                self.queue(key)


def main():
    # Keep oversized D-Bus replies and any library failure outside the Shell.
    # There is deliberately no image library or file decoder in this process.
    limit = 192 * 1024 * 1024
    _, hard = resource.getrlimit(resource.RLIMIT_AS)
    if hard != resource.RLIM_INFINITY:
        limit = min(limit, hard)
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    global Gio, GLib
    from gi.repository import Gio, GLib
    Monitor()
    GLib.MainLoop().run()


if __name__ == "__main__":
    try:
        main()
    except (ImportError, OSError, MemoryError) as error:
        print(f"Tray frame monitor: {error}", file=sys.stderr)
        raise SystemExit(1)

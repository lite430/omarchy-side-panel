"""Exercise raw SNI blinking and assert untrusted PNGs are never opened."""
import ctypes
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

from check_tray_recovery import stop, wait_for

SOURCE = Path(__file__).resolve().parents[1]


def session():
    omarchy = Path(os.environ.get("OMARCHY_PATH", "/usr/share/omarchy"))
    with tempfile.TemporaryDirectory(prefix="side-panel-tray-security-") as directory:
        root = Path(directory)
        (root / "Commons").symlink_to(omarchy / "shell/Commons", target_is_directory=True)
        shutil.copytree(omarchy / "shell/Ui", root / "Ui")
        popup = root / "Ui/PopupCard.qml"
        popup.write_text(popup.read_text().replace('active: root.open && root.triggerMode === "click"', 'active: false'))
        plugin = root / "Plugin"
        plugin.mkdir()
        for path in (*SOURCE.glob("*.qml"), *SOURCE.glob("*.js"), SOURCE / "monitor-tray-frames.py"):
            shutil.copy2(path, plugin / path.name)
        for name in ("CompatUi", "Ui", "Icons"):
            shutil.copytree(SOURCE / name, plugin / name)
        for package in (plugin, plugin / "Ui"):
            with (package / "qmldir").open("a") as stream:
                for path in package.glob("*.qml"):
                    if path.stem != "PopupAppearance":
                        stream.write(f"{path.stem} 1.0 {path.name}\n")
        shutil.copy2(SOURCE / "tests/qml/tray-security.qml", root / "shell.qml")
        icons = root / "untrusted"
        icons.mkdir()

        def chunk(kind, payload):
            return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))

        # A small, valid PNG with compressed text metadata. IN_OPEN observes
        # the dangerous file access without exhausting the test machine.
        image = icons / "side-panel-untrusted-test.png"
        image.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
            + chunk(b"zTXt", b"Comment\0\0" + zlib.compress(b"x" * 1024 * 1024))
            + chunk(b"IDAT", zlib.compress(b"\0\xff\0\0\xff")) + chunk(b"IEND", b""))
        libc = ctypes.CDLL(None, use_errno=True)
        descriptor = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if descriptor < 0 or libc.inotify_add_watch(descriptor, os.fsencode(image), 0x20) < 0:
            raise OSError(ctypes.get_errno(), "Cannot watch untrusted PNG")
        environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
                       "QT_QPA_PLATFORMTHEME": "", "QT_ACCESSIBILITY": "0", "NO_AT_BRIDGE": "1",
                       "QT_LOGGING_RULES": "", "GIO_USE_VFS": "local", "QS_DISABLE_FILE_WATCHER": "1",
                       "TRAY_ICON_FIXTURE_DIR": str(icons)}
        try:
            with (root / "fixture.log").open("w+") as log:
                exporter = subprocess.Popen([sys.executable, str(SOURCE / "tests/check_tray_integration.py"), "--export-menu"],
                                            stdout=log, stderr=log, env=environment)
                try:
                    def ready():
                        log.seek(0)
                        return "EXPORTED" in log.read()
                    wait_for(ready, "SNI fixture did not start")
                    result = subprocess.run(["quickshell", "-p", str(root), "--no-color"], env=environment,
                                            capture_output=True, text=True, timeout=30)
                    output = result.stdout + result.stderr
                    log.seek(0)
                    fixture = log.read()
                    if result.returncode or "TRAY_SECURITY_PASS" not in output or re.search(
                            r"TRAY_SECURITY_FAIL|TypeError|ReferenceError|ERROR:|Traceback|Cannot read property", output):
                        raise AssertionError(output[-8000:] + "\nFixture:\n" + fixture[-4000:])
                    for expected in ("TRAY_ACTION Activate", "TRAY_ACTION SecondaryActivate", "MENU_EVENT 3 clicked"):
                        assert expected in fixture, f"Native action was lost: {expected}"
                    try:
                        events = os.read(descriptor, 65536)
                    except BlockingIOError:
                        events = b""
                    assert not events, "An untrusted PNG was opened by the Shell or frame helper"
                finally:
                    stop(exporter)
        finally:
            os.close(descriptor)
        print("Real SNI raw-pixel blinking, shared dismissal, malformed pixels, fallback attention and nested menus passed; untrusted PNG opens: 0")


if __name__ == "__main__":
    if "--session" in sys.argv:
        session()
    else:
        result = subprocess.run(["dbus-run-session", "--", sys.executable, str(Path(__file__).resolve()), "--session"],
                                capture_output=True, text=True, timeout=35)
        if result.returncode:
            raise SystemExit(result.stdout + result.stderr[-12000:])
        print(result.stdout.strip())

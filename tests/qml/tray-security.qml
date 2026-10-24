import QtQuick
import QtTest
import Quickshell
import Quickshell.Io
import Quickshell.Services.SystemTray
import "Plugin" as Plugin
import "Plugin/Ui" as PanelUi

ShellRoot {
    id: root
    property string phase: "registration"
    readonly property var wechat: SystemTray.items.values[0] || null
    function check(value, message) { if (!value) throw new Error(message); }
    Plugin.TrayAttention { id: alerts }
    Item {
        id: host
        property var trayAttention: alerts
        property var options: ({pixelated: false, iconPixels: 16})
        property int barSize: 28
        property bool vertical: true
        property string position: "left"
        property color foreground: "#dddddd"
        property string fontFamily: "monospace"
        property var layoutConfig: ({right: ["omarchy.tray"]})
        function recordIconClick(key) {}
        function showTooltip(target, text) {}
        function hideTooltip(target) {}
        function requestPopout(item) {}
        function releasePopout(item) {}
        function targetBelongsToWindow(target, window) { return true; }
    }
    Plugin.TrayController { id: tray; bar: host; settings: ({}) }
    FloatingWindow {
        implicitWidth: 200; implicitHeight: 80; visible: true; color: "transparent"
        Plugin.TrayButton { id: a; x: 10; y: 10; host: host; controller: tray; modelData: root.wechat || ({id: "pending"}) }
        Plugin.TrayButton { id: b; x: 50; y: 10; host: host; controller: tray; modelData: root.wechat || ({id: "pending"}) }
        Item {
            x: 100; y: 10; width: 28; height: 28
            property var modelData: root.wechat
            Item {
                id: legacyIcon
                anchors.fill: parent
                property string icon: root.wechat ? root.wechat.icon : ""
                Image { id: legacyImage; anchors.fill: parent }
            }
            PanelUi.VectorTray { anchors.fill: parent; trayIcon: legacyIcon; sourceImage: legacyImage }
        }
    }
    TestCase { id: input; when: false }
    Process {
        id: control
        property int exitCode: -1
        onExited: function(code) { exitCode = code; }
    }
    function send(method, value) {
        control.exitCode = -1;
        control.command = ["busctl", "--user", "call", "org.example.SidePanelFixture", "/StatusNotifierItem",
            "org.example.SidePanelFixture", method, "s", value];
        control.running = true;
        input.tryVerify(function() { return control.exitCode !== -1; }, 2000);
        check(control.exitCode === 0, "Fixture command failed: " + method + " " + value);
    }
    Timer {
        interval: 200; running: true
        onTriggered: {
            try {
                input.tryVerify(function() { return root.wechat && alerts.stateFor(root.wechat); }, 5000);
                check(root.wechat && root.wechat.id === "wechat", "Real SNI fixture did not register");
                var state = alerts.stateFor(root.wechat);
                phase = "raw pixel monitor";
                input.tryVerify(function() { return state.currentFrame !== ""; }, 3000);
                check(state.currentFrame !== "" && !state.lastBlank, "Helper did not deliver raw pixels");
                check(!a.attention && !b.attention, "Initial frame raised an alert");
                send("Frame", "normal");
                input.wait(300);
                check(!a.attention && !b.attention, "Repeated identical bitmap was treated as a blink");
                phase = "Catlink blink and shared dismissal";
                send("Frame", "blank");
                input.tryVerify(function() { return a.attention && b.attention; }, 2000);
                check(a.attention && b.attention && root.wechat.status === Status.Active,
                    "Raw-pixel blink did not raise shared dots while SNI status stayed Active");
                send("Frame", "normal");
                input.wait(200);
                check(a.attention && b.attention, "Bright frame cleared the alert prematurely");
                input.mouseClick(a, 14, 14, Qt.LeftButton);
                check(!a.attention && !b.attention, "Click did not dismiss both screen copies");
                send("Frame", "blank");
                input.wait(200);
                send("Frame", "normal");
                input.wait(200);
                check(!a.attention && !b.attention, "Acknowledged episode reappeared");
                input.tryVerify(function() { return !state.blinking && !state.acknowledged; }, 3500);
                check(!state.blinking && !state.acknowledged, "Blink end did not reset acknowledgement");
                phase = "malformed and file-only icons";
                var previous = state.currentFrame;
                send("Frame", "oversized");
                input.wait(250);
                send("Frame", "file-only");
                input.wait(250);
                check(state.currentFrame === previous && !a.attention, "Unsupported icon became a false blank frame");
                phase = "standard attention without monitor";
                alerts.monitorFrames = false;
                send("Status", "NeedsAttention");
                input.tryVerify(function() { return a.attention && b.attention; }, 1000);
                check(a.attention && b.attention, "Standard attention depends on the helper");
                input.mouseClick(b, 14, 14, Qt.MiddleButton);
                check(!a.attention && !b.attention, "Middle click did not dismiss attention");
                send("Status", "Active");
                phase = "monitor restart";
                alerts.monitorFrames = true;
                send("Frame", "normal");
                input.wait(300);
                send("Frame", "blank");
                input.tryVerify(function() { return a.attention && b.attention; }, 2000);
                check(a.attention && b.attention, "Frame monitoring did not recover after restart");
                send("Frame", "normal");
                input.mouseClick(a, 14, 14, Qt.LeftButton);
                phase = "untrusted management and menu icons";
                tray.managePopupOpen = true;
                input.wait(200);
                tray.managePopupOpen = false;
                input.mouseClick(a, 14, 14, Qt.RightButton);
                input.tryVerify(function() { return tray.currentChildren.values.length > 0; }, 2000);
                check(tray.trayMenuOpen && tray.currentChildren.values[0].text === "Nested", "Native menu did not open");
                var entry = tray.currentChildren.values[0];
                tray.enterSubmenu(entry, entry.text);
                input.tryVerify(function() { return tray.currentChildren.values.length > 0; }, 2000);
                entry = tray.currentChildren.values[0];
                tray.enterSubmenu(entry, entry.text);
                input.tryVerify(function() { return tray.currentChildren.values.length > 0; }, 2000);
                tray.currentChildren.values[0].triggered();
                tray.close();
                input.wait(200);
                console.log("TRAY_SECURITY_PASS");
            } catch (error) { console.log("TRAY_SECURITY_FAIL", phase, String(error), JSON.stringify(alerts.snapshot())); }
            Qt.quit();
        }
    }
    Timer { interval: 25000; running: true; onTriggered: { console.log("TRAY_SECURITY_FAIL timeout"); Qt.quit(); } }
}

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.SystemTray
import "TrayIconModel.js" as TrayModel

// Share each alert and its acknowledgement across every screen's tray cell.
Item {
    id: root
    property var items: SystemTray.items.values
    property var states: []
    property var frames: ({})
    property bool monitorFrames: true
    readonly property string helperPath: decodeURIComponent(String(Qt.resolvedUrl("monitor-tray-frames.py")).replace(/^file:\/\//, ""))
    onMonitorFramesChanged: {
        restart.stop();
        monitor.running = monitorFrames;
    }

    function receiveFrame(record) {
        if (!record || !Array.isArray(record.identity) || record.identity.length !== 3
            || !record.frame || typeof record.frame.signature !== "string"
            || typeof record.frame.blank !== "boolean") return;
        var key = JSON.stringify(record.identity);
        var next = Object.assign({}, frames);
        if (!(key in next) && Object.keys(next).length >= 64) delete next[Object.keys(next)[0]];
        next[key] = record.frame;
        frames = next;
    }

    function frameFor(identity) {
        // Names are not protocol addresses: ambiguous identities get only
        // the app's own SNI status, never another item's sampled frame.
        return states.filter(function(state) { return state.identity === identity; }).length === 1
            ? frames[identity] || null : null;
    }

    Process {
        id: monitor
        command: ["python3", root.helperPath]
        running: root.monitorFrames
        stdout: SplitParser {
            onRead: function(data) {
                try { root.receiveFrame(JSON.parse(data)); }
                catch (error) { console.warn("Invalid tray frame report:", String(error)); }
            }
        }
        onExited: {
            root.frames = ({});
            if (root.monitorFrames) restart.restart();
        }
    }
    Timer { id: restart; interval: 5000; onTriggered: if (root.monitorFrames) monitor.running = true }

    function stateFor(item) { return states.find(function(state) { return state.modelData === item; }) || null; }
    function snapshot() { return states.map(function(state) { return state.snapshot(); }); }

    Instantiator {
        model: root.items
        onObjectAdded: function(index, object) { root.states = root.states.concat([object]); }
        onObjectRemoved: function(index, object) { root.states = root.states.filter(function(state) { return state !== object; }); }
        delegate: Item {
            id: state
            required property var modelData
            readonly property string identity: TrayModel.identity(modelData)
            readonly property var rawFrame: root.frameFor(identity)
            readonly property bool protocolAttention: modelData.status === Status.NeedsAttention
            property bool blinking: false
            property bool acknowledged: false
            readonly property bool requested: protocolAttention || blinking
            readonly property bool pending: requested && !acknowledged
            property string currentFrame: ""
            property string previousFrame: ""
            property bool lastBlank: true
            property double lastFrameTime: 0

            onRawFrameChanged: if (rawFrame) observeFrame(rawFrame)

            function acknowledge() { if (requested) acknowledged = true; }
            function observeFrame(frame) {
                if (frame.signature === currentFrame) return;
                var now = Date.now();
                var becameBlank = currentFrame !== "" && frame.blank && !lastBlank;
                var alternating = frame.signature === previousFrame && now - lastFrameTime <= 2000;
                if (becameBlank || alternating) blinking = true;
                previousFrame = currentFrame;
                currentFrame = frame.signature;
                lastBlank = frame.blank;
                lastFrameTime = now;
                if (blinking) stopped.restart();
            }
            function snapshot() {
                return {name: TrayModel.name(modelData), initial: TrayModel.initial(modelData),
                    attention: pending, protocolAttention: protocolAttention,
                    blinking: blinking, acknowledged: acknowledged};
            }
            onRequestedChanged: if (!requested) acknowledged = false
            Timer {
                id: stopped
                interval: 2500
                onTriggered: state.blinking = false
            }
        }
    }
}

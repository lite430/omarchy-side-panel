import QtQuick
import "TraySvg.js" as Svg
import "../TrayIconModel.js" as TrayModel

// Legacy widget adapter: use only bundled artwork or a monogram. Never trace
// the widget's native icon through an application-controlled image provider.
Item {
    id: vector
    readonly property bool sidePanelVectorGlyph: true
    required property var sourceImage
    required property var trayIcon
    readonly property var trayItem: trayIcon.parent && "modelData" in trayIcon.parent ? trayIcon.parent.modelData : null
    readonly property string identity: trayItem ? String(trayItem.id || trayItem.title || trayItem.tooltipTitle || "") : ""
    readonly property string file: Svg.packagedFile(identity, "")
    property color foreground: "#fff"
    readonly property bool ready: true
    anchors.fill: parent
    Binding { target: vector.sourceImage; property: "source"; value: ""; restoreMode: Binding.RestoreBindingOrValue }
    Binding { target: vector.sourceImage; property: "opacity"; value: 0; restoreMode: Binding.RestoreBindingOrValue }
    TrayMonogram {
        anchors.fill: parent
        initial: TrayModel.initial(vector.trayItem || {})
        outlined: !vector.file && /wechat|weixin|微信/i.test(vector.identity)
        customIconSource: vector.file ? Qt.resolvedUrl("../Icons/" + vector.file) : ""
        foreground: vector.foreground
    }
}

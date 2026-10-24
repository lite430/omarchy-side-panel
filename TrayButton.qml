import QtQuick
import QtQuick.Window
import Quickshell
import qs.Commons as Commons
import "UsageModel.js" as Usage
import "TrayIconModel.js" as TrayModel
import "Ui/TraySvg.js" as TraySvg
import "Ui" as PanelUi

// Individual tray cells share the side panel's internal menu controller.
Item {
    id: button
    required property var host
    required property var controller
    required property var modelData
    readonly property string usageKey: Usage.trayKey(modelData)
    readonly property color foreground: host.foreground
    readonly property string customIconFile: TraySvg.packagedFile(
        [modelData.id, modelData.title, modelData.tooltipTitle].join(" "), "")
    readonly property bool outlined: !customIconFile && /wechat|weixin|微信/i.test(TrayModel.name(modelData) + " " + String(modelData.id || ""))
    readonly property string initial: outlined ? "W" : TrayModel.initial(modelData)
    readonly property var attentionState: "trayAttention" in host ? host.trayAttention.stateFor(modelData) : null
    readonly property bool attention: attentionState ? attentionState.pending : false
    readonly property bool tooltipHovered: visible && mouse.containsMouse
    readonly property var iconNormalizer: PanelUi.IconNormalizer {
        parent: button
        sourceItem: button
        targetSize: Commons.Style.bar.iconCanvas
    }
    implicitWidth: host.barSize
    implicitHeight: Commons.Style.bar.iconSlot
    width: implicitWidth
    height: implicitHeight
    layer.enabled: true
    layer.sourceRect: iconNormalizer.sourceRect
    layer.smooth: !host.options.pixelated
    layer.textureSize: host.options.pixelated
        ? Qt.size(Math.round(width * host.options.iconPixels / Commons.Style.bar.iconCanvas),
            Math.round(height * host.options.iconPixels / Commons.Style.bar.iconCanvas))
        : Qt.size(Math.ceil(width * Screen.devicePixelRatio * 4), Math.ceil(height * Screen.devicePixelRatio * 4))
    PanelUi.TrayMonogram {
        id: icon
        anchors.centerIn: parent
        anchors.alignWhenCentered: false
        width: Commons.Style.bar.iconCanvas
        height: Commons.Style.bar.iconCanvas
        initial: button.initial
        outlined: button.outlined
        customIconSource: button.customIconFile ? Qt.resolvedUrl("Icons/" + button.customIconFile) : ""
        foreground: button.foreground
        attentionColor: Commons.Color.accent
        fontFamily: button.host.fontFamily
        attention: button.attention
    }
    // Native icon URLs are untrusted. Shared attention detection consumes
    // bounded raw SNI pixels in a separate process, never an image provider.
    function dismissAttention() { if (attentionState) attentionState.acknowledge(); }
    function snapshot() {
        return {name: TrayModel.name(modelData), initial: customIconFile ? "" : initial, attention: attention,
            customIcon: customIconFile, style: customIconFile ? "custom" : outlined ? "outline" : "tile",
            background: customIconFile || outlined ? "transparent" : String(icon.background),
            color: String(foreground), attentionColor: String(icon.attentionColor)};
    }
    function openMenu(event) { controller.openTrayMenu(modelData, button, event); }
    MouseArea {
        id: mouse
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onEntered: button.host.showTooltip(button, button.controller.trayTooltip(button.modelData))
        onExited: button.host.hideTooltip(button)
        onPressed: function(event) {
            if (event.button === Qt.RightButton) {
                button.dismissAttention();
                button.host.recordIconClick(button.usageKey);
                button.openMenu(event);
                event.accepted = true;
            }
        }
        onClicked: function(event) {
            if (event.button === Qt.RightButton) return;
            button.dismissAttention();
            button.host.recordIconClick(button.usageKey);
            if (event.button === Qt.MiddleButton) button.modelData.secondaryActivate();
            else if (button.modelData.onlyMenu) button.openMenu(event);
            else button.modelData.activate();
        }
        onWheel: function(event) { button.modelData.scroll(event.angleDelta.y, false); }
    }
    Component.onDestruction: host.hideTooltip(button)
}

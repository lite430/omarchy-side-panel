import QtQuick
import QtQuick.Effects

Item {
    id: root
    property color color: "white"
    property bool multiple: false

    Image {
        id: artwork
        anchors.fill: parent
        source: Qt.resolvedUrl("../Icons/widgets/" + (root.multiple ? "monitors.svg" : "monitor.svg"))
        sourceSize: Qt.size(128, 128)
        fillMode: Image.PreserveAspectFit
        smooth: true
        visible: false
        layer.enabled: true
        layer.textureSize: Qt.size(128, 128)
        layer.smooth: true
        layer.mipmap: false
    }
    MultiEffect {
        anchors.fill: parent
        source: artwork
        colorization: 1
        colorizationColor: root.color
        autoPaddingEnabled: false
    }
}

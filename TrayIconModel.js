function name(item) {
    return String(item && (item.title || item.tooltipTitle || item.id) || "").trim();
}

function initial(item) {
    var names = item ? [item.title, item.tooltipTitle, item.id] : [];
    for (var i = 0; i < names.length; i++) {
        var letter = String(names[i] || "").match(/[a-z]/i);
        if (letter) return letter[0].toUpperCase();
    }
    return (Array.from(name(item))[0] || "?").toUpperCase();
}

function identity(item) {
    return JSON.stringify([String(item.id || ""), String(item.title || ""), String(item.tooltipTitle || "")]);
}

if (typeof module !== "undefined") module.exports = {name: name, initial: initial, identity: identity};

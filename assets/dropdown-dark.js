(function () {
    var C = {
        bg:     "#161616",
        bg2:    "#1c1c1c",
        border: "#262626",
        text:   "#e8e8e8",
        faint:  "#5a5a5a",
        hover:  "#202020",
    };

    function set(el, prop, val) {
        el.style.setProperty(prop, val, "important");
    }

    function applyDark() {
        var el = document.getElementById("owner-filter");
        if (!el) return;

        set(el, "background-color", C.bg);
        set(el, "border-color", C.border);

        // Panel is a sibling rendered via Radix portal into dash-dropdown-wrapper
        var wrapper = el.closest(".dash-dropdown-wrapper") || el;
        var sel = function (q) { return wrapper.querySelectorAll(q); };

        sel(".dash-dropdown-grid-container.dash-dropdown-trigger").forEach(function (el) {
            set(el, "background-color", C.bg);
            set(el, "border-color", C.border);
        });

        sel(".dash-dropdown-placeholder").forEach(function (el) {
            set(el, "color", C.faint);
        });

        sel(".dash-dropdown-value").forEach(function (el) {
            set(el, "color", C.text);
        });

        sel(".dash-dropdown-value-item").forEach(function (el) {
            set(el, "background-color", C.bg2);
            set(el, "border-color", C.border);
            set(el, "color", C.text);
        });

        sel(".dash-dropdown-search").forEach(function (el) {
            set(el, "background-color", C.bg);
            set(el, "color", C.text);
        });

        sel(".dash-dropdown-clear, .dash-dropdown-trigger-icon").forEach(function (el) {
            set(el, "color", C.faint);
        });

        sel(".dash-dropdown-content").forEach(function (el) {
            set(el, "background-color", C.bg);
            set(el, "border-color", C.border);
        });

        sel(".dash-dropdown-options").forEach(function (el) {
            set(el, "background-color", C.bg);
        });

        sel(".dash-dropdown-option").forEach(function (el) {
            set(el, "background-color", C.bg);
            set(el, "color", C.text);
        });
    }

    var observer = new MutationObserver(applyDark);

    document.addEventListener("DOMContentLoaded", function () {
        applyDark();
        observer.observe(document.body, { childList: true, subtree: true });
    });

    setTimeout(applyDark, 100);
    setTimeout(applyDark, 500);
})();

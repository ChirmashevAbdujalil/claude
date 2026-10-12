/* «Natijalar» sahifasi grafiklari: kutubxonasiz, SVG. Konteyner kengligiga moslashadi,
   sichqoncha yoki barmoq bilan har bir hafta qiymati ko'rinadi. */
(function () {
  "use strict";

  var SVG = "http://www.w3.org/2000/svg";
  var tip = document.querySelector(".chart-tip");

  function el(name, attrs, parent) {
    var node = document.createElementNS(SVG, name);
    Object.keys(attrs || {}).forEach(function (key) { node.setAttribute(key, attrs[key]); });
    if (parent) parent.appendChild(node);
    return node;
  }

  function niceMax(value) {
    if (value <= 4) return 4;
    var step = Math.pow(10, Math.floor(Math.log10(value)));
    var options = [1, 2, 2.5, 5, 10];
    for (var i = 0; i < options.length; i++) {
      if (options[i] * step >= value) return options[i] * step;
    }
    return 10 * step;
  }

  function compact(value) {
    if (value >= 1e6) return (value / 1e6).toFixed(1).replace(/\.0$/, "") + "M";
    if (value >= 1e3) return (value / 1e3).toFixed(1).replace(/\.0$/, "") + "K";
    return String(value);
  }

  function showTip(html, x, y) {
    if (!tip) return;
    tip.innerHTML = html;
    tip.hidden = false;
    var w = tip.offsetWidth, h = tip.offsetHeight;
    var left = Math.min(Math.max(8, x - w / 2), window.innerWidth - w - 8);
    var top = y - h - 12 < 8 ? y + 16 : y - h - 12;
    tip.style.transform = "translate(" + left + "px," + top + "px)";
  }

  function hideTip() { if (tip) tip.hidden = true; }

  function render(box) {
    var rows = JSON.parse(document.getElementById(box.dataset.source).textContent);
    var key = box.dataset.key, unit = box.dataset.unit, kind = box.dataset.chart;
    var values = rows.map(function (r) { return r[key]; });
    var width = box.clientWidth, height = 220;
    var m = { top: 18, right: kind === "line" ? 34 : 12, bottom: 26, left: 34 };
    var iw = width - m.left - m.right, ih = height - m.top - m.bottom;
    var max = niceMax(Math.max.apply(null, values.concat([0])));
    var band = iw / rows.length;
    var y = function (v) { return m.top + ih - (v / max) * ih; };
    var x = function (i) { return m.left + band * i + band / 2; };

    box.innerHTML = "";
    var svg = el("svg", { width: width, height: height, viewBox: "0 0 " + width + " " + height }, box);

    // To'r chiziqlari va y o'qi: 0, yarmi, maksimum
    [0, max / 2, max].forEach(function (tick) {
      el("line", { x1: m.left, x2: width - m.right, y1: y(tick), y2: y(tick), class: "chart-grid" }, svg);
      el("text", { x: m.left - 8, y: y(tick) + 4, class: "chart-axis", "text-anchor": "end" }, svg).textContent = compact(tick);
    });

    // x o'qi: tor ekranda har ikkinchi yoki uchinchi hafta
    var every = band < 26 ? 3 : band < 44 ? 2 : 1;
    rows.forEach(function (r, i) {
      if ((rows.length - 1 - i) % every) return;
      el("text", { x: x(i), y: height - 6, class: "chart-axis", "text-anchor": "middle" }, svg).textContent = r.label;
    });

    var marks = [];
    var last = rows.length - 1;
    if (kind === "line") {
      var points = values.map(function (v, i) { return x(i) + "," + y(v); });
      el("path", { d: "M" + x(0) + "," + y(0) + " L" + points.join(" L") + " L" + x(last) + "," + y(0) + " Z", class: "chart-area" }, svg);
      el("polyline", { points: points.join(" "), class: "chart-line" }, svg);
      var cross = el("line", { y1: m.top, y2: m.top + ih, class: "chart-cross", visibility: "hidden" }, svg);
      var dot = el("circle", { r: 5, class: "chart-dot", visibility: "hidden" }, svg);
      el("circle", { cx: x(last), cy: y(values[last]), r: 5, class: "chart-dot" }, svg);
      el("text", { x: x(last) + 9, y: y(values[last]) + 4, class: "chart-value" }, svg).textContent = compact(values[last]);
      marks.focus = function (i) {
        var on = i !== null;
        cross.setAttribute("visibility", on ? "visible" : "hidden");
        dot.setAttribute("visibility", on ? "visible" : "hidden");
        if (on) {
          cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i));
          dot.setAttribute("cx", x(i)); dot.setAttribute("cy", y(values[i]));
        }
      };
    } else {
      var bw = Math.min(24, band * 0.62);
      values.forEach(function (v, i) {
        var top = y(v), h = m.top + ih - top, left = x(i) - bw / 2, r = Math.min(4, h);
        // Faqat ma'lumot uchi yumaloq, asos tekis
        var d = h > 0
          ? "M" + left + "," + (top + h) + " V" + (top + r) + " Q" + left + "," + top + " " + (left + r) + "," + top +
            " H" + (left + bw - r) + " Q" + (left + bw) + "," + top + " " + (left + bw) + "," + (top + r) + " V" + (top + h) + " Z"
          : "";
        marks.push(el("path", { d: d, class: "chart-bar" + (rows[i].partial ? " is-partial" : "") }, svg));
      });
      if (values[last]) {
        el("text", { x: x(last), y: y(values[last]) - 6, class: "chart-value", "text-anchor": "middle" }, svg).textContent = compact(values[last]);
      }
      marks.focus = function (i) {
        marks.forEach(function (bar, j) { bar.classList.toggle("is-dim", i !== null && j !== i); });
      };
    }

    // Kursor qatlami: butun ustun kengligi bo'yicha (kichik nishonga tegish shart emas)
    var hit = el("rect", { x: m.left, y: m.top, width: iw, height: ih, fill: "transparent" }, svg);
    function move(event) {
      var rect = svg.getBoundingClientRect();
      var point = event.touches ? event.touches[0] : event;
      var i = Math.max(0, Math.min(last, Math.floor((point.clientX - rect.left - m.left) / band)));
      marks.focus(i);
      showTip("<b>" + rows[i][key] + "</b> " + unit + "<br><span>" + rows[i].range + "</span>" +
        (key === "total" && rows[i]["new"] ? "<br><span>+" + rows[i]["new"] + " yangi</span>" : "") +
        (rows[i].partial ? "<br><span>joriy hafta, davom etmoqda</span>" : ""),
        rect.left + x(i), rect.top + y(values[i]));
    }
    function leave() { marks.focus(null); hideTip(); }
    hit.addEventListener("pointermove", move);
    hit.addEventListener("pointerdown", move);
    hit.addEventListener("pointerleave", leave);
  }

  var charts = Array.prototype.slice.call(document.querySelectorAll("[data-chart]"));
  charts.forEach(render);
  if (window.ResizeObserver) {
    var widths = new WeakMap();
    var observer = new ResizeObserver(function (entries) {
      entries.forEach(function (entry) {
        var w = Math.round(entry.contentRect.width);
        if (widths.get(entry.target) !== w) { widths.set(entry.target, w); render(entry.target); }
      });
    });
    charts.forEach(function (box) { observer.observe(box); });
  }

  // Gorizontal ustunlar: qiymat sichqoncha ostida
  document.querySelectorAll("[data-tip]").forEach(function (row) {
    row.addEventListener("pointermove", function (event) { showTip(row.dataset.tip, event.clientX, event.clientY); });
    row.addEventListener("pointerleave", hideTip);
  });
  window.addEventListener("scroll", hideTip, { passive: true });
})();

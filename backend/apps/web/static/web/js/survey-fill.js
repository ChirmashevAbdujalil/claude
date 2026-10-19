/* So'rovnomani to'ldirish: jarayon chizig'i, majburiy savollarni tekshirish va qoralamani brauzerda saqlash. */
(function () {
  "use strict";

  var form = document.querySelector("[data-survey-fill]");
  if (!form) return;

  var questions = Array.prototype.slice.call(form.querySelectorAll("[data-q]"));
  var bar = document.querySelector("[data-progress-bar]");
  var text = form.querySelector("[data-progress-text]");
  var draftKey = form.dataset.draftKey;
  var REQUIRED = "Bu savolga javob berish majburiy";

  questions.forEach(function (q, i) {
    var no = q.querySelector("[data-qno]");
    if (no) no.textContent = String(i + 1);
  });

  function isAnswered(q) {
    var fields = q.querySelectorAll("input, textarea, select");
    for (var i = 0; i < fields.length; i++) {
      var f = fields[i];
      if (f.hasAttribute("data-other-text")) continue;
      if (f.type === "radio" || f.type === "checkbox") {
        if (!f.checked) continue;
        if (f.hasAttribute("data-other-toggle")) {
          var other = q.querySelector("[data-other-text]");
          if (other && other.value.trim()) return true;
          continue;
        }
        return true;
      }
      if (f.value && f.value.trim()) return true;
    }
    return false;
  }

  function setError(q, message) {
    var box = q.querySelector("[data-error]");
    if (box) box.textContent = message || "";
    q.classList.toggle("has-error", !!message);
  }

  function update() {
    var done = 0;
    questions.forEach(function (q) {
      var answered = isAnswered(q);
      q.classList.toggle("is-answered", answered);
      if (answered) {
        done++;
        if (q.classList.contains("has-error")) setError(q, "");
      }
    });
    var total = questions.length || 1;
    if (bar) bar.style.width = Math.round((done / total) * 100) + "%";
    if (text) text.textContent = done + " / " + questions.length + " savolga javob berildi";
  }

  /* ---------- Qoralama: sahifa yopilib qolsa, javoblar yo'qolmaydi ---------- */
  function storage() {
    try { return window.localStorage; } catch (e) { return null; }
  }

  function saveDraft() {
    var store = storage();
    if (!store || !draftKey) return;
    var data = [];
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || el.name === "csrfmiddlewaretoken" || el.name === "website") return;
      if ((el.type === "radio" || el.type === "checkbox") && !el.checked) return;
      if (el.type === "submit" || el.type === "button") return;
      data.push([el.name, el.value]);
    });
    try { store.setItem(draftKey, JSON.stringify({ at: Date.now(), data: data })); } catch (e) { /* joy yo'q */ }
  }

  function restoreDraft() {
    var store = storage();
    if (!store || !draftKey || form.dataset.restore !== "1") return false;
    var raw;
    try { raw = JSON.parse(store.getItem(draftKey) || "null"); } catch (e) { raw = null; }
    if (!raw || !raw.data || !raw.data.length || Date.now() - raw.at > 14 * 864e5) return false;
    raw.data.forEach(function (pair) {
      var fields = form.querySelectorAll('[name="' + pair[0].replace(/"/g, "") + '"]');
      Array.prototype.forEach.call(fields, function (el) {
        if (el.type === "radio" || el.type === "checkbox") { if (el.value === pair[1]) el.checked = true; }
        else if (!el.value) el.value = pair[1];
      });
    });
    return true;
  }

  var timer;
  function onChange(e) {
    var q = e.target.closest("[data-q]");
    if (e.target.hasAttribute("data-other-text") && e.target.value.trim()) {
      var toggle = e.target.parentElement.querySelector("[data-other-toggle]");
      if (toggle) toggle.checked = true;
    }
    if (e.target.closest(".field.has-error") && e.target.value) e.target.closest(".field").classList.remove("has-error");
    if (q) update();
    clearTimeout(timer);
    timer = setTimeout(saveDraft, 400);
  }
  form.addEventListener("input", onChange);
  form.addEventListener("change", onChange);

  /* Guruh: K-21-05 ko'rinishida avtomatik formatlanadi */
  var CYR = { "А": "A", "Б": "B", "В": "V", "Г": "G", "Ғ": "G", "Д": "D", "Е": "E", "Ж": "J", "З": "Z", "И": "I",
    "Й": "Y", "К": "K", "Қ": "Q", "Л": "L", "М": "M", "Н": "N", "О": "O", "Ў": "O", "П": "P", "Р": "R", "С": "S",
    "Т": "T", "У": "U", "Ф": "F", "Х": "X", "Ҳ": "H", "Ш": "SH", "Ч": "CH", "Э": "E", "Ю": "YU", "Я": "YA" };
  var GROUP_RE = /^[A-Z]{1,5}-\d{2}-\d{2}$/;
  function formatGroup(value) {
    var upper = value.toUpperCase().split("").map(function (ch) { return CYR[ch] || ch; }).join("");
    var letters = (upper.match(/[A-Z]/g) || []).join("").slice(0, 5);
    var digits = (upper.match(/\d/g) || []).join("").slice(0, 4);
    var out = letters;
    if (digits.length) out += "-" + digits.slice(0, 2);
    if (digits.length > 2) out += "-" + digits.slice(2);
    return out;
  }
  function groupError(input, message) {
    var field = input.closest(".field");
    if (!field) return;
    var box = field.querySelector(".error[data-js]");
    if (message && !box) {
      box = document.createElement("span");
      box.className = "error";
      box.setAttribute("data-js", "");
      field.appendChild(box);
    }
    if (box) box.textContent = message || "";
    field.classList.toggle("has-error", !!message);
  }
  form.querySelectorAll("[data-group-input]").forEach(function (input) {
    input.addEventListener("input", function () {
      var formatted = formatGroup(input.value);
      if (formatted !== input.value) input.value = formatted;
      if (GROUP_RE.test(input.value)) groupError(input, "");
    });
    input.addEventListener("blur", function () {
      if (input.value && !GROUP_RE.test(input.value)) groupError(input, "Guruhni K-21-05 ko'rinishida yozing");
    });
    if (input.value) input.value = formatGroup(input.value);
  });

  /* Batafsil javob maydoni matnga qarab o'sadi */
  form.querySelectorAll("[data-autogrow]").forEach(function (area) {
    function grow() { area.style.height = "auto"; area.style.height = Math.min(area.scrollHeight + 2, 480) + "px"; }
    area.addEventListener("input", grow);
    grow();
  });

  /* ---------- Yuborishdan oldin tekshirish ---------- */
  form.addEventListener("submit", function (e) {
    var first = null;
    questions.forEach(function (q) {
      if (q.hasAttribute("data-required") && !isAnswered(q)) {
        setError(q, REQUIRED);
        first = first || q;
      }
    });
    form.querySelectorAll(".sv-identity [required]").forEach(function (el) {
      if (!el.value.trim()) {
        el.closest(".field").classList.add("has-error");
        first = first || el.closest(".field");
      }
    });
    form.querySelectorAll("[data-group-input]").forEach(function (el) {
      if (el.value && !GROUP_RE.test(el.value)) {
        groupError(el, "Guruhni K-21-05 ko'rinishida yozing");
        first = first || el.closest(".field");
      }
    });
    if (first) {
      e.preventDefault();
      first.scrollIntoView({ behavior: "smooth", block: "center" });
      var focusable = first.querySelector("input, textarea, select");
      if (focusable) setTimeout(function () { focusable.focus({ preventScroll: true }); }, 350);
      return;
    }
    saveDraft();
    var send = form.querySelector("[data-send]");
    if (send) { send.disabled = true; send.classList.add("is-loading"); }
  });

  var restored = restoreDraft();
  update();
  if (restored) {
    var note = document.createElement("div");
    note.className = "sv-restored";
    note.innerHTML = "<span>↺ Avvalgi javoblaringiz tiklandi</span>";
    var clear = document.createElement("button");
    clear.type = "button";
    clear.textContent = "Tozalash";
    clear.addEventListener("click", function () {
      try { storage().removeItem(draftKey); } catch (err) { /* e'tiborsiz */ }
      window.location.reload();
    });
    note.appendChild(clear);
    form.insertBefore(note, form.firstChild);
  }

  var firstError = document.querySelector(".sv-q.has-error, .sv-identity .field.has-error");
  if (firstError) setTimeout(function () { firstError.scrollIntoView({ block: "center" }); }, 100);
})();

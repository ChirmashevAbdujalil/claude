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
      if (f.type === "file") { if (f.files && f.files.length) return true; continue; }
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
      if (el.type === "submit" || el.type === "button" || el.type === "file") return;
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
        if (el.type === "file") return;
        if (el.type === "radio" || el.type === "checkbox") { if (el.value === pair[1]) el.checked = true; }
        else if (!el.value) el.value = pair[1];
      });
    });
    return true;
  }

  var timer;
  function onChange(e) {
    if (e.target.type === "file") return; // fayl maydonini o'z ishlovchisi tekshiradi va xatoni ko'rsatadi
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

  /* Tyutor: faqat tanlangan fakultet tyutorlari ko'rinadi */
  var facultySelect = form.querySelector("[data-faculty-select]");
  var tutorSelect = form.querySelector("[data-tutor-select]");
  function syncTutors() {
    if (!facultySelect || !tutorSelect) return;
    var faculty = facultySelect.value;
    var visible = 0;
    Array.prototype.forEach.call(tutorSelect.options, function (option) {
      if (!option.value) return;
      var match = option.dataset.faculty === faculty;
      option.hidden = !match;
      option.disabled = !match;
      if (match) visible++;
      if (!match && option.selected) tutorSelect.value = "";
    });
    var field = tutorSelect.closest("[data-tutor-field]");
    if (field) field.hidden = Boolean(faculty) && visible === 0;
    tutorSelect.disabled = !faculty;
    tutorSelect.options[0].textContent = faculty ? "Tanlang" : "Avval fakultetni tanlang";
  }
  if (facultySelect && tutorSelect) {
    facultySelect.addEventListener("change", syncTutors);
    syncTutors();
  }

  /* ---------- Fayl yuklash: tanlangan fayllar ro'yxati, ko'rinish va tekshiruv ---------- */
  var MB = 1024 * 1024;
  var canRebuild = (function () { try { return !!new DataTransfer(); } catch (e) { return false; } })();

  function humanSize(size) {
    return size >= MB ? (size / MB).toFixed(1).replace(".0", "") + " MB" : Math.max(1, Math.round(size / 1024)) + " KB";
  }
  function fileIcon(name) {
    var ext = (name.split(".").pop() || "").toLowerCase();
    if (ext === "pdf") return "📕";
    if (["doc", "docx"].indexOf(ext) !== -1) return "📘";
    if (["xls", "xlsx"].indexOf(ext) !== -1) return "📗";
    if (["ppt", "pptx"].indexOf(ext) !== -1) return "📙";
    return "🖼";
  }

  form.querySelectorAll("[data-upload]").forEach(function (box) {
    var input = box.querySelector("[data-file-input]");
    var list = box.querySelector("[data-file-list]");
    var drop = box.querySelector("[data-drop]");
    var q = box.closest("[data-q]");
    var maxFiles = parseInt(box.dataset.maxFiles, 10) || 1;
    var maxMb = parseInt(box.dataset.maxMb, 10) || 10;
    var exts = (box.dataset.exts || "").split(",");
    var selected = [];
    var urls = [];

    function check(file) {
      var ext = (file.name.split(".").pop() || "").toLowerCase();
      if (exts.indexOf(ext) === -1) return "«" + file.name + "»: bu turdagi fayl qabul qilinmaydi";
      if (file.size > maxMb * MB) return "«" + file.name + "» hajmi " + humanSize(file.size) + ": har bir fayl " + maxMb + " MB dan oshmasin";
      if (!file.size) return "«" + file.name + "» bo'sh fayl";
      return "";
    }

    function sync() {
      if (canRebuild) {
        var transfer = new DataTransfer();
        selected.forEach(function (file) { transfer.items.add(file); });
        input.files = transfer.files;
      }
      urls.forEach(function (url) { URL.revokeObjectURL(url); });
      urls = [];
      list.innerHTML = "";
      selected.forEach(function (file, index) {
        var item = document.createElement("li");
        item.className = "sv-file";
        var thumb = document.createElement("span");
        thumb.className = "sv-file-thumb";
        if (/^image\/(jpeg|png|webp|gif)$/.test(file.type)) {
          var url = URL.createObjectURL(file);
          urls.push(url);
          var img = document.createElement("img");
          img.src = url;
          img.alt = "";
          thumb.appendChild(img);
        } else {
          thumb.textContent = fileIcon(file.name);
        }
        var info = document.createElement("span");
        info.className = "sv-file-info";
        var name = document.createElement("b");
        name.textContent = file.name;
        var size = document.createElement("small");
        size.textContent = humanSize(file.size) + " · tayyor";
        info.appendChild(name);
        info.appendChild(size);
        item.appendChild(thumb);
        item.appendChild(info);
        if (canRebuild) {
          var remove = document.createElement("button");
          remove.type = "button";
          remove.className = "sv-file-remove";
          remove.setAttribute("aria-label", file.name + " faylini olib tashlash");
          remove.textContent = "✕";
          remove.addEventListener("click", function () { selected.splice(index, 1); sync(); update(); });
          item.appendChild(remove);
        }
        list.appendChild(item);
      });
      box.classList.toggle("has-files", selected.length > 0);
      box.classList.toggle("is-full", selected.length >= maxFiles);
    }

    function add(files) {
      var problems = [];
      var incoming = Array.prototype.slice.call(files || []);
      if (!canRebuild || maxFiles === 1) selected = [];
      incoming.forEach(function (file) {
        var problem = check(file);
        if (problem) { problems.push(problem); return; }
        var duplicate = selected.some(function (f) { return f.name === file.name && f.size === file.size; });
        if (duplicate) return;
        if (selected.length >= maxFiles) { problems.push("Ko'pi bilan " + maxFiles + " ta fayl yuklash mumkin"); return; }
        selected.push(file);
      });
      sync();
      update();
      setError(q, problems.length ? problems[0] : "");
    }

    input.addEventListener("change", function () { add(input.files); });
    if (!canRebuild) return; // eski brauzer: faylni maydonning o'ziga tashlash ishlaydi
    ["dragenter", "dragover"].forEach(function (name) {
      drop.addEventListener(name, function (e) { e.preventDefault(); drop.classList.add("is-over"); });
    });
    ["dragleave", "drop"].forEach(function (name) {
      drop.addEventListener(name, function () { drop.classList.remove("is-over"); });
    });
    drop.addEventListener("drop", function (e) {
      e.preventDefault();
      if (e.dataTransfer && e.dataTransfer.files) add(e.dataTransfer.files);
    });
  });

  function selectedFiles() {
    var total = 0, count = 0;
    form.querySelectorAll("[data-file-input]").forEach(function (input) {
      Array.prototype.forEach.call(input.files || [], function (file) { total += file.size; count++; });
    });
    return { count: count, total: total };
  }

  /* Fayl bo'lsa, javob XHR orqali yuboriladi: talaba yuklanish foizini ko'rib turadi */
  function sendWithProgress() {
    var files = selectedFiles();
    var send = form.querySelector("[data-send]");
    var panel = document.createElement("div");
    panel.className = "sv-uploading";
    panel.innerHTML = '<div class="sv-uploading-row"><span>📤 Fayllar yuklanmoqda…</span><b data-pct>0%</b></div>' +
      '<div class="sv-uploading-bar"><span data-bar></span></div><small data-bytes></small>';
    document.body.appendChild(panel);
    var pct = panel.querySelector("[data-pct]"), barEl = panel.querySelector("[data-bar]"), bytes = panel.querySelector("[data-bytes]");
    bytes.textContent = files.count + " ta fayl · " + humanSize(files.total);

    var xhr = new XMLHttpRequest();
    xhr.open("POST", form.action || window.location.href);
    xhr.upload.addEventListener("progress", function (e) {
      if (!e.lengthComputable) return;
      var value = Math.min(100, Math.round((e.loaded / e.total) * 100));
      pct.textContent = value + "%";
      barEl.style.width = value + "%";
      bytes.textContent = humanSize(e.loaded) + " / " + humanSize(e.total);
      if (value >= 100) panel.querySelector("span").textContent = "✅ Yuklandi, saqlanmoqda…";
    });
    xhr.addEventListener("load", function () {
      if (xhr.responseURL && xhr.responseURL.indexOf("/rahmat/") !== -1) {
        window.location.href = xhr.responseURL;
        return;
      }
      document.open();
      document.write(xhr.responseText);
      document.close();
    });
    xhr.addEventListener("error", function () {
      panel.remove();
      if (send) { send.disabled = false; send.classList.remove("is-loading"); }
      alert("Internet aloqasi uzildi: javob yuborilmadi. Aloqani tekshirib, qayta yuboring.");
    });
    xhr.send(new FormData(form));
  }

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
    if (tutorSelect && !tutorSelect.disabled && !tutorSelect.closest("[data-tutor-field]").hidden && !tutorSelect.value) {
      tutorSelect.closest(".field").classList.add("has-error");
      first = first || tutorSelect.closest(".field");
    }
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
    if (selectedFiles().count && window.FormData && window.XMLHttpRequest) {
      e.preventDefault();
      sendWithProgress();
    }
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

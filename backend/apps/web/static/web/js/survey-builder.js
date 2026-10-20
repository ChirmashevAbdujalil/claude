/* So'rovnoma konstruktori: savollar ro'yxati brauzerda tahrirlanadi va saqlashda JSON sifatida yuboriladi. */
(function () {
  "use strict";

  var root = document.getElementById("survey-builder");
  var form = document.querySelector("[data-survey-form]");
  if (!root || !form) return;

  var questions = JSON.parse(document.getElementById("survey-schema-data").textContent || "[]");
  var kinds = JSON.parse(document.getElementById("survey-kinds-data").textContent || "[]");
  var hidden = document.getElementById("survey-schema");
  var counter = document.querySelector("[data-sb-count]");
  var CHOICE = { single: true, multiple: true, dropdown: true };
  var MARK = { single: "○", multiple: "☐", dropdown: "" };
  var TRACKS = ["Ilmiy tadqiqot", "Fan olimpiadalari", "Ixtirochilik va muhandislik", "IT va dasturlash",
    "Startap va tadbirkorlik", "Dizayn va ijod"];
  var dirty = false;

  function blank(kind) {
    var q = { kind: kind, title: "", help_text: "", required: false, options: [], allow_other: false,
      scale_max: 5, scale_min_label: "", scale_max_label: "", file_types: [], max_files: 1, max_file_mb: 10 };
    if (CHOICE[kind]) q.options = ["1-variant"];
    if (kind === "file") {
      q.title = "Yutuqlaringizni tasdiqlovchi hujjatni yuklang (sertifikat, diplom)";
      q.file_types = ["pdf", "image"];
    }
    if (kind === "track") q.title = "Qaysi yo'nalishda o'zingizni eng kuchli his qilasiz?";
    if (kind === "section") q.title = "Yangi bo'lim";
    return q;
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) {
      if (key === "text") node.textContent = attrs[key];
      else if (key === "on") Object.keys(attrs.on).forEach(function (ev) { node.addEventListener(ev, attrs.on[ev]); });
      else if (key in node && key !== "list") node[key] = attrs[key];
      else node.setAttribute(key, attrs[key]);
    });
    (children || []).forEach(function (child) { if (child) node.appendChild(child); });
    return node;
  }

  function touch() { dirty = true; updateCount(); }

  function updateCount() {
    var answerable = questions.filter(function (q) { return q.kind !== "section"; }).length;
    var required = questions.filter(function (q) { return q.required && q.kind !== "section"; }).length;
    if (counter) counter.textContent = answerable + " ta savol · " + required + " tasi majburiy";
  }

  function tool(label, title, handler, disabled) {
    return el("button", { type: "button", className: "btn btn-ghost btn-sm btn-icon", title: title, "aria-label": title,
      text: label, disabled: !!disabled, on: { click: handler } });
  }

  function move(index, delta) {
    var target = index + delta;
    if (target < 0 || target >= questions.length) return;
    var item = questions.splice(index, 1)[0];
    questions.splice(target, 0, item);
    touch(); render(target);
  }

  function optionsEditor(q, index) {
    var list = el("div", { className: "sb-options" });
    q.options.forEach(function (option, i) {
      var input = el("input", { className: "input", value: option, maxLength: 200, placeholder: (i + 1) + "-variant",
        "aria-label": (i + 1) + "-variant",
        on: {
          input: function (e) { q.options[i] = e.target.value; touch(); },
          keydown: function (e) {
            if (e.key === "Enter") { e.preventDefault(); q.options.splice(i + 1, 0, ""); touch(); render(index, i + 1); }
          },
          paste: function (e) {
            var text = (e.clipboardData || window.clipboardData).getData("text");
            var lines = text.split(/\r?\n/).map(function (s) { return s.trim(); }).filter(Boolean);
            if (lines.length < 2) return;
            e.preventDefault();
            q.options.splice.apply(q.options, [i, 1].concat(lines));
            touch(); render(index);
          }
        } });
      list.appendChild(el("div", { className: "sb-option" }, [
        el("span", { className: "sb-mark", text: MARK[q.kind] || (i + 1) + "." }),
        input,
        tool("✕", "Variantni o'chirish", function () { q.options.splice(i, 1); touch(); render(index); }, q.options.length < 2)
      ]));
    });
    var add = el("button", { type: "button", className: "btn btn-ghost btn-sm", text: "+ Variant qo'shish",
      on: { click: function () { q.options.push(""); touch(); render(index, q.options.length - 1); } } });
    var extras = [add];
    if (q.kind !== "dropdown") {
      var other = el("input", { type: "checkbox", checked: q.allow_other,
        on: { change: function (e) { q.allow_other = e.target.checked; touch(); } } });
      extras.push(el("label", { className: "check small" }, [other, document.createTextNode(" «Boshqa» varianti (o'zi yozadi)")]));
    }
    return el("div", { className: "stack-sm" }, [list, el("div", { className: "row-sm wrap" }, extras),
      el("p", { className: "tiny muted", text: "Maslahat: bir nechta qatorli matnni nusxalab qo'ysangiz, har bir qator alohida variant bo'ladi." })]);
  }

  function scaleEditor(q) {
    var select = el("select", { className: "input", "aria-label": "Shkala chegarasi",
      on: { change: function (e) { q.scale_max = parseInt(e.target.value, 10); touch(); render(); } } });
    for (var n = 2; n <= 10; n++) select.appendChild(el("option", { value: n, text: "1 dan " + n + " gacha", selected: q.scale_max === n }));
    var preview = el("div", { className: "sb-scale-preview" });
    for (var i = 1; i <= q.scale_max; i++) preview.appendChild(el("span", { text: String(i) }));
    return el("div", { className: "stack-sm" }, [
      el("div", { className: "sb-scale" }, [
        select,
        el("input", { className: "input", value: q.scale_min_label, maxLength: 40, placeholder: "1 — izoh (masalan, Yomon)",
          on: { input: function (e) { q.scale_min_label = e.target.value; touch(); } } }),
        el("input", { className: "input", value: q.scale_max_label, maxLength: 40, placeholder: q.scale_max + " — izoh (masalan, A'lo)",
          on: { input: function (e) { q.scale_max_label = e.target.value; touch(); } } })
      ]),
      preview
    ]);
  }

  var FILE_TYPES = [
    ["pdf", "📕 PDF"], ["image", "🖼 Rasm (JPG, PNG, HEIC)"], ["word", "📘 Word"], ["excel", "📗 Excel"],
    ["slides", "📙 PowerPoint"]
  ];

  function fileEditor(q) {
    q.file_types = q.file_types || [];
    var types = el("div", { className: "sb-file-types" }, FILE_TYPES.map(function (t) {
      var box = el("input", { type: "checkbox", checked: q.file_types.indexOf(t[0]) !== -1,
        on: { change: function (e) {
          q.file_types = FILE_TYPES.map(function (x) { return x[0]; }).filter(function (key) {
            return key === t[0] ? e.target.checked : q.file_types.indexOf(key) !== -1;
          });
          touch(); render();
        } } });
      return el("label", { className: "chip chip-outline sb-file-type" + (box.checked ? " is-on" : "") }, [box, document.createTextNode(" " + t[1])]);
    }));
    var count = el("select", { className: "input", "aria-label": "Fayllar soni",
      on: { change: function (e) { q.max_files = parseInt(e.target.value, 10); touch(); render(); } } });
    for (var n = 1; n <= 10; n++) count.appendChild(el("option", { value: n, text: n === 1 ? "1 ta fayl" : "Ko'pi bilan " + n + " ta fayl", selected: q.max_files === n }));
    var size = el("select", { className: "input", "aria-label": "Bitta fayl hajmi",
      on: { change: function (e) { q.max_file_mb = parseInt(e.target.value, 10); touch(); render(); } } });
    [2, 5, 10, 15, 20].forEach(function (mb) { size.appendChild(el("option", { value: mb, text: "Har biri " + mb + " MB gacha", selected: q.max_file_mb === mb })); });
    var allowed = q.file_types.length ? FILE_TYPES.filter(function (t) { return q.file_types.indexOf(t[0]) !== -1; }).map(function (t) { return t[1].split(" ").slice(1).join(" "); }).join(", ") : "istalgan hujjat yoki rasm";
    return el("div", { className: "stack-sm sb-file" }, [
      el("span", { className: "small bold", text: "Qaysi fayllar qabul qilinadi?" }),
      types,
      el("div", { className: "sb-scale" }, [count, size]),
      hint("Talaba: " + allowed + ". Hech biri belgilanmasa, PDF, rasm, Word, Excel va PowerPoint qabul qilinadi. Fayl turi ichidan tekshiriladi; fayllarni faqat rahbariyat ko'radi.")
    ]);
  }

  function hint(text) { return el("p", { className: "sb-hint small", text: text }); }

  function card(q, index) {
    var kindSelect = el("select", { className: "input sb-kind", "aria-label": "Savol turi",
      on: { change: function (e) {
        var kind = e.target.value;
        if (CHOICE[kind] && !q.options.length) q.options = ["1-variant"];
        if (kind === "section") q.required = false;
        if (kind === "file" && !q.max_files) { q.file_types = q.file_types || []; q.max_files = 1; q.max_file_mb = 10; }
        q.kind = kind; touch(); render(index);
      } } });
    kinds.forEach(function (k) { kindSelect.appendChild(el("option", { value: k.value, text: k.label, selected: k.value === q.kind })); });

    var isSection = q.kind === "section";
    var body = [
      el("div", { className: "sb-q-head" }, [
        el("span", { className: "sb-no", text: isSection ? "§" : String(questions.slice(0, index + 1).filter(function (x) { return x.kind !== "section"; }).length) }),
        kindSelect,
        el("div", { className: "sb-tools" }, [
          tool("↑", "Yuqoriga", function () { move(index, -1); }, index === 0),
          tool("↓", "Pastga", function () { move(index, 1); }, index === questions.length - 1),
          tool("⧉", "Nusxa olish", function () {
            var copy = JSON.parse(JSON.stringify(q)); delete copy.id;
            questions.splice(index + 1, 0, copy); touch(); render(index + 1);
          }),
          tool("🗑", "O'chirish", function () {
            if (q.id && !confirm("Savol o'chirilsinmi? Unga berilgan javoblar natijalarda ko'rinmay qoladi.")) return;
            questions.splice(index, 1); touch(); render(Math.min(index, questions.length - 1));
          })
        ])
      ]),
      el("input", { className: "input sb-title", value: q.title, maxLength: 300, required: true,
        placeholder: isSection ? "Bo'lim nomi" : "Savol matni", "aria-label": "Savol matni",
        on: { input: function (e) { q.title = e.target.value; touch(); } } }),
      el("input", { className: "input sb-help", value: q.help_text, maxLength: 300,
        placeholder: isSection ? "Bo'lim haqida izoh (ixtiyoriy)" : "Izoh yoki ko'rsatma (ixtiyoriy)",
        on: { input: function (e) { q.help_text = e.target.value; touch(); } } })
    ];

    if (CHOICE[q.kind]) body.push(optionsEditor(q, index));
    if (q.kind === "scale") body.push(scaleEditor(q));
    if (q.kind === "file") body.push(fileEditor(q));
    if (q.kind === "track") body.push(hint("Variantlar avtomatik: " + TRACKS.join(", ") + ". Javob talabani iqtidorlar reyestriga qo'shishda yo'nalish sifatida olinadi."));
    if (q.kind === "short") body.push(hint("Talaba bir qatorli javob yozadi."));
    if (q.kind === "long") body.push(hint("Talaba bir necha jumladan iborat javob yozadi."));
    if (q.kind === "number") body.push(hint("Faqat raqam qabul qilinadi; natijalarda o'rtacha, eng kichik va eng katta qiymat ko'rsatiladi."));
    if (q.kind === "email" || q.kind === "phone" || q.kind === "date") body.push(hint("Javob formati avtomatik tekshiriladi."));

    if (!isSection) {
      var req = el("input", { type: "checkbox", checked: q.required,
        on: { change: function (e) { q.required = e.target.checked; touch(); render(index); } } });
      body.push(el("div", { className: "sb-q-foot" }, [
        el("label", { className: "check small" }, [req, document.createTextNode(" Majburiy savol")])
      ]));
    }
    return el("div", { className: "card sb-q" + (isSection ? " sb-section" : "") + (q.required ? " is-required" : "") }, body);
  }

  function render(focusIndex, optionIndex) {
    root.textContent = "";
    if (!questions.length) {
      root.appendChild(el("div", { className: "card empty" }, [
        el("div", { className: "empty-icon", text: "📝" }),
        el("h3", { text: "Savollar yo'q" }),
        el("p", { text: "Pastdagi tugma bilan birinchi savolni qo'shing." })
      ]));
    }
    questions.forEach(function (q, index) { root.appendChild(card(q, index)); });
    updateCount();
    if (typeof focusIndex === "number" && root.children[focusIndex]) {
      var target = root.children[focusIndex];
      var input = typeof optionIndex === "number"
        ? target.querySelectorAll(".sb-option input")[optionIndex]
        : target.querySelector(".sb-title");
      if (input) { input.focus(); if (input.select && typeof optionIndex !== "number" && !input.value) input.select(); }
    }
  }

  document.querySelectorAll("[data-add]").forEach(function (button) {
    button.addEventListener("click", function () {
      questions.push(blank(button.dataset.add)); touch(); render(questions.length - 1);
      root.lastElementChild.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  });

  form.addEventListener("submit", function (e) {
    var empty = questions.findIndex(function (q) { return !q.title.trim(); });
    if (empty >= 0) {
      e.preventDefault();
      render(empty);
      root.children[empty].scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    questions.forEach(function (q) { q.options = (q.options || []).map(function (o) { return o.trim(); }).filter(Boolean); });
    hidden.value = JSON.stringify(questions);
    dirty = false;
  });

  form.addEventListener("input", function () { dirty = true; });

  window.addEventListener("beforeunload", function (e) {
    if (dirty) { e.preventDefault(); e.returnValue = ""; }
  });

  render();
})();

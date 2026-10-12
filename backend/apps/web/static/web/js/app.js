/* ANDTI Talent Hub: kichik progressiv yaxshilanishlar. JS o'chiq bo'lsa ham barcha formalar ishlaydi. */
(function () {
  "use strict";

  function csrfToken() {
    var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    if (match) return decodeURIComponent(match[1]);
    var input = document.querySelector("input[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  /* ---------- Yorug' / qorong'i rejim ---------- */
  function storedTheme() {
    try {
      var value = localStorage.getItem("theme");
      return value === "dark" || value === "light" ? value : null;
    } catch (e) {
      return null;
    }
  }

  function currentTheme() {
    var attr = document.documentElement.getAttribute("data-theme");
    if (attr === "dark" || attr === "light") return attr;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
    button.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try {
        localStorage.setItem("theme", next);
      } catch (e) {
        /* Shaxsiy rejimda saqlab bo'lmasa ham almashtirish ishlayveradi */
      }
      var meta = document.querySelector('meta[name="theme-color"]');
      if (meta) meta.setAttribute("content", next === "dark" ? "#0f1f25" : "#062d3b");
    });
  });

  /* ---------- Toast xabarlar ---------- */
  document.querySelectorAll(".toast").forEach(function (toast) {
    var close = toast.querySelector("button");
    if (close) close.addEventListener("click", function () { toast.remove(); });
    setTimeout(function () {
      toast.style.transition = "opacity .3s ease";
      toast.style.opacity = "0";
      setTimeout(function () { toast.remove(); }, 300);
    }, 5000);
  });

  /* ---------- Telegram Mini App ---------- */
  var tg = window.Telegram && window.Telegram.WebApp;
  if (tg && tg.initData) {
    tg.ready();
    tg.expand();
    if (!storedTheme()) {
      document.documentElement.setAttribute("data-theme", tg.colorScheme === "dark" ? "dark" : "light");
    }
    var body = document.body;
    if (body.dataset.authenticated !== "1" && body.dataset.telegramLogin) {
      fetch(body.dataset.telegramLogin, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded", "X-CSRFToken": csrfToken() },
        body: "init_data=" + encodeURIComponent(tg.initData),
        credentials: "same-origin",
      }).then(function (response) {
        if (response.ok) window.location.href = body.dataset.next || "/app/";
      });
    }
  }

  /* ---------- Layk (sahifani yangilamasdan) ---------- */
  document.querySelectorAll("form[data-like]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var button = form.querySelector("button");
      fetch(form.action, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken(), "X-Requested-With": "fetch" },
        credentials: "same-origin",
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          button.classList.toggle("liked", data.liked);
          button.querySelector("[data-count]").textContent = data.like_count;
        });
    });
  });

  /* ---------- Textarea avtomatik balandlik ---------- */
  document.querySelectorAll("textarea[data-autosize]").forEach(function (area) {
    var resize = function () {
      area.style.height = "auto";
      area.style.height = Math.min(area.scrollHeight, 160) + "px";
    };
    area.addEventListener("input", resize);
    resize();
  });

  /* ---------- AI chat ---------- */
  var chatLog = document.querySelector("[data-chat-log]");
  if (chatLog) chatLog.scrollTop = chatLog.scrollHeight;
  var chatForm = document.querySelector("form[data-chat]");
  if (chatForm) {
    var area = chatForm.querySelector("textarea");
    area.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey && area.value.trim()) {
        event.preventDefault();
        chatForm.requestSubmit();
      }
    });
    chatForm.addEventListener("submit", function () {
      if (!area.value.trim()) return;
      var bubble = document.createElement("div");
      bubble.className = "bubble bubble-user";
      bubble.textContent = area.value;
      var typing = document.querySelector("[data-typing]");
      chatLog.insertBefore(bubble, typing);
      typing.classList.add("show");
      chatLog.scrollTop = chatLog.scrollHeight;
      chatForm.querySelector("button").disabled = true;
      area.readOnly = true;
    });
  }

  /* ---------- QR kod ---------- */
  document.querySelectorAll("[data-qr]").forEach(function (box) {
    if (window.QRCode) {
      new window.QRCode(box, { text: box.dataset.qr, width: 240, height: 240, correctLevel: window.QRCode.CorrectLevel.M });
    }
  });

  /* ---------- Havolani nusxalash ---------- */
  document.querySelectorAll("[data-copy]").forEach(function (button) {
    button.addEventListener("click", function () {
      navigator.clipboard.writeText(button.dataset.copy).then(function () {
        var label = button.querySelector("[data-label]");
        if (label) {
          var old = label.textContent;
          label.textContent = "Nusxa olindi!";
          setTimeout(function () { label.textContent = old; }, 1600);
        }
      });
    });
  });
})();

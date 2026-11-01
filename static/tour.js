/* First-visit onboarding tour. Self-contained: depends only on the TopBar markup in index.html. */
(function () {
  "use strict";

  var STORAGE_KEY = "pakal_tour_completed";
  var START_DELAY_MS = 1500;
  var PAD = 8;

  var TEXT = {
    he: {
      step: function (n, total) { return "צעד " + n + " מתוך " + total; },
      skip: "דילוג",
      next: "הבא",
      back: "הקודם",
      finish: "סיום",
      openDocker: "מעבר למאגר Docker",
      featured: "מומלץ",
      steps: [
        {
          title: "חיפוש מהיר במאגר",
          body: "חיפוש מרכזי לכל התוכנות, החבילות והכלים בפורטל. זמין מכל מקום בלחיצת Ctrl+K.",
        },
        {
          title: "מאגר Docker ארגוני (Internal Docker Hub)",
          body: "מאגר אימג'ים וקונטיינרים מלא הפועל כ-Docker Hub פנימי ברשת. משם ניתן למשוך ולנהל אימג'ים מורשים במהירות ובאופן מאובטח.",
        },
        {
          title: "התקנות ופעולות ב-1-Click",
          body: "הרצת סקריפטים, התקנת PowerShell 7 ו-NuGet בלחיצה אחת, ללא צורך בטרמינל או בהרשאות אדמין.",
        },
        {
          title: "מאגרים וערכות פיתוח",
          body: "גישה ישירה למאגרי PyPI, פלטפורמות עבודה וערכות כלי פיתוח מותאמות לפי תפקיד.",
        },
        {
          title: "פניות, דרישות ומשובים",
          body: "מקום מרכזי לשליחת בקשות להתקנת תוכנות חדשות, דיווח על תקלות ומשוב ישיר לצוות ה-DevOps.",
        },
      ],
    },
    en: {
      step: function (n, total) { return "Step " + n + " of " + total; },
      skip: "Skip",
      next: "Next",
      back: "Back",
      finish: "Finish",
      openDocker: "Open the Docker registry",
      featured: "Featured",
      steps: [
        {
          title: "Quick catalog search",
          body: "One search for every app, package and tool in the portal. Available anywhere with Ctrl+K.",
        },
        {
          title: "Internal Docker Hub",
          body: "A full image and container registry that works as an internal Docker Hub on the network. Pull and manage approved images quickly and securely.",
        },
        {
          title: "1-Click installs and actions",
          body: "Run scripts and install PowerShell 7 and NuGet in one click, with no terminal and no admin rights.",
        },
        {
          title: "Repositories and developer kits",
          body: "Direct access to PyPI, work platforms and role-based developer tool kits.",
        },
        {
          title: "Requests, demands and feedback",
          body: "One place to request new software installs, report issues and send feedback straight to the DevOps team.",
        },
      ],
    },
  };

  var STEPS = [
    { targets: [".header-actions .qs-btn"] },
    { targets: ['.nav [data-view="docker"]'], featured: true },
    { targets: ['.nav [data-view="actions"]'] },
    { targets: ['.nav [data-view="pypi"]', '.nav [data-view="platforms"]', '.nav [data-view="bundles"]'] },
    { targets: ['[data-action="feedback"]'] },
  ];

  var tour = null;

  function lang() {
    return document.documentElement.lang === "en" ? "en" : "he";
  }

  function visible(el) {
    if (!el || el.hidden) return false;
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function stepTargets(step) {
    var found = [];
    step.targets.forEach(function (sel) {
      var el = document.querySelector(sel);
      if (visible(el)) found.push(el);
    });
    return found;
  }

  function unionRect(els) {
    var rect = { top: Infinity, left: Infinity, right: -Infinity, bottom: -Infinity };
    els.forEach(function (el) {
      var r = el.getBoundingClientRect();
      rect.top = Math.min(rect.top, r.top);
      rect.left = Math.min(rect.left, r.left);
      rect.right = Math.max(rect.right, r.right);
      rect.bottom = Math.max(rect.bottom, r.bottom);
    });
    return rect;
  }

  function markCompleted() {
    try { localStorage.setItem(STORAGE_KEY, "true"); } catch (_) { /* storage blocked */ }
  }

  function isCompleted() {
    try { return localStorage.getItem(STORAGE_KEY) === "true"; } catch (_) { return true; }
  }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  function build() {
    var root = el("div", "tour");
    root.setAttribute("role", "dialog");
    root.setAttribute("aria-modal", "true");
    root.setAttribute("aria-labelledby", "tour-title");
    root.setAttribute("aria-describedby", "tour-body");

    var spot = el("div", "tour-spotlight");
    var card = el("div", "tour-card");
    card.tabIndex = -1;

    var head = el("div", "tour-card-head");
    var counter = el("span", "tour-step");
    var badge = el("span", "tour-badge");
    head.appendChild(counter);
    head.appendChild(badge);

    var title = el("h2", "tour-title");
    title.id = "tour-title";
    var body = el("p", "tour-body");
    body.id = "tour-body";

    var dots = el("div", "tour-dots");
    dots.setAttribute("aria-hidden", "true");

    var foot = el("div", "tour-foot");
    var skip = el("button", "btn btn-ghost btn-sm tour-skip");
    skip.type = "button";
    skip.dataset.tour = "skip";
    var nav = el("div", "tour-nav");
    var extra = el("button", "btn btn-secondary btn-sm tour-extra");
    extra.type = "button";
    extra.dataset.tour = "docker";
    var back = el("button", "btn btn-ghost btn-sm");
    back.type = "button";
    back.dataset.tour = "back";
    var next = el("button", "btn btn-primary btn-sm");
    next.type = "button";
    next.dataset.tour = "next";
    nav.appendChild(extra);
    nav.appendChild(back);
    nav.appendChild(next);
    foot.appendChild(skip);
    foot.appendChild(nav);

    card.appendChild(head);
    card.appendChild(title);
    card.appendChild(body);
    card.appendChild(dots);
    card.appendChild(foot);
    root.appendChild(spot);
    root.appendChild(card);

    root.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-tour]");
      if (!btn) return;
      var action = btn.dataset.tour;
      if (action === "skip") end();
      else if (action === "back") go(tour.index - 1);
      else if (action === "next") go(tour.index + 1);
      else if (action === "docker") {
        var target = document.querySelector('.nav [data-view="docker"]');
        end();
        if (target) target.click();
      }
    });

    return {
      root: root, spot: spot, card: card, counter: counter, badge: badge, title: title, body: body,
      dots: dots, skip: skip, extra: extra, back: back, next: next,
    };
  }

  function activeSteps() {
    return STEPS.map(function (step, i) { return { step: step, i: i, els: stepTargets(step) }; })
      .filter(function (s) { return s.els.length; });
  }

  function place() {
    if (!tour) return;
    var current = tour.steps[tour.index];
    var els = stepTargets(current.step);
    if (!els.length) return;
    var r = unionRect(els);
    var ui = tour.ui;
    var top = r.top - PAD, left = r.left - PAD;
    var width = r.right - r.left + PAD * 2, height = r.bottom - r.top + PAD * 2;
    ui.spot.style.transform = "translate(" + left + "px," + top + "px)";
    ui.spot.style.width = width + "px";
    ui.spot.style.height = height + "px";

    var card = ui.card;
    var cw = card.offsetWidth, ch = card.offsetHeight;
    var vw = window.innerWidth, vh = window.innerHeight;
    var gap = 16;
    var cardTop = r.bottom + PAD + gap;
    if (cardTop + ch > vh - 12) cardTop = Math.max(12, r.top - PAD - gap - ch);
    var center = (r.left + r.right) / 2;
    var cardLeft = Math.min(Math.max(12, center - cw / 2), vw - cw - 12);
    card.style.transform = "translate(" + Math.round(cardLeft) + "px," + Math.round(cardTop) + "px)";

    var arrow = Math.min(Math.max(24, center - cardLeft), cw - 24);
    card.style.setProperty("--tour-arrow-x", Math.round(arrow) + "px");
    card.classList.toggle("is-above", cardTop < r.top);
  }

  function render() {
    var ui = tour.ui;
    var t = TEXT[lang()];
    var current = tour.steps[tour.index];
    var copy = t.steps[current.i];
    var total = tour.steps.length;
    var last = tour.index === total - 1;

    ui.root.dir = lang() === "he" ? "rtl" : "ltr";
    ui.root.classList.toggle("is-featured", Boolean(current.step.featured));
    ui.counter.textContent = t.step(tour.index + 1, total);
    ui.badge.textContent = "⭐ " + t.featured;
    ui.badge.hidden = !current.step.featured;
    ui.title.textContent = copy.title;
    ui.body.textContent = copy.body;
    ui.skip.textContent = t.skip;
    ui.back.textContent = t.back;
    ui.back.hidden = tour.index === 0;
    ui.next.textContent = last ? t.finish : t.next;
    ui.extra.textContent = t.openDocker;
    ui.extra.hidden = !current.step.featured;

    ui.dots.textContent = "";
    for (var i = 0; i < total; i++) {
      ui.dots.appendChild(el("span", i === tour.index ? "is-current" : i < tour.index ? "is-done" : ""));
    }

    var targets = stepTargets(current.step);
    if (targets.length) targets[0].scrollIntoView({ block: "nearest", inline: "nearest" });
    if (targets.length > 1) targets[targets.length - 1].scrollIntoView({ block: "nearest", inline: "nearest" });

    ui.card.classList.remove("is-in");
    void ui.card.offsetWidth;
    place();
    ui.card.classList.add("is-in");
    ui.next.focus({ preventScroll: true });
  }

  function go(index) {
    if (!tour || index < 0) return;
    if (index >= tour.steps.length) { end(); return; }
    tour.index = index;
    render();
  }

  function onKey(e) {
    if (!tour) return;
    var forward = lang() === "he" ? "ArrowLeft" : "ArrowRight";
    var backward = lang() === "he" ? "ArrowRight" : "ArrowLeft";
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); end(); }
    else if (e.key === forward) { e.preventDefault(); go(tour.index + 1); }
    else if (e.key === backward) { e.preventDefault(); go(tour.index - 1); }
    else if (e.key === "Tab") {
      var focusables = tour.ui.card.querySelectorAll("button:not([hidden])");
      if (!focusables.length) return;
      var first = focusables[0], lastBtn = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); lastBtn.focus(); }
      else if (!e.shiftKey && document.activeElement === lastBtn) { e.preventDefault(); first.focus(); }
    }
  }

  function onResize() {
    if (tour) place();
  }

  function start() {
    if (tour) return;
    var steps = activeSteps();
    if (!steps.length) return;
    window.scrollTo({ top: 0, behavior: "smooth" });
    var ui = build();
    tour = { ui: ui, steps: steps, index: 0, opener: document.activeElement };
    document.body.appendChild(ui.root);
    document.addEventListener("keydown", onKey, true);
    window.addEventListener("resize", onResize);
    window.addEventListener("scroll", onResize, { capture: true, passive: true });
    render();
    requestAnimationFrame(function () { ui.root.classList.add("is-open"); });
  }

  function end() {
    if (!tour) return;
    markCompleted();
    var current = tour;
    tour = null;
    document.removeEventListener("keydown", onKey, true);
    window.removeEventListener("resize", onResize);
    window.removeEventListener("scroll", onResize, { capture: true });
    current.ui.root.classList.remove("is-open");
    current.ui.root.classList.add("is-leaving");
    window.setTimeout(function () { current.ui.root.remove(); }, 260);
    if (current.opener && typeof current.opener.focus === "function" && current.opener.isConnected) {
      current.opener.focus({ preventScroll: true });
    }
  }

  function whenSplashGone(callback) {
    var check = function () {
      var splash = document.getElementById("app-splash-screen");
      if (!splash || !splash.isConnected) { callback(); return; }
      window.setTimeout(check, 100);
    };
    check();
  }

  function autoStart() {
    if (isCompleted() || window.PAKAL_TOUR_DISABLED) return;
    whenSplashGone(function () {
      window.setTimeout(function () {
        if (isCompleted() || window.PAKAL_TOUR_DISABLED
            || document.querySelector("#modal:not([hidden]), #quick-search:not([hidden])")) return;
        start();
      }, START_DELAY_MS);
    });
  }

  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-tour-start]")) start();
  });

  window.PAKAL_TOUR = { start: start, end: end };

  if (document.readyState === "complete") autoStart();
  else window.addEventListener("load", autoStart, { once: true });
})();

/* app.js dismisses the splash after /api/auth/me and a 1000ms minimum. This is only a fallback. */
(function () {
  function dismissSplash() {
    var splash = document.getElementById("app-splash-screen");
    if (!splash || splash.classList.contains("is-leaving")) return;
    splash.classList.add("is-leaving");
    splash.setAttribute("aria-busy", "false");
    var remove = function () {
      if (splash.isConnected) splash.remove();
    };
    splash.addEventListener("transitionend", function (event) {
      if (event.target === splash && event.propertyName === "opacity") remove();
    });
    window.setTimeout(remove, 500);
  }

  window.PAKAL_DISMISS_SPLASH = dismissSplash;
  window.setTimeout(dismissSplash, 12000);
})();

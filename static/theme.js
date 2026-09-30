// Loaded synchronously in <head> so the saved theme applies before first paint.
(() => {
  let theme = "light";
  try {
    if (localStorage.getItem("pakal.theme") === "dark") theme = "dark";
  } catch (_) { /* storage disabled */ }
  document.documentElement.dataset.theme = theme;
})();

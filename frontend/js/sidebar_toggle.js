(function () {
  const KEY = "vigila_sidebar_collapsed";

  function init() {
    const body = document.body;
    if (!body) return;

    // Apply saved preference
    const saved = localStorage.getItem(KEY);
    if (saved === "1") body.classList.add("sidebar-collapsed");

    // Bind toggle
    const btn = document.getElementById("v2-sidebar-toggle");
    if (!btn) return;

    btn.addEventListener("click", () => {
      body.classList.toggle("sidebar-collapsed");
      localStorage.setItem(KEY, body.classList.contains("sidebar-collapsed") ? "1" : "0");
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
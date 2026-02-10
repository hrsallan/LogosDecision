/**
 * Lógica de Alternância da Barra Lateral (Sidebar Toggle)
 *
 * Gerencia o estado (expandido/colapsado) do menu lateral.
 * Persiste a preferência do usuário no localStorage para manter
 * o estado entre recarregamentos de página.
 */
(function () {
  const KEY = "vigila_sidebar_collapsed";

  function init() {
    const body = document.body;
    if (!body) return;

    // Restaurar estado salvo
    const saved = localStorage.getItem(KEY);
    if (saved === "1") {
        body.classList.add("sidebar-collapsed");
    }

    const btn = document.getElementById("v2-sidebar-toggle");
    if (!btn) return;

    // Adicionar listener de clique
    btn.addEventListener("click", () => {
      body.classList.toggle("sidebar-collapsed");
      // Salvar novo estado (1 = colapsado, 0 = expandido)
      localStorage.setItem(KEY, body.classList.contains("sidebar-collapsed") ? "1" : "0");
    });
  }

  // Inicializar quando o DOM estiver pronto
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

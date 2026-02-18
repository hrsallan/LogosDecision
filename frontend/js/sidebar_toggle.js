/**
 * Lógica de Alternância da Barra Lateral (Sidebar Toggle)
 *
 * Gerencia o comportamento responsivo e o estado (expandido/colapsado) do menu lateral.
 * Utiliza o localStorage para persistir a preferência do usuário, mantendo a interface
 * consistente entre navegações e recarregamentos de página.
 */
(function () {
  // Chave utilizada no localStorage para salvar o estado
  const KEY = "vigila_sidebar_collapsed";

  /**
   * Inicializa o comportamento da sidebar.
   * Verifica o estado salvo e configura o ouvinte de eventos no botão de alternância.
   */
  function init() {
    const body = document.body;
    if (!body) return;

    // 1. Restaurar estado salvo anteriormente
    const saved = localStorage.getItem(KEY);
    if (saved === "1") {
        // Adiciona a classe que aplica o estilo "colapsado" (ícones apenas)
        body.classList.add("sidebar-collapsed");
    }

    // 2. Configurar o botão de toggle
    const btn = document.getElementById("v2-sidebar-toggle");
    if (!btn) return;

    btn.addEventListener("click", () => {
      // Alterna a classe no body
      body.classList.toggle("sidebar-collapsed");

      // Salva o novo estado (1 = colapsado, 0 = expandido)
      const isCollapsed = body.classList.contains("sidebar-collapsed");
      localStorage.setItem(KEY, isCollapsed ? "1" : "0");
    });
  }

  // Garante que o script rode apenas após o DOM estar carregado
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

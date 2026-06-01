function qs(selector, root = document) {
  return root.querySelector(selector);
}

function qsa(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

function normalize(value) {
  return (value || "").toString().toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

document.addEventListener("DOMContentLoaded", () => {
  const shell = qs("[data-app-shell]");
  const sidebarToggle = qs("[data-sidebar-toggle]");
  const mobileToggle = qs("[data-mobile-menu-toggle]");
  const userMenu = qs("[data-user-menu]");
  const userMenuButton = qs("[data-user-menu-button]");

  if (shell && sidebarToggle) {
    sidebarToggle.addEventListener("click", () => {
      shell.classList.toggle("sidebar-collapsed");
      localStorage.setItem("ecnp-sidebar-collapsed", shell.classList.contains("sidebar-collapsed") ? "1" : "0");
    });
    if (localStorage.getItem("ecnp-sidebar-collapsed") === "1") {
      shell.classList.add("sidebar-collapsed");
    }
  }

  if (shell && mobileToggle) {
    mobileToggle.addEventListener("click", () => shell.classList.toggle("mobile-nav-open"));
  }

  if (userMenu && userMenuButton) {
    userMenuButton.addEventListener("click", (event) => {
      event.stopPropagation();
      userMenu.classList.toggle("is-open");
    });
    document.addEventListener("click", (event) => {
      if (!userMenu.contains(event.target)) userMenu.classList.remove("is-open");
    });
  }

  qsa("[data-confirm]").forEach((element) => {
    element.addEventListener("submit", (event) => {
      const message = element.getAttribute("data-confirm") || "Confirme esta acción.";
      if (!window.confirm(message)) event.preventDefault();
    });
  });

  qsa("[data-table-search]").forEach((input) => {
    const tableId = input.getAttribute("data-table-search");
    const table = qs(`[data-table-id="${tableId}"]`);
    if (!table) return;
    input.addEventListener("input", () => {
      const needle = normalize(input.value);
      qsa("tbody tr", table).forEach((row) => {
        row.hidden = needle && !normalize(row.innerText).includes(needle);
      });
    });
  });

  qsa("[data-table-filter]").forEach((select) => {
    const tableId = select.getAttribute("data-table-filter");
    const attr = select.getAttribute("data-filter-attr") || "estado";
    const table = qs(`[data-table-id="${tableId}"]`);
    if (!table) return;
    select.addEventListener("change", () => {
      const value = select.value;
      qsa("tbody tr", table).forEach((row) => {
        row.hidden = value && row.dataset[attr] !== value;
      });
    });
  });
});

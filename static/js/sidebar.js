"use strict";

// Config
const STORAGE_KEY = "sidebar_collapsed";
const BREAKPOINT_MD = 1100;

// State
function isDesktop() {
  return window.innerWidth >= BREAKPOINT_MD;
}

function initToggleTooltip(toggleBtn) {
  if (!toggleBtn || typeof bootstrap === "undefined") return null;

  return new bootstrap.Tooltip(toggleBtn, {
    trigger: "hover",
    placement: "right",
    delay: { show: 500, hide: 80 },
  });
}

function updateToggleTooltipText(toggleBtn, collapsed) {
  if (!toggleBtn) return;

  toggleBtn.setAttribute(
    "data-bs-original-title",
    collapsed ? "Abrir menu lateral" : "Fechar menu lateral"
  );
}

// Desktop sidebar
function initDesktopSidebar(sidebar, toggleBtn) {
  if (!sidebar) return;

  const tooltip = initToggleTooltip(toggleBtn);

  function applyCollapsed(collapsed, animate = true) {
    if (!animate) {
      sidebar.style.transition = "none";
      void sidebar.offsetHeight;
      requestAnimationFrame(() => {
        sidebar.style.transition = "";
      });
    }

    sidebar.classList.toggle("collapsed", collapsed);

    const icon = toggleBtn?.querySelector(".material-symbols-outlined");

    if (icon) {
      icon.textContent = collapsed
        ? "left_panel_open"
        : "left_panel_close";
    }

    toggleBtn?.setAttribute(
      "aria-label",
      collapsed ? "Expandir menu" : "Recolher menu"
    );

    updateToggleTooltipText(toggleBtn, collapsed);
  }

  if (isDesktop()) {
    const saved = localStorage.getItem(STORAGE_KEY) === "true";
    applyCollapsed(saved, false);
  }

  toggleBtn?.addEventListener("click", () => {
    if (!isDesktop()) return;

    const next = !sidebar.classList.contains("collapsed");
    localStorage.setItem(STORAGE_KEY, next);
    applyCollapsed(next, true);
  });

  return { applyCollapsed };
}

// Mobile sidebar
function initMobileSidebar(sidebar, backdrop, hamburger, desktopAPI) {
  if (!sidebar) return;

  function open() {
    sidebar.classList.add("mobile-open");
    backdrop?.classList.add("show");
    document.body.style.overflow = "hidden";
  }

  function close() {
    sidebar.classList.remove("mobile-open");
    backdrop?.classList.remove("show");
    document.body.style.overflow = "";
  }

  hamburger?.addEventListener("click", () => {
    sidebar.classList.contains("mobile-open") ? close() : open();
  });

  backdrop?.addEventListener("click", close);

  sidebar.querySelectorAll(".sidebar-link").forEach((link) => {
    link.addEventListener("click", () => {
      if (!isDesktop()) close();
    });
  });

  window.addEventListener("resize", () => {
    if (isDesktop()) {
      close();

      const saved = localStorage.getItem(STORAGE_KEY) === "true";
      desktopAPI?.applyCollapsed(saved, false);
    }
  });
}

function initApp() {
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("sidebarBackdrop");
  const toggleBtn = document.getElementById("toggleSidebar");
  const hamburger = document.getElementById("headerHamburger");

  const desktopAPI = initDesktopSidebar(sidebar, toggleBtn);
  initMobileSidebar(sidebar, backdrop, hamburger, desktopAPI);
}

initApp();
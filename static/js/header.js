"use strict";

// Menu do usuário
function initUserMenu() {
  const menu = document.getElementById("headerUserMenu");
  const btn = document.getElementById("headerUserButton");

  if (!menu || !btn) return;

  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    menu.classList.toggle("open");
  });

  document.addEventListener("click", (e) => {
    if (!menu.contains(e.target)) {
      menu.classList.remove("open");
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      menu.classList.remove("open");
    }
  });
}

function initTooltips() {
  const ids = [
    "headerHamburger",
    "headerSearchBtn",
    "headerSearchBack",
    "toggleTheme",
    "headerUserButton",
  ];

  ids.forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;

    bootstrap.Tooltip.getOrCreateInstance(el, {
      trigger: "hover",
      delay: {
        show: 500,
        hide: 80,
      },
    });
  });

  const userBtn = document.getElementById("headerUserButton");

  userBtn?.addEventListener("click", () => {
    bootstrap.Tooltip.getInstance(userBtn)?.hide();
  });
}

function initApp() {
  initUserMenu();
  initTooltips();
}

initApp();
(function () {
  var STORAGE_KEY = "planner-theme";
  var root = document.documentElement;

  function normalizeTheme(theme) {
    return theme === "dark" ? "dark" : "light";
  }

  function getStoredTheme() {
    try {
      return normalizeTheme(localStorage.getItem(STORAGE_KEY));
    } catch (error) {
      return "light";
    }
  }

  function storeTheme(theme) {
    try {
      localStorage.setItem(STORAGE_KEY, normalizeTheme(theme));
    } catch (error) {
    }
  }

  function syncToggle(toggle, theme) {
    var nextTheme = theme === "dark" ? "light" : "dark";
    var label = toggle.querySelector("[data-theme-toggle-label]");
    var meta = toggle.querySelector("[data-theme-toggle-meta]");

    toggle.setAttribute("aria-pressed", String(theme === "dark"));
    toggle.setAttribute("aria-label", "Activate " + nextTheme + " mode");

    if (label) {
      label.textContent = theme === "dark" ? "Dark mode" : "Light mode";
    }

    if (meta) {
      meta.textContent = "Switch to " + nextTheme + " mode";
    }
  }

  function syncAllToggles(theme) {
    document.querySelectorAll("[data-theme-toggle]").forEach(function (toggle) {
      syncToggle(toggle, theme);
    });
  }

  function applyTheme(theme) {
    var normalizedTheme = normalizeTheme(theme);
    root.dataset.theme = normalizedTheme;
    root.style.colorScheme = normalizedTheme;
    syncAllToggles(normalizedTheme);
  }

  function toggleTheme() {
    var nextTheme = root.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(nextTheme);
    storeTheme(nextTheme);
  }

  document.addEventListener("click", function (event) {
    var toggle = event.target.closest("[data-theme-toggle]");
    if (!toggle) {
      return;
    }

    event.preventDefault();
    toggleTheme();
  });

  window.addEventListener("storage", function (event) {
    if (event.key !== STORAGE_KEY) {
      return;
    }
    applyTheme(event.newValue);
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      applyTheme(getStoredTheme());
    });
  } else {
    applyTheme(getStoredTheme());
  }
})();

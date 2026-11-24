/*
 * app.js: behaviour shared by every page (vanilla ES6, no framework).
 *  - mobile navigation drawer
 *  - dismissible flash messages
 *  - confirmation prompts for destructive buttons (data-confirm)
 *  - light client-side validation (the server always re-validates)
 */
(function () {
  "use strict";

  /* ---------- Mobile navigation ---------- */
  const sidebar = document.getElementById("sidebar");
  const toggle = document.querySelector("[data-nav-toggle]");
  const scrim = document.querySelector(".scrim");

  function openNav() {
    if (!sidebar) return;
    sidebar.classList.add("is-open");
    if (scrim) scrim.hidden = false;
    if (toggle) toggle.setAttribute("aria-expanded", "true");
    const firstLink = sidebar.querySelector(".nav__link");
    if (firstLink) firstLink.focus();
  }

  function closeNav() {
    if (!sidebar) return;
    sidebar.classList.remove("is-open");
    if (scrim) scrim.hidden = true;
    if (toggle) {
      toggle.setAttribute("aria-expanded", "false");
    }
  }

  if (toggle) toggle.addEventListener("click", openNav);
  document.querySelectorAll("[data-nav-close]").forEach(function (el) {
    el.addEventListener("click", closeNav);
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && sidebar && sidebar.classList.contains("is-open")) {
      closeNav();
      if (toggle) toggle.focus();
    }
  });

  /* ---------- Flash messages ---------- */
  document.querySelectorAll("[data-dismiss]").forEach(function (button) {
    button.addEventListener("click", function () {
      const box = button.closest("[data-dismissible]");
      if (box) box.remove();
    });
  });

  // Auto-hide success messages after a few seconds.
  document.querySelectorAll(".alert--success[data-dismissible]").forEach(function (box) {
    window.setTimeout(function () {
      box.remove();
    }, 6000);
  });

  /* ---------- Confirm destructive actions ---------- */
  document.addEventListener("click", function (event) {
    const trigger = event.target.closest("[data-confirm]");
    if (!trigger) return;
    const message = trigger.getAttribute("data-confirm") || "Are you sure?";
    if (!window.confirm(message)) {
      event.preventDefault();
      event.stopPropagation();
    }
  });

  /* ---------- Client-side validation ---------- */
  function showError(input, message) {
    const field = input.closest(".field");
    if (!field) return;
    field.classList.add("field--error");
    let error = field.querySelector(".field__error[data-client]");
    if (!error) {
      error = document.createElement("p");
      error.className = "field__error";
      error.setAttribute("data-client", "");
      error.setAttribute("role", "alert");
      field.appendChild(error);
    }
    error.textContent = message;
  }

  function clearError(input) {
    const field = input.closest(".field");
    if (!field) return;
    const error = field.querySelector(".field__error[data-client]");
    if (error) error.remove();
    if (!field.querySelector(".field__error")) field.classList.remove("field--error");
  }

  document.querySelectorAll("form[data-validate]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      let firstInvalid = null;
      form.querySelectorAll("input, select, textarea").forEach(function (input) {
        clearError(input);
        if (input.type === "hidden" || input.disabled) return;
        if (input.required && !String(input.value).trim() && input.type !== "checkbox") {
          showError(input, "This field is required.");
          firstInvalid = firstInvalid || input;
        } else if (input.required && input.type === "checkbox" && !input.checked) {
          showError(input, "Please tick this box to continue.");
          firstInvalid = firstInvalid || input;
        } else if (input.type === "number" && input.value !== "") {
          const value = Number(input.value);
          const min = input.min !== "" ? Number(input.min) : null;
          if (Number.isNaN(value)) {
            showError(input, "Enter a valid number.");
            firstInvalid = firstInvalid || input;
          } else if (min !== null && value < min) {
            showError(input, "Enter a value of at least " + min + ".");
            firstInvalid = firstInvalid || input;
          }
        }
      });
      if (firstInvalid) {
        event.preventDefault();
        firstInvalid.focus();
      }
    });
  });
})();

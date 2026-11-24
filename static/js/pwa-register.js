/*
 * pwa-register.js: registers the service worker and wires up the optional
 * "Install app" buttons (vanilla ES6).
 */
(function () {
  "use strict";

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/service-worker.js", { scope: "/" }).catch(function (error) {
        console.error("Service worker registration failed:", error);
      });
    });
  }

  let deferredPrompt = null;
  const buttons = document.querySelectorAll("[data-install-button]");
  const unavailable = document.querySelectorAll("[data-install-unavailable]");

  // Chrome / Edge / Android fire this when the app can be installed.
  window.addEventListener("beforeinstallprompt", function (event) {
    event.preventDefault();
    deferredPrompt = event;
    buttons.forEach(function (b) { b.hidden = false; });
    unavailable.forEach(function (n) { n.hidden = true; });
  });

  buttons.forEach(function (button) {
    button.addEventListener("click", async function () {
      if (!deferredPrompt) {
        window.location.href = "/install/";
        return;
      }
      deferredPrompt.prompt();
      await deferredPrompt.userChoice;
      deferredPrompt = null;
      buttons.forEach(function (b) { b.hidden = true; });
    });
  });

  window.addEventListener("appinstalled", function () {
    buttons.forEach(function (b) { b.hidden = true; });
  });
})();

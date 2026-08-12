(() => {
  const script = document.currentScript;
  const base = script?.dataset.base || "";

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", async () => {
      try {
        const registration = await navigator.serviceWorker.register(`${base}service-worker.js`);
        registration.update();
      } catch (error) {
        console.warn("PWA service worker registration failed", error);
      }
    });
  }

  const standalone = window.matchMedia("(display-mode: standalone)").matches
    || window.navigator.standalone === true;
  const installButton = document.querySelector("[data-install-app]");
  const installedMessage = document.querySelector("[data-installed-message]");
  let installPrompt = null;

  if (standalone) {
    if (installButton) installButton.hidden = true;
    if (installedMessage) installedMessage.hidden = false;
    document.documentElement.dataset.displayMode = "standalone";
  }

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPrompt = event;
    if (installButton && !standalone) {
      installButton.hidden = false;
      installButton.disabled = false;
    }
  });

  installButton?.addEventListener("click", async () => {
    if (!installPrompt) return;
    installButton.disabled = true;
    await installPrompt.prompt();
    await installPrompt.userChoice;
    installPrompt = null;
  });

  window.addEventListener("appinstalled", () => {
    if (installButton) installButton.hidden = true;
    if (installedMessage) installedMessage.hidden = false;
  });
})();

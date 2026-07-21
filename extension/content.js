// Content script : affiche les sous-titres traduits, y compris en plein écran.
(() => {
  if (window.__lvtInjected) return;
  window.__lvtInjected = true;

  let container = null;
  let lineEl = null;
  let hideTimer = null;

  function ensureContainer() {
    if (!container) {
      container = document.createElement('div');
      container.id = 'lvt-subtitles';
      lineEl = document.createElement('div');
      lineEl.id = 'lvt-line';
      container.appendChild(lineEl);
      container.style.display = 'none';
    }
    // En plein écran, seul l'élément fullscreen (et ses descendants) est rendu :
    // on greffe donc l'overlay À L'INTÉRIEUR de cet élément.
    let root = document.fullscreenElement || document.body;
    if (root.tagName === 'VIDEO') {
      // Impossible d'insérer un overlay DANS un <video>. Cas rare : la plupart
      // des players passent un conteneur en fullscreen, pas la balise video.
      root = document.body;
    }
    if (container.parentElement !== root) root.appendChild(container);
  }

  document.addEventListener('fullscreenchange', ensureContainer);

  chrome.runtime.onMessage.addListener((msg) => {
    if (!msg || msg.target !== 'content') return;
    if (msg.kind === 'subtitle') render(msg.payload);
    if (msg.kind === 'stop') hide();
  });

  function render(payload) {
    const text = payload.dst;
    if (!text) return; // partiel non traduit : on garde l'affichage courant
    ensureContainer();
    lineEl.textContent = text;
    lineEl.classList.toggle('lvt-partial', payload.type === 'partial');
    container.style.display = 'block';
    clearTimeout(hideTimer);
    if (payload.type === 'final') hideTimer = setTimeout(hide, 5000);
  }

  function hide() {
    if (container) container.style.display = 'none';
  }
})();

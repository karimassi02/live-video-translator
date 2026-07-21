// Content script : affiche les sous-titres traduits, y compris en plein écran.
// Injecté dans TOUTES les frames (le player peut vivre dans une iframe) :
// chaque frame détermine si c'est à elle d'afficher.
(() => {
  if (window.__lvtInjected) return;
  window.__lvtInjected = true;

  const isTopFrame = window === window.top;
  let container = null;
  let lineEl = null;
  let hideTimer = null;
  let current = null; // dernier sous-titre affichable

  // Renvoie l'élément où greffer l'overlay, ou null si cette frame ne doit pas afficher.
  function activeRoot() {
    const fs = document.fullscreenElement;
    if (fs) {
      // Un élément de CETTE frame est en plein écran.
      if (fs.tagName === 'IFRAME') return null; // le contenu vit dans l'iframe : elle affichera elle-même
      if (fs.tagName === 'VIDEO') {
        // Impossible d'insérer un overlay DANS une balise <video>.
        console.warn('[LVT] Le site met la balise <video> elle-même en plein écran — overlay impossible dans ce mode.');
        return null;
      }
      return fs;
    }
    // Pas de plein écran dans cette frame : seule la frame principale affiche.
    return isTopFrame ? document.body : null;
  }

  function ensureContainer(root) {
    if (!container) {
      container = document.createElement('div');
      container.id = 'lvt-subtitles';
      lineEl = document.createElement('div');
      lineEl.id = 'lvt-line';
      container.appendChild(lineEl);
      container.style.display = 'none';
    }
    if (container.parentElement !== root) root.appendChild(container);
  }

  function show(payload) {
    const root = activeRoot();
    if (!root) {
      hide();
      return;
    }
    ensureContainer(root);
    lineEl.textContent = payload.dst;
    lineEl.classList.toggle('lvt-partial', payload.type === 'partial');
    container.style.display = 'block';
    clearTimeout(hideTimer);
    if (payload.type === 'final') {
      hideTimer = setTimeout(() => {
        current = null;
        hide();
      }, 5000);
    }
  }

  function hide() {
    if (container) container.style.display = 'none';
  }

  document.addEventListener('fullscreenchange', () => {
    const fs = document.fullscreenElement;
    console.debug(
      '[LVT] fullscreenchange —',
      fs ? `élément: ${fs.tagName}` : 'sortie du plein écran',
      '| frame:', isTopFrame ? 'principale' : 'iframe'
    );
    if (current) show(current);
    else hide();
  });

  chrome.runtime.onMessage.addListener((msg) => {
    if (!msg || msg.target !== 'content') return;
    if (msg.kind === 'subtitle') {
      if (!msg.payload.dst) return; // partiel non traduit : on garde l'affichage courant
      current = msg.payload;
      show(current);
    }
    if (msg.kind === 'stop') {
      current = null;
      hide();
    }
  });
})();

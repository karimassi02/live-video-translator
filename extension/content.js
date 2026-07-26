// Content script : affiche les sous-titres traduits, y compris en plein écran.
// Injecté dans TOUTES les frames (le player peut vivre dans une iframe) :
// chaque frame détermine si c'est à elle d'afficher.
//
// Affichage sur 2 lignes : les deux dernières phrases finalisées restent
// empilées (la plus récente en bas), chacune apparaît d'un bloc et expire
// après un temps de lecture proportionnel à sa longueur. Si le backend envoie
// des partiels (TRANSLATE_PARTIALS=true), ils s'affichent en dessous en
// italique (ligne « live »).
(() => {
  if (window.__lvtInjected) return;
  window.__lvtInjected = true;

  const isTopFrame = window === window.top;
  const MAX_FINAL_LINES = 2;
  let container = null;

  // État : phrases finalisées (plus ancienne en premier) + partiel courant.
  let finalLines = []; // [{ id, text, timer }]
  let liveText = null;
  const shownIds = new Set(); // finales déjà affichées (pour ignorer les mises à jour tardives)

  // Temps de lecture d'une phrase, proportionnel à sa longueur.
  function readingTimeMs(text) {
    return Math.max(4000, Math.min(10000, 1500 + 60 * text.length));
  }

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
      container.style.display = 'none';
    }
    if (container.parentElement !== root) root.appendChild(container);
  }

  function render() {
    const root = activeRoot();
    if (!root) {
      if (container) container.style.display = 'none';
      return;
    }
    ensureContainer(root);
    container.textContent = '';
    for (const line of finalLines) {
      const div = document.createElement('div');
      div.className = 'lvt-line';
      div.textContent = line.text;
      container.appendChild(div);
    }
    if (liveText) {
      const div = document.createElement('div');
      div.className = 'lvt-line lvt-live';
      div.textContent = liveText;
      container.appendChild(div);
    }
    container.style.display = finalLines.length || liveText ? 'block' : 'none';
  }

  function removeLine(line) {
    clearTimeout(line.timer);
    const i = finalLines.indexOf(line);
    if (i !== -1) finalLines.splice(i, 1);
  }

  function pushFinal(id, text) {
    while (finalLines.length >= MAX_FINAL_LINES) removeLine(finalLines[0]);
    const line = { id, text, timer: null };
    line.timer = setTimeout(() => {
      removeLine(line);
      render();
    }, readingTimeMs(text));
    finalLines.push(line);
    shownIds.add(id);
  }

  function onSubtitle(payload) {
    if (!payload.dst) return; // segment non traduit : on garde l'affichage courant
    if (payload.type === 'partial') {
      liveText = payload.dst;
    } else if (payload.type === 'final') {
      liveText = null;
      pushFinal(payload.id, payload.dst);
    } else if (payload.type === 'final_update') {
      // Version améliorée (Claude) : remplace le texte de la ligne en place.
      const line = finalLines.find((l) => l.id === payload.id);
      if (line) {
        line.text = payload.dst;
      } else if (!shownIds.has(payload.id)) {
        // La version rapide (DeepL) avait échoué : la ligne apparaît maintenant.
        pushFinal(payload.id, payload.dst);
      } else {
        return; // ligne déjà expirée : trop tard, on n'affiche pas
      }
    }
    render();
  }

  function reset() {
    for (const line of finalLines) clearTimeout(line.timer);
    finalLines = [];
    liveText = null;
    shownIds.clear(); // les ids repartent de zéro à la prochaine session
    render();
  }

  document.addEventListener('fullscreenchange', () => {
    const fs = document.fullscreenElement;
    console.debug(
      '[LVT] fullscreenchange —',
      fs ? `élément: ${fs.tagName}` : 'sortie du plein écran',
      '| frame:', isTopFrame ? 'principale' : 'iframe'
    );
    // Onglet capturé → Chromium simule le plein écran DANS l'onglet
    // (« fullscreen within tab ») : les barres du navigateur restent visibles.
    // On demande au background de passer la fenêtre elle-même en plein écran.
    chrome.runtime.sendMessage({ target: 'background', cmd: 'page-fullscreen', full: !!fs }).catch(() => {});
    render();
  });

  chrome.runtime.onMessage.addListener((msg) => {
    if (!msg || msg.target !== 'content') return;
    if (msg.kind === 'subtitle') onSubtitle(msg.payload);
    if (msg.kind === 'stop') reset();
  });
})();

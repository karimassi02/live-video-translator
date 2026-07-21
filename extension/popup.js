// Popup : démarre / arrête la session de sous-titrage sur l'onglet actif.
// Le streamId DOIT être obtenu ici (contexte de geste utilisateur + activeTab).

const statusEl = document.getElementById('status');
const toggleBtn = document.getElementById('toggle');
let state = { running: false };

async function refresh() {
  try {
    state = (await chrome.runtime.sendMessage({ target: 'background', cmd: 'get-state' })) || { running: false };
  } catch {
    state = { running: false };
  }
  toggleBtn.textContent = state.running ? 'Arrêter' : 'Démarrer';
  toggleBtn.classList.toggle('running', !!state.running);
  statusEl.textContent = statusLabel(state);
  statusEl.className = state.status === 'error' ? 'error'
    : (state.running && (state.status === 'connected' || state.status === 'ready')) ? 'active' : '';
}

function statusLabel(s) {
  if (!s.running) return 'Inactif';
  switch (s.status) {
    case 'connected':
    case 'ready':
      return 'Sous-titres actifs ✓';
    case 'error':
      return `Erreur : ${s.detail || 'inconnue'}`;
    case 'disconnected':
      return 'Backend déconnecté';
    default:
      return 'Démarrage…';
  }
}

toggleBtn.addEventListener('click', async () => {
  if (state.running) {
    await chrome.runtime.sendMessage({ target: 'background', cmd: 'stop' });
  } else {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) return;
    try {
      const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id });
      await chrome.runtime.sendMessage({ target: 'background', cmd: 'start', tabId: tab.id, streamId });
    } catch (e) {
      statusEl.textContent = `Erreur : ${e.message}`;
      statusEl.className = 'error';
      return;
    }
  }
  setTimeout(refresh, 400);
});

refresh();
// Rafraîchit le statut tant que le popup est ouvert.
setInterval(refresh, 1500);

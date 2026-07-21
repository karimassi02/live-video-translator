// Service worker : orchestre la capture, l'injection du content script
// et le relais des messages popup → offscreen → content script.

async function ensureOffscreenDocument() {
  const contexts = await chrome.runtime.getContexts({ contextTypes: ['OFFSCREEN_DOCUMENT'] });
  if (contexts.length > 0) return;
  await chrome.offscreen.createDocument({
    url: 'offscreen.html',
    reasons: ['USER_MEDIA'],
    justification: "Capture de l'audio de l'onglet pour sous-titrage traduit en direct",
  });
}

async function getState() {
  return chrome.storage.session.get({ running: false, tabId: null, status: null, detail: null });
}

async function handleStart(tabId, streamId) {
  await chrome.storage.session.set({ running: true, tabId, status: 'starting', detail: null });
  await ensureOffscreenDocument();
  try {
    await chrome.scripting.insertCSS({ target: { tabId }, files: ['content.css'] });
    await chrome.scripting.executeScript({ target: { tabId }, files: ['content.js'] });
  } catch (e) {
    console.warn('Injection du content script impossible', e);
  }
  chrome.runtime.sendMessage({ target: 'offscreen', cmd: 'start', streamId }).catch(() => {});
  chrome.action.setBadgeBackgroundColor({ color: '#16a34a' });
  chrome.action.setBadgeText({ text: 'ON' });
}

async function handleStop() {
  const { tabId } = await getState();
  chrome.runtime.sendMessage({ target: 'offscreen', cmd: 'stop' }).catch(() => {});
  if (tabId) {
    chrome.tabs.sendMessage(tabId, { target: 'content', kind: 'stop' }).catch(() => {});
  }
  await chrome.storage.session.set({ running: false, status: null, detail: null });
  chrome.action.setBadgeText({ text: '' });
  try { await chrome.offscreen.closeDocument(); } catch {}
}

async function handleStatus(status, detail) {
  const cur = await getState();
  if (!cur.running) return;
  await chrome.storage.session.set({ status, detail: detail || null });
  if (status === 'error') {
    chrome.action.setBadgeBackgroundColor({ color: '#dc2626' });
    chrome.action.setBadgeText({ text: 'ERR' });
  } else if (status === 'connected' || status === 'ready') {
    chrome.action.setBadgeBackgroundColor({ color: '#16a34a' });
    chrome.action.setBadgeText({ text: 'ON' });
  }
}

async function relaySubtitle(payload) {
  const { tabId } = await getState();
  if (!tabId) return;
  try {
    await chrome.tabs.sendMessage(tabId, { target: 'content', kind: 'subtitle', payload });
  } catch {
    // Onglet fermé ou content script absent : rien à faire.
  }
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!msg || msg.target !== 'background') return;
  (async () => {
    switch (msg.cmd) {
      case 'start':
        await handleStart(msg.tabId, msg.streamId);
        sendResponse({ ok: true });
        break;
      case 'stop':
        await handleStop();
        sendResponse({ ok: true });
        break;
      case 'get-state':
        sendResponse(await getState());
        break;
      case 'status':
        await handleStatus(msg.status, msg.detail);
        sendResponse({ ok: true });
        break;
      case 'relay-subtitle':
        await relaySubtitle(msg.payload);
        sendResponse({ ok: true });
        break;
      default:
        sendResponse({ ok: false });
    }
  })();
  return true; // réponse asynchrone
});

// Nettoyage si l'onglet capturé est fermé.
chrome.tabs.onRemoved.addListener(async (closedTabId) => {
  const { running, tabId } = await getState();
  if (running && tabId === closedTabId) handleStop();
});

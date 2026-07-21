// Document offscreen : consomme le flux audio de l'onglet capturé, le convertit
// en PCM mono 16 kHz et le pousse vers le backend local via WebSocket.
// Reçoit en retour les sous-titres et les relaie au content script (via le SW).

const BACKEND_WS_URL = 'ws://127.0.0.1:8710/ws';
const TARGET_SAMPLE_RATE = 16000;
const CHUNK_SAMPLES = 1600; // 100 ms à 16 kHz

let audioCtx = null;
let mediaStream = null;
let ws = null;
let running = false;

chrome.runtime.onMessage.addListener((msg) => {
  if (!msg || msg.target !== 'offscreen') return;
  if (msg.cmd === 'start') start(msg.streamId);
  if (msg.cmd === 'stop') stop();
});

function reportStatus(status, detail) {
  chrome.runtime.sendMessage({ target: 'background', cmd: 'status', status, detail }).catch(() => {});
}

async function start(streamId) {
  if (running) await stop();
  running = true;

  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        mandatory: { chromeMediaSource: 'tab', chromeMediaSourceId: streamId },
      },
      video: false,
    });
  } catch (e) {
    reportStatus('error', `Capture audio impossible : ${e.message}`);
    running = false;
    return;
  }

  audioCtx = new AudioContext();
  if (audioCtx.state === 'suspended') await audioCtx.resume();
  const source = audioCtx.createMediaStreamSource(mediaStream);

  // Indispensable : capturer un onglet coupe son audio. On le rejoue vers la
  // sortie pour continuer à entendre la vidéo normalement.
  source.connect(audioCtx.destination);

  await audioCtx.audioWorklet.addModule('pcm-worklet.js');
  const worklet = new AudioWorkletNode(audioCtx, 'pcm-processor');
  source.connect(worklet);

  const resampler = new Resampler(audioCtx.sampleRate, TARGET_SAMPLE_RATE);
  let pending = [];

  worklet.port.onmessage = (event) => {
    if (!running || !ws || ws.readyState !== WebSocket.OPEN) return;
    pending = pending.concat(resampler.push(event.data));
    while (pending.length >= CHUNK_SAMPLES) {
      const chunk = pending.slice(0, CHUNK_SAMPLES);
      pending = pending.slice(CHUNK_SAMPLES);
      ws.send(floatsToInt16(chunk).buffer);
    }
  };

  connectBackend();
}

function connectBackend() {
  ws = new WebSocket(BACKEND_WS_URL);
  ws.binaryType = 'arraybuffer';

  ws.onopen = () => reportStatus('connected');

  ws.onmessage = (event) => {
    let msg;
    try { msg = JSON.parse(event.data); } catch { return; }
    if (msg.type === 'partial' || msg.type === 'final') {
      chrome.runtime.sendMessage({ target: 'background', cmd: 'relay-subtitle', payload: msg }).catch(() => {});
    } else if (msg.type === 'status') {
      reportStatus(msg.status, msg.detail);
    }
  };

  ws.onerror = () => {
    reportStatus('error', 'Backend injoignable — lance `uvicorn main:app --port 8710` dans backend/');
  };

  ws.onclose = () => {
    if (running) reportStatus('disconnected');
  };
}

async function stop() {
  running = false;
  if (ws) {
    try { ws.close(); } catch {}
    ws = null;
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop());
    mediaStream = null;
  }
  if (audioCtx) {
    try { await audioCtx.close(); } catch {}
    audioCtx = null;
  }
}

// Rééchantillonneur linéaire avec continuité entre blocs (48 kHz → 16 kHz en général).
class Resampler {
  constructor(inRate, outRate) {
    this.ratio = inRate / outRate;
    this.buf = new Float32Array(0);
    this.t = 0;
  }

  /** @param {Float32Array} chunk @returns {number[]} échantillons au taux de sortie */
  push(chunk) {
    const merged = new Float32Array(this.buf.length + chunk.length);
    merged.set(this.buf);
    merged.set(chunk, this.buf.length);
    this.buf = merged;

    const out = [];
    while (Math.floor(this.t) + 1 < this.buf.length) {
      const i = Math.floor(this.t);
      const frac = this.t - i;
      out.push(this.buf[i] * (1 - frac) + this.buf[i + 1] * frac);
      this.t += this.ratio;
    }
    const keep = Math.floor(this.t);
    this.buf = this.buf.slice(keep);
    this.t -= keep;
    return out;
  }
}

function floatsToInt16(floats) {
  const out = new Int16Array(floats.length);
  for (let i = 0; i < floats.length; i++) {
    const s = Math.max(-1, Math.min(1, floats[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

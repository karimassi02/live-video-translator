# Live Video Translator

Sous-titres traduits **en direct** pour n'importe quelle vidéo jouée dans le navigateur. L'extension capture l'audio de l'onglet, un backend local le transcrit et le traduit en streaming, et les sous-titres s'affichent **dans la page** — y compris en plein écran, et visibles lors d'un partage d'écran (Discord, Meet, Teams…).

Cas d'usage typique : regarder un contenu dans une langue avec des personnes qui ne la parlent pas, en visionnage partagé ou à distance.

## Architecture

```
┌────────────── Navigateur (Chrome/Edge) ──────────────┐      ┌───── Backend local (Python) ─────┐
│                                                      │      │                                  │
│  Onglet vidéo ──► tabCapture ──► offscreen document ─┼─WS──►│ Deepgram (STT streaming)         │
│      ▲                           (PCM mono 16 kHz)   │      │        │                         │
│      │                                               │      │        ▼                         │
│  content script ◄── background ◄─────────────────────┼──WS──│ DeepL (traduction)               │
│  (overlay sous-titres, plein écran inclus)           │      │                                  │
└──────────────────────────────────────────────────────┘      └──────────────────────────────────┘
```

- **STT** : Deepgram `nova-2` en streaming (latence ~300 ms, résultats partiels).
- **Traduction** : DeepL. Les langues source/cible se configurent librement dans `.env` (`SOURCE_LANG`, `TARGET_LANG`).
- **Moteurs interchangeables** : les interfaces abstraites (`stt/base.py`, `translate/base.py`) permettent de brancher un autre moteur (Whisper local sur GPU, traduction par LLM…) sans toucher au reste du pipeline.
- **Latence bout en bout** : ~1 à 2 s.

### Points techniques notables

- **Plein écran** : l'overlay de sous-titres est re-greffé dynamiquement dans `document.fullscreenElement`, ce qui le garde visible quand le player passe en fullscreen.
- **Audio préservé** : `tabCapture` coupe le son de l'onglet capturé ; le flux est rejoué vers la sortie audio pour une écoute normale.
- **Anti-flicker** : les transcriptions partielles s'affichent en italique et sont stabilisées à la finalisation de chaque phrase ; les partiels obsolètes sont rejetés.
- **Quota-friendly** : throttle de traduction des partiels (réglable) + cache des segments répétés.

## Prérequis

- Python 3.11+
- Chrome ou Edge (Chromium 116+)
- Une clé API [Deepgram](https://console.deepgram.com) (crédit gratuit offert à l'inscription)
- Une clé API [DeepL](https://www.deepl.com/pro-api) (plan Developer gratuit)

## Installation

### 1. Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
# → éditer .env : renseigner DEEPGRAM_API_KEY, DEEPL_API_KEY et les langues souhaitées
```

Lancement :

```powershell
.venv\Scripts\python.exe main.py
```

Vérification : ouvrir http://127.0.0.1:8710/ → `{"status": "ok", ...}`

### 2. Extension

1. Ouvrir `chrome://extensions` (ou `edge://extensions`)
2. Activer le **mode développeur**
3. **Charger l'extension non empaquetée** → sélectionner le dossier `extension/`

## Utilisation

1. Lancer le backend (voir ci-dessus)
2. Ouvrir l'onglet contenant la vidéo
3. Cliquer sur l'icône de l'extension → **Démarrer**
4. Le badge passe à `ON` : les sous-titres apparaissent en bas de la vidéo dès que quelqu'un parle
5. Le plein écran est géré automatiquement

## Dépannage

| Symptôme | Cause / solution |
|---|---|
| Badge `ERR` rouge | Backend non lancé, ou clés API absentes → voir le popup pour le détail |
| Pas de sous-titres mais badge `ON` | Vérifier les logs du backend (transcriptions visibles ?) ; monter le son de la vidéo |
| Vidéo **noire** côté spectateurs en partage d'écran | DRM + accélération matérielle sur certains sites de streaming. Désactiver l'**accélération graphique** dans les paramètres du navigateur, puis relancer |
| Capture audio refusée sur un site | Rare (protection DRM stricte). Alternative prévue en roadmap : capture système WASAPI loopback |
| Sous-titres invisibles en plein écran sur un site précis | Le site passe la balise `<video>` elle-même en fullscreen (cas rare) — la plupart des players passent un conteneur |

## Coûts en pratique

Les crédits gratuits fonctionnent en prépayé : quand ils sont épuisés, le service s'arrête — **aucune facturation automatique**.

- **Deepgram** : ~0,35 $/h d'audio (nova-2 streaming) → le crédit d'inscription couvre plusieurs centaines d'heures
- **DeepL** : consommation mesurée ~60–70k caractères/h de parole dense → le crédit gratuit de 1M caractères couvre ~15-20 h de vidéo
- Pour économiser DeepL : monter `PARTIAL_TRANSLATE_INTERVAL` dans `.env` (moins de rafraîchissements intermédiaires), ou brancher un traducteur LLM (voir roadmap)

## Roadmap

- [ ] STT local `faster-whisper` (GPU NVIDIA) comme alternative gratuite → nouvelle classe dans `backend/stt/`
- [ ] Traduction par LLM (meilleure sur le registre familier/argot) → nouvelle classe dans `backend/translate/`
- [ ] Affichage optionnel de la ligne source sous la traduction
- [ ] Réglages de style des sous-titres (taille, position) dans le popup
- [ ] Capture système WASAPI loopback (fallback si un site bloque `tabCapture`)

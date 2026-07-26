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
│  content script ◄── background ◄─────────────────────┼──WS──│ Traduction hybride :             │
│  (overlay 2 lignes, plein écran inclus)              │      │  partiels → DeepL (rapide)       │
└──────────────────────────────────────────────────────┘      │  finales  → Claude (idiomatique) │
                                                              └──────────────────────────────────┘
```

- **STT** : Deepgram `nova-2` en streaming (latence ~300 ms, résultats partiels).
- **Traduction en deux temps** : dès la fin de la réplique, la version DeepL (~200 ms) s'affiche en bloc ; ~1 s plus tard, la version LLM (Claude Haiku 4.5) — qui rend l'argot et les idiomes par le sens (« il ne me calcule pas » → « he's blanking me ») grâce au contexte des phrases précédentes — remplace discrètement le texte de la ligne. `FINAL_TRANSLATOR=deepl` restaure le mode 100 % DeepL. Langues configurables dans `.env` (`SOURCE_LANG`, `TARGET_LANG`).
- **Moteurs interchangeables** : les interfaces abstraites (`stt/base.py`, `translate/base.py`) permettent de brancher un autre moteur (Whisper local sur GPU…) sans toucher au reste du pipeline.
- **Latence bout en bout** : ~1 à 2 s.

### Points techniques notables

- **Plein écran** : l'overlay de sous-titres est re-greffé dynamiquement dans `document.fullscreenElement`, ce qui le garde visible quand le player passe en fullscreen.
- **Plein écran pendant la capture** : Chromium confine le plein écran d'un onglet capturé à la zone de l'onglet (« fullscreen within tab », crbug.com/350491) — les barres du navigateur resteraient visibles. L'extension bascule donc automatiquement la fenêtre du navigateur en plein écran quand le player y passe, et restaure l'état en sortant.
- **Audio préservé** : `tabCapture` coupe le son de l'onglet capturé ; le flux est rejoué vers la sortie audio pour une écoute normale.
- **Affichage 2 lignes, apparition en bloc** : chaque phrase apparaît entière ~0,4 s après la fin de la réplique (détection de fin `DEEPGRAM_ENDPOINTING`, 200 ms par défaut + DeepL ~200 ms, connexions préchauffées au démarrage). Les deux dernières répliques restent empilées, chacune le temps d'être lue ; le texte d'une ligne est remplacé une seule fois quand la version Claude arrive. `TRANSLATE_PARTIALS=true` réactive une ligne « live » en italique qui s'écrit pendant la phrase.
- **Quota-friendly** : partiels désactivés par défaut (DeepL quasi inutilisé), throttle + cache si on les réactive.

## Prérequis

- Python 3.11+
- Chrome ou Edge (Chromium 116+)
- Une clé API [Deepgram](https://console.deepgram.com) (crédit gratuit offert à l'inscription)
- Une clé API [DeepL](https://www.deepl.com/pro-api) (plan Developer gratuit)
- Une clé API [Anthropic](https://console.anthropic.com) (crédit prépayé) — pour la traduction LLM des phrases finales ; facultative avec `FINAL_TRANSLATOR=deepl`

## Installation

### 1. Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
# → éditer .env : renseigner DEEPGRAM_API_KEY, DEEPL_API_KEY, ANTHROPIC_API_KEY et les langues souhaitées
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
| Warning `Claude indisponible, repli DeepL` dans les logs | Clé `ANTHROPIC_API_KEY` invalide ou crédit épuisé → les finales repassent par DeepL (mot-à-mot) le temps de corriger |
| Sous-titres invisibles en plein écran sur un site précis | Le site passe la balise `<video>` elle-même en fullscreen (cas rare) — la plupart des players passent un conteneur |
| Plein écran confiné à l'onglet (barres du navigateur visibles) | Comportement Chromium sur onglet capturé, normalement compensé automatiquement. Si le plein écran était actif AVANT de démarrer la capture, ressortir puis remettre le plein écran |

## Coûts en pratique

Les crédits gratuits fonctionnent en prépayé : quand ils sont épuisés, le service s'arrête — **aucune facturation automatique**.

- **Deepgram** : ~0,35 $/h d'audio (nova-2 streaming) → le crédit d'inscription couvre plusieurs centaines d'heures
- **Anthropic** (finales, Claude Haiku 4.5) : ~0,45 $/h de parole dense (~600-700 phrases + contexte)
- **DeepL** : une passe par finale (affichage immédiat) ≈ ~25-30k caractères/h → le crédit gratuit de 1M caractères couvre ~30-40 h. Avec `TRANSLATE_PARTIALS=true`, compter ~60-70k caractères/h
- Pour couper le coût Anthropic : `FINAL_TRANSLATOR=deepl` (gratuit, mais mot-à-mot sur l'argot)

## Roadmap

- [ ] STT local `faster-whisper` (GPU NVIDIA) comme alternative gratuite → nouvelle classe dans `backend/stt/`
- [x] Traduction par LLM (meilleure sur le registre familier/argot) → `backend/translate/claude_translator.py` (phrases finales)
- [ ] Affichage optionnel de la ligne source sous la traduction
- [ ] Réglages de style des sous-titres (taille, position) dans le popup
- [ ] Capture système WASAPI loopback (fallback si un site bloque `tabCapture`)

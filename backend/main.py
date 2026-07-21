"""Backend local Live Video Translator.

Reçoit l'audio PCM 16 kHz de l'extension via WebSocket, le transcrit
(Deepgram), le traduit (DeepL) et renvoie les sous-titres.

Lancement :
    uvicorn main:app --host 127.0.0.1 --port 8710
"""
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from config import settings
from pipeline import SubtitlePipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s — %(message)s")
log = logging.getLogger("lvt")

app = FastAPI(title="Live Video Translator")


@app.get("/")
async def health() -> dict:
    final_engine = f"claude/{settings.claude_model}" if settings.final_translator == "claude" else "deepl"
    partials = "deepl" if settings.translate_partials else "désactivés"
    return {
        "status": "ok",
        "stt": f"deepgram/{settings.deepgram_model}",
        "translate": f"partiels: {partials}, finales: {final_engine} ({settings.source_lang}->{settings.target_lang})",
    }


@app.websocket("/ws")
async def audio_ws(ws: WebSocket) -> None:
    await ws.accept()
    log.info("Extension connectée")

    missing = [
        name
        for name, value in [
            ("DEEPGRAM_API_KEY", settings.deepgram_api_key),
            ("DEEPL_API_KEY", settings.deepl_api_key),
        ]
        if not value
    ]
    if settings.final_translator == "claude" and not settings.anthropic_api_key:
        missing.append("ANTHROPIC_API_KEY")
    if missing:
        await ws.send_json({
            "type": "status",
            "status": "error",
            "detail": f"Clés API manquantes ({', '.join(missing)}) : complète backend/.env",
        })
        await ws.close()
        return

    pipeline = SubtitlePipeline(ws.send_json)
    try:
        await pipeline.start()
    except Exception as e:
        log.exception("Échec de démarrage du moteur STT")
        await ws.send_json({
            "type": "status",
            "status": "error",
            "detail": f"Connexion Deepgram impossible : {e}",
        })
        await ws.close()
        return

    await ws.send_json({"type": "status", "status": "ready"})

    try:
        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                break
            data = message.get("bytes")
            if data:
                await pipeline.feed(data)
    except WebSocketDisconnect:
        pass
    finally:
        log.info("Session terminée")
        await pipeline.stop()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=settings.port)

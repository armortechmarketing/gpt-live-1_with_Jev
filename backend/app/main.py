import logging

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.live_proxy import LiveProxy

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="Action Gate")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    missing = get_settings().missing_keys()
    return {"status": "ok" if not missing else "missing_keys", "missing": ",".join(missing)}


@app.websocket("/ws/session")
async def session(websocket: WebSocket) -> None:
    await websocket.accept()
    proxy = LiveProxy(websocket, get_settings())
    await proxy.run()

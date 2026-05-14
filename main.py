"""
main.py — FastAPI backend for Lâm Đồng AI Voice Chatbot.

Pattern copied from gemini-live-genai-python-sdk/main.py (original repo).
Extensions added:
  - navigate_vr_scene tool injection
  - System prompt loaded from prompt.txt (hot-reloadable via /admin/prompt)
  - Admin UI for editing prompt.txt without server restart
  - Serves pano2vr_new frontend as static files

Source reference:
  https://github.com/google-gemini/gemini-live-api-examples/tree/main/gemini-live-genai-python-sdk
"""

import asyncio
import base64
import hashlib
import hmac as _hmac
import json
import logging
import os
import secrets
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from gemini_live import GeminiLive
from tools import (
    build_navigate_tool, navigate_vr_scene,
    build_weather_tool, get_weather_for_scene,
    build_get_pano_nodeid_tool, get_pano_nodeid,
    build_add_memory_tool, SessionMemory,
)

# ─── Load environment variables ───────────────────────────────────────────────
load_dotenv()

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logging.getLogger("gemini_live").setLevel(logging.DEBUG)
logging.getLogger(__name__).setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)

# ─── Config (all from .env, no hardcoded values) ──────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-live-preview")
GEMINI_VOICE = os.getenv("GEMINI_VOICE", "Aoede")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# ─── Mutable runtime config (overridable via POST /admin/config) ──────────────
_CURRENT_MODEL: str = GEMINI_MODEL
_CURRENT_VOICE: str = GEMINI_VOICE
AVAILABLE_VOICES = ["Aoede", "Charon", "Fenrir", "Kore", "Puck"]

BASE_DIR = Path(__file__).parent
PROMPT_FILE = BASE_DIR / "prompt.txt"

# admin-dist: try backend/admin-dist first (production), then pano2vr_new/admin-dist (local dev)
ADMIN_DIST_DIR = BASE_DIR / "admin-dist"
if not ADMIN_DIST_DIR.exists():
    ADMIN_DIST_DIR = BASE_DIR.parent / "pano2vr_new" / "admin-dist"
    if not ADMIN_DIST_DIR.exists():
        ADMIN_DIST_DIR = None
        logger.warning("admin-dist not found — admin UI will fall back to static/admin.html")

# ─── Data directory (scenes.json + nodes.json) ────────────────────────────────
# Priority: DATA_DIR env var → backend/data (production) → ../pano2vr_new/data (local dev)
_data_dir_env = os.getenv("DATA_DIR", "").strip()
if _data_dir_env:
    DATA_DIR = Path(_data_dir_env)
elif (BASE_DIR / "data").exists():
    DATA_DIR = BASE_DIR / "data"   # production: bundled in backend/data/
else:
    DATA_DIR = BASE_DIR.parent / "pano2vr_new" / "data"  # local dev: shared folder
    if not DATA_DIR.exists():
        DATA_DIR = BASE_DIR / "data"
        DATA_DIR.mkdir(exist_ok=True)
SCENES_FILE = DATA_DIR / "scenes.json"
NODES_FILE  = DATA_DIR / "nodes.json"
logger.info("Data directory: %s", DATA_DIR)

# ─── System prompt (hot-reloadable) ───────────────────────────────────────────
def load_prompt() -> str:
    try:
        return PROMPT_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.warning("prompt.txt not found, using default system prompt.")
        return "Bạn là trợ lý du lịch Lâm Đồng thân thiện và hữu ích."


SYSTEM_PROMPT = load_prompt()
_INITIAL_PROMPT = SYSTEM_PROMPT  # baseline for POST /admin/reset
logger.info("System prompt loaded (%d chars)", len(SYSTEM_PROMPT))

# ─── Tool setup (built once at startup; scene map from SCENE_MAP_JSON env) ────
NAVIGATE_TOOL         = build_navigate_tool()
WEATHER_TOOL          = build_weather_tool()
GET_PANO_NODEID_TOOL  = build_get_pano_nodeid_tool()
ADD_MEMORY_TOOL       = build_add_memory_tool()

# Global (stateless) tools — shared across all sessions
_GLOBAL_TOOL_MAPPING: dict = {
    "navigate_vr_scene": navigate_vr_scene,
    "get_weather_for_scene": get_weather_for_scene,
    "get_pano_nodeid": get_pano_nodeid,
}
ALL_TOOLS = [NAVIGATE_TOOL, WEATHER_TOOL, GET_PANO_NODEID_TOOL, ADD_MEMORY_TOOL]

# ─── Token-based auth (HMAC stateless, survives restarts) ───────────────────────────────

def _gen_admin_token() -> str:
    expiry = str(int(time.time() * 1000) + 24 * 3600 * 1000)
    sig = _hmac.new(ADMIN_PASSWORD.encode("utf-8"), expiry.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{expiry}.{sig}"


def _check_admin_token(token: str) -> bool:
    if not ADMIN_PASSWORD:
        return True  # auth disabled
    if not token or "." not in token:
        return False
    dot = token.rfind(".")
    expiry, sig = token[:dot], token[dot + 1:]
    expected = _hmac.new(ADMIN_PASSWORD.encode("utf-8"), expiry.encode("utf-8"), hashlib.sha256).hexdigest()
    try:
        if not _hmac.compare_digest(sig, expected):
            return False
        return int(time.time() * 1000) <= int(expiry)
    except Exception:
        return False


# ─── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(title="Lâm Đồng AI Chatbot Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://stagingdulichlamdong.vt360.vn", "https://www.stagingdulichlamdong.vt360.vn"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Static files (admin UI assets) ──────────────────────────────────────────
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if ADMIN_DIST_DIR and (ADMIN_DIST_DIR / "assets").exists():
    app.mount("/admin/assets", StaticFiles(directory=ADMIN_DIST_DIR / "assets"), name="admin_assets")
    logger.info("admin-dist assets mounted from %s", ADMIN_DIST_DIR)
# ─── HTTP Basic Auth for admin endpoints ──────────────────────────────────────
security = HTTPBasic(auto_error=False)


_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
}

def _spa_response():
    """Return the React admin SPA HTML file.

    Always served with no-store so the browser never caches the SPA HTML.
    Without this the browser would return the cached HTML for subsequent
    fetch() calls from React (e.g. getConfig()), causing JSON parse failures.
    """
    if ADMIN_DIST_DIR and (ADMIN_DIST_DIR / "index.html").exists():
        return FileResponse(ADMIN_DIST_DIR / "index.html", headers=_NO_CACHE_HEADERS)
    return FileResponse(STATIC_DIR / "admin.html", headers=_NO_CACHE_HEADERS)


def _is_api_request(request: Request) -> bool:
    """True when the request comes from the React SPA fetch.

    The React SPA always includes the X-Admin-Token header (even when empty),
    while a plain browser navigation never sends that header at all.
    We also treat requests that explicitly Accept JSON (and not HTML) as API
    requests so curl / other clients work as expected.
    """
    # Header present (even empty) → React SPA fetch
    if "x-admin-token" in request.headers:
        return True
    # Explicit JSON accept without HTML → programmatic client
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return True
    return False


def verify_admin(
    request: Request,
    credentials: Optional[HTTPBasicCredentials] = Depends(security),
) -> None:
    """Accept X-Admin-Token (React admin) OR HTTP Basic Auth (legacy/curl).
    Browser navigations (no token, no Basic creds) are allowed through so that
    the route function can serve the SPA HTML instead of a 401.
    """
    # Auth disabled → allow everything through immediately
    if not ADMIN_PASSWORD:
        return

    # No auth provided at all → only let through if this looks like a browser navigation
    token = request.headers.get("X-Admin-Token", "").strip()
    if not token and not credentials:
        # If it's an API-style request (X-Admin-Token header present but empty, or JSON Accept)
        # we must reject with 401 so the SPA can redirect to login.
        if _is_api_request(request):
            raise HTTPException(
                status_code=401,
                detail="Unauthorized",
                headers={"WWW-Authenticate": 'Bearer, Basic realm="Admin"'},
            )
        return  # browser navigation → route will serve SPA HTML
    if token and _check_admin_token(token):
        return
    if credentials and secrets.compare_digest(
        credentials.password.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8")
    ):
        return
    raise HTTPException(
        status_code=401,
        detail="Unauthorized",
        headers={"WWW-Authenticate": 'Bearer, Basic realm="Admin"'},
    )


# ─── Admin: view / edit system prompt ─────────────────────────────────────────
@app.post("/admin/login")
async def admin_login(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    password = (body.get("password") or "").strip()
    if ADMIN_PASSWORD and not secrets.compare_digest(
        password.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Sai mật khẩu")
    return JSONResponse({"token": _gen_admin_token(), "message": "Đăng nhập thành công"})


@app.post("/admin/logout")
async def admin_logout():
    return JSONResponse({"ok": True})


@app.get("/admin/api/me")
async def admin_me(request: Request):
    token = request.headers.get("X-Admin-Token", "").strip()
    if not _check_admin_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return JSONResponse({"ok": True})


@app.get("/admin/models")
async def admin_models(request: Request, _: None = Depends(verify_admin)):
    if not _is_api_request(request):
        return _spa_response()
    return JSONResponse({"models": [
        {"name": "gemini-3.1-flash-live-preview",                    "displayName": "Gemini 3.1 Flash Live Preview"},
        {"name": "gemini-2.5-flash-native-audio-latest",             "displayName": "Gemini 2.5 Flash Native Audio (Latest)"},
        {"name": "gemini-2.5-flash-native-audio-preview-09-2025",    "displayName": "Gemini 2.5 Flash Native Audio (Sep 2025)"},
        {"name": "gemini-2.5-flash-native-audio-preview-12-2025",    "displayName": "Gemini 2.5 Flash Native Audio (Dec 2025)"},
    ]})


@app.get("/admin")
@app.get("/admin/")
async def admin_page(request: Request):
    """Serve React admin SPA, fallback to static/admin.html."""
    return _spa_response()


# (helpers _spa_response and _is_api_request are defined above verify_admin)


# ─── Admin: prompt / config / reset ─────────────────────────────────────────────────────────


@app.get("/admin/prompt")
async def get_prompt(request: Request, _: None = Depends(verify_admin)):
    """Return current system prompt as JSON."""
    if not _is_api_request(request):
        return _spa_response()
    current = PROMPT_FILE.read_text(encoding="utf-8") if PROMPT_FILE.exists() else SYSTEM_PROMPT
    return JSONResponse({"prompt": current})


@app.post("/admin/prompt")
async def save_prompt(request: Request, _: None = Depends(verify_admin)):
    """Save new system prompt to prompt.txt and reload in-memory value."""
    global SYSTEM_PROMPT
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    new_prompt = body.get("prompt", "").strip()
    if not new_prompt:
        raise HTTPException(status_code=400, detail="Prompt không được để trống")

    PROMPT_FILE.write_text(new_prompt, encoding="utf-8")
    SYSTEM_PROMPT = new_prompt
    logger.info("System prompt hot-reloaded via admin UI (%d chars)", len(SYSTEM_PROMPT))
    return JSONResponse({"message": "Đã lưu và áp dụng prompt mới thành công"})


@app.get("/admin/config")
async def admin_config(request: Request, _: None = Depends(verify_admin)):
    """Return server config for display in admin UI."""
    if not _is_api_request(request):
        return _spa_response()
    scene_map_json = os.getenv("SCENE_MAP_JSON", "{}")
    try:
        scene_map = json.loads(scene_map_json)
    except json.JSONDecodeError:
        scene_map = {}
    platform = (
        "Vertex AI"
        if os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE"
        else "AI Studio"
    )
    current_prompt = PROMPT_FILE.read_text(encoding="utf-8") if PROMPT_FILE.exists() else SYSTEM_PROMPT
    return JSONResponse({
        "model": _CURRENT_MODEL,
        "voice": _CURRENT_VOICE,
        "availableVoices": AVAILABLE_VOICES,
        "prompt": current_prompt,
        "platform": platform,
        "scene_ids": list(scene_map.keys()),
    })


@app.post("/admin/config")
async def save_config(request: Request, _: None = Depends(verify_admin)):
    """Hot-reload model and voice without restarting the server.

    Changes take effect on the **next** WebSocket session.
    """
    global _CURRENT_MODEL, _CURRENT_VOICE
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    model = (body.get("model") or "").strip()
    voice = (body.get("voice") or "").strip()

    if not model:
        raise HTTPException(status_code=400, detail="model không được để trống")
    if voice and voice not in AVAILABLE_VOICES:
        raise HTTPException(
            status_code=400,
            detail=f"voice không hợp lệ. Chọn một trong: {', '.join(AVAILABLE_VOICES)}",
        )

    _CURRENT_MODEL = model
    if voice:
        _CURRENT_VOICE = voice

    logger.info("Config hot-reloaded: model=%s voice=%s", _CURRENT_MODEL, _CURRENT_VOICE)
    return JSONResponse({
        "message": "Đã lưu cấu hình. Phiên WebSocket tiếp theo sẽ dùng model và voice mới.",
        "model": _CURRENT_MODEL,
        "voice": _CURRENT_VOICE,
    })


@app.post("/admin/reset")
async def reset_prompt_to_default(_: None = Depends(verify_admin)):
    """Reset SYSTEM_PROMPT to the value loaded at server startup."""
    global SYSTEM_PROMPT
    SYSTEM_PROMPT = _INITIAL_PROMPT
    PROMPT_FILE.write_text(_INITIAL_PROMPT, encoding="utf-8")
    logger.info("System prompt reset to initial value (%d chars)", len(SYSTEM_PROMPT))
    return JSONResponse({"message": "Đã reset về mặc định"})


# ─── Helpers: read/write scenes & nodes JSON ──────────────────────────────────

def _read_json(path: Path, default=None):
    if default is None:
        default = []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ─── Public API (no auth) ─────────────────────────────────────────────────────

@app.get("/api/scenes")
async def public_scenes():
    """Public — list all scenes (used by pano2vr frontend)."""
    return JSONResponse(_read_json(SCENES_FILE))

@app.get("/api/nodes")
async def public_nodes():
    """Public — list all nodes (used by pano2vr map)."""
    return JSONResponse(_read_json(NODES_FILE))


# ─── Admin CRUD: scenes ───────────────────────────────────────────────────────

@app.get("/admin/scenes")
async def list_scenes(request: Request, _: None = Depends(verify_admin)):
    if not _is_api_request(request):
        return _spa_response()
    return JSONResponse(_read_json(SCENES_FILE))

@app.post("/admin/scenes")
async def create_scene(request: Request, _: None = Depends(verify_admin)):
    try:
        scene = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not scene.get("id") or not scene.get("panoNodeId"):
        raise HTTPException(status_code=400, detail="id và panoNodeId là bắt buộc")
    scenes = _read_json(SCENES_FILE)
    if any(s["id"] == scene["id"] for s in scenes):
        raise HTTPException(status_code=409, detail=f"Scene id '{scene['id']}' đã tồn tại")
    scenes.append(scene)
    _write_json(SCENES_FILE, scenes)
    logger.info("Scene created: %s", scene["id"])
    return JSONResponse(scene, status_code=201)

@app.put("/admin/scenes/{scene_id}")
async def update_scene(scene_id: str, request: Request, _: None = Depends(verify_admin)):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    scenes = _read_json(SCENES_FILE)
    idx = next((i for i, s in enumerate(scenes) if s["id"] == scene_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy scene")
    scenes[idx] = {**scenes[idx], **body, "id": scene_id}
    _write_json(SCENES_FILE, scenes)
    logger.info("Scene updated: %s", scene_id)
    return JSONResponse(scenes[idx])

@app.delete("/admin/scenes/{scene_id}")
async def delete_scene(scene_id: str, _: None = Depends(verify_admin)):
    scenes = [s for s in _read_json(SCENES_FILE) if s["id"] != scene_id]
    _write_json(SCENES_FILE, scenes)
    logger.info("Scene deleted: %s", scene_id)
    return JSONResponse({"ok": True})


# ─── Admin CRUD: nodes ────────────────────────────────────────────────────────

@app.get("/admin/nodes")
async def list_nodes(request: Request, _: None = Depends(verify_admin)):
    if not _is_api_request(request):
        return _spa_response()
    return JSONResponse(_read_json(NODES_FILE))

@app.post("/admin/nodes")
async def create_node(request: Request, _: None = Depends(verify_admin)):
    try:
        node = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not node.get("nodeId"):
        raise HTTPException(status_code=400, detail="nodeId là bắt buộc")
    nodes = _read_json(NODES_FILE)
    if any(n["nodeId"] == node["nodeId"] for n in nodes):
        raise HTTPException(status_code=409, detail=f"nodeId '{node['nodeId']}' đã tồn tại")
    nodes.append(node)
    _write_json(NODES_FILE, nodes)
    logger.info("Node created: %s", node["nodeId"])
    return JSONResponse(node, status_code=201)

@app.put("/admin/nodes/{node_id}")
async def update_node(node_id: str, request: Request, _: None = Depends(verify_admin)):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    nodes = _read_json(NODES_FILE)
    idx = next((i for i, n in enumerate(nodes) if n["nodeId"] == node_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy node")
    nodes[idx] = {**nodes[idx], **body, "nodeId": node_id}
    _write_json(NODES_FILE, nodes)
    logger.info("Node updated: %s", node_id)
    return JSONResponse(nodes[idx])

@app.delete("/admin/nodes/{node_id}")
async def delete_node(node_id: str, _: None = Depends(verify_admin)):
    nodes = [n for n in _read_json(NODES_FILE) if n["nodeId"] != node_id]
    _write_json(NODES_FILE, nodes)
    logger.info("Node deleted: %s", node_id)
    return JSONResponse({"ok": True})


@app.get("/admin/{full_path:path}")
async def admin_spa_fallback(full_path: str, request: Request):
    """SPA catch-all: serve index.html for client-side routes (assets handled by mount)."""
    if ADMIN_DIST_DIR and (ADMIN_DIST_DIR / "index.html").exists():
        return FileResponse(ADMIN_DIST_DIR / "index.html")
    return FileResponse(STATIC_DIR / "admin.html")


# ─── WebSocket endpoint (pattern from repo main.py) ───────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for Gemini Live AI voice chat."""
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    audio_input_queue: asyncio.Queue = asyncio.Queue()
    video_input_queue: asyncio.Queue = asyncio.Queue()
    text_input_queue: asyncio.Queue = asyncio.Queue()

    async def audio_output_callback(data: bytes):
        await websocket.send_bytes(data)

    async def audio_interrupt_callback():
        pass

    # Each WebSocket session captures the current model/voice/prompt at connection time.
    # add_to_memory is session-scoped — create a fresh SessionMemory per connection.
    _session_mem = SessionMemory()
    _current_node: dict = {"nodeId": None, "sceneId": None}  # updated by node_changed events

    def _get_pano_nodeid_session() -> dict:
        if _current_node["nodeId"]:
            return {
                "nodeId":  _current_node["nodeId"],
                "sceneId": _current_node["sceneId"],
            }
        return {
            "error": (
                "Chưa nhận được vị trí VR từ trình duyệt. "
                "Hãy mở ứng dụng VR360 và xem một cảnh panorama trước."
            )
        }

    _session_tool_mapping = {
        **_GLOBAL_TOOL_MAPPING,
        "add_to_memory":   _session_mem.add_to_memory,
        "get_pano_nodeid": _get_pano_nodeid_session,
    }
    gemini_client = GeminiLive(
        api_key=GEMINI_API_KEY,
        model=_CURRENT_MODEL,
        input_sample_rate=16000,
        system_instruction=SYSTEM_PROMPT,
        voice_name=_CURRENT_VOICE,
        tools=ALL_TOOLS,
        tool_mapping=_session_tool_mapping,
    )

    async def receive_from_client():
        try:
            while True:
                message = await websocket.receive()

                if message.get("bytes"):
                    await audio_input_queue.put(message["bytes"])
                elif message.get("text"):
                    text = message["text"]
                    try:
                        payload = json.loads(text)

                        # realtimeInput: audio sent by browser ScriptProcessor
                        if isinstance(payload, dict) and "realtimeInput" in payload:
                            rt = payload["realtimeInput"]
                            audio_obj = rt.get("audio") if isinstance(rt, dict) else None
                            if isinstance(audio_obj, dict):
                                b64 = audio_obj.get("data", "")
                                if b64:
                                    await audio_input_queue.put(base64.b64decode(b64))
                            continue

                        # node_changed: frontend reports which VR panorama is active
                        if isinstance(payload, dict) and payload.get("type") == "node_changed":
                            _current_node["nodeId"]  = payload.get("nodeId")
                            _current_node["sceneId"] = payload.get("sceneId")
                            logger.debug("VR node updated: %s / %s",
                                         _current_node["nodeId"], _current_node["sceneId"])
                            continue

                        # image frame
                        if isinstance(payload, dict) and payload.get("type") == "image":
                            logger.debug(
                                "Received image chunk: %d base64 chars",
                                len(payload.get("data", "")),
                            )
                            image_data = base64.b64decode(payload["data"])
                            await video_input_queue.put(image_data)
                            continue

                        # clientContent: text sent by browser sendText()
                        if isinstance(payload, dict) and "clientContent" in payload:
                            cc = payload["clientContent"]
                            for turn in cc.get("turns") or []:
                                for part in turn.get("parts") or []:
                                    actual = (part.get("text") or "").strip()
                                    if actual:
                                        await text_input_queue.put(actual)
                            continue

                    except (json.JSONDecodeError, Exception):
                        pass

                    await text_input_queue.put(text)

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error("Error receiving from client: %s", e)

    receive_task = asyncio.create_task(receive_from_client())

    async def run_session():
        async for event in gemini_client.start_session(
            audio_input_queue=audio_input_queue,
            video_input_queue=video_input_queue,
            text_input_queue=text_input_queue,
            audio_output_callback=audio_output_callback,
            audio_interrupt_callback=audio_interrupt_callback,
        ):
            if not event:
                continue

            if event.get("type") == "tool_call":
                name = event.get("name")

                # navigate_vr_scene → also push vr_navigate to client
                if name == "navigate_vr_scene":
                    result = event.get("result", {})
                    node_id = result.get("node_id") if isinstance(result, dict) else None
                    scene_id = (event.get("args") or {}).get("scene_id")
                    if node_id:
                        logger.info("Sending vr_navigate: nodeId=%s sceneId=%s", node_id, scene_id)
                        await websocket.send_json({
                            "type": "vr_navigate",
                            "nodeId": node_id,
                            "sceneId": scene_id,
                        })

                # add_to_memory → push memory_update to client for display
                elif name == "add_to_memory":
                    await websocket.send_json({
                        "type": "memory_update",
                        "memories": _session_mem.get_all(),
                    })

                # Forward the tool_call event for client-side logging in all cases
                await websocket.send_json(event)
            else:
                await websocket.send_json(event)

    try:
        await run_session()
    except Exception as e:
        import traceback

        logger.error(
            "Error in Gemini session: %s: %s\n%s",
            type(e).__name__,
            e,
            traceback.format_exc(),
        )
    finally:
        receive_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass


# ─── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}

"""
tools.py — VR navigation and assistant tools for Lâm Đồng AI chatbot.

Scene map is auto-loaded from pano2vr_new/data/scenes.json (single source of truth).
SCENE_MAP_JSON env var is only used as a fallback override.
"""

import json
import os
import time
from pathlib import Path

import httpx
from google.genai import types

def _find_scenes_json() -> Path | None:
    """Locate scenes.json. Checks in order:
      1. backend/data/scenes.json  (Docker container / self-contained)
      2. pano2vr_new/data/scenes.json  (local dev with pano2vr_new sibling)
    """
    local = Path(__file__).parent / "data" / "scenes.json"
    if local.exists():
        return local
    sibling = Path(__file__).parent.parent / "pano2vr_new" / "data" / "scenes.json"
    if sibling.exists():
        return sibling
    return None


def _load_scene_map() -> dict:
    """Build {scene_id: panoNodeId} map.

    Priority:
      1. backend/data/scenes.json or pano2vr_new/data/scenes.json
      2. SCENE_MAP_JSON env var  — override / fallback
    """
    scenes_path = _find_scenes_json()
    if scenes_path:
        try:
            data = json.loads(scenes_path.read_text(encoding="utf-8"))
            return {
                item["id"]: item["panoNodeId"]
                for item in data
                if "id" in item and "panoNodeId" in item
            }
        except Exception:
            pass
    # Fallback: env var
    scene_map_json = os.getenv("SCENE_MAP_JSON", "{}")
    try:
        return json.loads(scene_map_json)
    except json.JSONDecodeError:
        return {}


# ─── Known coordinates (mirrors frontend KNOWN_COORDS in LamDongGuide.tsx) ────
_KNOWN_COORDS: dict[str, dict] = {
    # Phan Thiết / Mũi Né (Bình Thuận)
    "mui-ke-ga":             {"lat": 10.740, "lng": 108.011},
    "nova-world-phan-thiet": {"lat": 10.853, "lng": 108.042},
    "movenpick-phan-thiet":  {"lat": 10.855, "lng": 108.046},
    "bai-bien-phan-thiet":   {"lat": 10.923, "lng": 108.116},
    "bai-bien-phu-hai":      {"lat": 10.932, "lng": 108.171},
    "sea-links-city":        {"lat": 11.017, "lng": 108.248},
    "bai-bien-ham-tien":     {"lat": 11.000, "lng": 108.235},
    "bien-bai-rang":         {"lat": 11.060, "lng": 108.276},
    "bai-bien-mui-ne":       {"lat": 11.067, "lng": 108.283},
    # Đà Lạt
    "toan-canh-da-lat":      {"lat": 11.940, "lng": 108.458},
    "trung-tam-da-lat":      {"lat": 11.941, "lng": 108.442},
    "quang-truong-lam-vien": {"lat": 11.934, "lng": 108.441},
    "ho-xuan-huong":         {"lat": 11.938, "lng": 108.443},
    "cho-da-lat":            {"lat": 11.942, "lng": 108.440},
    # Bảo Lộc
    "trung-tam-bao-loc":     {"lat": 11.545, "lng": 107.807},
    # Legacy IDs
    "ho-tuyen-lam":          {"lat": 11.917, "lng": 108.417},
    "da-lat":                {"lat": 11.940, "lng": 108.458},
    "langbiang":             {"lat": 12.050, "lng": 108.433},
    "pongour":               {"lat": 11.625, "lng": 108.133},
    "tinh-yeu":              {"lat": 11.958, "lng": 108.442},
}

# ─── Weather cache (shared across sessions, TTL 10 min) ───────────────────────
_weather_cache: dict[str, tuple[float, dict]] = {}
_WEATHER_TTL = 600


# ══════════════════════════════════════════════════════════════════════════════
#  navigate_vr_scene
# ══════════════════════════════════════════════════════════════════════════════

def navigate_vr_scene(scene_id: str) -> dict:
    """Navigate to a VR panorama scene by scene_id."""
    scene_map = _load_scene_map()
    node_id = scene_map.get(scene_id)
    if node_id is None:
        available = list(scene_map.keys())
        return {"error": f"Unknown scene_id '{scene_id}'. Available: {available}"}
    return {"result": "navigated", "node_id": node_id}


def build_navigate_tool() -> types.Tool:
    """Build the Gemini tool declaration for navigate_vr_scene."""
    scene_map = _load_scene_map()
    scene_ids = list(scene_map.keys())

    scene_id_schema = types.Schema(
        type=types.Type.STRING,
        description="ID định danh của điểm đến muốn chuyển tới",
    )
    if scene_ids:
        scene_id_schema = types.Schema(
            type=types.Type.STRING,
            description="ID định danh của điểm đến muốn chuyển tới",
            enum=scene_ids,
        )

    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="navigate_vr_scene",
                description=(
                    "Chuyển camera panorama đến một điểm đến cụ thể trong tour VR 360 Lâm Đồng. "
                    "Gọi hàm này khi người dùng yêu cầu xem hoặc đến một địa điểm."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={"scene_id": scene_id_schema},
                    required=["scene_id"],
                ),
            )
        ]
    )


# ══════════════════════════════════════════════════════════════════════════════
#  get_weather_for_scene
# ══════════════════════════════════════════════════════════════════════════════

async def get_weather_for_scene(scene_id: str) -> dict:
    """Fetch current weather and elevation from Open-Meteo for a scene."""
    coords = _KNOWN_COORDS.get(scene_id)
    if coords is None:
        return {
            "error": (
                f"Unknown scene_id '{scene_id}'. "
                f"Available: {list(_KNOWN_COORDS.keys())}"
            )
        }

    lat, lng = coords["lat"], coords["lng"]
    cache_key = f"{lat:.3f},{lng:.3f}"
    now = time.time()

    if cache_key in _weather_cache:
        ts, cached = _weather_cache[cache_key]
        if now - ts < _WEATHER_TTL:
            return cached

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lng}"
        f"&current=temperature_2m,weathercode,windspeed_10m,relativehumidity_2m"
        f"&timezone=auto&forecast_days=1"
    )
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(url)
            data = response.json()
        curr = data["current"]
        result = {
            "scene_id": scene_id,
            "temperature_celsius": curr["temperature_2m"],
            "humidity_percent": curr["relativehumidity_2m"],
            "windspeed_kmh": curr["windspeed_10m"],
            "elevation_meters": round(data.get("elevation", 0)),
            "weather_code": curr["weathercode"],
        }
        _weather_cache[cache_key] = (now, result)
        return result
    except Exception as e:
        return {"error": f"Không thể lấy thông tin thời tiết: {e}"}


def build_weather_tool() -> types.Tool:
    """Build the Gemini tool declaration for get_weather_for_scene."""
    scene_map_ids = list(_load_scene_map().keys())
    all_ids = list(dict.fromkeys(scene_map_ids + list(_KNOWN_COORDS.keys())))
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_weather_for_scene",
                description=(
                    "Lấy nhiệt độ hiện tại, độ ẩm, tốc độ gió và độ cao của một điểm đến. "
                    "Gọi khi người dùng hỏi về thời tiết, nhiệt độ, hoặc muốn biết độ cao."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "scene_id": types.Schema(
                            type=types.Type.STRING,
                            description=f"ID của điểm đến. Một trong: {', '.join(all_ids)}.",
                        )
                    },
                    required=["scene_id"],
                ),
            )
        ]
    )


# ══════════════════════════════════════════════════════════════════════════════
#  get_pano_nodeid  (stub — backend cannot query browser VR state)
# ══════════════════════════════════════════════════════════════════════════════

def get_pano_nodeid() -> dict:
    """Backend stub: browser VR state is unavailable in a voice-only session."""
    return {
        "error": (
            "Không thể xác định node VR trong phiên thoại không có trình duyệt. "
            "Tính năng này chỉ khả dụng khi sử dụng ứng dụng web VR360."
        )
    }


def build_get_pano_nodeid_tool() -> types.Tool:
    """Build the Gemini tool declaration for get_pano_nodeid."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_pano_nodeid",
                description=(
                    "Lấy node ID và scene ID của cảnh panorama VR mà du khách đang xem. "
                    "Gọi khi cần biết chính xác du khách đang đứng ở đâu trong không gian VR."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={},
                ),
            )
        ]
    )


# ══════════════════════════════════════════════════════════════════════════════
#  add_to_memory  (session-scoped — instantiate SessionMemory per WebSocket)
# ══════════════════════════════════════════════════════════════════════════════

class SessionMemory:
    """Stores memory items added by the add_to_memory tool during a session."""

    def __init__(self):
        self._items: list[dict] = []

    def add_to_memory(self, memory: str, emoji: str = "📝") -> dict:
        self._items.append({"memory": memory, "emoji": emoji})
        return {"success": True, "total": len(self._items)}

    def get_all(self) -> list[dict]:
        return list(self._items)


def build_add_memory_tool() -> types.Tool:
    """Build the Gemini tool declaration for add_to_memory."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="add_to_memory",
                description=(
                    "Lưu một ghi chú về sở thích hoặc thông tin quan trọng của du khách "
                    "trong phiên trò chuyện này. Gọi bất cứ khi nào du khách tiết lộ thông tin "
                    "hữu ích (ví dụ: muốn đến đâu, thích gì, không thích gì, dị ứng gì)."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "memory": types.Schema(
                            type=types.Type.STRING,
                            description="Nội dung ghi chú ngắn gọn (1-2 câu).",
                        ),
                        "emoji": types.Schema(
                            type=types.Type.STRING,
                            description="Emoji đại diện (ví dụ: 🏖️, ❤️, 🍜).",
                        ),
                    },
                    required=["memory"],
                ),
            )
        ]
    )

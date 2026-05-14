"""Quick test: connect to Gemini Live and see the real error."""
import asyncio, sys, os, logging, base64
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout,
                    format="%(levelname)s %(name)s: %(message)s")

from dotenv import load_dotenv
load_dotenv()

from gemini_live import GeminiLive
from tools import build_navigate_tool, navigate_vr_scene

client = GeminiLive(
    api_key=os.getenv("GEMINI_API_KEY"),
    model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-live-preview"),
    input_sample_rate=16000,
    system_instruction="You are a helpful assistant.",
    voice_name="Aoede",
    tools=[build_navigate_tool()],
    tool_mapping={"navigate_vr_scene": navigate_vr_scene},
)

async def run():
    q_audio, q_video, q_text = asyncio.Queue(), asyncio.Queue(), asyncio.Queue()
    # Feed one fake audio chunk so send_audio doesn't just wait
    await q_audio.put(bytes(256))
    async def on_audio(data): print(f"[AUDIO OUT] {len(data)} bytes")
    print("Connecting to Gemini Live...")
    try:
        count = 0
        async for event in client.start_session(q_audio, q_video, q_text, on_audio):
            count += 1
            print(f"EVENT #{count}:", event)
            if count >= 5:
                break
    except Exception as e:
        import traceback
        print("SESSION ERROR:", type(e).__name__, e)
        traceback.print_exc()

asyncio.run(run())

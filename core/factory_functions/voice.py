"""Factory function: voice — speech-to-text and text-to-speech.

Actions: transcribe (audio file → text) and speak (text → audio file).
Uses whisper for STT (auto-installs via openai-whisper) and edge-tts for TTS.
"""
import json
import os
import subprocess
import sys
import tempfile

SPEC = {
    "description": "Voice I/O: transcribe audio files to text, or speak text to audio. transcribe: supports mp3, wav, m4a, ogg. speak: generates mp3 audio file. Both auto-install dependencies if missing.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "'transcribe' for speech-to-text, 'speak' for text-to-speech",
                "enum": ["transcribe", "speak"],
            },
            "audio_path": {
                "type": "string",
                "description": "Path to the audio file to transcribe (for transcribe action)",
            },
            "text": {
                "type": "string",
                "description": "Text to convert to speech (for speak action). Max 3000 chars.",
            },
            "language": {
                "type": "string",
                "description": "Language code for transcription (e.g. 'en', 'cs', 'auto'). Default 'auto'.",
            },
        },
        "required": ["action"],
    },
}


def _ensure_package(pkg_name: str, import_name: str | None = None) -> bool:
    import_name = import_name or pkg_name
    try:
        __import__(import_name)
        return True
    except ImportError:
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg_name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False


def _transcribe(audio_path: str, language: str) -> dict:
    if not os.path.exists(audio_path):
        return {"success": False, "error": f"Audio file not found: {audio_path}"}

    if not _ensure_package("openai-whisper", "whisper"):
        return {"success": False, "error": "Failed to install openai-whisper. Try: pip install openai-whisper"}

    import whisper
    try:
        model = whisper.load_model("base")
        lang = None if language == "auto" else language
        result = model.transcribe(audio_path, language=lang)
        return {
            "success": True,
            "text": result["text"].strip(),
            "language": result.get("language", "unknown"),
            "segments_count": len(result.get("segments", [])),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _speak(text: str) -> dict:
    if not text or not text.strip():
        return {"success": False, "error": "No text provided"}

    if len(text) > 3000:
        text = text[:3000]

    if not _ensure_package("edge-tts", "edge_tts"):
        return {"success": False, "error": "Failed to install edge-tts. Try: pip install edge-tts"}

    try:
        import edge_tts
        import asyncio

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3", prefix="cell_voice_")
        tmp.close()

        async def _do():
            communicate = edge_tts.Communicate(text, voice="en-US-JennyNeural")
            await communicate.save(tmp.name)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _do())
                    future.result(timeout=60)
            else:
                asyncio.run(_do())
        except RuntimeError:
            asyncio.run(_do())

        return {
            "success": True,
            "file_path": tmp.name,
            "format": "mp3",
            "chars": len(text),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def run(**kwargs):
    action = kwargs["action"]

    if action == "transcribe":
        result = _transcribe(
            kwargs.get("audio_path", ""),
            kwargs.get("language", "auto"),
        )
    elif action == "speak":
        result = _speak(kwargs.get("text", ""))
    else:
        result = {"success": False, "error": f"Unknown action: {action}"}

    return json.dumps(result, ensure_ascii=False)

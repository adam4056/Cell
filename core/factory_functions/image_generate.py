"""Factory function: image_generate — generate images via DALL-E or Stability AI.

Uses OpenAI DALL-E 3 by default (via the configured OpenAI provider).
Stores images to a temp file and returns the path.
"""
import base64
import json
import os
import tempfile

SPEC = {
    "description": "Generate an image from a text prompt using DALL-E or Stability AI. The image is saved to a temporary file. Returns success, file path, and optional base64 preview. The user's OpenAI API key is used for DALL-E; for Stability, set STABILITY_API_KEY via smart_interaction.",
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Image generation prompt in English. Be detailed about style, composition, lighting, colors. Example: 'A futuristic city skyline at sunset, cyberpunk style, neon lights reflecting on wet streets, 4K photorealistic'",
            },
            "size": {
                "type": "string",
                "description": "Image size. DALL-E: '1024x1024', '1792x1024', '1024x1792'. Default '1024x1024'.",
            },
            "quality": {
                "type": "string",
                "description": "DALL-E quality: 'standard' or 'hd'. Default 'standard'.",
            },
        },
        "required": ["prompt"],
    },
}


def run(**kwargs):
    prompt = kwargs["prompt"]
    size = kwargs.get("size", "1024x1024")
    quality = kwargs.get("quality", "standard")

    try:
        import requests
        import yaml

        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(root, "config.yaml")
        cfg = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}

        providers = cfg.get("providers", {})
        openai_cfg = providers.get("openai", {})
        api_key = openai_cfg.get("api_key", "")
        api_base = openai_cfg.get("api_base", "https://api.openai.com/v1")

        if not api_key:
            keys_path = os.path.join(os.path.expanduser("~"), ".cell-2", "keys.json")
            if os.path.exists(keys_path):
                with open(keys_path, "r", encoding="utf-8") as f:
                    keys = json.load(f)
                api_key = keys.get("openai", {}).get("api_key", "") or keys.get("api_key", "")

        if not api_key:
            return json.dumps({
                "success": False,
                "error": "No OpenAI API key configured. Set it in config.yaml under providers.openai.api_key or use smart_interaction to request it.",
            })

        r = requests.post(
            f"{api_base}/images/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": size,
                "quality": quality,
            },
            timeout=90,
        )
        data = r.json()

        if not r.ok:
            return json.dumps({"success": False, "error": data.get("error", {}).get("message", str(data))})

        image_url = data["data"][0].get("url", "")
        revised_prompt = data["data"][0].get("revised_prompt", prompt)

        img_r = requests.get(image_url, timeout=30)
        ext = ".png"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext, prefix="cell_image_")
        tmp.write(img_r.content)
        tmp.close()

        b64 = base64.b64encode(img_r.content).decode("ascii")
        return json.dumps({
            "success": True,
            "file_path": tmp.name,
            "revised_prompt": revised_prompt,
            "image_base64": b64,
            "mime_type": "image/png",
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

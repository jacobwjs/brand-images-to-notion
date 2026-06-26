#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.4.0"]
# ///
"""Brand Images -> Notion MCP server.

A two-step creative pipeline that Claude orchestrates:

  1. generate_brand_image   render a PNG with OpenAI's gpt-image-2, either through
                            the OpenAI Images API directly or via the Codex CLI.
  2. upload_image_to_notion attach one or more local images to a Notion page as
                            native (Notion-hosted) image blocks - no public URL,
                            no manual drag-and-drop.
  3. check_setup            report which backends and credentials are ready
                            (read-only; safe to call any time).

Claude does the creative work (reading a brand guide, writing the prompt). These
tools just do the two things Claude can't do natively: call the image model and
push bytes into Notion.

Secrets are read from the environment or a `.env` file sitting next to this script:
  OPENAI_API_KEY   for backend="openai"      (https://platform.openai.com/api-keys)
  NOTION_TOKEN     for upload_image_to_notion (https://www.notion.so/my-integrations)
The Codex backend needs no key here - it uses your existing `codex login`.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Literal

import urllib.error
import urllib.request

from mcp.server.fastmcp import FastMCP

# --------------------------------------------------------------------------- #
# Config / secrets
# --------------------------------------------------------------------------- #

def _load_dotenv() -> None:
    """Load KEY=VALUE pairs from a .env next to this script (without overriding
    anything already present in the real environment)."""
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()

OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"
NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
IMAGE_MODEL = "gpt-image-2"
VALID_SIZES = {"1024x1024", "1024x1536", "1536x1024", "auto"}

mcp = FastMCP("brand-images")


# --------------------------------------------------------------------------- #
# Small HTTP helpers (stdlib only - keeps the dependency surface tiny)
# --------------------------------------------------------------------------- #

def _http_json(method: str, url: str, headers: dict, body: dict | None = None, timeout: int = 300) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise RuntimeError(f"{method} {url} -> HTTP {e.code}: {detail}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"{method} {url} failed: {e.reason}") from None


def _notion_headers() -> dict:
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "NOTION_TOKEN is not set. Create an internal integration at "
            "https://www.notion.so/my-integrations, copy its secret, and put it in the "
            ".env file next to server.py as NOTION_TOKEN=ntn_..."
        )
    return {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION, "Content-Type": "application/json"}


def _notion_page_id(page: str) -> str:
    """Accept a Notion page URL or raw id and return a dashed UUID."""
    tail = page.strip().split("?")[0].rstrip("/").split("/")[-1]
    hexpart = "".join(c for c in tail if c in "0123456789abcdefABCDEF")[-32:]
    if len(hexpart) != 32:
        raise ValueError(f"Could not find a 32-char page id in: {page!r}")
    h = hexpart.lower()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


# --------------------------------------------------------------------------- #
# Image generation backends
# --------------------------------------------------------------------------- #

def _generate_openai(prompt: str, size: str, quality: str) -> bytes:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "OPENAI_API_KEY is not set. Add it to the .env file next to server.py "
            "(https://platform.openai.com/api-keys), or call generate_brand_image with "
            'backend="codex" to use the Codex CLI instead.'
        )
    payload = {"model": IMAGE_MODEL, "prompt": prompt, "size": size, "n": 1}
    if quality and quality != "auto":
        payload["quality"] = quality
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    resp = _http_json("POST", OPENAI_IMAGES_URL, headers, payload, timeout=300)
    try:
        return base64.b64decode(resp["data"][0]["b64_json"])
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected OpenAI image response: {json.dumps(resp)[:500]}") from e


def _generate_codex(prompt: str, out_path: Path, size: str) -> None:
    """Drive the Codex CLI `$imagegen` skill. Forbids any code-rendered fallback so
    the deliverable is always the raw gpt-image-2 output."""
    codex = shutil.which("codex")
    if not codex:
        raise ValueError(
            "The `codex` CLI was not found on PATH. Install it (npm install -g @openai/codex; "
            'codex login), or call generate_brand_image with backend="openai" instead.'
        )
    out_dir = str(out_path.resolve().parent)
    fname = out_path.name
    full_prompt = (
        f"{prompt}\n\n"
        "Use the imagegen skill: $imagegen\n"
        "HARD CONSTRAINTS:\n"
        "- Generate the image ONLY with the built-in image_gen tool (OpenAI gpt-image-2).\n"
        "- Do NOT hand-draw or synthesize with Pillow/PIL, matplotlib, SVG, or HTML/CSS. "
        "The deliverable MUST be the raw output of the image model.\n"
        "- If text rendering is imperfect, that is acceptable - do NOT substitute a code-rendered replacement.\n"
        f"- Aim for a {size} aspect where possible.\n"
        f"- Save the model's selected output into this workspace at ./{fname} "
        "(copy it out of the default generated_images path). Report the final saved path."
    )
    cmd = [
        codex, "exec", "--skip-git-repo-check", "-C", out_dir,
        "-c", "approval_policy=never", "-c", "sandbox_mode=workspace-write",
        full_prompt,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Codex generation failed (exit {e.returncode}):\n{e.stderr[-1500:]}") from None
    except subprocess.TimeoutExpired:
        raise RuntimeError("Codex generation timed out after 600s.") from None


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #

@mcp.tool()
def generate_brand_image(
    prompt: str,
    output_path: str,
    backend: Literal["openai", "codex"] = "openai",
    size: Literal["1024x1024", "1024x1536", "1536x1024", "auto"] = "1024x1536",
    quality: Literal["low", "medium", "high", "auto"] = "high",
) -> dict:
    """Generate a single image with OpenAI's gpt-image-2 and save it to disk.

    Claude should construct `prompt` itself from the brand/design guide: include the
    exact palette (hex), fonts, logo description, layout, the verbatim text to render,
    and an instruction to render no other text. Keep brand voice in the prompt.

    Args:
        prompt: The full image-generation prompt (Claude writes this).
        output_path: Where to save the PNG (absolute, or relative to the server's cwd).
        backend: "openai" calls the Images API directly (needs OPENAI_API_KEY).
                 "codex" drives the Codex CLI `$imagegen` skill (needs `codex login`).
        size: Output size. "1024x1536" (portrait) suits most infographics.
        quality: Rendering quality for the openai backend.

    Returns a dict with the saved path, backend, model, and file size in bytes.
    Note: image models occasionally reinterpret logos or garble small text - if so,
    just call this again (each run differs) or refine one detail and re-run.
    """
    if not prompt.strip():
        raise ValueError("prompt is empty.")
    if size not in VALID_SIZES:
        raise ValueError(f"size must be one of {sorted(VALID_SIZES)}.")

    out = Path(output_path).expanduser()
    if not out.is_absolute():
        out = Path.cwd() / out
    out.parent.mkdir(parents=True, exist_ok=True)

    if backend == "openai":
        data = _generate_openai(prompt, size, quality)
        out.write_bytes(data)
    elif backend == "codex":
        _generate_codex(prompt, out, size)
        if not out.exists():
            raise RuntimeError(
                f"Codex finished but no file was found at {out}. The model may have saved "
                "elsewhere; try the openai backend or check the Codex output."
            )
    else:
        raise ValueError('backend must be "openai" or "codex".')

    return {
        "saved_path": str(out.resolve()),
        "backend": backend,
        "model": IMAGE_MODEL,
        "size_bytes": out.stat().st_size,
    }


@mcp.tool()
def upload_image_to_notion(page: str, image_path: str, caption: str = "") -> dict:
    """Upload a local image to a Notion page as a native image block.

    Uses Notion's File Upload API (create -> send -> attach), so the file is hosted
    privately by Notion. Requires NOTION_TOKEN and that the target page has been shared
    with that integration (page ••• -> Connections -> add the integration).

    Args:
        page: Notion page URL or id to append the image to.
        image_path: Path to a local image file (PNG/JPG/GIF/WebP).
        caption: Optional caption shown under the image.

    Returns a dict with the page id and the uploaded file's id.
    """
    src = Path(image_path).expanduser()
    if not src.is_absolute():
        src = Path.cwd() / src
    if not src.exists():
        raise ValueError(f"Image not found: {src}")

    page_id = _notion_page_id(page)

    # 1) create the file upload
    upload_id = _http_json(
        "POST", f"{NOTION_API}/file_uploads", _notion_headers(),
        {"mode": "single_part", "filename": src.name},
    )["id"]

    # 2) send the bytes (multipart/form-data)
    boundary = f"----brandimg{uuid.uuid4().hex}"
    ctype = mimetypes.guess_type(str(src))[0] or "application/octet-stream"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{src.name}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode() + src.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    send_headers = {
        "Authorization": _notion_headers()["Authorization"],
        "Notion-Version": NOTION_VERSION,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    send_req = urllib.request.Request(
        f"{NOTION_API}/file_uploads/{upload_id}/send", data=body, headers=send_headers, method="POST"
    )
    try:
        with urllib.request.urlopen(send_req, timeout=300) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Notion send failed: HTTP {e.code}: {e.read().decode(errors='replace')}") from None

    # 3) attach as an image block (must happen within 1 hour of upload)
    image_block: dict = {
        "object": "block",
        "type": "image",
        "image": {"type": "file_upload", "file_upload": {"id": upload_id}},
    }
    if caption:
        image_block["image"]["caption"] = [{"type": "text", "text": {"content": caption}}]
    _http_json(
        "PATCH", f"{NOTION_API}/blocks/{page_id}/children", _notion_headers(),
        {"children": [image_block]},
    )

    return {"page_id": page_id, "file_upload_id": upload_id, "uploaded": src.name}


@mcp.tool()
def check_setup() -> dict:
    """Report which backends and credentials are ready. Read-only; safe to call any time.

    Use this right after setup to confirm the friend's machine is ready before
    generating anything.
    """
    return {
        "openai_api_key_present": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
        "notion_token_present": bool(os.environ.get("NOTION_TOKEN", "").strip()),
        "codex_cli_available": shutil.which("codex") is not None,
        "image_model": IMAGE_MODEL,
        "notes": (
            "Need at least one image backend: OPENAI_API_KEY (backend='openai') or the "
            "codex CLI (backend='codex'). NOTION_TOKEN is required for uploads, and the "
            "target page must be shared with the integration."
        ),
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

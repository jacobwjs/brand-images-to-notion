# CLAUDE.md — operating guide for this repo

This repo is an MCP server that lets you (Claude) **generate on-brand images with
OpenAI's gpt-image-2 and upload them into Notion**. The human you're working with may
not be technical — drive the whole flow for them and explain each step plainly.

You are the orchestrator. The MCP server gives you three tools:
`generate_brand_image`, `upload_image_to_notion`, and `check_setup`. Everything else
(reading the brand guide, writing the image prompt) is your job.

---

## Part 1 — Setting up (do this once, when the user says "set up this repo")

Run these steps yourself, explaining as you go. Ask for secrets when you reach them.

1. **Confirm `uv` is installed** (it launches the server with no manual pip step):
   - Check: `command -v uv`
   - If missing, install it: `curl -LsSf https://astral.sh/uv/install.sh | sh`
     (or `brew install uv`). Then confirm `uv --version`.
   - Fallback if the user can't/won't use uv: `pip install mcp` and change `.mcp.json`
     to `"command": "python3", "args": ["server.py"]`.

2. **Create the `.env`**: copy `.env.example` to `.env`. Then collect the secrets the
   user needs and write them into `.env` (never echo them back, never commit them):
   - `OPENAI_API_KEY` — for the recommended `openai` backend. From
     https://platform.openai.com/api-keys
   - `NOTION_TOKEN` — required for uploading. Walk them through:
     create an internal integration at https://www.notion.so/my-integrations, copy the
     secret (starts with `ntn_`), and **share the target Notion page with it**
     (page → ••• → Connections → add the integration). Uploads fail without this share.
   - The `codex` backend needs no key here — just `codex login` once in a terminal.

3. **Load the server**: the committed `.mcp.json` registers it automatically, but
   Claude Code only reads MCP config and `.env` at startup. Tell the user to **restart
   their Claude Code session / reopen this folder**, approve the `brand-images` server
   when prompted, then come back.

4. **Verify**: call `check_setup`. Confirm at least one image backend and the Notion
   token are present before generating anything real.

---

## Part 2 — Making an image and putting it in Notion

When the user gives you a brand/design guide and an ask (e.g. "make an infographic
about X and put it in our Notion"):

1. **Read the brand guide.** Extract the palette (hex codes), fonts, logo description,
   and the brand voice. ⚠️ **The file must live in a normal local folder** (Desktop,
   Downloads, this repo). macOS blocks reading files inside Google Drive / iCloud
   **`CloudStorage/`** folders — if the guide is there, ask the user to drag a copy out
   first. (Symptom if ignored: `Operation not permitted` on read.)

2. **Write the prompt yourself** and pass it to `generate_brand_image`. A good prompt
   names: exact hex colors, the two fonts, the logo, the layout top-to-bottom, the
   **verbatim text to render**, and "render no other text." Keep the brand's voice in
   any copy you invent. Save to a path in this repo or a folder the user names.
   - Default `backend="openai"`, `size="1024x1536"` for portrait infographics.
   - Use `backend="codex"` only if the user asks for it (needs `codex login`).

3. **Inspect the result.** Open the saved PNG. Image models reinterpret logos and
   sometimes garble small text — if that happens, **re-run** (each run differs) or
   refine one detail and regenerate. Never substitute a hand-coded/SVG image; the
   deliverable is the gpt-image-2 output.

4. **Upload to Notion** with `upload_image_to_notion(page=<url>, image_path=<png>,
   caption=...)`. The image lands as a native, Notion-hosted block. Confirm the page
   URL is one shared with the integration.

5. **Offer variants.** If the user wants options, generate 2+ with genuinely different
   creative directions (e.g. light editorial vs. dark mode), not minor tweaks.

---

## Hard-won rules (don't relearn these)

- **gpt-image-2 only, never a code-drawn fallback.** If a render's text is imperfect,
  re-run — do not "fix" it by drawing the image with Pillow/SVG/HTML.
- **CloudStorage is unreadable** to this toolchain — keep brand files in a plain local
  folder.
- **Notion needs the page shared with the integration**, and uploaded files must be
  attached within ~1 hour (the tool does this immediately, so it's fine).
- **Treat tokens as secrets.** Keep them in `.env`; suggest rotating any token that
  ends up pasted into a chat.
- **"EY"-style trademark caution:** when an image references another company, use their
  name as plain text only — don't reproduce their logo.

# Brand Images → Notion

Generate **on-brand images with OpenAI's gpt-image-2** and drop them straight into a
**Notion page** — all by chatting with Claude. You bring a brand/design guide and an
idea ("make me an infographic about X"); Claude reads the guide, writes the image
prompt, renders it, and uploads the result into Notion as a real image block. No public
image hosting, no manual drag-and-drop.

It's a small [MCP](https://modelcontextprotocol.io) server with three tools that
Claude drives:

| Tool | What it does |
|------|--------------|
| `generate_brand_image` | Renders a PNG with gpt-image-2 — via the OpenAI API (default) or the Codex CLI. |
| `upload_image_to_notion` | Uploads a local image into a Notion page (Notion-hosted, private). |
| `check_setup` | Reports which keys/backends are ready. |

---

## Quick start (no coding required)

You'll do everything by talking to **Claude Code** (the CLI, the desktop app, or the
VS Code extension).

1. **Get the repo onto your machine.** In Claude, say:
   > Clone `https://github.com/jacobwjs/brand-images-to-notion` and open it.

2. **Let Claude set it up.** Then say:
   > Set up this repo.

   Claude reads [`CLAUDE.md`](./CLAUDE.md) and walks you through it: installs `uv`,
   creates your `.env`, and asks you for two things —
   - an **OpenAI API key** (https://platform.openai.com/api-keys), and
   - a **Notion integration token** (https://www.notion.so/my-integrations) — Claude
     will explain how to make one and how to share your Notion page with it.

3. **Restart Claude Code** when it asks (so the server and your keys load), then say:
   > Run check_setup.

4. **Make something.** Point Claude at your brand guide and ask, e.g.:
   > Here's our brand guide `~/Desktop/brand.html`. Make a portrait infographic about
   > why Acme should hire us, and upload it to this Notion page: `<paste page URL>`.

That's it. Ask for "two different variants" any time you want options.

---

## What you need

- **Claude Code** (you're already using it).
- An **OpenAI API key** — for image generation. *(Or use the Codex CLI backend instead;
  run `codex login` once — no key needed.)*
- A **Notion integration token**, with your target page shared to it.
- Your **brand/design guide** in a normal local folder.
  ⚠️ Not inside Google Drive / iCloud "CloudStorage" folders — macOS blocks reading
  those. Drag a copy to your Desktop first if needed.

---

## Manual setup (for the technically curious)

```bash
# 1. Install uv (launches the server with no pip/venv juggling)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Configure secrets
cp .env.example .env        # then edit .env and fill in your keys

# 3. The server is registered via .mcp.json. Open the folder in Claude Code,
#    approve the "brand-images" server, restart, and ask Claude to run check_setup.
```

No-`uv` fallback: `pip install mcp`, then set `.mcp.json` to
`"command": "python3", "args": ["server.py"]`.

---

## How it works

1. Claude reads your brand guide and writes a detailed gpt-image-2 prompt (exact colors,
   fonts, logo, layout, verbatim text).
2. `generate_brand_image` renders it to a PNG.
3. `upload_image_to_notion` uses Notion's [File Upload API](https://developers.notion.com/docs/uploading-small-files)
   (`create → send → attach`) to post it as a native image block — privately hosted by
   Notion, no public URL.

## Notes & limits

- Image models occasionally reinterpret logos or garble small text. Just re-run (each
  run differs) or ask Claude to refine one detail. The output is always the real
  gpt-image-2 image — never a code-drawn substitute.
- Keep your tokens in `.env` (git-ignored). Rotate any token you paste into a chat.
- When an image references another company, use their name as text only — don't
  reproduce their logo.

## License

MIT — see [LICENSE](./LICENSE).

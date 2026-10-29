# F.R.I.D.A.Y.

A hybrid voice assistant. Say **"Hey Friday"**, and she listens, thinks with
**Claude Code**, and acts — on the web, through your MCP tools, and on **your
own computer** through a Python "hands" layer.

It joins two open projects into one:

| Part | Comes from | Does |
|---|---|---|
| **Face** — `src/` | jarvis (Aditya Dewaskar) | Holographic React + Three.js interface, wake word, speech in/out, blades (panels), hand tracking |
| **Brain** — `bridge/` | jarvis (Aditya Dewaskar) | Node bridge running Claude Code headless via the Agent SDK, with every MCP server you have configured |
| **Hands** — `hands/` | Mark LVI (FatihMakes) | Desktop actions served to the brain over MCP: apps, files, documents, settings, reminders, messages, memory, undo |

```
  ┌─ browser (face) ──────────┐  ws   ┌─ bridge (brain) ─────────────┐ stdio ┌─ hands (Python) ──────────┐
  │ "Hey Friday" wake word    │◄────► │ Claude Agent SDK = Claude    │◄────► │ open_app · file_controller│
  │ VAD → speech to text      │ 8787  │ Code, headless               │  MCP  │ file_processor · reminder │
  │ reactor UI, blades, HUD   │       │ your MCP servers (~/.claude) │       │ computer_settings · undo  │
  │ text to speech            │       │ permission gate (decideTool) │       │ memory_save / recall      │
  └───────────────────────────┘       └──────────────────────────────┘       └───────────────────────────┘
```

---

## Requirements

- **Claude Code CLI, installed and logged in.** The bridge borrows its login —
  no API key. The desktop app alone is not enough; install the CLI and log in once:
  ```bash
  npm install -g @anthropic-ai/claude-code
  claude
  ```
  (type `/login` inside it if it does not ask.)
- **Node.js 20+** and **Python 3.10+**.
- **Chrome or Edge**, in a real window (embedded previews block the microphone).
- Optional: **ElevenLabs** key for a better voice; a **free Gemini key** for the
  smart step in some hands tools (see below).

## Quick start

Full day-to-day instructions: **[GUIDE.md](GUIDE.md)**.

```bash
npm install
npm run hands:setup   # once: Python venv for the desktop hands
npm start             # brain + face together
```

Open http://localhost:5173 in Chrome, click **INITIALISE**, allow the
microphone, and say **"Hey Friday"**.

**macOS permissions.** For typing, clicking and screenshots, allow your terminal
under System Settings → Privacy & Security → **Accessibility** and **Screen
Recording**.

**Best voice on a Mac.** Install the free **Moira (Enhanced)** Irish voice:
System Settings → Accessibility → Spoken Content → System Voice → Manage Voices.
FRIDAY picks it automatically.

---

## The wake word

- **"Hey / Hi / OK Friday"** wakes her. "Friday" alone does not, so "file it by
  Friday" in a meeting stays quiet.
- **"Jarvis"** still works as an alias, with or without "hey".
- **Space** talks without the wake word; just speak to interrupt her.

## What the hands can do

| Tool | Free in read-only mode | Needs write mode |
|---|---|---|
| `memory_save` / `memory_recall` / `memory_forget` | ✔ | |
| `undo` (reverse the last file/setting change) | ✔ | |
| `open_app` (verifies the app really opened) | ✔ | |
| `open_url` (new browser tab, works without the extension) | ✔ | |
| `reminder`, `weather_report`, `web_search`, `youtube_video`, `flight_finder` | ✔ | |
| `file_processor` (PDF, Word, Excel, images) | ✔ | |
| `file_controller` | list, read, find, largest, disk_usage, info | create, move, copy, rename, delete, write, organise |
| `desktop_control` | current_wallpaper, list, stats | wallpaper, organise, clean |
| `computer_control` (type, click, screenshot) | | ✔ |
| `computer_settings` (volume, brightness, Wi-Fi…) | | ✔ |
| `send_message` | | ✔ |

Shutdown, restart and other irreversible actions are **always refused** — there
is no on-screen confirmation in this build, so they decline rather than run.

To allow the write column:

```bash
npm run bridge:writes
```

### Hybrid: the optional free Gemini key

Claude Code is the brain. Some hands tools also have a "smart step" built on
Gemini — web grounding, YouTube summaries, reading documents and images,
finding a button on screen. Get a free key at https://aistudio.google.com/apikey
and save it as `hands/config/api_keys.json`:

```json
{ "gemini_api_key": "YOUR_KEY" }
```

That file is gitignored. Without it, those tools say so and FRIDAY does the job
another way where she can.

### Adding a skill

Drop a `.py` file into `hands/actions/` with a module-level `TOOL` dict
(`name`, `description`, Gemini-style `parameters`, `handler`). It is discovered
at the next bridge start. Then add it to `HANDS_FREE` or `HANDS_READ` in
`bridge/server.mjs` if it should run without write mode.

---

## Configuration

| Variable | Default | Effect |
|---|---|---|
| `JARVIS_MODEL` | `claude-opus-5-5` | Model the brain runs |
| `JARVIS_EFFORT` | `high` | Reasoning effort |
| `JARVIS_ALLOW_WRITES` | off | `1` allows effectful tools |
| `JARVIS_BRIDGE_PORT` | `8787` | Bridge port |
| `ELEVENLABS_API_KEY` | — | Better voice + transcription |
| `JARVIS_VOICE_ID` | Alice | ElevenLabs voice |

Frontend options live in `.env.local` — see `.env.example`.

## Controls

| Key | Does |
|---|---|
| **Space** | Talk without the wake word |
| **V** | Cycle the browser voice |
| **Escape** | Stand down |
| **D** | Diagnostics |
| **T** | Audio self-test |

## Troubleshooting

- **"Not logged in · Please run /login"** — install the Claude Code CLI and log
  in (see Requirements).
- **Hands missing** — run `npm run hands:setup`, then restart the bridge.
- **Can't hear / no voice** — real Chrome window, microphone allowed; press **D**.

---

## Credits & licence

- Face and brain: **jarvis** by Aditya Dewaskar — MIT.
- Hands: **Mark LVI** by [FatihMakes](https://www.youtube.com/@FatihMakes) — CC BY-NC 4.0.

Because the hands are CC BY-NC 4.0, **this project as a whole is for
non-commercial use only.** See [LICENSE](LICENSE). Audio in `public/audio/`
ships for the demo; clear its rights before any other use.

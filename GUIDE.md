# Using FRIDAY

## One-time setup (already done on this Mac, except the two marked ✋)

1. `npm install` and `npm run hands:setup` — done.
2. Claude Code CLI — installed. ✋ **Log in once:** run `claude` in Terminal,
   choose a theme, then pick **Claude account with subscription** and finish
   the login in the browser. Type `/exit` when it says you're logged in.
3. ✋ **Mac permissions:** System Settings → Privacy & Security →
   - **Accessibility** → turn on **Terminal** (lets FRIDAY type, click, press keys)
   - **Screen Recording** → turn on **Terminal** (lets FRIDAY take screenshots)
   - **Microphone** → Chrome will ask the first time; click **Allow**.
4. Optional, recommended:
   - **Moira (Enhanced)** voice: System Settings → Accessibility → Spoken
     Content → System Voice → Manage Voices → English (Ireland) → Moira.
   - **Free Gemini key** (aistudio.google.com/apikey) saved as
     `hands/config/api_keys.json` → `{"gemini_api_key": "YOUR_KEY"}`.
     Unlocks reading PDFs/images, YouTube summaries and on-screen finding.

## Starting and stopping

- **Start:** double-click **Friday.command** on your Desktop. A Terminal window
  opens (leave it open) and Chrome opens the interface.
  - The first time, macOS may say it's from an unidentified developer:
    right-click the file → **Open** → **Open**.
- Click **INITIALISE**, allow the microphone, and say **"Hey Friday"**.
- **Stop:** press **Escape** to put her to sleep; close the Terminal window to
  shut her down completely.

The launcher starts **write mode**: she can move files, type, click and change
settings. For a look-but-don't-touch session, run `npm start` in the project
folder instead.

## Talking to her

- Say **"Hey Friday"**, then your request in the same breath, e.g.
  *"Hey Friday, open Excel."*
- After she answers she keeps listening for a follow-up — no need to repeat
  her name.
- **Interrupt** by simply talking over her.
- **Space bar** = talk without the wake word.
- She calls you **boss** and keeps answers short. Ask "explain in detail" when
  you want more — the detail goes on a panel on screen.

## Things to say

**Apps and the computer**
- "Open Tally / Excel / Chrome / WhatsApp."
- "Turn the volume down to thirty percent." · "Set brightness to max."
- "Take a screenshot and show me."
- "Type: Dear Sir, please find attached the audit report."
- "Press command S."

**Files**
- "What's in my Downloads folder?"
- "Find all PDFs with GST in the name."
- "Move the latest PDF in Downloads to Documents slash Audit."
- "What are the largest files on my Desktop?"
- "Organise my desktop." · "Undo that."

**Documents and work**
- "Read this PDF and summarise it: Downloads slash notice.pdf."
- "Open the Excel file client-list in Documents and tell me how many rows have
  pending status."
- "Draft a reply to a GST notice asking for fifteen days' extension." (it
  appears on a panel; say "copy it" or "type it" to use it)
- "What's the due date for GSTR-3B this month?"

**Web and research**
- "Search the latest CBDT circular on TDS."
- "Open the income tax e-filing site." (uses your real Chrome, already
  signed in, when the Claude extension is installed)
- "Summarise this YouTube video: …"

**Reminders and memory**
- "Remind me at five to call the Sharma client."
- "Remember that Ratan Sharma and Co's GSTIN is …" → later: "What's Ratan
  Sharma's GSTIN?"
- "What do you remember about me?" · "Forget the GSTIN."

**Messages** (write mode)
- "Send a WhatsApp to Rahul: the file is ready." — she says what she's about to
  send first; interrupt to stop it.

## Safety

- Shutdown/restart are always refused.
- "Undo" reverses her last file move/rename/create or setting change.
- Everything she remembers is in `hands/memory/long_term.json` on this Mac
  only (never committed to GitHub).
- Every request uses your Claude subscription.

## Keys

| Key | Does |
|---|---|
| Space | Talk without the wake word |
| Escape | Stand down |
| V | Change browser voice |
| D | Diagnostics (is she hearing me?) |
| T | Audio test |

## Troubleshooting

| Problem | Fix |
|---|---|
| She says "Not logged in" | Run `claude` in Terminal and log in |
| She looks alive but never answers | Must be a real Chrome window; check the Terminal window for errors |
| "Blocked: read-only mode" | You started with `npm start`; use the Desktop launcher |
| Typing/clicking does nothing | Accessibility permission for Terminal |
| Screenshot is black | Screen Recording permission for Terminal, then restart her |
| A tool says no Gemini key | Add the free key (setup step 4) or ignore |

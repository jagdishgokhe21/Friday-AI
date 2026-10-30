import { spawn } from 'node:child_process'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createInterface } from 'node:readline'

/**
 * Local speech-to-text: a client for hands/stt_worker.py.
 *
 * One worker lives as long as the bridge, because the model is the slow part
 * and it only has to load once. Requests sent while it loads simply wait in its
 * stdin. If it dies it is restarted on the next request, once, so a crash costs
 * one sentence; a worker that cannot start at all (faster-whisper missing, say)
 * marks the engine unavailable, and /health then sends the browser back to its
 * own recogniser instead of leaving her deaf.
 */

/** Generous, because the very first request can include downloading the model. */
const TIMEOUT_MS = 120_000

export function startWhisper(python, script) {
  let worker = null
  let failed = false
  let nextId = 1
  const pending = new Map()

  const settle = (id, fn, value) => {
    const entry = pending.get(id)
    if (!entry) return
    pending.delete(id)
    clearTimeout(entry.timer)
    entry[fn](value)
  }

  const boot = () => {
    const child = spawn(python, [script], { stdio: ['pipe', 'pipe', 'pipe'] })
    let answered = false
    worker = child
    child.stdin.on('error', () => {})
    child.stderr.on('data', (d) => {
      if (process.env.FRIDAY_DEBUG === '1') process.stderr.write(d)
    })
    createInterface({ input: child.stdout }).on('line', (line) => {
      let msg
      try {
        msg = JSON.parse(line)
      } catch {
        return
      }
      if (msg.ready) {
        answered = true
        console.log(`[friday] hearing via local Whisper (${msg.model})`)
        return
      }
      if (msg.error) settle(msg.id, 'reject', new Error(msg.error))
      else settle(msg.id, 'resolve', msg.text ?? '')
    })
    const down = () => {
      if (worker !== child) return
      worker = null
      if (!answered) {
        failed = true
        console.warn('[friday] local Whisper did not start — run npm run hands:setup')
      }
      for (const id of [...pending.keys()]) {
        settle(id, 'reject', new Error('the speech worker stopped'))
      }
    }
    child.on('exit', down)
    child.on('error', down)
  }

  boot()

  return {
    available: () => !failed,
    async transcribe(audio, contentType) {
      if (!worker) boot()
      const ext = contentType.includes('ogg') ? 'ogg' : contentType.includes('mp4') ? 'mp4' : 'webm'
      const dir = await mkdtemp(join(tmpdir(), 'friday-stt-'))
      const path = join(dir, `speech.${ext}`)
      try {
        await writeFile(path, audio)
        const id = nextId++
        return await new Promise((resolve, reject) => {
          const timer = setTimeout(
            () => settle(id, 'reject', new Error('transcription timed out')),
            TIMEOUT_MS,
          )
          pending.set(id, { resolve, reject, timer })
          worker.stdin.write(`${JSON.stringify({ id, path })}\n`)
        })
      } finally {
        await rm(dir, { recursive: true, force: true })
      }
    },
  }
}

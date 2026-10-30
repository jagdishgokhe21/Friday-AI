import { getMic } from './audio'

/**
 * Voice-activity detection and segment capture.
 *
 * This is the piece that makes the assistant reliable, and it exists because
 * the browser's SpeechRecognition does not. That API dies silently under
 * always-on use — Chrome throttles it, it stops firing events, and nothing you
 * can catch tells you it has gone deaf. Detecting that a human is speaking is
 * not a language problem, though; it is an energy problem, and energy on the
 * microphone signal is something we can measure ourselves, every frame, with no
 * black box that can quietly stop answering.
 *
 * So: a running-mean noise floor, a threshold above it, and a hysteresis gate.
 * When the signal crosses the threshold a fresh recorder starts; when it falls
 * quiet for long enough the recorder stops and hands back one self-contained
 * audio blob for the bridge to transcribe. The detection is instant and local
 * — that is what makes barge-in feel natural — and the words come back a moment
 * later from a real transcriber that cannot silently fail the way the browser
 * one did.
 *
 * Hearing himself is the one hard part. The microphone picks up FRIDAY's own
 * voice through the speakers, and raw energy cannot tell that from the user.
 * Two things handle it: getUserMedia is asked for echo cancellation, which
 * removes most of the playback, and while he is speaking the trigger threshold
 * is raised so the residue that leaks through does not cross it. A text check
 * after transcription is the final backstop, in voice.ts.
 */

export type VadHandlers = {
  /** The signal crossed into speech. Instant; this is the barge-in trigger. */
  onStart: () => void
  /** Speech ended. The blob is one complete, decodable audio file. */
  onEnd: (audio: Blob, ms: number) => void
  /** 0..1 smoothed input level, for the caption/orb while capturing. */
  onLevel: (v: number) => void
  /** Capture is impossible — no microphone, or no MediaRecorder support. */
  onError: (message: string) => void
}

export type Vad = {
  stop: () => void
  /** Raise the trigger bar while FRIDAY speaks, so his own playback leaking
   *  past echo cancellation does not register as the user talking. */
  setGuard: (on: boolean) => void
  live: () => boolean
  /** Live internals, for the diagnostics panel. */
  meter: () => { energy: number; floor: number; threshold: number; speaking: boolean }
}

// ---------------------------------------------------------------------------
// Tuning
// ---------------------------------------------------------------------------

/** How far above the noise floor the signal must rise to count as speech.
 *  The floor tracks the room, so this is a ratio, not an absolute level. */
const TRIGGER_OVER_FLOOR = 2
/** While she is speaking, demand this much more, so residual echo is ignored.
 *  Together with the line above this keeps the bar where it was for barge-in:
 *  only the resting bar came down, so that a soft voice registers. */
const GUARD_BOOST = 3.1
/** Falling back below trigger×this ends the segment. Hysteresis stops a single
 *  dip mid-word from cutting a sentence in half. The product with the trigger
 *  has to stay well above 1: at about 1 the bar sits on the room's own noise,
 *  the segment never ends, and she waits for silence that cannot arrive. */
const RELEASE_RATIO = 0.78

/** Sustained energy for this long confirms speech rather than a knock or click. */
const START_MS = 110
/**
 * Quiet for this long ends the SEGMENT — which is no longer the same thing as
 * ending the turn.
 *
 * It used to be both, which is why this number was impossible to set: long
 * enough not to clip someone thinking mid-sentence meant every completed
 * question also sat waiting for nothing. Deciding whether the thought is
 * actually finished now happens a layer up, on the words rather than the
 * energy (see makeAssembler in voice.ts), so this can go back to being what it
 * should always have been — a cheap "have they stopped making noise" — and the
 * shorter window gets the transcript moving sooner.
 */
const SILENCE_MS = 800
/** Nobody speaks one segment for this long; cut it and transcribe what we have. */
const MAX_MS = 20000

/** The floor adapts slowly upward (a fan spinning up) and quickly downward (a
 *  door closing), so it settles to genuine ambient noise without chasing speech. */
const FLOOR_UP = 0.0008
const FLOOR_DOWN = 0.02

/**
 * Software gain ahead of everything else, limited so a loud voice cannot clip.
 * A laptop mic set low delivers speech too faint for the detector and for the
 * transcriber alike. Noise rises with it, which is fine: the floor is relative.
 */
const MIC_GAIN = 4

/**
 * The recorder hears the signal this much later than the detector does.
 *
 * Speech only crosses the threshold partway into its first syllable, and the
 * recorder can only start after that. Delaying what it records means the audio
 * from just before the crossing is still on its way when it starts, so "Hey"
 * survives, and with it the wake phrase. Must stay below SILENCE_MS.
 */
const PRE_ROLL_S = 0.35

/** ≈21ms at 48kHz, about the rate the detector was tuned at. */
const FRAME_SAMPLES = 1024

function pickMime(): string {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
  ]
  for (const m of candidates) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(m)) {
      return m
    }
  }
  return ''
}

export async function startVad(h: VadHandlers): Promise<Vad> {
  let stream: MediaStream
  try {
    stream = await getMic()
  } catch (err) {
    h.onError(
      err instanceof DOMException && err.name === 'NotAllowedError'
        ? 'Microphone access denied — voice input is unavailable.'
        : 'No microphone available.',
    )
    return { stop: () => {}, setGuard: () => {}, live: () => false, meter: () => ({ energy: 0, floor: 0, threshold: 0, speaking: false }) }
  }

  if (typeof MediaRecorder === 'undefined') {
    h.onError('This browser cannot record audio — voice input is unavailable.')
    return { stop: () => {}, setGuard: () => {}, live: () => false, meter: () => ({ energy: 0, floor: 0, threshold: 0, speaking: false }) }
  }

  const mime = pickMime()
  const ctx = new AudioContext()
  // Some browsers start an AudioContext suspended even after a gesture; resume
  // is a no-op when it is already running.
  void ctx.resume()
  const source = ctx.createMediaStreamSource(stream)
  const boost = ctx.createGain()
  boost.gain.value = MIC_GAIN
  const limiter = ctx.createDynamicsCompressor()
  limiter.threshold.value = -6
  limiter.ratio.value = 20
  const preRoll = ctx.createDelay(1)
  preRoll.delayTime.value = PRE_ROLL_S
  const recorded = ctx.createMediaStreamDestination()
  source.connect(boost)
  boost.connect(limiter)
  limiter.connect(preRoll)
  preRoll.connect(recorded)

  // The detector runs on the audio clock, not on requestAnimationFrame. Animation
  // frames stop when the tab is behind another window, which would leave her
  // deaf the moment she opened Excel for you. The node has to reach the output
  // to be driven at all, hence the silent gain after it.
  const frames = ctx.createScriptProcessor(FRAME_SAMPLES, 1, 1)
  const mute = ctx.createGain()
  mute.gain.value = 0
  limiter.connect(frames)
  frames.connect(mute)
  mute.connect(ctx.destination)

  let stopped = false
  let guard = false
  let floor = 0.01
  let smoothEnergy = 0
  let threshold = 0

  // Segment state.
  let recorder: MediaRecorder | null = null
  let parts: Blob[] = []
  let armedAt = 0 // energy first rose; recording may be pre-rolling
  let speaking = false
  let speechStartedAt = 0
  let lastLoud = 0

  const rms = (buf: Float32Array): number => {
    let sum = 0
    for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i]
    return Math.sqrt(sum / buf.length)
  }

  const startRecorder = () => {
    parts = []
    try {
      recorder = mime
        ? new MediaRecorder(recorded.stream, { mimeType: mime })
        : new MediaRecorder(recorded.stream)
    } catch {
      recorder = new MediaRecorder(recorded.stream)
    }
    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size) parts.push(e.data)
    }
    recorder.start()
  }

  const discardRecorder = () => {
    if (!recorder) return
    try {
      recorder.ondataavailable = null
      if (recorder.state !== 'inactive') recorder.stop()
    } catch {
      /* already gone */
    }
    recorder = null
    parts = []
  }

  const endSegment = () => {
    const rec = recorder
    const startedAt = speechStartedAt
    speaking = false
    speechStartedAt = 0
    if (!rec) return
    recorder = null

    const finalise = () => {
      const type = rec.mimeType || mime || 'audio/webm'
      const blob = new Blob(parts, { type })
      parts = []
      const ms = startedAt ? performance.now() - startedAt : 0
      h.onEnd(blob, ms)
    }
    rec.onstop = finalise
    try {
      if (rec.state !== 'inactive') rec.stop()
      else finalise()
    } catch {
      finalise()
    }
  }

  frames.onaudioprocess = (e) => {
    if (stopped) return

    const energy = rms(e.inputBuffer.getChannelData(0))
    smoothEnergy += (energy - smoothEnergy) * 0.5
    h.onLevel(Math.min(1, smoothEnergy * 12))

    // Adapt the floor only when we are confident this is not speech.
    if (!speaking && armedAt === 0) {
      const rate = smoothEnergy > floor ? FLOOR_UP : FLOOR_DOWN
      floor += (smoothEnergy - floor) * rate
      floor = Math.max(floor, 0.0015)
    }

    threshold = floor * TRIGGER_OVER_FLOOR * (guard ? GUARD_BOOST : 1)
    const release = threshold * RELEASE_RATIO
    const now = performance.now()

    if (!speaking) {
      if (smoothEnergy > threshold) {
        if (armedAt === 0) {
          // Onset: start recording immediately so the first phoneme is captured,
          // before we have even confirmed this is speech. If it turns out to be
          // a blip, the recorder is discarded and nothing was lost.
          armedAt = now
          startRecorder()
        } else if (now - armedAt >= START_MS) {
          // Confirmed. This is the moment barge-in fires.
          speaking = true
          speechStartedAt = armedAt
          lastLoud = now
          h.onStart()
        }
      } else if (armedAt !== 0) {
        // Rose and fell without confirming — a knock, a click, a lip smack.
        armedAt = 0
        discardRecorder()
      }
    } else {
      if (smoothEnergy > release) lastLoud = now
      const quietFor = now - lastLoud
      const runFor = now - speechStartedAt
      if (quietFor >= SILENCE_MS || runFor >= MAX_MS) {
        armedAt = 0
        endSegment()
      }
    }
  }

  return {
    stop: () => {
      stopped = true
      frames.onaudioprocess = null
      discardRecorder()
      try {
        source.disconnect()
        void ctx.close()
      } catch {
        /* noop */
      }
    },
    setGuard: (on) => {
      guard = on
    },
    live: () => !stopped,
    meter: () => ({ energy: smoothEnergy, floor, threshold, speaking }),
  }
}

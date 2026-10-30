"""
FRIDAY's ears — Whisper on this machine, as a long-lived worker.

The bridge spawns one of these and keeps it, because loading the model takes a
few seconds and a transcription takes about one. It reads one JSON request per
line on stdin, {"id": 1, "path": "/tmp/…/speech.webm"}, and answers on stdout,
{"id": 1, "text": "…"}. Nothing leaves the computer and no key is needed.

WHY THIS AND NOT CHROME'S RECOGNISER
    Chrome's SpeechRecognition captures the microphone itself, so nothing can be
    done to quiet speech before it hears it, and it runs on a server that cannot
    be told what words to expect. Here the browser boosts the signal first and
    the model is told the vocabulary below.

THE GPU, WHEN THERE IS ONE
    On Apple Silicon this runs on the GPU through MLX, which took a sentence
    from 2.5-8 seconds to 0.7 on an 8GB M1 with the interface running. The CPU
    has nothing to spare there: the slow cores are busy with the 3D scene, and
    adding threads made it worse. Elsewhere it falls back to faster-whisper.
    MLX has no silence filter of its own and invents sentences without one, so
    faster-whisper's speech detector runs first on both paths.

THE PROMPT IS ONLY A LIST OF TERMS
    Whisper is biased towards words it has just been shown, which is how "GSTR"
    survives an Indian accent. But on a faint or clipped sound it recites the
    prompt back as if it had been said. A sentence came back as a sentence and
    went to the brain as a question, so the prompt is bare terms, never holds
    the wake phrase, and anything that is mostly the prompt is thrown away.
"""
from __future__ import annotations

import json
import os
import platform
import re
import sys

# stdout is the protocol. Anything a library prints goes to stderr instead.
_OUT = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8")
os.dup2(2, 1)
sys.stdout = sys.stderr

import numpy as np  # noqa: E402
from faster_whisper import WhisperModel  # noqa: E402
from faster_whisper.audio import decode_audio  # noqa: E402
from faster_whisper.vad import VadOptions, get_speech_timestamps  # noqa: E402

MODEL = os.environ.get("FRIDAY_WHISPER_MODEL", "small.en")

_PROMPT = (
    "GST, GSTR-1, GSTR-3B, GSTIN, TDS, ITR, CBDT, PAN, Aadhaar, Tally, Excel, "
    "audit, balance sheet, rupees, lakh, crore."
)
_PROMPT_WORDS = set(re.findall(r"[a-z0-9-]+", _PROMPT.lower()))

# The browser has already decided someone is talking; this removes what it
# cannot, and is kept sensitive so that soft speech survives.
_VAD = VadOptions(threshold=0.25, min_silence_duration_ms=600)

# Above this the model itself is saying it heard no speech.
_NO_SPEECH = 0.6

# Below this the model is guessing, which is what recitation looks like.
_MIN_LOGPROB = -1.0


def _is_recitation(text: str) -> bool:
    """Three or more words, and most of them are from the prompt."""
    words = re.findall(r"[a-z0-9-]+", text.lower())
    if len(words) < 3:
        return False
    return sum(w in _PROMPT_WORDS for w in words) / len(words) >= 0.6


def _send(payload: dict) -> None:
    _OUT.write(json.dumps(payload) + "\n")
    _OUT.flush()


def _keep(segments) -> str:
    """The text of the segments the model itself believes in."""
    text = " ".join(
        seg["text"].strip()
        for seg in segments
        if seg["no_speech_prob"] < _NO_SPEECH and seg["avg_logprob"] > _MIN_LOGPROB
    ).strip()
    return "" if _is_recitation(text) else text


def _gpu_engine():
    """Whisper on the Apple GPU, or None where that is not available."""
    if sys.platform != "darwin" or platform.machine() != "arm64":
        return None
    try:
        import mlx_whisper
    except Exception as err:
        print(f"[stt] no GPU engine: {err}", file=sys.stderr)
        return None
    repo = f"mlx-community/whisper-{MODEL}-mlx"

    def run(audio) -> str:
        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=repo,
            language="en",
            initial_prompt=_PROMPT,
            # Each request is one utterance, so nothing carries over.
            condition_on_previous_text=False,
        )
        return _keep(result["segments"])

    return run


def _cpu_engine():
    model = WhisperModel(MODEL, device="cpu", compute_type="int8")

    def run(audio) -> str:
        segments, _ = model.transcribe(
            audio,
            language="en",
            beam_size=3,
            initial_prompt=_PROMPT,
            condition_on_previous_text=False,
        )
        return _keep(
            {"text": s.text, "no_speech_prob": s.no_speech_prob, "avg_logprob": s.avg_logprob}
            for s in segments
        )

    return run


def _transcribe(engine, path: str) -> str:
    audio = decode_audio(path)
    if not get_speech_timestamps(audio, _VAD):
        return ""
    return engine(audio)


def main() -> None:
    gpu = _gpu_engine()
    engine = gpu or _cpu_engine()
    # A word of silence loads the model, so the first real sentence is not slow.
    engine(np.zeros(16000, dtype=np.float32))
    _send({"ready": True, "model": f"{MODEL}, {'GPU' if gpu else 'CPU'}"})
    for line in sys.stdin:
        request_id = None
        try:
            request = json.loads(line)
            request_id = request["id"]
            _send({"id": request_id, "text": _transcribe(engine, request["path"])})
        except Exception as err:  # one bad clip must not take her ears with it
            _send({"id": request_id, "error": str(err)})


if __name__ == "__main__":
    main()

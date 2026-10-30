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

THE PROMPT IS DESCRIPTIVE ON PURPOSE
    Whisper is biased towards words it has just been shown, which is how "GSTR"
    survives an Indian accent. But on near-silence it can recite its prompt
    back, so the prompt never contains the wake phrase itself: a hiss must not
    be able to wake her.
"""
from __future__ import annotations

import json
import os
import sys

# stdout is the protocol. Anything a library prints goes to stderr instead.
_OUT = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8")
os.dup2(2, 1)
sys.stdout = sys.stderr

from faster_whisper import WhisperModel  # noqa: E402

MODEL = os.environ.get("FRIDAY_WHISPER_MODEL", "small.en")

_PROMPT = (
    "A chartered accountant in India speaking to an assistant named Friday. "
    "GST, GSTR-1, GSTR-3B, GSTIN, TDS, ITR, CBDT, PAN, Aadhaar, Tally, Excel, "
    "audit, balance sheet, rupees, lakh, crore."
)

# Below this the model itself is saying it heard no speech.
_NO_SPEECH = 0.6


def _send(payload: dict) -> None:
    _OUT.write(json.dumps(payload) + "\n")
    _OUT.flush()


def _transcribe(model: WhisperModel, path: str) -> str:
    segments, _ = model.transcribe(
        path,
        language="en",
        beam_size=3,
        initial_prompt=_PROMPT,
        # Each request is one utterance, so nothing carries over between them.
        condition_on_previous_text=False,
        # The browser has already decided someone is talking; this removes
        # what it cannot, and is kept sensitive so that soft speech survives.
        vad_filter=True,
        vad_parameters={"threshold": 0.25, "min_silence_duration_ms": 600},
    )
    return " ".join(s.text.strip() for s in segments if s.no_speech_prob < _NO_SPEECH).strip()


def main() -> None:
    model = WhisperModel(MODEL, device="cpu", compute_type="int8")
    _send({"ready": True, "model": MODEL})
    for line in sys.stdin:
        request_id = None
        try:
            request = json.loads(line)
            request_id = request["id"]
            _send({"id": request_id, "text": _transcribe(model, request["path"])})
        except Exception as err:  # one bad clip must not take her ears with it
            _send({"id": request_id, "error": str(err)})


if __name__ == "__main__":
    main()

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
import re
import sys

# stdout is the protocol. Anything a library prints goes to stderr instead.
_OUT = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8")
os.dup2(2, 1)
sys.stdout = sys.stderr

from faster_whisper import WhisperModel  # noqa: E402

MODEL = os.environ.get("FRIDAY_WHISPER_MODEL", "small.en")

_PROMPT = (
    "GST, GSTR-1, GSTR-3B, GSTIN, TDS, ITR, CBDT, PAN, Aadhaar, Tally, Excel, "
    "audit, balance sheet, rupees, lakh, crore."
)
_PROMPT_WORDS = set(re.findall(r"[a-z0-9-]+", _PROMPT.lower()))

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
    text = " ".join(
        s.text.strip()
        for s in segments
        if s.no_speech_prob < _NO_SPEECH and s.avg_logprob > _MIN_LOGPROB
    ).strip()
    return "" if _is_recitation(text) else text


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

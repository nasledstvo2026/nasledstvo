import sys, os, time
from faster_whisper import WhisperModel

if len(sys.argv) < 2:
    print("usage: transcribe.py <audio>", file=sys.stderr)
    sys.exit(2)

path = sys.argv[1]
lang = os.environ.get("WHISPER_LANG", "ru")
model_name = os.environ.get("WHISPER_MODEL", "small")
root = os.path.expanduser("~/.openclaw/models/faster-whisper")

try:
    t0 = time.time()
    model = WhisperModel(model_name, device="cpu", compute_type="int8", download_root=root)
    segments, info = model.transcribe(path, language=lang, beam_size=1, vad_filter=True)
    text = " ".join(s.text.strip() for s in segments).strip()
    print(text)
    print("stt lang=%s prob=%.2f sec=%.2f chars=%d" % (info.language, info.language_probability, time.time()-t0, len(text)), file=sys.stderr)
except Exception as e:
    print("stt failed: %s" % str(e)[:300], file=sys.stderr)
    sys.exit(1)

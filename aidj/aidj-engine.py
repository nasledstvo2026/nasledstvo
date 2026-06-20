#!/usr/bin/env python3
"""
AI DJ — Audio Mixing Engine (isolated subprocess)
Usage: python3 aidj-engine.py track_a.mp3 track_b.mp3 [--output mix.mp3] [--json]

Dependencies: ffmpeg, aubio (python3)
"""

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


def log(msg, verbose=True):
    if verbose:
        print(msg, file=sys.stderr)


def get_bpm_aubio(filepath: str) -> float:
    """Detect BPM using aubio CLI."""
    try:
        result = subprocess.run(
            ["aubio", "tempo", filepath],
            capture_output=True, text=True, timeout=30
        )
        out = result.stdout.strip()
        if out:
            return float(out.split()[-1])
    except Exception:
        pass
    return 0.0


def get_bpm(filepath: str) -> float:
    """Get BPM with aubio, fallback to 120."""
    bpm = get_bpm_aubio(filepath)
    if bpm and bpm > 20:
        return round(bpm, 1)
    return 120.0


def get_duration(filepath: str) -> float:
    """Get audio duration in seconds via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of", "json", filepath
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def mix_tracks(track_a: str, track_b: str, output: str,
               crossfade: float = 15.0, verbose: bool = False) -> dict:
    """
    Mix two tracks: align BPM, crossfade.

    Returns dict with result info.
    """
    result = {
        "track_a": track_a,
        "track_b": track_b,
        "output": output,
        "status": "processing",
        "bpm_a": 0,
        "bpm_b": 0,
        "duration": 0
    }

    log("[AI DJ] Detecting BPM...", verbose)
    bpm_a = get_bpm(track_a)
    bpm_b = get_bpm(track_b)
    result["bpm_a"] = bpm_a
    result["bpm_b"] = bpm_b
    log(f"[AI DJ] Track A: {bpm_a} BPM | Track B: {bpm_b} BPM", verbose)

    target_bpm = max(bpm_a, bpm_b)
    log(f"[AI DJ] Target BPM: {target_bpm}", verbose)

    dur_a = get_duration(track_a)
    dur_b = get_duration(track_b)
    log(f"[AI DJ] Duration A: {dur_a:.1f}s | Duration B: {dur_b:.1f}s", verbose)

    crossfade = min(crossfade, dur_a - 5, dur_b - 5)
    if crossfade < 3:
        crossfade = min(dur_a, dur_b) / 3
    result["crossfade"] = round(crossfade, 1)
    log(f"[AI DJ] Crossfade: {crossfade:.1f}s", verbose)

    tmp_dir = Path(tempfile.mkdtemp(prefix="aidj_"))
    aligned_a = tmp_dir / "aligned_a.wav"
    aligned_b = tmp_dir / "aligned_b.wav"

    try:
        for track_path, aligned_path, bpm_orig, label in [
            (track_a, aligned_a, bpm_a, "A"),
            (track_b, aligned_b, bpm_b, "B")
        ]:
            tempo_ratio = target_bpm / bpm_orig
            if abs(tempo_ratio - 1.0) > 0.02:
                log(f"[AI DJ] Aligning Track {label}: {bpm_orig} -> {target_bpm} BPM (x{tempo_ratio:.3f})", verbose)
                cmd = [
                    "ffmpeg", "-y", "-i", str(track_path),
                    "-filter:a", f"atempo={tempo_ratio}",
                    "-ac", "2", "-ar", "44100",
                    str(aligned_path)
                ]
            else:
                cmd = [
                    "ffmpeg", "-y", "-i", str(track_path),
                    "-ac", "2", "-ar", "44100",
                    str(aligned_path)
                ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            log(f"[AI DJ] Track {label} aligned", verbose)

        log(f"[AI DJ] Crossfading...", verbose)
        cmd = [
            "ffmpeg", "-y",
            "-i", str(aligned_a),
            "-i", str(aligned_b),
            "-filter_complex",
            f"acrossfade=d={crossfade}:curve1=tri:curve2=tri",
            "-ac", "2", "-ar", "44100",
            "-b:a", "192k",
            str(output)
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        log(f"[AI DJ] Mix created", verbose)

        out_dur = get_duration(str(output))
        result["duration"] = round(out_dur, 1)
        result["status"] = "ok"
        result["output"] = str(Path(output).resolve())

    except subprocess.CalledProcessError as e:
        result["status"] = "error"
        result["error"] = f"ffmpeg failed: {e.stderr.decode(errors='replace')[:500]}"
        log(f"[AI DJ] ERROR: {result['error']}", verbose)
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        log(f"[AI DJ] ERROR: {result['error']}", verbose)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return result


def main():
    parser = argparse.ArgumentParser(description="AI DJ — Audio Mixing Engine")
    parser.add_argument("track_a", help="First audio track file")
    parser.add_argument("track_b", help="Second audio track file")
    parser.add_argument("--output", "-o", default=None,
                        help="Output file path (default: mix_<timestamp>.mp3)")
    parser.add_argument("--crossfade", "-c", type=float, default=15.0,
                        help="Crossfade duration in seconds (default: 15)")
    parser.add_argument("--json", action="store_true",
                        help="Output result as JSON only (logs to stderr)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print progress to stderr")

    args = parser.parse_args()

    if not args.output:
        ts = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"mix_{ts}.mp3"

    result = mix_tracks(args.track_a, args.track_b, args.output,
                        args.crossfade, args.verbose)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        log(f"\n{'='*40}", args.verbose or True)
        log(f"Status: {result['status']}", args.verbose or True)
        if result['status'] == 'ok':
            log(f"Output: {result['output']}", args.verbose or True)
            log(f"Duration: {result['duration']}s", args.verbose or True)
            log(f"BPM A: {result['bpm_a']} -> BPM B: {result['bpm_b']}", args.verbose or True)
            log(f"Crossfade: {result.get('crossfade', 'N/A')}s", args.verbose or True)
        else:
            log(f"Error: {result.get('error', 'Unknown')}", args.verbose or True)

    return 0 if result['status'] == 'ok' else 1


if __name__ == "__main__":
    sys.exit(main())

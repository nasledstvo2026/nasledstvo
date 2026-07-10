#!/usr/bin/env python3
"""
AI DJ — Audio Mixing Engine v2
Uses librosa for BPM, key detection & beat grid; ffmpeg for audio processing.

Usage:
  python3 aidj-engine.py track_a.mp3 track_b.mp3 [--output mix.mp3] [--json] [--verbose]
  python3 aidj-engine.py --config <set-id>      # server mode (reads from sets/)
"""

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from collections import OrderedDict
from datetime import datetime

import numpy as np

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

BASE_DIR = Path(__file__).resolve().parent

# Import smart modules
sys.path.insert(0, str(BASE_DIR))
from analyzers.track_structure import analyze_track_structure, find_crossfade_points

HAS_SMART_MIXING = True


# ═══════════════════════════════════════════════
#  Camelot Wheel — стандарт DJ для harmonic mixing
# ═══════════════════════════════════════════════

# Ключи по Кругу Камелота
# Major keys (B)
CAMELOT_MAJOR = {
    'C': '8B', 'G': '9B', 'D': '10B', 'A': '11B', 'E': '12B', 'B': '1B',
    'F#': '2B', 'C#': '3B', 'G#': '4B', 'D#': '5B', 'A#': '6B', 'F': '7B',
}
# Minor keys (A)
CAMELOT_MINOR = {
    'Am': '8A', 'Em': '9A', 'Bm': '10A', 'F#m': '11A', 'C#m': '12A', 'G#m': '1A',
    'D#m': '2A', 'A#m': '3A', 'Fm': '4A', 'Cm': '5A', 'Gm': '6A', 'Dm': '7A',
}

CAMELOT_DISPLAY = {**CAMELOT_MAJOR, **CAMELOT_MINOR}

# Krumhansl-Schmuckler profiles
KS_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
KS_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]

NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def detect_key(y, sr):
    """Определяет тональность (C, Dm, F#m, etc.) через Krumhansl-Schmuckler."""
    if not HAS_LIBROSA:
        return '?', None

    # Chromagram
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, n_chroma=12)
    chroma_mean = chroma.mean(axis=1)

    # Normalize
    chroma_mean = chroma_mean / np.max(chroma_mean)

    best_corr = -1
    best_key = 'C'
    best_mode = 'major'

    for i in range(12):
        rotated_major = np.roll(KS_MAJOR, i)
        rotated_minor = np.roll(KS_MINOR, i)

        corr_major = np.corrcoef(chroma_mean, rotated_major)[0, 1]
        corr_minor = np.corrcoef(chroma_mean, rotated_minor)[0, 1]

        if corr_major > best_corr:
            best_corr = corr_major
            best_key = NOTES[i]
            best_mode = 'major'

        if corr_minor > best_corr:
            best_corr = corr_minor
            best_key = NOTES[i] + 'm'
            best_mode = 'minor'

    return best_key, best_mode


def key_to_camelot(key_str):
    """Тональность → код Камелота (например C → 8B, Am → 8A)."""
    return CAMELOT_DISPLAY.get(key_str, '?')


def camelot_compatibility(ckey_a, ckey_b):
    """
    Оценка совместимости тональностей по кругу Камелота.
    0.0 = несовместимо, 1.0 = идеально.
    """
    if ckey_a == '?' or ckey_b == '?':
        return 0.5  # не знаем — нейтрально

    if ckey_a == ckey_b:
        return 1.0  # идеально

    num_a = int(ckey_a[:-1])
    num_b = int(ckey_b[:-1])
    mode_a = ckey_a[-1]
    mode_b = ckey_b[-1]

    # Одинаковый номер, разные моды (5A ↔ 5B) — гармонически совместимы
    if num_a == num_b:
        return 0.9

    diff = abs(num_a - num_b)
    if diff == 1:
        return 0.8  # соседи по кругу
    if diff == 2:
        return 0.5  # через один
    if diff <= 5:
        return 0.3

    return 0.1


def camelot_compatibility_label(score):
    if score >= 0.9:
        return '🔥 Perfect'
    if score >= 0.8:
        return '👍 Good'
    if score >= 0.5:
        return '👌 OK'
    if score >= 0.3:
        return '⚠️ Weak'
    return '❌ Bad'


# ═══════════════════════════════════════════════
#  BPM detection
# ═══════════════════════════════════════════════

def analyze_audio(filepath):
    """
    Full audio analysis: BPM, key, beats.
    Returns dict with all metadata.
    """
    info = {
        'file': filepath,
        'bpm': 120.0,
        'key': '?',
        'camelot': '?',
        'beats': [],
        'duration': 0,
    }

    # Duration via ffprobe
    try:
        res = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries',
             'format=duration', '-of', 'json', filepath],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(res.stdout)
        info['duration'] = float(data['format']['duration'])
    except Exception:
        pass

    if not HAS_LIBROSA:
        return info

    try:
        # Load audio (use mono for analysis, trim to first 60s for speed)
        duration_limit = min(info['duration'], 60) if info['duration'] > 0 else 60
        y, sr = librosa.load(filepath, sr=22050, mono=True, duration=duration_limit, res_type='kaiser_fast')

        # BPM (librosa может вернуть массив с одним элементом)
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units='time')
        if hasattr(tempo, '__iter__'):
            tempo = float(tempo[0])
        else:
            tempo = float(tempo)
        info['bpm'] = round(tempo, 1)
        info['beats'] = beats.tolist() if hasattr(beats, 'tolist') else list(beats)

        # Key detection
        key, mode = detect_key(y, sr)
        info['key'] = key
        info['camelot'] = key_to_camelot(key)

    except Exception as e:
        print(f"[WARN] librosa analysis failed for {filepath}: {e}", file=sys.stderr)

    return info


# ═══════════════════════════════════════════════
#  Audio processing with beat-synced crossfade
# ═══════════════════════════════════════════════

def find_nearest_beat(beats, time_sec, after=True):
    """
    Находит ближайший бит к time_sec.
    after=True → следующий бит после time_sec
    after=False → ближайший (может быть до или после)
    Возвращает время бита в секундах.
    """
    if not beats or len(beats) < 2:
        return time_sec

    if after:
        for b in beats:
            if b >= time_sec:
                return b
        return beats[-1]
    else:
        # Найти ближайший
        return min(beats, key=lambda b: abs(b - time_sec))


def format_time(seconds):
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f'{mins}:{secs:02d}'


def mix_tracks_v2(track_a, track_b, output,
                  crossfade_sec=15.0, verbose=False,
                  preset_params=None):
    """
    Mix two tracks with harmonic analysis, BPM alignment, and beat-synced crossfade.
    Supports preset parameters for different mixing styles.
    """
    preset_params = preset_params or {}
    result = OrderedDict([
        ('status', 'processing'),
        ('track_a', track_a),
        ('track_b', track_b),
        ('output', str(Path(output).resolve())),
        ('bpm_a', 0),
        ('bpm_b', 0),
        ('key_a', '?'),
        ('key_b', '?'),
        ('camelot_a', '?'),
        ('camelot_b', '?'),
        ('harmonic_score', 0),
        ('harmonic_label', '?'),
        ('crossfade', crossfade_sec),
        ('duration', 0),
        ('preset', preset_params.get('preset', 'default')),
        ('preset_name', preset_params.get('preset_name', 'Standard')),
    ])

    log = lambda msg: print(f'[AI DJ] {msg}', file=sys.stderr) if verbose else None

    # ── Step 1: Analyze ──
    if verbose:
        print('[AI DJ] Analysing Track A...', file=sys.stderr)
    info_a = analyze_audio(track_a)
    if verbose:
        print('[AI DJ] Analysing Track B...', file=sys.stderr)

    info_b = analyze_audio(track_b)

    result['bpm_a'] = info_a['bpm']
    result['bpm_b'] = info_b['bpm']
    result['key_a'] = info_a['key']
    result['key_b'] = info_b['key']
    result['camelot_a'] = info_a['camelot']
    result['camelot_b'] = info_b['camelot']

    # Harmonic compatibility
    harm_score = camelot_compatibility(info_a['camelot'], info_b['camelot'])
    result['harmonic_score'] = round(harm_score, 2)
    result['harmonic_label'] = camelot_compatibility_label(harm_score)

    if verbose:
        print(f'[AI DJ] Track A: {info_a["bpm"]} BPM | {info_a["key"]} ({info_a["camelot"]}) | {format_time(info_a["duration"])}', file=sys.stderr)
        print(f'[AI DJ] Track B: {info_b["bpm"]} BPM | {info_b["key"]} ({info_b["camelot"]}) | {format_time(info_b["duration"])}', file=sys.stderr)
        print(f'[AI DJ] Harmonic match: {result["harmonic_label"]} ({harm_score:.2f})', file=sys.stderr)

    # ── Step 2: BPM alignment (with preset override) ──
    preset_tempo_mode = preset_params.get('tempo_mode', 'follow_fastest')
    if preset_tempo_mode == 'lock_tight':
        # Lock tight: keep original BPMs, warn if difference > tolerance
        tolerance = preset_params.get('tempo_tolerance', 0.5)
        bpm_diff = abs(info_a['bpm'] - info_b['bpm'])
        if bpm_diff > tolerance:
            # BPM mismatch too large for lock_tight (stretching beyond ±5-7% degrades quality)
            # Use fastest BPM instead, but keep ALL other preset params (breakdown_matching, layering, etc.)
            target_bpm = max(info_a['bpm'], info_b['bpm'])
            if verbose:
                print(f'[AI DJ] ⚠️ BPM diff {bpm_diff:.1f} > ±{tolerance}, targeting fastest BPM {target_bpm} (preset features preserved)', file=sys.stderr)
        else:
            target_bpm = info_a['bpm']  # follow first track
    else:
        target_bpm = max(info_a['bpm'], info_b['bpm'])
    
    if verbose:
        print(f'[AI DJ] Target BPM: {target_bpm} (mode: {preset_tempo_mode})', file=sys.stderr)

    dur_a = info_a['duration']
    dur_b = info_b['duration']

    # Dynamic crossfade
    cf = min(crossfade_sec, dur_a - 5, dur_b - 5)
    if cf < 3:
        cf = min(dur_a, dur_b) / 3
    result['crossfade'] = round(cf, 1)

    # Beat-synced crossfade: align to nearest beat grid
    beats_a = info_a.get('beats', [])
    beats_b = info_b.get('beats', [])

    # Crossfade start in Track A = (dur_a - cf) seconds, adjusted to nearest beat
    crossfade_start_a = dur_a - cf
    beat_crossfade_start = find_nearest_beat(beats_a, crossfade_start_a, after=False)

    # Crossfade start in Track B = 0, but we want B's first beat to align
    # So we start B slightly earlier to hit the beat at the crossfade start
    b_start_offset = 0.0
    if len(beats_b) > 1:
        # Start B such that its first beats align with A's crossfade section
        # Simple approach: start B at 0, crossfade naturally
        pass  # Keep it simple for MVP

    if verbose:
        print(f'[AI DJ] Crossfade start (beat-aligned): {format_time(beat_crossfade_start)}', file=sys.stderr)

    # ── Step 3: Structure-aware Smart Crossfade ──
    tmp_dir = Path(tempfile.mkdtemp(prefix='aidj_'))
    aligned_a = tmp_dir / 'aligned_a.wav'
    aligned_b = tmp_dir / 'aligned_b.wav'

    try:
        # Align BPM
        for track_path, aligned_path, bpm_orig, label in [
            (track_a, aligned_a, info_a['bpm'], 'A'),
            (track_b, aligned_b, info_b['bpm'], 'B')
        ]:
            tempo_ratio = target_bpm / bpm_orig
            if abs(tempo_ratio - 1.0) > 0.02:
                if verbose:
                    print(f'[AI DJ] Tempo {label}: {bpm_orig}→{target_bpm} BPM (x{tempo_ratio:.3f})', file=sys.stderr)
                cmd = [
                    'ffmpeg', '-y', '-i', str(track_path),
                    '-filter:a', f'atempo={tempo_ratio}',
                    '-ac', '2', '-ar', '44100',
                    str(aligned_path)
                ]
            else:
                cmd = [
                    'ffmpeg', '-y', '-i', str(track_path),
                    '-ac', '2', '-ar', '44100',
                    str(aligned_path)
                ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            if verbose:
                print(f'[AI DJ] Track {label} aligned', file=sys.stderr)

        # ── Smart: analyze track structure ──
        blend_type = preset_params.get('blend_type', 'crossfade')
        curve1 = preset_params.get('curve1', 'tri')
        curve2 = preset_params.get('curve2', 'tri')

        do_smart = blend_type == 'layering' or preset_params.get('breakdown_matching')

        if do_smart and HAS_SMART_MIXING:
            if verbose:
                print(f'[AI DJ] Smart structure analysis ({preset_params.get("preset_name", "?")})...', file=sys.stderr)

            struct_a = analyze_track_structure(str(aligned_a), verbose=False)
            struct_b = analyze_track_structure(str(aligned_b), verbose=False)

            if verbose:
                print(f'[AI DJ] A: intro={struct_a["intro_duration"]:.0f}s, breakdowns={struct_a["breakdown_count"]} (main at {struct_a.get("main_breakdown_sec",0):.0f}s)', file=sys.stderr)
                print(f'[AI DJ] B: intro={struct_b["intro_duration"]:.0f}s, breakdowns={struct_b["breakdown_count"]}', file=sys.stderr)

            # Find optimal crossfade points
            xfade_pts = find_crossfade_points(struct_a, struct_b, preset_params)
            cf = xfade_pts['crossfade_duration']
            result['crossfade'] = round(cf, 1)
            result['crossfade_method'] = xfade_pts['method']

            if verbose:
                print(f'[AI DJ] Crossfade: {cf:.0f}s (method: {xfade_pts["method"]})', file=sys.stderr)
        else:
            # Standard fixed crossfade
            cf = min(crossfade_sec, dur_a - 5, dur_b - 5)
            if cf < 3:
                cf = min(dur_a, dur_b) / 3
            result['crossfade'] = round(cf, 1)

        # ── Apply crossfade ──
        # ffmpeg acrossfade стабильно работает до ~30-35с, дальше buffer underflow
        FFMPEG_SAFE_CF = 32
        if cf > FFMPEG_SAFE_CF:
            if verbose:
                print(f'[AI DJ] Crossfade {cf:.0f}s exceeds safe ffmpeg limit ({FFMPEG_SAFE_CF}s), capping', file=sys.stderr)
            cf = FFMPEG_SAFE_CF
            result['crossfade'] = cf
            result['crossfade_capped'] = True

        if verbose:
            print(f'[AI DJ] Applying acrossfade (d={cf:.0f}s, curve={curve1}/{curve2})...', file=sys.stderr)

        cmd = [
            'ffmpeg', '-y',
            '-i', str(aligned_a),
            '-i', str(aligned_b),
            '-filter_complex',
            f'acrossfade=d={cf}:curve1={curve1}:curve2={curve2}',
            '-ac', '2', '-ar', '44100',
            '-b:a', '192k',
            str(output)
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)

        # ── Verify output ──
        out_dur = 0
        try:
            res = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries',
                 'format=duration', '-of', 'json', str(output)],
                capture_output=True, text=True, timeout=10
            )
            data = json.loads(res.stdout)
            out_dur = round(float(data['format']['duration']), 1)
        except Exception:
            pass

        result['duration'] = out_dur
        result['status'] = 'ok'

        if verbose:
            print(f'[AI DJ] ✅ Mix created: {Path(output).name} ({format_time(out_dur)})', file=sys.stderr)

    except subprocess.CalledProcessError as e:
        result['status'] = 'error'
        result['error'] = f'ffmpeg: {e.stderr.decode(errors="replace")[:500]}'
        if verbose:
            print(f'[AI DJ] ❌ {result["error"]}', file=sys.stderr)
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)[:500]
        if verbose:
            print(f'[AI DJ] ❌ {result["error"]}', file=sys.stderr)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return result


def resolve_path(filepath):
    """Resolve a track path relative to workspace root."""
    if os.path.isabs(filepath):
        return filepath
    # Try relative to workspace (parent of aidj/)
    ws_path = BASE_DIR.parent / filepath
    if ws_path.exists():
        return str(ws_path)
    # Try relative to aidj/
    aidj_path = BASE_DIR / filepath
    if aidj_path.exists():
        return str(aidj_path)
    return str(ws_path)


def mix_set_tracks(tracks, output_dir=None, preset_params=None):
    """
    Сведение всех треков из сета последовательно.
    tracks: список [{title, artist, url, ...}]
    preset_params: параметры пресета (из presets/engine.py)
    """
    preset_params = preset_params or {}
    static_dir = BASE_DIR / 'static'
    output_dir = Path(output_dir or static_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results = []

    if len(tracks) < 2:
        return {'status': 'error', 'error': 'Need at least 2 tracks'}

    # Mix sequentially: track[0]+track[1] → mix1, then mix1+track[2] → mix2, etc.
    current_file = resolve_path(tracks[0].get('filepath', tracks[0].get('url', '')))

    for i in range(1, len(tracks)):
        next_file = resolve_path(tracks[i].get('filepath', tracks[i].get('url', '')))
        output_file = str(output_dir / f'mix_seg_{timestamp}_{i}.mp3')

        seg_result = mix_tracks_v2(
            resolve_path(current_file),
            next_file,
            output_file,
            crossfade_sec=preset_params.get('crossfade_seconds', 15),
            verbose=True,
            preset_params=preset_params,
        )

        seg_result['seg_index'] = i
        results.append(seg_result)

        if seg_result['status'] != 'ok':
            return {'status': 'error', 'error': f'Failed at segment {i}: {seg_result.get("error", "?")}', 'segments': results}

        current_file = output_file

    # Final mix with preset name
    preset_slug = preset_params.get('preset', 'default')
    final_output = str(output_dir / f'mix_{timestamp}_{preset_slug}.mp3')
    if os.path.exists(current_file):
        shutil.move(current_file, final_output)

    return {
        'status': 'ok',
        'output': final_output,
        'segments': results,
        'track_count': len(tracks),
        'preset': preset_params.get('preset', 'default'),
        'preset_name': preset_params.get('preset_name', 'Standard'),
    }


# ═══════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='AI DJ — Audio Mixing Engine v2')
    parser.add_argument('track_a', nargs='?', help='First audio track')
    parser.add_argument('track_b', nargs='?', help='Second audio track')
    parser.add_argument('--output', '-o', default=None, help='Output file path')
    parser.add_argument('--crossfade', '-c', type=float, default=15.0, help='Crossfade (s)')
    parser.add_argument('--json', action='store_true', help='JSON output only')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose stderr')
    parser.add_argument('--config', help='Server mode: JSON config or set-id')

    args = parser.parse_args()

    # Server mode: read config from stdin or args
    if args.config:
        config_data = None
        # Try reading as set-id from sets directory
        set_path = BASE_DIR / 'sets' / f'set-{args.config}.json'
        if set_path.exists():
            config_data = json.loads(set_path.read_text())
        else:
            # Try as raw JSON
            raw = args.config
            # If config starts with '{' but might be too long for cmd line, try stdin
            if raw == '-':
                raw = sys.stdin.read()
            try:
                config_data = json.loads(raw)
            except json.JSONDecodeError:
                print(json.dumps({'status': 'error', 'error': f'Config not found: {args.config}'}))
                sys.exit(1)

        tracks = config_data.get('tracks', [])
        if len(tracks) < 2:
            print(json.dumps({'status': 'error', 'error': 'Need at least 2 tracks in config'}))
            sys.exit(1)

        raw_preset = config_data.get('preset', {}) or {}
        if isinstance(raw_preset, dict) and 'preset' in raw_preset:
            # Resolve through preset engine
            from presets.engine import preset_to_mix_params
            track_info = {}
            preset_params = preset_to_mix_params(tracks, raw_preset['preset'], track_info)
        elif isinstance(raw_preset, str):
            from presets.engine import preset_to_mix_params
            preset_params = preset_to_mix_params(tracks, raw_preset, {})
        else:
            preset_params = raw_preset

        result = mix_set_tracks(tracks, preset_params=preset_params)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get('status') == 'ok' else 1

    # Normal mode
    if not args.track_a or not args.track_b:
        parser.print_help()
        sys.exit(1)

    if not args.output:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        args.output = f'mix_{ts}.mp3'

    result = mix_tracks_v2(args.track_a, args.track_b, args.output,
                           args.crossfade, args.verbose)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = result['status']
        sep = '=' * 50
        print(f'\n{sep}', file=sys.stderr)
        print(f'Status: {status}', file=sys.stderr)
        if status == 'ok':
            print(f'Output: {result["output"]}', file=sys.stderr)
            print(f'Duration: {result["duration"]}s', file=sys.stderr)
            print(f'Tracks: {result["bpm_a"]} BPM ({result["key_a"]} / {result["camelot_a"]}) → '
                  f'{result["bpm_b"]} BPM ({result["key_b"]} / {result["camelot_b"]})', file=sys.stderr)
            print(f'Harmonic: {result["harmonic_label"]} (score: {result["harmonic_score"]})', file=sys.stderr)
            print(f'Crossfade: {result["crossfade"]}s', file=sys.stderr)
        else:
            print(f'Error: {result.get("error", "?")}', file=sys.stderr)

    return 0 if status == 'ok' else 1


if __name__ == '__main__':
    sys.exit(main())

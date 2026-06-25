#!/usr/bin/env python3
"""
Phase Mixer — segment-based layering mixer with per-phase EQ + bass swap.
Uses ffmpeg exclusively: cut → eq/filter → amix → concat.

Oakenfold 4-phase protocol:
  Phase 1 (sneak_in):    incoming = no bass, only fader rising
  Phase 2 (melodic):     incoming = full mid/high, still no bass
  Phase 3 (bass_swap):   instant swap — outgoing bass out, incoming bass in
  Phase 4 (fade_out):    outgoing fades out, incoming = full
"""

import json
import math
import os
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def format_time(seconds):
    """Seconds → HH:MM:SS.mmm for ffmpeg"""
    if seconds < 0:
        seconds = 0
    return f'{int(seconds // 3600):02d}:{int((seconds % 3600) // 60):02d}:{seconds % 60:06.3f}'


def run_ffmpeg(cmd, desc='', timeout=120):
    """Run ffmpeg and capture stderr for errors."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if res.returncode != 0:
            err = res.stderr[-500:] if res.stderr else 'unknown error'
            raise RuntimeError(f'ffmpeg {desc}: {err}')
        return res
    except subprocess.TimeoutExpired:
        raise RuntimeError(f'ffmpeg {desc}: timeout {timeout}s')
    except FileNotFoundError:
        raise RuntimeError('ffmpeg not found')


def get_duration_sec(filepath):
    """Get audio duration in seconds via ffprobe."""
    try:
        res = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries',
             'format=duration', '-of', 'json', str(filepath)],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(res.stdout)
        return float(data['format']['duration'])
    except Exception:
        return 0


def extract_segment(input_file, output_file, start_sec, end_sec):
    """Extract a segment from audio (trim)."""
    duration = end_sec - start_sec
    if duration <= 0:
        return False
    cmd = [
        'ffmpeg', '-y',
        '-i', str(input_file),
        '-ss', format_time(start_sec),
        '-t', format_time(duration),
        '-ac', '2', '-ar', '44100',
        str(output_file)
    ]
    run_ffmpeg(cmd, f'trim {start_sec:.1f}-{end_sec:.1f}s')
    return True


def apply_eq(input_file, output_file, eq_params, label='eq'):
    """
    Apply EQ filters to audio file.

    eq_params: dict with 'low', 'mid', 'high' gain in dB (0 = flat, -60 = muted, 12 = boosted)
    ffmpeg equalizer filter: equalizer=f=<freq>:width_type=o:width=<width>:g=<gain>
    """
    if not eq_params:
        shutil.copy2(input_file, output_file)
        return

    low_db = float(eq_params.get('low', 0))
    mid_db = float(eq_params.get('mid', 0))
    high_db = float(eq_params.get('high', 0))

    filters = []
    # Bass shelving filter (low shelf, freq=250Hz, Q=0.7)
    if abs(low_db) > 0.1:
        filters.append(f'equalizer=f=250:width_type=o:width=0.5:g={low_db}')
    # Mid peaking filter (freq=2500Hz, Q=0.7)
    if abs(mid_db) > 0.1:
        filters.append(f'equalizer=f=2500:width_type=o:width=0.5:g={mid_db}')
    # High shelving filter (high shelf, freq=8000Hz, Q=0.7)
    if abs(high_db) > 0.1:
        filters.append(f'equalizer=f=8000:width_type=o:width=0.5:g={high_db}')

    if not filters:
        shutil.copy2(input_file, output_file)
        return

    filter_str = ','.join(filters)
    cmd = [
        'ffmpeg', '-y',
        '-i', str(input_file),
        '-af', f'volume=1.0,{filter_str}',
        '-ac', '2', '-ar', '44100',
        str(output_file)
    ]
    run_ffmpeg(cmd, f'EQ {label}')


def apply_fade(input_file, output_file, fade_in=0, fade_out=0):
    """Apply fade in/out (seconds)."""
    if fade_in <= 0 and fade_out <= 0:
        shutil.copy2(input_file, output_file)
        return

    filters = []
    if fade_in > 0:
        filters.append(f'afade=t=in:d={fade_in}')
    if fade_out > 0:
        total = get_duration_sec(input_file)
        start = max(0, total - fade_out)
        filters.append(f'afade=t=out:st={start:.3f}:d={fade_out}')

    cmd = [
        'ffmpeg', '-y',
        '-i', str(input_file),
        '-af', ','.join(filters),
        '-ac', '2', '-ar', '44100',
        str(output_file)
    ]
    run_ffmpeg(cmd, 'fade')
    return True


def amix_tracks(track_files, output_file, durations=None, gains=None):
    """
    Mix multiple audio tracks together with optional gains.
    track_files: list of paths
    gains: list of relative gains (e.g. [1.0, 0.7]), or None
    """
    n = len(track_files)
    if n == 0:
        return False
    if n == 1:
        shutil.copy2(track_files[0], output_file)
        return True

    inputs = []
    for t in track_files:
        inputs.extend(['-i', str(t)])

    # amix with dropout detection disabled (longest input sets duration)
    amix_inputs = ':'.join([f'[0:a][1:a]' if n == 2 else ''])
    if gains:
        # Apply volume per input
        vol_filters = []
        for i, g in enumerate(gains):
            if abs(g - 1.0) > 0.01:
                vol_filters.append(f'[{i}:a]volume={g:.4f}[v{i}]')
            else:
                vol_filters.append(f'[{i}:a]acopy[v{i}]')

        vol_filter_str = ';'.join(vol_filters)
        mix_input_str = ''.join([f'[v{i}]' for i in range(n)])
        filter_complex = f'{vol_filter_str};{mix_input_str}amix=inputs={n}:duration=longest'
    else:
        filter_complex = f'[0:a][1:a]amix=inputs={n}:duration=first' if n == 2 else \
                         ''.join([f'[{i}:a]' for i in range(n)]) + f'amix=inputs={n}:duration=first'

    cmd = [
        'ffmpeg', '-y', *inputs,
        '-filter_complex', filter_complex,
        '-ac', '2', '-ar', '44100',
        '-b:a', '192k',
        str(output_file)
    ]
    run_ffmpeg(cmd, f'amix {n} tracks')
    return True


def concat_tracks(track_files, output_file):
    """Concatenate audio files (same format/sample rate)."""
    if not track_files:
        return False
    if len(track_files) == 1:
        shutil.copy2(track_files[0], output_file)
        return True

    # Use concat demuxer
    concat_file = Path(tempfile.mktemp(suffix='.txt', prefix='concat_'))
    try:
        lines = [f"file '{Path(f).resolve()}'\n" for f in track_files]
        concat_file.write_text(''.join(lines), encoding='utf-8')

        cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', str(concat_file),
            '-c', 'copy',
            str(output_file)
        ]
        run_ffmpeg(cmd, 'concat')
        return True
    finally:
        concat_file.unlink(missing_ok=True)


# ═══════════════════════════════════════════════
#  Phase definitions from preset
# ═══════════════════════════════════════════════

def generate_phases_from_preset(preset_params, dur_a, dur_b):
    """
    Создаёт расписание фаз из EQ-фаз пресета.
    Возвращает список dict: [{'name', 'start', 'end', 'eq_a': dict, 'eq_b': dict, 'gain_a', 'gain_b'}]
    """
    eq_phases = preset_params.get('eq_phases', [])
    if not eq_phases:
        # Fallback: one flat phase
        return [{
            'name': 'full',
            'start': 0,
            'end': max(dur_a, dur_b),
            'eq_a': {'low': 0, 'mid': 0, 'high': 0},
            'eq_b': {'low': 0, 'mid': 0, 'high': 0},
            'gain_a': 1.0,
            'gain_b': 0.0,
        }]

    blend_end = preset_params.get('crossfade_seconds', 135)
    phases = []

    for ph in eq_phases:
        name = ph.get('name', 'phase')
        action = ph.get('action', '')

        # Skip instant-only phases (bass_swap is a 1-beat event, not a segment)
        if action == 'instant':
            continue

        time_range = ph.get('time_seconds', [0, 0])
        start = float(time_range[0]) if isinstance(time_range, (list, tuple)) else 0
        end = float(time_range[1]) if isinstance(time_range, (list, tuple)) else start + 10

        # Parse EQ values
        incoming_eq = ph.get('incoming', {})
        outgoing_eq = ph.get('outgoing', {})

        eq_b = {
            'low': parse_db(incoming_eq.get('low', 0)),
            'mid': parse_db(incoming_eq.get('mid', 0)),
            'high': parse_db(incoming_eq.get('high', 0)),
        }
        eq_a = {
            'low': parse_db(outgoing_eq.get('low', 0)),
            'mid': parse_db(outgoing_eq.get('mid', 0)),
            'high': parse_db(outgoing_eq.get('high', 0)),
        }

        # Parse fader into gain
        fader_in = str(incoming_eq.get('fader', '100%'))
        fader_out = str(outgoing_eq.get('fader', '100%'))

        phases.append({
            'name': name,
            'start': start,
            'end': end,
            'eq_a': eq_a,
            'eq_b': eq_b,
            'gain_a': parse_fader(fader_out) / 100.0,
            'gain_b': parse_fader(fader_in) / 100.0,
        })

    return phases


def parse_db(value):
    """Parse EQ dB value. Handles strings like '−60', '9→12', '12→0', '-inf', '−∞'."""
    if value is None:
        return 0
    s = str(value).strip()
    # Handle "→" ranges: take the final value
    if '→' in s:
        s = s.split('→')[-1].strip()
    # Handle "-inf" / "−∞"
    if s in ('-inf', '−∞', '-∞'):
        return -60
    # Handle negative sign variants
    s = s.replace('−', '-')
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0


def parse_fader(value):
    """Parse fader string like '100%', '0→70%' → 0..100 float."""
    if value is None:
        return 100
    s = str(value).strip()
    if '→' in s:
        # Take the final value
        s = s.split('→')[-1].strip()
    s = s.replace('%', '')
    try:
        return float(s)
    except (ValueError, TypeError):
        return 100


# ═══════════════════════════════════════════════
#  Main layering mixer
# ═══════════════════════════════════════════════

def phase_mix(track_a, track_b, output, preset_params, verbose=False):
    """
    Full phase-based layering.

    Works in temp dir:
    1. Align BPM (same as aidj-engine.py does)
    2. Cut tracks by phase schedule
    3. Apply per-phase EQ + gain to each segment
    4. Mix overlapping segments (amix)
    5. Concatenate non-overlapping segments + mixes

    Returns: dict result
    """
    log = lambda msg: print(f'[PHASE MIX] {msg}', file=sys.stderr) if verbose else None
    blend_type = preset_params.get('blend_type', 'crossfade')

    if blend_type != 'layering':
        return None  # Not our job

    dur_a = get_duration_sec(track_a)
    dur_b = get_duration_sec(track_b)

    if verbose:
        log(f'Tracks: A={dur_a:.1f}s B={dur_b:.1f}s')

    # Generate phase schedule
    phases = generate_phases_from_preset(preset_params, dur_a, dur_b)
    if verbose:
        for p in phases:
            log(f'  Phase: {p["name"]} ({p["start"]:.0f}s-{p["end"]:.0f}s)')

    tmp_dir = Path(tempfile.mkdtemp(prefix='phase_mix_'))
    try:
        # Step 1: Pre-roll — incoming track starting at 0 (phase 1 overlap)
        # Step 2: For each overlapping region, cut both tracks → apply EQ + gain → amix
        # Step 3: Outro — tail of outgoing track after blend

        blend_end = max(p['end'] for p in phases) if phases else min(dur_a, dur_b)

        # Segments of Track A (outgoing)
        a_segments = []
        # Segments of Track B (incoming)
        b_segments = []

        for idx, ph in enumerate(phases):
            s, e = ph['start'], ph['end']
            if s >= e:
                continue

            # Cut Track A segment (might extend beyond dur_a — clipped by extract)
            a_seg_path = tmp_dir / f'seg_a_ph{idx}.wav'
            if s < dur_a:
                extract_segment(track_a, a_seg_path, s, min(e, dur_a))
                eq_a_path = tmp_dir / f'eq_a_ph{idx}.wav'
                apply_eq(a_seg_path, eq_a_path, ph['eq_a'], f'A phase {idx}')
                gain_a = ph['gain_a']
            else:
                eq_a_path = None

            # Cut Track B segment
            b_seg_path = tmp_dir / f'seg_b_ph{idx}.wav'
            if s < dur_b:
                extract_segment(track_b, b_seg_path, s, min(e, dur_b))
                eq_b_path = tmp_dir / f'eq_b_ph{idx}.wav'
                apply_eq(b_seg_path, eq_b_path, ph['eq_b'], f'B phase {idx}')
                gain_b = ph['gain_b']
            else:
                eq_b_path = None

            # Mix overlapping segment
            if eq_a_path and eq_b_path:
                mix_path = tmp_dir / f'mix_ph{idx}.wav'
                amix_tracks(
                    [eq_a_path, eq_b_path],
                    mix_path,
                    gains=[gain_a, gain_b]
                )
                a_segments.append(mix_path)
            elif eq_a_path:
                a_segments.append(eq_a_path)
            elif eq_b_path:
                a_segments.append(eq_b_path)

        # Step 2: Intro — Track A before any blend
        intro_end = phases[0]['start'] if phases else blend_end
        if intro_end > 0:
            intro_path = tmp_dir / 'intro_a.wav'
            extract_segment(track_a, intro_path, 0, intro_end)
            a_segments.insert(0, intro_path)

        # Step 3: Outro — remaining Track B after blend
        outro_start = blend_end
        if outro_start < dur_b:
            outro_path = tmp_dir / 'outro_b.wav'
            extract_segment(track_b, outro_path, outro_start, dur_b)
            a_segments.append(outro_path)

        # Step 4: Concatenate all segments
        if not a_segments:
            raise RuntimeError('No segments generated — empty mix')

        out_path = tmp_dir / 'final.wav'
        concat_tracks(a_segments, str(out_path))

        # Step 5: Convert to mp3
        cmd = [
            'ffmpeg', '-y',
            '-i', str(out_path),
            '-ac', '2', '-ar', '44100',
            '-b:a', '192k',
            str(output)
        ]
        run_ffmpeg(cmd, 'final encode')

        out_dur = get_duration_sec(output)
        if verbose:
            log(f'✅ Phase mix done: {Path(output).name} ({out_dur:.1f}s, {len(a_segments)} segments)')

        return out_dur

    except Exception as e:
        if verbose:
            log(f'❌ {e}')
        raise
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

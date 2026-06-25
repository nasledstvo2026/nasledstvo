#!/usr/bin/env python3
"""
AI DJ — Track Structure Analyzer

Анализирует энергетическую структуру трека:
- Энергетические фазы (intro → buildup → peak → breakdown → outro)
- Точки breakdown (глубокие минимумы RMS)
- Длину intro (первая секция без бочки)
- Длину outro (последняя секция спада энергии)
- BPM-профиль всего трека

Используется для smart crossfade: находим breakdown Track A и стартуем
Track B в его минимуме.
"""

import json
import os
import sys
import warnings
import tempfile
import subprocess
from pathlib import Path

import numpy as np

warnings.filterwarnings('ignore')

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False


def analyze_track_structure(filepath, sr=22050, hop_length=512, verbose=False):
    """
    Полный анализ структуры трека.

    Returns:
        dict с:
          - duration_sec
          - bpm (средний)
          - energy_profile: [{time_sec, energy}]
          - breakdowns: [{time_sec, energy, depth}]
          - intro_duration: длительность тихого вступления (сек)
          - outro_start: время начала затухания (сек)
          - phases: фазы трека для визуализации
    """
    if not HAS_LIBROSA:
        return {'error': 'librosa not available'}

    result = {}

    # Load with lower quality for structure analysis
    try:
        if verbose:
            print(f'[STRUCTURE] Loading {os.path.basename(filepath)} ({sr} Hz)', file=sys.stderr)
        y, sr = librosa.load(filepath, sr=sr, mono=True, res_type='kaiser_fast')
    except Exception as e:
        return {'error': f'Cannot load: {e}'}

    duration = len(y) / sr
    result['duration_sec'] = round(duration, 1)

    # ── BPM ──
    try:
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop_length)
        if hasattr(tempo, 'item'):
            tempo = tempo.item()
        elif hasattr(tempo, '__iter__'):
            tempo = float(tempo[0])
        result['bpm'] = round(float(tempo), 1)
        result['beat_count'] = len(beats)
    except Exception as e:
        result['bpm'] = 0

    # ── RMS Energy Profile ──
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop_length)[0]

    # Smooth RMS
    window_size = max(1, int(sr / hop_length * 2))  # ~2 second window
    kernel = np.ones(window_size) / window_size
    rms_smooth = np.convolve(rms, kernel, mode='same')

    # Normalize
    rms_norm = rms_smooth / max(rms_smooth.max(), 1e-10)
    rms_time = np.arange(len(rms_norm)) * hop_length / sr

    result['energy_profile'] = [
        {'time_sec': round(float(t), 1), 'energy': round(float(e), 4)}
        for t, e in zip(rms_time[::10], rms_norm[::10])  # decimate 10x
    ]

    # ── Find Breakdowns (deep energy minima) ──
    # A breakdown is a local minimum below 40% energy
    from scipy.signal import argrelextrema
    minima = argrelextrema(rms_norm, np.less, order=int(sr / hop_length * 4))[0]

    breakdowns = []
    for idx in minima:
        if rms_norm[idx] < 0.40:
            t = rms_time[idx]
            # Find surrounding max
            left = max(0, idx - int(sr / hop_length * 10))
            right = min(len(rms_norm) - 1, idx + int(sr / hop_length * 10))
            local_max = max(rms_norm[left:right])
            depth = 1.0 - (rms_norm[idx] / max(local_max, 0.01))

            breakdowns.append({
                'time_sec': round(float(t), 1),
                'energy': round(float(rms_norm[idx]), 4),
                'depth': round(float(depth), 3),
            })

    # Deduplicate within 10s window
    deduped = []
    for b in breakdowns:
        if not deduped or b['time_sec'] - deduped[-1]['time_sec'] > 10:
            deduped.append(b)

    result['breakdowns'] = deduped
    result['breakdown_count'] = len(deduped)

    # ── Find deepest breakdown (likely the main one) ──
    if deduped:
        deepest = min(deduped, key=lambda b: b['energy'])
        result['main_breakdown_sec'] = deepest['time_sec']
        result['main_breakdown_energy'] = deepest['energy']
    else:
        result['main_breakdown_sec'] = duration / 2
        result['main_breakdown_energy'] = 0.5

    # ── Intro detection: first time RMS exceeds threshold ──
    threshold = rms_norm.max() * 0.15
    intro_frames = np.where(rms_norm > threshold)[0]

    if len(intro_frames) > 0:
        first_onset = rms_time[intro_frames[0]]
        # Check if really right at start — minimum 5s for intro
        if first_onset < 5:
            # Find first real buildup (sustained energy > 20%)
            onset_idx = 0
            for i in range(0, len(rms_norm), int(sr / hop_length)):
                if rms_norm[i] > 0.2:
                    # Check it sustains
                    window = rms_norm[i:i + int(sr / hop_length * 3)]
                    if np.mean(window) > 0.2:
                        onset_idx = i
                        break
            first_onset = rms_time[onset_idx] if onset_idx > 0 else 0

        result['intro_duration'] = round(first_onset, 1)
    else:
        result['intro_duration'] = 0

    # ── Outro detection: find last sustained energy then fade ──
    # Last point where energy > 40%
    outro_frames = np.where(rms_norm > 0.4)[0]
    if len(outro_frames) > 0:
        last_high = rms_time[outro_frames[-1]]
        outro_start = min(last_high, duration - 3)
        result['outro_start'] = round(outro_start, 1)
        result['outro_duration'] = round(duration - outro_start, 1)
    else:
        result['outro_start'] = duration - 10
        result['outro_duration'] = 10

    # ── Phase summary ──
    # Break track into meaningful phases based on energy tiers
    def get_phase(e):
        if e < 0.15: return 'silence'
        if e < 0.35: return 'low'
        if e < 0.55: return 'mid'
        if e < 0.75: return 'buildup'
        return 'peak'

    phases = []
    last_phase = None
    phase_start = 0

    for i in range(0, len(rms_norm), int(sr / hop_length * 2)):
        t = rms_time[min(i, len(rms_norm) - 1)]
        avg_e = np.mean(rms_norm[i:i + int(sr / hop_length * 2)])
        p = get_phase(avg_e)

        if p != last_phase:
            if last_phase is not None:
                phases.append({
                    'phase': last_phase,
                    'start': round(phase_start, 1),
                    'end': round(t, 1),
                })
            last_phase = p
            phase_start = t

    if last_phase:
        phases.append({
            'phase': last_phase,
            'start': round(phase_start, 1),
            'end': round(duration, 1),
        })

    result['phases'] = phases

    if verbose:
        print(f'[STRUCTURE] Duration: {duration/60:.1f} min, BPM: {result.get("bpm", "?")}', file=sys.stderr)
        print(f'[STRUCTURE] Intro: {result["intro_duration"]:.0f}s, Outro: {result.get("outro_duration",0):.0f}s', file=sys.stderr)
        print(f'[STRUCTURE] Breakdowns: {len(deduped)} (main at {result.get("main_breakdown_sec",0):.0f}s)', file=sys.stderr)
        print(f'[STRUCTURE] Phases: {len(phases)}', file=sys.stderr)
        if breakdowns:
            for b in deduped[:5]:
                print(f'  ⬇  {b["time_sec"]:.0f}s — energy {b["energy"]:.0%}, depth {b["depth"]:.0%}', file=sys.stderr)

    return result


def find_crossfade_points(structure_a, structure_b, preset_params=None):
    """
    Находит оптимальные точки crossfade на основе структуры треков.

    Args:
        structure_a: результат analyze_track_structure для трека A (outgoing)
        structure_b: результат analyze_track_structure для трека B (incoming)
        preset_params: параметры стиля сведения

    Returns:
        dict с точками входа/выхода
    """
    preset_params = preset_params or {}
    style = preset_params.get('blend_type', 'crossfade')

    dur_a = structure_a['duration_sec']
    dur_b = structure_b['duration_sec']

    # Default: последние N секунд трека A
    cf = preset_params.get('crossfade_seconds', 15)
    cf = min(cf, dur_a * 0.6, dur_b * 0.8)

    if style == 'layering' and preset_params.get('breakdown_matching'):
        # 🔥 Oakenfold-style: start track B at track A's breakdown
        breakdown_a = structure_a.get('main_breakdown_sec', dur_a * 0.7)

        # Start point in track A: a few seconds before its breakdown
        # Start point in track B: its intro (first energy rise)
        start_a = max(0, breakdown_a - 8)
        start_b = 0  # B starts from the beginning, but we want to hit B's structure

        # Find B's first notable event to align
        intro_b = structure_b.get('intro_duration', 5)
        first_breakdown_b = structure_b.get('main_breakdown_sec', dur_b * 0.3)

        cf_duration = dur_a - start_a  # from breakdown of A to end of A

        return {
            'start_in_a': round(start_a, 1),
            'start_in_b': round(start_b, 1),
            'crossfade_duration': round(min(cf_duration, dur_a - 5, 120), 1),
            'method': 'breakdown_matching',
            'note': f'B starts at A\'s breakdown ({start_a:.0f}s)',
        }

    if style == 'layering' and preset_params.get('intro_matching'):
        # Match B's intro with A's peak
        intro_b = structure_b.get('intro_duration', 5)
        peak_a_time = dur_a * 0.65

        start_a = max(0, peak_a_time - intro_b)

        return {
            'start_in_a': round(start_a, 1),
            'start_in_b': 0,
            'crossfade_duration': round(dur_a - start_a, 1),
            'method': 'intro_peak',
            'note': 'B intro overlays A peak',
        }

    # Default: last N seconds of A + first of B
    cf = min(cf, dur_a - 3, dur_b - 3)
    return {
        'start_in_a': round(dur_a - cf, 1),
        'start_in_b': 0,
        'crossfade_duration': round(cf, 1),
        'method': 'standard',
        'note': f'Standard crossfade {cf:.0f}s',
    }


def analyze_track_for_preset(filepath, preset_params=None):
    """
    Полный анализ трека с учётом пресета.
    Возвращает всё, что нужно для engine.
    """
    result = analyze_track_structure(filepath, verbose=False)

    # Если пресет требует breakdown-анализ — углубляем
    if preset_params and preset_params.get('blend_type') == 'layering':
        if preset_params.get('breakdown_matching'):
            result['compatible_transition'] = {
                'has_breakdown': len(result.get('breakdowns', [])) > 0,
                'breakdown_energy': result.get('main_breakdown_energy', 0),
                'intro_sec': result.get('intro_duration', 5),
                'outro_sec': result.get('outro_duration', 10),
            }

    return result


if __name__ == '__main__':
    # CLI: analyze a file
    if len(sys.argv) < 2:
        print(f'Usage: {sys.argv[0]} <audio_file> [--json]')
        sys.exit(1)

    filepath = sys.argv[1]
    to_json = '--json' in sys.argv

    result = analyze_track_structure(filepath, verbose=True)

    if to_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # Human-readable
        print(f'\n{"="*50}')
        print(f'Track: {os.path.basename(filepath)}')
        print(f'Duration: {result["duration_sec"]/60:.1f} min ({result["duration_sec"]:.0f}s)')
        print(f'BPM: {result.get("bpm", "?")}')
        print(f'Intro: {result["intro_duration"]:.0f}s | Outro: {result["outro_duration"]:.0f}s')
        print(f'Breakdowns: {result["breakdown_count"]}')
        print(f'Main breakdown: {result.get("main_breakdown_sec", 0):.0f}s (energy {result.get("main_breakdown_energy", 0):.0%})')
        print(f'Phases:')
        for p in result.get('phases', []):
            print(f'  {p["start"]:6.0f}s–{p["end"]:6.0f}s  {p["phase"]}')
        print(f'Breakdown points:')
        for b in result.get('breakdowns', [])[:8]:
            print(f'  ⬇  {b["time_sec"]:6.0f}s — energy {b["energy"]:.0%} (depth {b["depth"]:.0%})')

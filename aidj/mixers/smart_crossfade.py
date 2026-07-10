#!/usr/bin/env python3
"""
AI DJ — Smart Crossfade Engine

Выбирает и выполняет оптимальное сведение двух треков на основе их структуры.
Поддерживает стили:
  - Oakenfold (Tranceport 1998): breakdown-matching, variable length
  - Oakenfold (Fantazia 1997): плотные плавные переходы
  - Default: стандартный crossfade с фиксированной длиной

Не имитирует EQ-фазы — только реальные, подтверждённые анализом параметры.
"""

import json
import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent


def apply_smart_crossfade(track_a, track_b, output,
                          structure_a, structure_b,
                          preset_params=None,
                          verbose=False):
    """
    Сводит два трека с учётом их структуры и выбранного пресета.

    Args:
        track_a: путь к файлу трека A (outgoing)
        track_b: путь к файлу трека B (incoming)
        output: выходной файл
        structure_a: результат analyze_track_structure(track_a)
        structure_b: результат analyze_track_structure(track_b)
        preset_params: параметры стиля сведения

    Returns:
        dict с результатом сведения
    """
    preset_params = preset_params or {}
    preset_name = preset_params.get('preset_name', 'Standard')
    blend_type = preset_params.get('blend_type', 'crossfade')
    verbose = preset_params.get('verbose', verbose)

    log = lambda msg: print(f'[SMART] {msg}', file=sys.stderr) if verbose else None

    dur_a = structure_a.get('duration_sec', 300)
    dur_b = structure_b.get('duration_sec', 300)

    bpm_a = structure_a.get('bpm', 120)
    bpm_b = structure_b.get('bpm', 120)
    target_bpm = preset_params.get('target_bpm', max(bpm_a, bpm_b))

    log(f'A: {os.path.basename(track_a)} ({bpm_a} BPM, {dur_a/60:.1f}m)')
    log(f'B: {os.path.basename(track_b)} ({bpm_b} BPM, {dur_b/60:.1f}m)')

    # ── Determine crossfade parameters based on style ──
    if blend_type == 'layering':
        # Breakdown-matching (Oakenfold Tranceport style)
        breakdown_a = structure_a.get('main_breakdown_sec', dur_a * 0.65)
        intro_b = structure_b.get('intro_duration', 5)

        # Start B ~4-8 seconds before A's deepest breakdown
        start_in_a = max(0, breakdown_a - intro_b)
        # Duration: from start_in_a until end of A (but capped at 2 min max blend)
        cf_duration = min(dur_a - start_in_a, 120)

        # But respect the track's actual length
        if cf_duration > dur_a * 0.7:
            cf_duration = dur_a * 0.6
        if cf_duration > dur_b * 0.8:
            cf_duration = dur_b * 0.8

        log(f'Breakdown at {breakdown_a:.0f}s — start B at {start_in_a:.0f}s')
        log(f'Blend duration: {cf_duration:.0f}s')

    elif preset_params.get('style') == 'tight':
        # Fantazia-style: shorter, denser transitions
        # Prefer the end of A's strong energy phase, not breakdown
        cf_duration = min(preset_params.get('crossfade_seconds', 30), dur_a * 0.4, dur_b * 0.5)
        start_in_a = dur_a - cf_duration
        log(f'Tight blend: {cf_duration:.0f}s')

    else:
        # Standard fixed crossfade
        cf_duration = min(
            preset_params.get('crossfade_seconds', 15),
            dur_a - 5,
            dur_b - 5
        )
        if cf_duration < 3:
            cf_duration = min(dur_a, dur_b) / 3
        start_in_a = dur_a - cf_duration
        log(f'Standard crossfade: {cf_duration:.0f}s')

    # ── Align BPM with ffmpeg ──
    tmp_dir = Path(tempfile.mkdtemp(prefix='aidj_smart_'))
    aligned_a = tmp_dir / 'a_aligned.wav'
    aligned_b = tmp_dir / 'b_aligned.wav'

    try:
        for track, aligned, bpm_orig, label in [
            (track_a, aligned_a, bpm_a, 'A'),
            (track_b, aligned_b, bpm_b, 'B'),
        ]:
            ratio = target_bpm / max(bpm_orig, 1)
            if abs(ratio - 1.0) > 0.02:
                log(f'Tempo {label}: {bpm_orig} → {target_bpm} BPM (x{ratio:.3f})')
                cmd = [
                    'ffmpeg', '-y', '-i', str(track),
                    '-filter:a', f'atempo={ratio}',
                    '-ac', '2', '-ar', '44100',
                    str(aligned)
                ]
            else:
                cmd = [
                    'ffmpeg', '-y', '-i', str(track),
                    '-ac', '2', '-ar', '44100',
                    str(aligned)
                ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)

        # ── Apply crossfade ──
        curve1 = preset_params.get('curve1', 'tri')
        curve2 = preset_params.get('curve2', 'tri')

        cmd = [
            'ffmpeg', '-y',
            '-i', str(aligned_a),
            '-i', str(aligned_b),
            '-filter_complex',
            f'acrossfade=d={cf_duration}:curve1={curve1}:curve2={curve2}',
            '-ac', '2', '-ar', '44100',
            '-b:a', '192k',
            str(output)
        ]

        log(f'Applying acrossfade (d={cf_duration:.0f}s, curve={curve1}/{curve2})...')
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)

        # Verify
        out_dur = 0
        try:
            res = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries',
                 'format=duration', '-of', 'json', str(output)],
                capture_output=True, text=True, timeout=10
            )
            out_dur = round(float(json.loads(res.stdout)['format']['duration']), 1)
        except Exception:
            pass

        log(f'✅ Output: {os.path.basename(output)} ({out_dur:.0f}s)')

        return {
            'status': 'ok',
            'output': str(output),
            'duration': out_dur,
            'crossfade_actual': round(cf_duration, 1),
            'start_in_a': round(start_in_a, 1),
            'method': 'breakdown_matching' if blend_type == 'layering' else 'standard',
        }

    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors='replace')[:500]
        log(f'❌ ffmpeg: {err}')
        return {'status': 'error', 'error': f'ffmpeg: {err}'}
    except Exception as e:
        log(f'❌ {e}')
        return {'status': 'error', 'error': str(e)[:300]}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

#!/usr/bin/env python3
"""
AI DJ — Preset Engine v1
Применяет пресет стиля сведения к трекам и генерирует параметры для aidj-engine.py.

Usage:
  from presets.engine import apply_preset
  params = apply_preset(tracks, preset_id)
"""

import json
import math
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def load_preset(preset_id='default'):
    """Загружает пресет из JSON."""
    presets_index = BASE_DIR / 'index.json'
    if not presets_index.exists():
        return None

    index = json.loads(presets_index.read_text(encoding='utf-8'))

    for p in index.get('presets', []):
        if p['id'] == preset_id:
            preset_path = BASE_DIR / p.get('file', f'{preset_id}-preset.json')
            if preset_path.exists():
                preset = json.loads(preset_path.read_text(encoding='utf-8'))
                preset['meta'] = {k: v for k, v in p.items() if k != 'file'}
                return preset
    return None


def list_presets():
    """Возвращает список доступных пресетов."""
    presets_index = BASE_DIR / 'index.json'
    if not presets_index.exists():
        return []

    index = json.loads(presets_index.read_text(encoding='utf-8'))
    return index.get('presets', [])


def apply_preset(tracks, preset_id='default', track_info=None):
    """
    Применяет пресет к трекам. Возвращает параметры для mixing engine.

    Args:
        tracks: список треков для сведения
        preset_id: id пресета
        track_info: dict с результатами анализа треков (BPM, key, camelot, duration)

    Returns:
        dict: параметры сведения для engine
    """
    preset = load_preset(preset_id)
    if not preset:
        print(f'[PRESET] Preset "{preset_id}" not found, using default', file=sys.stderr)
        preset = load_preset('default')

    params = preset['parameters']
    track_info = track_info or {}

    result = {
        'preset_id': preset_id,
        'preset_name': preset['name'],
        'params': {},
        'segments': [],
        'warnings': [],
    }

    # ─── Crossfade / blend type ───
    cf = params.get('crossfade', {})
    cf_type = cf.get('type', 'crossfade')
    cf_range = cf.get('duration_seconds', [12, 15])

    if cf_type == 'smart_variable':
        # Variable blend: smart crossfade with structure analysis
        result['params']['blend_type'] = 'layering'
        result['params']['crossfade_seconds'] = sum(cf_range) / 2 if cf_range else 60
        result['params']['crossfade_range'] = [cf.get('min_seconds', 15), cf.get('max_seconds', 120)]
        result['params']['layering'] = True
        result['params']['breakdown_matching'] = cf.get('type', '') == 'smart_variable'
    elif cf_type == 'long_blend':
        # Long layout: треки накладываются на 1.5–3 мин
        result['params']['blend_type'] = 'layering'
        result['params']['crossfade_seconds'] = sum(cf_range) / 2
        result['params']['layering'] = True
    elif cf_type == 'fixed':
        result['params']['blend_type'] = 'crossfade'
        result['params']['crossfade_seconds'] = sum(cf_range) / 2 if cf_range else 35
        result['params']['layering'] = False
    elif cf_type == 'crossfade':
        result['params']['blend_type'] = 'crossfade'
        # Берём среднее
        result['params']['crossfade_seconds'] = sum(cf_range) / 2 if cf_range else 15
        result['params']['layering'] = False

    # ─── Tempo mode ───
    tempo = params.get('tempo', {})
    tempo_mode = tempo.get('mode', 'follow_fastest')
    result['params']['tempo_mode'] = tempo_mode

    if tempo_mode == 'lock_tight':
        # Все треки к первому (не подгоняем, только ±0.5)
        master_bpm = None
        for t in tracks:
            ti = track_info.get(t.get('filepath', t.get('url', '')), {})
            bpm = ti.get('bpm', 120)
            if master_bpm is None:
                master_bpm = bpm
            diff = abs(bpm - master_bpm)
            if diff > 0.5:
                result['warnings'].append(
                    f'BPM mismatch: {bpm} vs {master_bpm} (preset tolerates ±0.5)')
        result['params']['target_bpm'] = master_bpm
        result['params']['tempo_tolerance'] = tempo.get('tolerance_bpm', 0.5)
    elif tempo_mode == 'follow_fastest':
        # Выравнивание по самому быстрому
        fastest = max(t['bpm'] for t in tracks if 'bpm' in t) if track_info else 120
        result['params']['target_bpm'] = fastest

    # ─── EQ phases (for layering / long blend) ───
    eq = params.get('eq', {})
    eq_phases = eq.get('phases', [])

    if eq_phases:
        result['params']['eq_mode'] = 'phased'
        result['params']['eq_phases'] = eq_phases
    else:
        eq_mode = eq.get('mode', 'none')
        result['params']['eq_mode'] = eq_mode

    # ─── Harmonic mode ───
    harmonic = params.get('harmonic', {})
    harm_mode = harmonic.get('mode', 'ignore')
    result['params']['harmonic_mode'] = harm_mode

    if harm_mode == 'camelot_wheel':
        allowed = harmonic.get('allowed_transitions', ['same'])
        # Проверяем совместимость треков по тональностям
        track_keys = []
        for t in tracks:
            ti = track_info.get(t.get('filepath', t.get('url', '')), {})
            track_keys.append(ti.get('camelot', '?'))

        for i in range(1, len(track_keys)):
            ck_prev = track_keys[i - 1]
            ck_curr = track_keys[i]
            if ck_prev == '?' or ck_curr == '?':
                continue
            num_prev = int(ck_prev[:-1])
            num_curr = int(ck_curr[:-1])
            diff = abs(num_prev - num_curr)
            ok = any(
                (t == 'same' and diff == 0) or
                (t == '+1_up' and diff == 1 and num_curr > num_prev) or
                (t == '+1_down' and diff == 1 and num_curr < num_prev)
                for t in allowed
            )
            if not ok:
                result['warnings'].append(
                    f'Harmonic mismatch: {ck_prev} → {ck_curr}'
                )

    # ─── Blend options (smart crossfade) ───
    blend = params.get('blend', {})
    if blend.get('breakdown_matching'):
        result['params']['breakdown_matching'] = True
        result['params']['blend_type'] = 'layering'
    if blend.get('intro_scan'):
        result['params']['intro_scan'] = True

    # ─── Style metadata ───
    style = params.get('style', {})
    if style:
        result['params']['style'] = style

    # ─── Curve type for ffmpeg acrossfade ───
    curve = params.get('curve', {})
    result['params']['curve_type'] = curve.get('type', 'linear')
    result['params']['curve1'] = curve.get('curve1', 'tri')
    result['params']['curve2'] = curve.get('curve2', 'tri')

    # ─── Structure ───
    structure = params.get('structure', {})
    if structure:
        result['params']['structure'] = structure

    # ─── Narrative acts metadata ───
    narrative = params.get('narrative', {})
    if narrative:
        result['params']['narrative'] = narrative

    return result


def preset_to_mix_params(tracks, preset_id='default', track_info=None):
    """
    Упрощённый интерфейс: возвращает только то, что нужно aidj-engine.py.
    """
    result = apply_preset(tracks, preset_id, track_info)
    p = result['params']

    params = {
        'preset': preset_id,
        'preset_name': result['preset_name'],
        'crossfade_seconds': p.get('crossfade_seconds', 15),
        'target_bpm': p.get('target_bpm', 120),
        'blend_type': p.get('blend_type', 'crossfade'),
        'curve_type': p.get('curve_type', 'linear'),
        'curve1': p.get('curve1', 'tri'),
        'curve2': p.get('curve2', 'tri'),
        'tempo_mode': p.get('tempo_mode', 'follow_fastest'),
        'tempo_tolerance': p.get('tempo_tolerance', 1),
        'eq_mode': p.get('eq_mode', 'none'),
        'harmonic_mode': p.get('harmonic_mode', 'ignore'),
        'warnings': result.get('warnings', []),
        # Smart mixing flags
        'breakdown_matching': p.get('breakdown_matching', False),
        'intro_scan': p.get('intro_scan', False),
        'style': p.get('style', {}).get('type', 'standard'),
    }

    # Dynamic crossfade range (Tranceport-style: 15-120s)
    crossfade_range = p.get('crossfade_range', None)
    if crossfade_range:
        params['crossfade_min'] = crossfade_range[0]
        params['crossfade_max'] = crossfade_range[1]

    # EQ phases (для layering-пресетов)
    if p.get('eq_phases'):
        params['eq_phases'] = p['eq_phases']

    return params


def test():
    """Тест: применение Oakenfold пресета к двум трекам."""
    from pathlib import Path

    tracks = [
        {'title': 'Track A', 'url': 'tracks/track_a.mp3'},
        {'title': 'Track B', 'url': 'tracks/track_b.mp3'},
    ]

    track_info = {
        'tracks/track_a.mp3': {'bpm': 134, 'key': 'Am', 'camelot': '8A'},
        'tracks/track_b.mp3': {'bpm': 134, 'key': 'Am', 'camelot': '8A'},
    }

    params = preset_to_mix_params(tracks, 'oakenfold', track_info)
    print(json.dumps(params, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    test()

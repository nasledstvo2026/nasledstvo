#!/usr/bin/env python3
"""
Анализ каждого перехода Tranceport с построением energy profile.
Для каждого перехода выводит JSON с точками: время, energy.
"""

import sys, os, json, subprocess
import numpy as np
import librosa

TRANCEPORT_FILE = '/home/user1/.openclaw/workspace/aidj/fantazia-tracks/Tranceport-merged.flac'
WAV_CACHE = '/tmp/tranceport-analysis.wav'

# Точные моменты стыков из research (конец трека = начало перехода)
TRANSITIONS = [
    {'id': 1, 'a': 'The Dream Traveler — Time', 'b': 'Three Drives on a Vinyl — Greece 2000', 'a_end': 396},
    {'id': 2, 'a': 'Three Drives on a Vinyl — Greece 2000', 'b': 'Tilt vs. Paul van Dyk — Rendezvous', 'a_end': 786},
    {'id': 3, 'a': 'Tilt vs. Paul van Dyk — Rendezvous', 'b': 'Gus Gus — Purple', 'a_end': 1025},
    {'id': 4, 'a': 'Gus Gus — Purple', 'b': 'Ascension — Someone', 'a_end': 1520},
    {'id': 5, 'a': 'Ascension — Someone', 'b': 'Agnelli & Nelson — El Niño', 'a_end': 2018},
    {'id': 6, 'a': 'Agnelli & Nelson — El Niño', 'b': 'Energy 52 — Café del Mar', 'a_end': 2459},
    {'id': 7, 'a': 'Energy 52 — Café del Mar', 'b': 'Binary Finary — 1998', 'a_end': 2891},
    {'id': 8, 'a': 'Binary Finary — 1998', 'b': 'Paul van Dyk — Words', 'a_end': 3181},
    {'id': 9, 'a': 'Paul van Dyk — Words', 'b': 'Lost Tribe — Gamemaster', 'a_end': 3506},
    {'id': 10, 'a': 'Lost Tribe — Gamemaster', 'b': 'Transa — Enervate', 'a_end': 3944},
]

def main():
    # Подготовка WAV
    if not os.path.exists(WAV_CACHE):
        print('Converting to WAV...', file=sys.stderr)
        subprocess.run(['ffmpeg', '-y', '-i', TRANCEPORT_FILE, '-ac', '1', '-ar', '22050',
                       WAV_CACHE], check=True, capture_output=True, timeout=120)

    print('Loading...', file=sys.stderr)
    y, sr = librosa.load(WAV_CACHE, sr=22050, mono=True)
    duration = len(y) / sr
    hop_length = 512

    # RMS всего микса
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop_length)[0]
    rms_smooth = np.convolve(rms, np.ones(87)/87, mode='same')
    rms_norm = rms_smooth / max(rms_smooth.max(), 1e-10)
    rms_time = np.arange(len(rms_norm)) * hop_length / sr

    results = []

    for t in TRANSITIONS:
        tid = t['id']
        a_end = t['a_end']
        # Окно: от 2 мин до конца трека А до 30с после начала трека Б
        win_start = max(0, a_end - 120)
        win_end = min(duration, a_end + 30)

        idx_start = max(0, int(win_start * sr / hop_length))
        idx_end = min(len(rms_norm), int(win_end * sr / hop_length))
        
        seg_time = rms_time[idx_start:idx_end]
        seg_energy = rms_norm[idx_start:idx_end]

        # Профиль (децимация для вывода)
        profile = []
        for i in range(0, len(seg_time), 5):
            profile.append({
                't': round(float(seg_time[i] - a_end), 1),  # относительно стыка
                'e': round(float(seg_energy[i]), 4)
            })

        # Минимум
        min_idx = np.argmin(seg_energy)
        min_abs_time = seg_time[min_idx]

        # Найти: 
        # - когда энергия падает ниже 50% (начало crossfade)
        # - когда поднимается выше 50% после минимума (конец crossfade)
        cf_start = 0
        cf_end = len(seg_energy) - 1
        for i in range(min_idx, -1, -1):
            if seg_energy[i] < 0.5:
                cf_start = i
            else:
                break
        for i in range(min_idx, len(seg_energy)):
            if seg_energy[i] < 0.5:
                cf_end = i
            else:
                break

        cf_duration = seg_time[cf_end] - seg_time[cf_start]

        print(f"\n{tid}. {t['a']} → {t['b']}", file=sys.stderr)
        print(f"   Crossfade: {seg_time[cf_start]-a_end:.0f}s → {seg_time[cf_end]-a_end:.0f}s (dur={cf_duration:.0f}s)", file=sys.stderr)
        print(f"   Min energy: {seg_energy[min_idx]:.3f} at {min_abs_time-a_end:.0f}s", file=sys.stderr)
        print(f"   Type: ", end='', file=sys.stderr)
        
        # Классификация
        energy_before = seg_energy[max(0, cf_start-5)]
        energy_after = seg_energy[min(len(seg_energy)-1, cf_end+5)]
        
        if min_idx < len(seg_energy) * 0.3:
            trans_type = 'outro_fade'  # трек А дозвучал, Б входит
            print('Outro fade (A finishes → B starts)', file=sys.stderr)
        elif energy_before > 0.6 and seg_energy[min_idx] < 0.3:
            trans_type = 'breakdown_matching'
            print('Breakdown matching (A breaks → B enters)', file=sys.stderr)
        else:
            trans_type = 'smooth_blend'
            print('Smooth long blend', file=sys.stderr)

        results.append({
            'transition_id': tid,
            'track_a': t['a'],
            'track_b': t['b'],
            'a_end_sec': a_end,
            'crossfade': {
                'start_rel_sec': round(float(seg_time[cf_start] - a_end), 1),
                'end_rel_sec': round(float(seg_time[cf_end] - a_end), 1),
                'duration_sec': round(cf_duration, 1),
                'min_energy': round(float(seg_energy[min_idx]), 3),
                'min_at_rel_sec': round(float(min_abs_time - a_end), 1),
                'type': trans_type,
            },
            'profile': profile,
        })

    # Итоговая статистика
    cfs = [r['crossfade']['duration_sec'] for r in results]
    print(f"\n{'='*50}", file=sys.stderr)
    print(f"Total: {len(results)} transitions", file=sys.stderr)
    print(f"Crossfade: mean={np.mean(cfs):.0f}s, min={min(cfs):.0f}s, max={max(cfs):.0f}s", file=sys.stderr)
    print(f"Types:", file=sys.stderr)
    for r in results:
        print(f"  {r['transition_id']}: {r['crossfade']['type']} ({r['crossfade']['duration_sec']:.0f}s)", file=sys.stderr)

    out = {
        'source': 'Paul Oakenfold — Tranceport (1998)',
        'bpm': 136.0,
        'transitions': results,
        'stats': {
            'mean_crossfade': round(np.mean(cfs), 1),
            'min_crossfade': min(cfs),
            'max_crossfade': max(cfs),
        }
    }

    out_path = '/home/user1/.openclaw/workspace/aidj/fantazia-tracks/tranceport-transitions-v2.json'
    with open(out_path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Saved to {out_path}", file=sys.stderr)
    print(json.dumps(out['stats'], ensure_ascii=False))

if __name__ == '__main__':
    main()

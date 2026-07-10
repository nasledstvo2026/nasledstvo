#!/usr/bin/env python3
"""
Точный анализ каждого перехода в Paul Oakenfold — Tranceport (1998).
Извлекает реальные параметры crossfade из готового склеенного микса.
"""

import sys, os, json, subprocess
import numpy as np
import librosa

TRANCEPORT_FILE = '/home/user1/.openclaw/workspace/aidj/fantazia-tracks/Tranceport-merged.flac'

# Треклист с таймингом (из research-oakenfold.md)
TRACKS = [
    {'name': 'The Dream Traveler — Time', 'start': 0, 'end': 396},
    {'name': 'Three Drives on a Vinyl — Greece 2000', 'start': 396, 'end': 786},
    {'name': 'Tilt vs. Paul van Dyk — Rendezvous', 'start': 786, 'end': 1025},
    {'name': 'Gus Gus — Purple (Sasha vs. The Light)', 'start': 1025, 'end': 1520},
    {'name': 'Ascension — Someone', 'start': 1520, 'end': 2018},
    {'name': 'Agnelli & Nelson — El Niño', 'start': 2018, 'end': 2459},
    {'name': 'Energy 52 — Café del Mar (Three N One Remix)', 'start': 2459, 'end': 2891},
    {'name': 'Binary Finary — 1998', 'start': 2891, 'end': 3181},
    {'name': 'Paul van Dyk — Words (For Love)', 'start': 3181, 'end': 3506},
    {'name': 'Lost Tribe — Gamemaster', 'start': 3506, 'end': 3944},
    {'name': 'Transa — Enervate', 'start': 3944, 'end': 4410},
]

def analyze_transition(y, sr, start_sec, end_sec, name_a, name_b, hop_length=512):
    """Анализирует один переход между треками."""
    start_sample = int(start_sec * sr)
    end_sample = int(end_sec * sr)
    seg = y[start_sample:end_sample]

    # RMS energy
    rms = librosa.feature.rms(y=seg, frame_length=2048, hop_length=hop_length)[0]
    rms_smooth = np.convolve(rms, np.ones(43)/43, mode='same')
    rms_norm = rms_smooth / max(rms_smooth.max(), 1e-10)
    rms_time = np.arange(len(rms_norm)) * hop_length / sr

    # Найти момент, когда энергия падает ниже 30% (начинается переход)
    # И момент, когда поднимается выше 50% (заканчивается переход)
    transition_start = None
    transition_end = None
    in_transition = False
    
    for i in range(len(rms_norm)):
        if not in_transition and rms_norm[i] < 0.30:
            transition_start = rms_time[i]
            in_transition = True
        elif in_transition and rms_norm[i] > 0.50:
            transition_end = rms_time[i]
            in_transition = False
            # Если это первый выход — он наш
            if transition_end and transition_start:
                break

    if transition_start is None:
        transition_start = 0
        transition_end = rms_time[-1]
    
    if transition_start is None or transition_end is None:
        # Fallback: найти минимум и измерить вокруг него
        min_idx = np.argmin(rms_norm)
        transition_start = rms_time[max(0, min_idx - len(rms_norm)//4)]
        transition_end = rms_time[min(len(rms_norm)-1, min_idx + len(rms_norm)//4)]
    elif transition_start > transition_end - 5:
        # Fallback: найти минимум и измерить вокруг него
        min_idx = np.argmin(rms_norm)
        transition_start = rms_time[max(0, min_idx - len(rms_norm)//4)]
        transition_end = rms_time[min(len(rms_norm)-1, min_idx + len(rms_norm)//4)]

    crossfade_dur = transition_end - transition_start if transition_end else 0
    
    # Энергия на момент старта crossfade и на момент завершения
    start_frame = int(transition_start * sr / hop_length)
    end_frame = int(transition_end * sr / hop_length)
    start_energy = float(rms_norm[min(start_frame, len(rms_norm)-1)])
    end_energy = float(rms_norm[min(end_frame, len(rms_norm)-1)])
    min_energy = float(rms_norm.min())

    return {
        'transition_start_sec': round(transition_start, 1),
        'transition_end_sec': round(transition_end if transition_end else transition_start, 1),
        'crossfade_duration_sec': round(crossfade_dur, 1),
        'energy_at_start': round(start_energy, 3),
        'energy_at_end': round(end_energy, 3),
        'min_energy_during_transition': round(min_energy, 3),
        'total_window_sec': round(end_sec - start_sec, 1),
    }


def main():
    # Загружаем через преобразованный wav (librosa не всегда корректно читает сложные flac)
    wav_path = '/tmp/tranceport-analysis.wav'
    if not os.path.exists(wav_path):
        print('Converting to WAV for analysis...', file=sys.stderr)
        subprocess.run(['ffmpeg', '-y', '-i', TRANCEPORT_FILE, '-ac', '1', '-ar', '22050',
                       wav_path], check=True, capture_output=True, timeout=120)
    
    print(f'Loading {wav_path}...', file=sys.stderr)
    y, sr = librosa.load(wav_path, sr=22050, mono=True)
    print(f'Loaded: {len(y)/sr:.0f}s @ {sr}Hz', file=sys.stderr)

    transitions = []

    for i in range(len(TRACKS) - 1):
        a_end = TRACKS[i]['end']
        b_start = TRACKS[i+1]['start']
        
        # Окно анализа: 60 секунд до конца трека A и 60 секунд после начала трека B
        # Tranceport имеет длинные blend'ы до 2 мин, нужно широкое окно
        window_start = max(0, a_end - 60)
        window_end = min(len(y)/sr, b_start + 60)
        
        print(f'\n{i+1}→{i+2}: {TRACKS[i]["name"]} → {TRACKS[i+1]["name"]}', file=sys.stderr)
        print(f'   Window: {window_start:.0f}s - {window_end:.0f}s', file=sys.stderr)
        
        result = analyze_transition(
            y, sr, window_start, window_end,
            TRACKS[i]['name'], TRACKS[i+1]['name']
        )
        result['transition_id'] = i + 1
        result['track_a'] = TRACKS[i]['name']
        result['track_b'] = TRACKS[i+1]['name']
        result['track_a_end'] = a_end
        result['crossfade_end_abs'] = round(window_start + result['transition_start_sec'], 1)
        result['crossfade_start_abs'] = round(window_start + result['transition_end_sec'], 1)
        
        transitions.append(result)
        print(f'   Crossfade: {result["transition_start_sec"]}s → {result["transition_end_sec"]}s (dur={result["crossfade_duration_sec"]}s)', file=sys.stderr)
        print(f'   Energy: {result["energy_at_start"]} → min {result["min_energy_during_transition"]} → {result["energy_at_end"]}', file=sys.stderr)

    # Вывод JSON
    summary = {
        'source': 'Paul Oakenfold — Tranceport (1998)',
        'analysis_date': '2026-06-28',
        'bpm': 136.0,
        'transitions': transitions,
        'stats': {
            'avg_crossfade_duration': round(np.mean([t['crossfade_duration_sec'] for t in transitions]), 1),
            'min_crossfade_duration': min(t['crossfade_duration_sec'] for t in transitions),
            'max_crossfade_duration': max(t['crossfade_duration_sec'] for t in transitions),
            'avg_min_energy': round(np.mean([t['min_energy_during_transition'] for t in transitions]), 3),
        }
    }

    out_path = '/home/user1/.openclaw/workspace/aidj/fantazia-tracks/tranceport-transitions-detailed.json'
    with open(out_path, 'w') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f'\n✅ Saved to {out_path}', file=sys.stderr)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()

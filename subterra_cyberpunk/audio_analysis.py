from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import librosa
import numpy as np
from scipy.signal import find_peaks


@dataclass
class AudioSummary:
    source: str
    duration_seconds: float
    sample_rate: int
    estimated_bpm: float
    estimated_key: str
    beats: int
    sections: list[dict[str, Any]]
    energy_mean: float
    energy_peak: float
    brightness_mean: float
    percussiveness: float
    dynamic_range: float
    mood_tags: list[str]


_MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _normalize(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    if not x.size:
        return np.zeros_like(x)
    lo, hi = np.nanpercentile(x, [2, 98])
    if hi <= lo + 1e-9:
        return np.zeros_like(x)
    return np.clip((x - lo) / (hi - lo), 0.0, 1.0)


def _estimate_key(chroma: np.ndarray) -> str:
    avg = np.mean(chroma, axis=1)
    avg = (avg - avg.mean()) / (avg.std() + 1e-8)
    candidates: list[tuple[float, str]] = []
    for root in range(12):
        candidates.append((float(np.corrcoef(avg, np.roll(_MAJOR_PROFILE, root))[0, 1]), f"{_NOTES[root]} major"))
        candidates.append((float(np.corrcoef(avg, np.roll(_MINOR_PROFILE, root))[0, 1]), f"{_NOTES[root]} minor"))
    return max(candidates, key=lambda x: x[0])[1]


def _section_boundaries(features: np.ndarray, times: np.ndarray, duration: float) -> np.ndarray:
    if features.shape[1] < 4:
        return np.array([0.0, duration], dtype=np.float32)
    smooth = np.vstack([np.convolve(row, np.ones(13) / 13, mode="same") for row in features])
    novelty = np.linalg.norm(np.diff(smooth, axis=1, prepend=smooth[:, :1]), axis=0)
    novelty = _normalize(novelty)
    dt = max(times[1] - times[0], 1e-3) if len(times) > 1 else 1.0
    frame_gap = max(1, int(6.0 / dt))
    peaks, props = find_peaks(novelty, distance=frame_gap, prominence=0.15)
    ranked = peaks[np.argsort(props.get("prominences", np.ones(len(peaks))))[::-1]] if len(peaks) else peaks
    max_sections = max(3, min(18, int(duration // 14) + 3))
    selected = sorted(ranked[: max_sections - 1].tolist())
    bounds = [0.0] + [float(times[min(i, len(times) - 1)]) for i in selected] + [float(duration)]
    cleaned = [bounds[0]]
    for b in bounds[1:]:
        if b - cleaned[-1] >= 3.5 or b == duration:
            cleaned.append(b)
    if cleaned[-1] != duration:
        cleaned.append(duration)
    return np.asarray(cleaned, dtype=np.float32)


def _band_curve(S: np.ndarray, freqs: np.ndarray, lo: float, hi: float) -> np.ndarray:
    mask = (freqs >= lo) & (freqs < hi)
    if not np.any(mask):
        return np.zeros(S.shape[1], dtype=np.float32)
    return _normalize(np.mean(S[mask], axis=0))


def _assign_roles(sections: list[dict[str, Any]]) -> None:
    if not sections:
        return
    energies = np.asarray([s["energy"] for s in sections], dtype=np.float32)
    impacts = np.asarray([s["impact"] for s in sections], dtype=np.float32)
    low, med, high = np.quantile(energies, [0.25, 0.5, 0.76])
    imp_hi = float(np.quantile(impacts, 0.72))
    for i, s in enumerate(sections):
        e, imp = s["energy"], s["impact"]
        prev_e = sections[i - 1]["energy"] if i else e
        next_e = sections[i + 1]["energy"] if i + 1 < len(sections) else e
        if i == 0 and s["start"] <= 1.0:
            role = "intro"
        elif i == len(sections) - 1 and e < med:
            role = "outro"
        elif e >= high or (e >= med and imp >= imp_hi):
            role = "climax"
        elif e <= low:
            role = "breakdown"
        elif e - prev_e > 0.18 and prev_e <= med:
            role = "drop"
        elif next_e - e > 0.12:
            role = "buildup"
        else:
            role = "development"
        s["role"] = role


def analyze_audio(audio_path: str | Path, output_dir: str | Path) -> tuple[AudioSummary, Path, Path]:
    audio_path = Path(audio_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
    if y.size == 0:
        raise ValueError("O arquivo de áudio está vazio ou não pôde ser decodificado.")
    duration = float(librosa.get_duration(y=y, sr=sr))
    hop = 512

    harmonic, percussive = librosa.effects.hpss(y)
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    onset = librosa.onset.onset_strength(y=percussive, sr=sr, hop_length=hop)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop)[0]
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr, hop_length=hop)[0]
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, hop_length=hop, roll_percent=0.90)[0]
    flatness = librosa.feature.spectral_flatness(y=y, hop_length=hop)[0]
    chroma = librosa.feature.chroma_cens(y=harmonic, sr=sr, hop_length=hop)
    contrast = librosa.feature.spectral_contrast(y=y, sr=sr, hop_length=hop)
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop)

    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset, sr=sr, hop_length=hop)
    bpm = float(np.asarray(tempo).reshape(-1)[0]) if np.asarray(tempo).size else 0.0
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop)

    min_len = min(len(rms), len(onset), len(centroid), len(bandwidth), len(rolloff), len(flatness), chroma.shape[1], contrast.shape[1], S.shape[1])
    times, rms, onset = times[:min_len], rms[:min_len], onset[:min_len]
    centroid, bandwidth, rolloff, flatness = centroid[:min_len], bandwidth[:min_len], rolloff[:min_len], flatness[:min_len]
    chroma, contrast, S = chroma[:, :min_len], contrast[:, :min_len], S[:, :min_len]

    energy = _normalize(rms)
    impact = _normalize(onset)
    brightness = _normalize(centroid)
    texture = _normalize(flatness)
    width = _normalize(bandwidth)
    high = _normalize(rolloff)
    harmonicity = _normalize(np.mean(chroma, axis=0))
    contrast_mean = _normalize(np.mean(contrast, axis=0))
    flux = _normalize(np.sqrt(np.sum(np.maximum(0.0, np.diff(S, axis=1, prepend=S[:, :1])) ** 2, axis=0)))
    sub = _band_curve(S, freqs, 20, 80)
    bass = _band_curve(S, freqs, 80, 250)
    low_mid = _band_curve(S, freqs, 250, 700)
    mid = _band_curve(S, freqs, 700, 2500)
    presence = _band_curve(S, freqs, 2500, 6000)
    air = _band_curve(S, freqs, 6000, sr / 2 + 1)

    struct_features = np.vstack([chroma, energy[None, :], brightness[None, :], impact[None, :], bass[None, :], flux[None, :]])
    bounds = _section_boundaries(struct_features, times, duration)

    sections: list[dict[str, Any]] = []
    for idx in range(len(bounds) - 1):
        start, end = float(bounds[idx]), float(bounds[idx + 1])
        mask = (times >= start) & (times < end)
        if not np.any(mask):
            mask = np.ones(len(times), dtype=bool)
        sections.append({
            "index": idx,
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(end - start, 3),
            "energy": round(float(np.mean(energy[mask])), 4),
            "impact": round(float(np.mean(impact[mask])), 4),
            "brightness": round(float(np.mean(brightness[mask])), 4),
            "bass": round(float(np.mean(bass[mask])), 4),
            "flux": round(float(np.mean(flux[mask])), 4),
            "role": "development",
        })
    _assign_roles(sections)

    perc_ratio = float(np.sqrt(np.mean(percussive**2)) / (np.sqrt(np.mean(y**2)) + 1e-9))
    dynamic_range = float(np.percentile(rms, 95) - np.percentile(rms, 10))
    mood: list[str] = []
    mood.append("aggressive" if np.mean(impact) > 0.38 else "hypnotic")
    mood.append("bright" if np.mean(brightness) > 0.52 else "dark")
    mood.append("dense" if np.mean(texture) > 0.45 else "spacious")
    mood.append("bass-heavy" if np.mean(bass) > np.mean(presence) else "aerial")
    if bpm >= 125:
        mood.append("driving")

    summary = AudioSummary(
        source=str(audio_path.resolve()),
        duration_seconds=round(duration, 4),
        sample_rate=sr,
        estimated_bpm=round(bpm, 3),
        estimated_key=_estimate_key(chroma),
        beats=int(len(beat_times)),
        sections=sections,
        energy_mean=round(float(np.mean(energy)), 4),
        energy_peak=round(float(np.max(energy)), 4),
        brightness_mean=round(float(np.mean(brightness)), 4),
        percussiveness=round(perc_ratio, 4),
        dynamic_range=round(dynamic_range, 5),
        mood_tags=mood,
    )

    json_path = output_dir / "analysis.json"
    npz_path = output_dir / "features.npz"
    json_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    np.savez_compressed(
        npz_path,
        times=times.astype(np.float32), energy=energy.astype(np.float32), impact=impact.astype(np.float32),
        brightness=brightness.astype(np.float32), texture=texture.astype(np.float32), width=width.astype(np.float32),
        high=high.astype(np.float32), harmonicity=harmonicity.astype(np.float32), contrast=contrast_mean.astype(np.float32),
        flux=flux.astype(np.float32), sub=sub.astype(np.float32), bass=bass.astype(np.float32), low_mid=low_mid.astype(np.float32),
        mid=mid.astype(np.float32), presence=presence.astype(np.float32), air=air.astype(np.float32),
        beat_times=np.asarray(beat_times, dtype=np.float32), section_bounds=bounds.astype(np.float32),
    )
    return summary, json_path, npz_path

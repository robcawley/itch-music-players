#!/usr/bin/env python3
"""
Build the data a player needs from a folder of WAV (or any ffmpeg-readable) files:
a 128 kbps MP3 preview of each track in <out>/audio/ and the JSON file the page loads.

    build_player.py <style> <audio-folder> <out-folder> [options]

styles
    deck    waveform + track list                -> tracks.json  (players/deck)
    scope   adds loudness curve and onset hits   -> tracks.json  (players/night-vision)
    chase   adds kicks, beat grid, heat sections -> tracks.json  (players/night-chase)
    single  one track, waveform only             -> track.json   (players/rain-and-neon)

options
    --bpm 95,90     tempo of each track, in file order (chase only; default: 100)
    --bitrate 128   MP3 bitrate in kbps (default 128)
    --no-mp3        rebuild the JSON only
    --only 1,3      process only these track numbers (files are numbered in sorted order)
    --artist NAME   written into the MP3 tags
    --album NAME    written into the MP3 tags

The page expects the result next to index.html:  index.html, tracks.json (or track.json), audio/01.mp3 ...
Needs Python 3, numpy and ffmpeg on the PATH.
"""
import json, os, re, subprocess, sys
import numpy as np

SR, HOP, N = 22050, 512, 2048
EXT = (".wav", ".aif", ".aiff", ".flac", ".mp3", ".ogg", ".m4a")


def load(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def rms(a):
    return float(np.sqrt((a ** 2).mean())) if len(a) else 0.0


def peaks(x, n):
    seg = max(1, len(x) // n)
    pk = np.array([rms(x[i * seg:(i + 1) * seg]) for i in range(n)])
    return pk / (pk.max() or 1)


def energy_curve(x):
    """Loudness, four values a second, scaled 0..1 between the 5th and 98th percentile."""
    step = SR // 4
    en = np.array([rms(x[i:i + step]) for i in range(0, len(x) - step + 1, step)])
    lo, hi = np.percentile(en, 5), np.percentile(en, 98)
    return np.clip((en - lo) / (hi - lo + 1e-9), 0, 1)


def spectrum(x):
    w = np.hanning(N)
    frames = np.lib.stride_tricks.sliding_window_view(x, N)[::HOP]
    S = np.abs(np.fft.rfft(frames * w, axis=1))
    return S, np.fft.rfftfreq(N, 1 / SR), SR / HOP


def flux(S, f, fps, lo, hi):
    b = np.log1p(S[:, (f >= lo) & (f < hi)] * 10)
    return np.concatenate([[0], np.maximum(0, np.diff(b, axis=0)).sum(1)])


def pick(env, fps, gap_s, pct):
    """Strongest onsets: local mean removed, peaks over a percentile, with a minimum gap."""
    env = env - np.convolve(env, np.ones(int(fps)) / int(fps), "same")
    thr = np.percentile(env, pct)
    out, last = [], -1e9
    for i in range(1, len(env) - 1):
        if env[i] > thr and env[i] >= env[i - 1] and env[i] >= env[i + 1] and (i - last) / fps >= gap_s:
            out.append(i)
            last = i
    s = env[out]
    s = (s - s.min()) / (np.ptp(s) + 1e-9) if len(out) else s
    return [[round(i / fps, 3), round(float(v), 2)] for i, v in zip(out, s)]


def analyse(style, x, bpm):
    secs = len(x) / SR
    if style == "deck":
        return dict(seconds=round(secs, 2), peaks=[round(float(v), 3) for v in peaks(x, 300)])
    if style == "single":
        return dict(seconds=round(secs, 2), peaks=[round(float(v), 3) for v in peaks(x, 120)])
    S, f, fps = spectrum(x)
    if style == "scope":
        hits = pick(flux(S, f, fps, 0, SR / 2), fps, 2.0, 98)
        return dict(seconds=round(secs, 2), peaks=[round(float(v), 3) for v in peaks(x, 120)],
                    energy=[round(float(v), 2) for v in energy_curve(x)], hits=hits)
    # chase
    low, full = flux(S, f, fps, 35, 160), flux(S, f, fps, 35, 8000)
    kicks, hits = pick(low, fps, 0.22, 88), pick(full, fps, 0.12, 85)
    per = 60.0 / bpm
    t = np.arange(len(full)) / fps
    env = low + 0.5 * full
    ph = np.linspace(0, per, 96, endpoint=False)
    score = [env[np.round(((np.arange(0, t[-1] - per, per) + p) * fps)).astype(int)].sum() for p in ph]
    phase = float(ph[int(np.argmax(score))])
    energy = energy_curve(x)
    # heat sections: 8 s smoothing, fixed levels, runs shorter than 8 s folded into the previous run
    sm = np.convolve(energy, np.ones(32) / 32, "same")
    lev = np.digitize(sm, [0.25, 0.5, 0.68])
    runs = []
    for i, l in enumerate(lev):
        if runs and runs[-1][1] == l:
            runs[-1][2] += 1
        else:
            runs.append([i, int(l), 1])
    heat = []
    for st, l, n in runs:
        if heat and (n < 32 or heat[-1][1] == l):
            continue
        heat.append([round(st / 4, 2), l])
    return dict(seconds=round(secs, 2), bpm=bpm, phase=round(phase, 3), peaks=[round(float(v), 3) for v in peaks(x, 120)],
                energy=[round(float(v), 2) for v in energy], kicks=kicks, hits=hits, heat=heat)


def clean_title(fn):
    t = os.path.splitext(fn)[0]
    t = re.sub(r"^\d+\s*[-._ ]\s*", "", t)          # "01 - Title" -> "Title"
    t = re.sub(r"^[^-]+ - (\d+ )?", "", t) if " - " in t else t   # "Artist - 01 Title" -> "Title"
    return t.replace("_", " ").strip()


def main(argv):
    if len(argv) < 4 or argv[1] not in ("deck", "scope", "chase", "single"):
        print(__doc__)
        return 1
    style, src, out = argv[1], argv[2], argv[3]

    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    bpms = [float(v) for v in opt("--bpm", "100").split(",")]
    kbps = opt("--bitrate", "128")
    artist, album = opt("--artist", ""), opt("--album", "")
    only = {int(v) for v in opt("--only", "").split(",") if v}
    os.makedirs(os.path.join(out, "audio"), exist_ok=True)
    files = sorted(f for f in os.listdir(src) if f.lower().endswith(EXT))
    if style == "single":
        files = files[:1]
    tracks = []
    for i, fn in enumerate(files, 1):
        if only and i not in only:
            continue
        path = os.path.join(src, fn)
        title = clean_title(fn)
        mp3 = "audio/%02d.mp3" % i
        if "--no-mp3" not in argv:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-c:a", "libmp3lame", "-b:a", kbps + "k", "-id3v2_version", "3",
                            "-metadata", "title=" + title, "-metadata", "artist=" + artist, "-metadata", "album=" + album,
                            "-metadata", "track=%d" % i, os.path.join(out, mp3)], check=True)
        a = analyse(style, load(path), bpms[min(i - 1, len(bpms) - 1)])
        a.update(title=title, file=mp3)
        if style == "chase":
            a["num"] = "%02d" % i
        elif style != "single":
            a["n"] = i
        tracks.append(a)
        print(i, title, a["seconds"], "s", flush=True)
    if style == "single":
        json.dump(tracks[0], open(os.path.join(out, "track.json"), "w"), separators=(",", ":"), ensure_ascii=False)
    elif style == "chase":
        json.dump({"tracks": tracks}, open(os.path.join(out, "tracks.json"), "w"), separators=(",", ":"), ensure_ascii=False)
    else:
        json.dump(tracks, open(os.path.join(out, "tracks.json"), "w"), separators=(",", ":"), ensure_ascii=False)
    print("ok", len(tracks), "tracks")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

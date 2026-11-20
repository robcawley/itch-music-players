# itch-music-players

Four single-file HTML music players for itch.io pack pages (or any web page). Each one is one `index.html` that reads a `tracks.json` and plays `audio/NN.mp3`. No build step, no dependencies, no tracking.

| Folder | Look | Data shape |
|---|---|---|
| `players/night-vision` | green night-vision scope with energy-driven visuals | scope |
| `players/night-chase` | pixel-art night chase that moves with the beat | chase |
| `players/rain-and-neon` | one-track sci-fi viewport | single |
| `players/deck` | plain track-list deck with waveform | deck |

The audio in this repo is synthetic demo sound (a drone and a 95 BPM pulse), so you can try everything straight away.

## Try it

```
python3 -m http.server 8000 -d players
```

Open `http://localhost:8000/night-chase/`. Players fetch their data, so they need a web server, not `file://`.

## Use your own music

Regenerate the demo sound with `python3 tools/make_demo.py`. Needs Python 3, `ffmpeg` and `numpy`.

```
python3 tools/build_player.py <style> <folder-of-wavs> <player-folder> --bpm 120 --bitrate 128 --artist "Your Name" --album "Your Album"
```

`<style>` is `deck`, `scope`, `chase` or `single`. It writes `audio/NN.mp3` and `tracks.json` (or `track.json` for `single`) into the player folder, next to its `index.html`. Options: `--no-mp3` (data only), `--only N` (one track).

## tracks.json formats

- **deck**: list of `{n, title, file, seconds, peaks[300]}`
- **scope**: as deck, with `peaks[120]`, `energy` (4 values per second) and `hits`
- **chase**: `{"tracks":[{num, title, file, seconds, bpm, phase, peaks, energy, kicks, hits, heat}]}`
- **single**: `{title, file, seconds, peaks[120]}`

## Make it yours

Titles, brand name and footer text are plain strings in each `index.html`. Search for `ROB CAWLEY`, the pack name and the `robcawley.com` link, and replace them with your own. Colours are CSS variables near the top of the file.

Itch tip: zip the player folder with `index.html` at the top level, upload it as an HTML5 project, and tick "This file will be played in the browser".

## Licence

MIT for the code. Your audio stays yours. The synthetic demo audio is free to use.

Made by Rob Cawley. Music at https://robcawley.com

# whistle-dictate

Local voice dictation for Hyprland using [Cactus Whistle](https://cactuscompute.com/blog/whistle) — 16.9 MB, on-device, 7 languages (en/de/fr/es/it/nl/pl).

Hex-like, in Python. Inspired by [anomalyco/hex](https://github.com/anomalyco/hex) (which can't load Whistle — Hex only runs GGUF Parakeet/Whisper-family models via `transcribe.cpp`; Whistle is a `.cact` for the Cactus engine).

## How it works

- hotkey starts recording → release stops → Whistle transcribes locally → text is pasted at the cursor
- first run downloads `whistle.cact` (~16.9 MB); after that nothing leaves your machine
- vocabulary biasing via `keywords` in config (Hex calls this Vocabulary)

## Install

```bash
cd ~/Projects/personal/whistle-dictate
uv sync
uv run whistle-dictate status
# optional but recommended on Hyprland (direct typing, like Hex's wtype path):
yay -S wtype
```

Without `wtype` it falls back to `wl-copy` + `hyprctl dispatch sendshortcut CTRL,V` (already installed on your box).

## UX: live glass overlay (no popups)

While recording, a top-center glass card (Hyprland float + no-focus rule,
same spot as the performance-mode OSD) shows a pulsing dot, `WHISTLE`,
a live timer, and a 24-band spectrum with glow bars + falling peak caps —
rendered with GTK/cairo on system python (no new deps). On stop it sweeps
to `… transcribing`, then fades; pasted text appearing at the cursor is the
confirmation. Errors/silence get a short card instead. Nothing ever steals
focus and clicks pass straight through the card.

## Hyprland binds

Hold-to-talk (mirrors Hex's `hex dictation start` / `stop` pattern):

```ini
bind = , End, exec, /home/arjun/Projects/personal/whistle-dictate/.venv/bin/whistle-dictate start
bindr = , End, exec, /home/arjun/Projects/personal/whistle-dictate/.venv/bin/whistle-dictate stop
```

Or single-key toggle (for portals/keys without release):

```ini
bind = SUPER, D, exec, /home/arjun/Projects/personal/whistle-dictate/.venv/bin/whistle-dictate toggle
```

See `hyprland.conf.example`.

> Hex tip we follow: prefer keys without Alt (Alt leaks to Electron apps and steals focus), and don't hold modifiers during paste.

## Usage

```bash
whistle-dictate start                 # begin recording
whistle-dictate stop                  # stop + transcribe + paste
whistle-dictate stop --print          # print instead of only pasting
whistle-dictate toggle                # start, then stop+paste
whistle-dictate cancel                # discard recording
whistle-dictate listen --duration 5   # blocking test (no binds needed)
whistle-dictate transcribe clip.wav   # file transcription (like `hex transcribe`)
whistle-dictate transcribe clip.wav --words --json
whistle-dictate status --json
whistle-dictate history --limit 20
whistle-dictate paste-last
whistle-dictate devices
```

## Config

`~/.config/whistle-dictate/config.toml`:

```toml
# language = "en"   # None = auto-detect
# keywords = ["Siobhan", "Krzysztof"]
# paste_method = "auto"  # auto | wtype | clipboard
```

History: `~/.local/share/whistle-dictate/history.jsonl`
State (pid/wav): `$XDG_RUNTIME_DIR/whistle-dictate/`

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -t .   # 40 tests, no mic/model/Hyprland needed
```

## Benchmarks (upstream)

11 ms TTFT, 1319 tok/s, 10 s audio on M4 Pro — vs Whisper base 73 ms / 266 tok/s at 145 MB.

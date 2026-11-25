<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://shieldcn.dev/header/gradient.svg?title=whistle-dictate&subtitle=Local+voice+dictation+for+Hyprland+with+Cactus+Whistle&align=center&mode=dark" />
    <img alt="whistle-dictate — local voice dictation for Hyprland with Cactus Whistle" src="https://shieldcn.dev/header/gradient.svg?title=whistle-dictate&subtitle=Local+voice+dictation+for+Hyprland+with+Cactus+Whistle&align=center&mode=light" />
  </picture>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img alt="python 3.10+" src="https://shieldcn.dev/badge/python-3.10+-3776AB.svg?variant=secondary" /></a>
  <a href="https://hyprland.org"><img alt="platform Hyprland Wayland" src="https://shieldcn.dev/badge/platform-hyprland_wayland-2EA043.svg?variant=secondary" /></a>
  <a href="https://cactuscompute.com/blog/whistle"><img alt="engine Whistle 16.9MB local" src="https://shieldcn.dev/badge/engine-whistle_16.9MB_local-7C3AED.svg?variant=secondary" /></a>
  <a href="#privacy"><img alt="audio 100 percent local" src="https://shieldcn.dev/badge/audio-100_percent_local-0891B2.svg?variant=secondary" /></a>
  <a href="LICENSE"><img alt="license MIT" src="https://shieldcn.dev/badge/license-MIT-94A3B8.svg?variant=secondary" /></a>
  <a href="#tests"><img alt="tests 52 passing" src="https://shieldcn.dev/badge/tests-52_passing-16A34A.svg?variant=secondary" /></a>
</p>

<p align="center"><em>Press a hotkey, speak, release — your words appear at the cursor. Nothing leaves your machine.</em></p>

**whistle-dictate** is Hex-like local voice dictation for Hyprland, in Python. It uses [Cactus Whistle](https://cactuscompute.com/blog/whistle) — a 16.9 MB on-device model (en/de/fr/es/it/nl/pl) — with a live glass recording card, global toggle hotkey, and paste-at-cursor. Inspired by [anomalyco/hex](https://github.com/anomalyco/hex) (Hex only runs GGUF Parakeet/Whisper-family models via `transcribe.cpp`; Whistle is a `.cact` for the Cactus engine, so this project exists).

## Contents

- [Where it works](#where-it-works)
- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Quickstart](#quickstart)
- [Hyprland binds](#hyprland-binds)
- [Usage](#usage)
- [Config](#config)
- [Backends (cross-platform)](#backends-cross-platform)
- [Troubleshooting](#troubleshooting)
- [Tests](#tests)
- [Benchmarks](#benchmarks)
- [Project layout](#project-layout)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)

## Where it works

| Environment | Status | Notes |
|---|---|---|
| Hyprland 0.57+ (Wayland, Linux) | ✅ Fully supported | Toggle binds, `wtype` typing, GTK glass card, Noctalia OSD |
| Other Wayland compositors (Sway, river…) | 🟡 Likely works, untested | `wtype` + `wl-copy` path is compositor-agnostic; card needs a float/no-focus rule |
| X11 / macOS / Windows | 🔲 Roadmap | Backend seams exist (`transcribers/`, `paste_backends/`, `overlays/`, `notifiers/`); contributions welcome |

Paste strategy on Linux, in order: `wtype` (direct typing, wlroots virtual keyboard) → `wl-copy` + `hyprctl sendshortcut CTRL,V` (terminals automatically get `CTRL_SHIFT,V`). No `sendshortcut` delivery on your compositor? Text still lands in the clipboard with a nudge to press `Ctrl+V`.

## How it works

```
hotkey (toggle) → mic records + Whistle preloads (parallel)
  → stop press → local transcribe → history append → paste at cursor
  → glass card fades (success is silent: your text *is* the confirmation)
```

- First run downloads `whistle.cact` (~16.9 MB); after that everything is offline.
- The record worker preloads the model *while* you speak, so stopping feels instant.
- Vocabulary biasing via `keywords` in config (Hex calls this Vocabulary).
- Silence/short clips are discarded with a short card instead of pasting garbage.

## Requirements

**System (Arch/Hyprland):**

```bash
yay -S wtype wl-clipboard        # typing + clipboard fallback
# Hyprland provides hyprctl; PipeWire provides the mic
# GTK overlay uses SYSTEM python — verify once:
 /usr/bin/python3 -c "import gi, cairo; print('overlay deps ok')"
# (Arch: python-gobject, gtk3, python-cairo — usually already present)
```

**Python:** 3.10+ via [uv](https://docs.astral.sh/uv/). The venv needs no GUI toolkit.

## Quickstart

```bash
git clone <your-fork-url> whistle-dictate
cd whistle-dictate
uv sync
uv run whistle-dictate status        # sanity: engine, platform, backends
uv run whistle-dictate mic-test      # speak — bars should move
uv run whistle-dictate warm          # pre-download whistle.cact (~16.9 MB)
uv run whistle-dictate listen --duration 5   # end-to-end without binds
```

Then wire the hotkey ([Hyprland binds](#hyprland-binds)), press it, speak, press again — text appears at the cursor.

> Fresh machine, step by step with expected outputs? See [`docs/SETUP.md`](docs/SETUP.md).

## Hyprland binds

Toggle (recommended — this box runs Hyprland 0.57 Lua, where `bindr` hold-to-talk isn't exposed, and Hex docs agree release timing is unreliable with modifiers):

```ini
# ~/.config/hypr/hyprland.conf (or see hyprland.conf.example)
bind = ALT, Space, exec, ~/.local/bin/whistle-dictate toggle
bind = CTRL, Space, exec, ~/.local/bin/whistle-dictate toggle
bind = , End, exec, ~/.local/bin/whistle-dictate toggle
```

Lua (0.57) equivalent:

```lua
hl.bind("ALT + Space", hl.dsp.exec_cmd(WD .. " toggle"))
```

Card rule + autostart:

```ini
# float, no-focus, top-center glass card
windowrule = float, title:^(wd-osd.*)$
windowrule = nofocus, title:^(wd-osd.*)$
```

```bash
whistle-dictate warm   # at login: first dictation is instant
```

> Prefer keys without Alt where possible — Alt leaks to Electron apps and steals focus. Never hold modifiers during paste.

## Usage

```bash
whistle-dictate start                 # begin recording
whistle-dictate stop                  # stop + transcribe + paste
whistle-dictate stop --print          # print instead of only pasting
whistle-dictate toggle                # one key: start, then stop+paste
whistle-dictate cancel                # discard recording
whistle-dictate listen --duration 5   # blocking test (no binds needed)
whistle-dictate transcribe clip.wav   # file transcription (like `hex transcribe`)
whistle-dictate transcribe clip.wav --words --json
whistle-dictate status --json
whistle-dictate history --limit 20
whistle-dictate paste-last
whistle-dictate devices               # list mic devices
whistle-dictate mic-test              # live level meter (speak to test)
```

While recording, a top-center glass card shows a pulsing dot, `WHISTLE`, a live timer, and a 24-band spectrum with glow bars + falling peak caps. On stop it sweeps to `… transcribing`, then fades. Errors/silence get a short card. Nothing steals focus; clicks pass through.

## Config

`~/.config/whistle-dictate/config.toml` (auto-seeded on first run — see also `config.example.toml`):

```toml
# language = "en"   # None = auto-detect (whistle langs: en/de/fr/es/it/nl/pl)
# keywords = ["Siobhan", "Krzysztof"]  # vocabulary biasing
# paste_method = "auto"  # auto | hyprland | wtype | clipboard | stdout
# transcriber = "whistle"      # only "whistle" today
# audio_source = "sounddevice" # only "sounddevice" today
# notifier = "auto"            # auto | noctalia | noop
# overlay = true               # true = auto card (gtk on Linux); false = headless
# mic = null  # pin input: sounddevice index or name substring (see `devices`)
# sensitivity = 1.0  # spectrum gate strictness, 0.3..3.0
```

- History: `~/.local/share/whistle-dictate/history.jsonl` (private, outside the repo)
- Ephemeral state: `$XDG_RUNTIME_DIR/whistle-dictate/` (`rec.pid`, `rec.stop`, `rec.result.json`, `rec.osd.json`)
- Paste debug log: `~/.local/share/whistle-dictate/paste-debug.log`

## Backends (cross-platform)

Same flow everywhere, different backends per OS. Hyprland/Linux is the only fully wired desktop today; other platforms reuse the flow by adding a backend — no pipeline changes needed.

| Surface | Interface | Today | Future |
|---|---|---|---|
| Transcription | `transcribers/base.Transcriber` | `whistle` (16.9 MB `.cact`) | whisper, macOS Speech, Windows SAPI |
| Audio | `audio_sources/base.AudioSource` | `sounddevice` | coreaudio, wasapi (or reuse sounddevice — it is cross-platform) |
| Paste | `paste_backends/base.PasteBackend` | `hyprland` (wtype → wl-copy+hyprctl) | `pbcopy`+osascript, `clip`+SendKeys |
| Overlay | `overlays/base.OverlayBackend` | `gtk` on Linux, `noop` elsewhere | aqua/windows native card |
| Notify | `notifiers/base.NotifierBackend` | `noctalia` on Hyprland, `noop` elsewhere | notification-center, toast |

Adding a platform = new file implementing the 2–4 method `Protocol` + one line in the package factory. `status --json` shows the resolved platform and backends. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `mic-test` flat / max peak silent | `wpctl status` — unmute, pick input; then pin it: `whistle-dictate devices` → set `mic = "<name substring>"` in config |
| Pasted nothing, "press Ctrl+V" card | Compositor blocked `sendshortcut` — text is in clipboard, press `Ctrl+V` (`Ctrl+Shift+V` in terminals); details in `paste-debug.log` |
| Card flashes on each paste | Expected: that's the compositor's keyboard indicator for `wtype`, not an error |
| No overlay card | `overlay = false` set, or system python lacks `gi`/`cairo` — run the verify command in [Requirements](#requirements); headless mode still pastes |
| First run slow / model error | Run `whistle-dictate warm`; it downloads `whistle.cact` once |
| `already recording` stuck | `whistle-dictate cancel`, then `status` should show `"recording": false` |
| `status` shows `not installed` engine | `uv sync` (needs `cactus-compute[mic]>=4.0`) |

## Tests

```bash
uv run python -m unittest discover -s tests -t .   # 52 tests, no mic/model/Hyprland needed
```

Unit tests cover the pipeline (stub engines), session lifecycle, config validation, paste adapters (mocked subprocess), and every backend factory (unknown names raise `ValueError`).

## Benchmarks

Upstream (Cactus): 11 ms TTFT, 1319 tok/s, 10 s audio on M4 Pro — vs Whisper base 73 ms / 266 tok/s at 145 MB. This box: recording ~165 MB transient, transcribe ~92 MB peak, 0 MB idle (no daemon), venv ~113 MB + 17 MB model.

## Project layout

```
whistle_dictate/
  cli.py            thin adapter: argparse in, user-facing messages out
  worker.py         detached _record program (mic + preload + transcribe + paste)
  session.py        lifecycle: pidfiles, spawn/stop/wait/reap/cancel
  state.py          overlay protocol seam (rec.osd.json schema + safe_unlink)
  pipeline.py       transcribe → history → paste decision chain
  engine.py         back-compat shim over transcribers/
  transcribers/     Transcriber protocol + whistle impl + factory
  audio_sources/    AudioSource protocol + sounddevice impl
  paste_backends/   PasteBackend protocol + hyprland impls
  overlays/         OverlayBackend (gtk vs noop)
  notifiers/        NotifierBackend (noctalia vs noop)
  platform.py       stdlib OS/desktop/capability probes
  config.py         XDG paths + validated config + accessors
  gtk_overlay.py    system-python glass card (reads rec.osd.json)
tests/              52 stdlib tests (no mic/model/Hyprland needed)
```

## Roadmap

- [ ] Publish to PyPI / `uv tool install`
- [ ] CI (ruff + mypy + pytest matrix)
- [ ] Sway/river smoke reports
- [ ] macOS paste + notifier backends
- [ ] Windows paste + notifier backends
- [ ] Optional whisper transcriber behind the same protocol

## Contributing

PRs welcome — especially new backends. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md) (uv setup, test loop, how to add a backend in ~20 lines).

## Privacy

<a id="privacy"></a>

All transcription is on-device. After the one-time `whistle.cact` download, no audio or text leaves your machine. History lives in your local `~/.local/share`; ephemeral state in `$XDG_RUNTIME_DIR`.

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgements

- [Cactus Whistle](https://cactuscompute.com/blog/whistle) for the tiny on-device model
- [anomalyco/hex](https://github.com/anomalyco/hex) for the interaction design this mirrors

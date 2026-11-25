# Fresh-machine setup (Linux + Hyprland)

This is the hand-holding companion to the README [Quickstart](../README.md#quickstart).
Expected outputs included so you know you're on track. ~10 minutes.

## 1. System deps

```bash
yay -S wtype wl-clipboard
/usr/bin/python3 -c "import gi, cairo; print('overlay deps ok')"
# expected: overlay deps ok
# (Arch packages if missing: python-gobject gtk3 python-cairo)
```

`wtype` is optional but recommended (direct typing). Without it, dictation falls
back to `wl-copy` + `hyprctl sendshortcut`.

## 2. Clone + Python env

```bash
git clone <your-fork-url> whistle-dictate
cd whistle-dictate
uv sync
```

Requires Python 3.10+; `uv` handles it. The venv needs no GUI toolkit — the
overlay runs on system python.

## 3. Sanity + mic

```bash
uv run whistle-dictate status
# expected: "os": "linux", "desktop": "hyprland", "recording": false

uv run whistle-dictate mic-test
# expected: bars move as you speak, "HEARS YOU"
# flat? -> wpctl status (unmute/pick input), then:
uv run whistle-dictate devices
# pin it in ~/.config/whistle-dictate/config.toml: mic = "<name substring>"
```

## 4. Model + end-to-end (no binds yet)

```bash
uv run whistle-dictate warm
# expected: downloads whistle.cact once (~16.9 MB), prints ready

uv run whistle-dictate listen --duration 5
# expected: speak for 5s -> transcription pasted/printed
```

## 5. Hotkey + card + autostart

Add to your Hyprland config (see `../hyprland.conf.example`):

```ini
bind = ALT, Space, exec, ~/.local/bin/whistle-dictate toggle
windowrule = float, title:^(wd-osd.*)$
windowrule = nofocus, title:^(wd-osd.*)$
```

Autostart (first dictation instant): `whistle-dictate warm` at login.

Expose the binary on PATH once (pick one):

```bash
# option A: symlink the venv entrypoint
ln -sf "$PWD/.venv/bin/whistle-dictate" ~/.local/bin/whistle-dictate
# option B: uv tool
uv tool install -e .
```

Test: focus any text field, press the hotkey, speak, press again — words appear
at the cursor and the glass card fades. Errors/silence get a short card instead.

## 6. Headless (optional)

No card, still pastes (saves ~65 MB transient):

```toml
# ~/.config/whistle-dictate/config.toml
overlay = false
```

## Still stuck?

Work through [Troubleshooting](../README.md#troubleshooting), then open an issue with:
`whistle-dictate status --json`, the failing command, and (for paste issues) the
last lines of `~/.local/share/whistle-dictate/paste-debug.log`.

# Changelog

All notable changes to whistle-dictate. Format follows Keep a Changelog; versioning is SemVer.

## [Unreleased]

- Cross-platform backend seams (`transcribers/`, `audio_sources/`, `paste_backends/`, `overlays/`, `notifiers/`, `platform.py`) with Hyprland defaults unchanged
- `status --json` reports resolved platform + backends

## [0.1.0] - 2026-11-25

- Initial release: local Whistle dictation on Hyprland
- Global toggle hotkey, paste at cursor (`wtype` → `wl-copy`+`hyprctl`), terminal-aware `Ctrl+Shift+V`
- GTK/cairo glass recording card (system python, click-through, no focus steal)
- Config (`config.toml`), history (`history.jsonl`), devices/mic-test, warm autostart
- 52 stdlib tests, no mic/model/Hyprland needed

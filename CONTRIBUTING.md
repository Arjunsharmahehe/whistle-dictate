# Contributing to whistle-dictate

Thanks for stopping by. This is a small, dependency-light Python project — the whole
thing is ~1.5k lines plus tests, stdlib-first, `uv`-managed.

## Dev setup

```bash
git clone <your-fork-url> whistle-dictate
cd whistle-dictate
uv sync
uv run whistle-dictate status
uv run python -m unittest discover -s tests -t .   # 52 tests, no mic/model/Hyprland needed
```

System tools for live testing on Hyprland: `wtype`, `wl-clipboard`, `hyprctl`
(Hyprland), PipeWire mic, and system python with `gi` + `cairo` for the overlay:

```bash
yay -S wtype wl-clipboard
/usr/bin/python3 -c "import gi, cairo; print('overlay deps ok')"
uv run whistle-dictate mic-test
uv run whistle-dictate listen --duration 5
```

## Test loop

- `uv run python -m unittest discover -s tests -t .` — full suite, must stay green.
- New behavior needs a test with a stub (fake engine/backend), never the real
  17 MB model or real subprocess calls — see `tests/test_backends.py` and
  `tests/util.py` (`isolated_runtime_dir` / `isolated_config_home`).
- Live smoke before pushing: `status` → `transcribe <clip.wav>` →
  `start` → `stop --no-paste --print` → overlay reaps cleanly.

## Code conventions

- Thin `cli.py` (argparse + messages only). Logic lives in `session.py`
  (lifecycle), `state.py` (overlay protocol), `pipeline.py` (decision chain).
- Every side effect arrives as an injected callable (`engine=`, `remember=`,
  `paste=`) so tests run in milliseconds.
- No comment twins: say it once, where it matters. Docstrings describe *why*,
  not *what* the code obviously does.
- `state.py` owns the `rec.osd.json` schema; `session.py` owns pidfile removal;
  the overlay only reads.
- Config: add defaults + validation in `config.py`, accessors alongside, and
  update the seeded example + `config.example.toml`.

## Adding a backend (new platform in ~20 lines)

1. Pick a surface: `transcribers/`, `audio_sources/`, `paste_backends/`,
   `overlays/`, or `notifiers/`. Read its `base.py` — it's a 2–4 method `Protocol`.
2. Add one module implementing it (import-light: no heavy deps at module top).
3. Register the name in that package's `__init__.py` factory. Unknown names must
   raise `ValueError` with the available list (tested).
4. Add a factory test in `tests/test_backends.py` + update the README backends table.
5. Verify `status --json` resolves your backend and the Hyprland defaults are untouched.

## PRs

- Keep PRs small and behavior-preserving unless the title says otherwise.
- Update README + CHANGELOG when user-facing behavior changes.
- No secrets, no absolute `/home/...` paths, no history/state files in commits.

"""OverlayBackend interface: recording card, on any desktop.

Hyprland today renders the GTK/cairo top-center card in a detached
process. Other platforms start headless (NoOp) until a native overlay
exists — the worker/pipeline never branches on platform, it just calls
this protocol via the factory.
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class OverlayBackend(Protocol):
    """Pluggable recording-card launcher."""

    name: str

    def available(self) -> bool:
        ...

    def spawn(self) -> None:
        ...

    def reap(self) -> None:
        ...

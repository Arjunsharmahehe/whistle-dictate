"""Futuristic recording overlay: glass card, live spectrum, timer.

Runs on SYSTEM python (/usr/bin/python3 has gi+cairo; the venv doesn't need
a GUI toolkit). Top-center via Hyprland rule (title wd-osd*): float +
no_focus + move. POPUP window = no taskbar, no focus; empty input shape =
click-through. Reads rec.osd.json written by the record worker:

  {"phase": "recording|transcribing|done|error|dismiss",
   "elapsed": seconds, "spec": [24 floats 0..1], "text": "...", "reason": "..."}
  (schema owned by whistle_dictate.state; this module only reads it).

30fps cairo redraw, lerped bars, peak caps, pulsing dot, group fade in/out.
"""
from __future__ import annotations
import math
import time

import cairo

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from . import state as _state

WINDOW_TITLE = "wd-osd"
W, H = 440, 156
NBARS = _state.NBANDS

ACCENT = (150 / 255, 235 / 255, 205 / 255)
RED = (1.0, 95 / 255, 110 / 255)


def rounded(cr, x, y, w, h, r):
    cr.move_to(x + r, y)
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, math.pi * 1.5)
    cr.close_path()


class Overlay:
    def __init__(self):
        self.levels = [0.0] * NBARS
        self.caps = [0.0] * NBARS
        self.fade = 0.0
        self.done_at = 0.0
        self.phase = _state.Phase.RECORDING
        self.text = ""
        self.elapsed = 0.0
        self.t0 = time.time()
        self.win = Gtk.Window(type=Gtk.WindowType.POPUP)
        self.win.set_title(WINDOW_TITLE)
        self.win.set_default_size(W, H)
        self.win.set_decorated(False)
        self.win.set_skip_taskbar_hint(True)
        self.win.set_skip_pager_hint(True)
        self.win.set_keep_above(True)
        self.win.set_accept_focus(False)
        self.win.set_focus_on_map(False)
        self.win.set_app_paintable(True)
        visual = self.win.get_screen().get_rgba_visual()
        if visual:
            self.win.set_visual(visual)
        self.area = Gtk.DrawingArea()
        self.area.connect("draw", self.draw)
        self.win.add(self.area)
        self.win.show_all()
        # click-through: empty input shape (needs realized window)
        try:
            self.win.input_shape_combine_region(cairo.Region())
        except Exception:
            pass
        GLib.timeout_add(50, self.poll)
        GLib.timeout_add(33, self.frame)

    def poll(self):
        st = _state.read()
        self.phase = st["phase"]
        self.elapsed = st["elapsed"]
        spec = st["spec"]
        for i in range(NBARS):
            self.levels[i] += (spec[i] - self.levels[i]) * 0.5
            self.caps[i] = max(self.caps[i] - 0.02, self.levels[i])
        now = time.time()
        if self.phase in (_state.Phase.RECORDING, _state.Phase.TRANSCRIBING):
            self.fade = min(1.0, self.fade + 0.15)
            self.done_at = 0.0
        elif self.phase == _state.Phase.DISMISS:
            # successful paste: no card, just fade out and quit
            if not self.done_at:
                self.done_at = now
            age = now - self.done_at
            if age > 0.15:
                self.fade -= 0.15
            if self.fade <= 0.0 and age > 0.15:
                _state.osd_pid_path().unlink(missing_ok=True)
                Gtk.main_quit()
                return
        else:
            if not self.done_at:
                self.done_at = now
                self.text = str(st.get("text") or st.get("reason") or "")
            age = now - self.done_at
            hold = 1.1 if self.phase == _state.Phase.DONE else 2.0
            if age > hold:
                self.fade -= 0.1
            if self.fade <= 0.0 and age > hold:
                _state.osd_pid_path().unlink(missing_ok=True)
                Gtk.main_quit()
                return False
        if self.phase in (_state.Phase.DONE, _state.Phase.ERROR) and not self.done_at:
            pass
        return True

    def frame(self):
        if self.phase in (_state.Phase.DONE, _state.Phase.ERROR) and self.fade <= 0.0 and self.done_at:
            return False
        self.area.queue_draw()
        return True

    def draw(self, _area, cr):
        now = time.time() - self.t0
        cr.push_group()
        # glass card
        cr.set_source_rgba(15 / 255, 17 / 255, 23 / 255, 0.92)
        rounded(cr, 1, 1, W - 2, H - 2, 22)
        cr.fill_preserve()
        cr.set_source_rgba(ACCENT[0], ACCENT[1], ACCENT[2], 0.14)
        cr.set_line_width(1.5)
        cr.stroke()

        # header dot
        if self.phase == _state.Phase.ERROR:
            cr.set_source_rgb(*RED)
        elif self.phase == _state.Phase.DONE:
            cr.set_source_rgb(*ACCENT)
        else:
            pulse = 0.55 + 0.45 * math.sin(now * 5.0)
            cr.set_source_rgb(RED[0] * pulse + 0.24, RED[1] * (1 - pulse) + 0.16,
                              RED[2] * (1 - pulse) + 0.16)
        cr.arc(34, 30, 6, 0, math.pi * 2)
        cr.fill()

        # labels
        cr.set_source_rgb(0.55, 0.59, 0.63)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(11)
        te = cr.text_extents("WHISTLE")
        cr.move_to(52, 34 - te[3] / 2 - te[1])
        cr.show_text("WHISTLE")
        m, s = divmod(int(self.elapsed), 60)
        cr.select_font_face("monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(12)
        cr.set_source_rgb(0.93, 0.94, 0.96)
        timer = f"{m}:{s:02d}"
        te = cr.text_extents(timer)
        cr.move_to(W - 28 - te[4], 34 - te[3] / 2 - te[1])
        cr.show_text(timer)

        if self.phase == _state.Phase.TRANSCRIBING:
            # simple spinner ring + label (new_sub_path: no stray line from text cursor)
            cx, cy, r = W / 2, 82, 24
            cr.set_source_rgba(1, 1, 1, 0.12)
            cr.set_line_width(5)
            cr.new_sub_path()
            cr.arc(cx, cy, r, 0, math.pi * 2)
            cr.stroke()
            a0 = now * 4.5
            cr.set_source_rgb(0.92, 0.95, 0.93)
            cr.new_sub_path()
            cr.arc(cx, cy, r, a0, a0 + math.pi * 1.2)
            cr.stroke()
            cr.set_source_rgb(0.55, 0.59, 0.63)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(11)
            msg = "transcribing"
            te = cr.text_extents(msg)
            cr.move_to((W - te[4]) / 2, 130)
            cr.show_text(msg)
            cr.pop_group_to_source()
            cr.paint_with_alpha(max(0.0, min(1.0, self.fade)))
            return False

        if self.phase in (_state.Phase.DONE, _state.Phase.ERROR):
            cr.set_source_rgb(0.55, 0.59, 0.63)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(12)
            msg = ("✓ " if self.phase == _state.Phase.DONE else "○ ") + self.text[:44]
            te = cr.text_extents(msg)
            cr.move_to(28, 110)
            cr.show_text(msg)
            cr.pop_group_to_source()
            cr.paint_with_alpha(max(0.0, min(1.0, self.fade)))
            return False

        # spectrum bars with glow + falling peak caps
        # (one shared vertical gradient: identical for every bar, so build once)
        area_x, area_y, area_w, area_h = 28, 56, W - 56, 64
        gap = 5
        bw = (area_w - gap * (NBARS - 1)) / NBARS
        g = cairo.LinearGradient(0, area_y + area_h, 0, area_y)
        g.add_color_stop_rgba(0, 150 / 255, 235 / 255, 205 / 255, 0.55)
        g.add_color_stop_rgba(0.7, 210 / 255, 250 / 255, 232 / 255, 0.90)
        g.add_color_stop_rgba(1, 190 / 255, 1, 225 / 255, 1.0)
        for i in range(NBARS):
            v = self.levels[i]
            bh = max(3.0, v * area_h)
            x = area_x + i * (bw + gap)
            y = area_y + area_h - bh
            cr.set_source_rgba(ACCENT[0], ACCENT[1], ACCENT[2], 0.07)
            rounded(cr, x - 2, y - 2, bw + 4, bh + 4, 4)
            cr.fill()
            cr.set_source(g)
            rounded(cr, x, y, bw, bh, 3)
            cr.fill()
            cy = area_y + area_h - max(3.0, self.caps[i] * area_h)
            cr.set_source_rgba(220 / 255, 255 / 255, 240 / 255, 0.70)
            rounded(cr, x, cy - 1.5, bw, 3, 1.5)
            cr.fill()
        cr.pop_group_to_source()
        cr.paint_with_alpha(max(0.0, min(1.0, self.fade)))
        return False


def run():
    Overlay()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

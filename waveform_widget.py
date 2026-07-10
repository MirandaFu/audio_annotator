"""
WaveformWidget — 音频波形显示 + 交互式片段标注画布
鼠标拖拽定义起止时间，点击跳转播放位置
支持一键打点模式：单击标记起点，再单击标记终点，选择发言人完成标注
"""
import numpy as np
import tkinter as tk


class WaveformWidget(tk.Canvas):
    PADDING_LEFT = 60
    PADDING_RIGHT = 20
    PADDING_TOP = 10
    PADDING_BOTTOM = 30

    def __init__(self, master, on_play_at=None, on_drag_start=None, on_drag_end=None,
                 on_mark_complete=None, **kw):
        super().__init__(master, bg="#1e1e2e", highlightthickness=0, **kw)
        self.on_play_at = on_play_at
        self.on_drag_start = on_drag_start
        self.on_drag_end = on_drag_end
        self.on_mark_complete = on_mark_complete

        self.audio_data = None
        self.sample_rate = 48000
        self.duration = 0.0
        self.segments = []
        self.speaker_colors = {}
        self.playhead = 0.0
        self._drag_x0 = None
        self._drag_t0 = None
        self._drag_rect = None
        self._drag_playhead = False
        self._current_speaker = None

        self._peaks = None
        self._peaks_full = None
        self._peak_count = 2000

        # View state
        self._zoom = 1.0
        self._view_start = 0.0
        self._view_end = 0.0
        self._height_scale = 1.0

        # Scrollbar reference (set by parent)
        self.scrollbar = None

        # Mark mode state
        self._mark_mode = False
        self._mark_start = None       # time of first click
        self._mark_line_start = None  # canvas line id for start marker
        self._mark_line_end = None    # canvas line id for end marker (temp)
        self._mark_lines = []         # persistent line ids for completed marks
        self._playhead_line = None
        self._playhead_tri = None

        self._redraw_after = None
        self.bind("<Configure>", self._schedule_redraw)
        self.bind("<Destroy>", self._on_destroy)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._motion)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Double-Button-1>", self._dbl_click)
        self.bind("<MouseWheel>", self._on_mousewheel)
        self.bind("<Button-4>", self._on_mousewheel)
        self.bind("<Button-5>", self._on_mousewheel)

    # ─── public API ─────────────────────────────────────────────────────────

    def bind_to(self, root):
        """Register global mouse-tracking so drag-release works even when
        the cursor leaves the canvas (e.g. fast drag to waveform edge)."""
        root.bind("<B1-Motion>", self._global_motion, add="+")
        root.bind("<ButtonRelease-1>", self._global_release, add="+")

    def set_audio(self, data, sample_rate):
        self.audio_data = data
        self.sample_rate = sample_rate
        self.duration = len(data) / sample_rate
        self._zoom = 1.0
        self._view_start = 0.0
        self._view_end = self.duration
        self._compute_peaks()
        self._update_scrollbar()
        self._redraw()

    def set_segments(self, segments, speaker_colors):
        self.segments = list(segments)
        self.speaker_colors = dict(speaker_colors)
        self._redraw()

    def set_playhead(self, t):
        self.playhead = t
        self._draw_playhead()

    def set_current_speaker(self, name):
        self._current_speaker = name
        self._redraw()

    def set_zoom(self, zoom_factor, center_time=None):
        """Set zoom level. zoom_factor > 1 means zoomed in."""
        if self.duration <= 0:
            return
        if center_time is None:
            center_time = self.playhead or self.duration / 2
        zoom = max(1.0, min(zoom_factor, 50.0))
        view_duration = self.duration / zoom
        half = view_duration / 2
        start = max(0, center_time - half)
        end = min(self.duration, start + view_duration)
        if end - start < view_duration:
            start = max(0, end - view_duration)
        self._zoom = zoom
        self._view_start = start
        self._view_end = end
        self._update_scrollbar()
        self._redraw()

    def zoom_in(self):
        self.set_zoom(self._zoom * 1.5)

    def zoom_out(self):
        self.set_zoom(self._zoom / 1.5)

    def zoom_reset(self):
        self._zoom = 1.0
        self._view_start = 0.0
        self._view_end = self.duration
        self._update_scrollbar()
        self._redraw()

    def set_height_scale(self, scale):
        self._height_scale = max(0.3, min(scale, 3.0))
        self._redraw()

    # ─── Scrollbar ──────────────────────────────────────────────────────────

    def _update_scrollbar(self):
        """Show/hide scrollbar based on zoom level and update its position."""
        if self.scrollbar is None:
            return
        if self._zoom > 1.0 and self.duration > 0:
            if not self.scrollbar.winfo_ismapped():
                self.scrollbar.pack(fill="x", side="bottom")
            view_duration = self._view_end - self._view_start
            total = self.duration
            if total > 0:
                slider_size = view_duration / total
                slider_pos = self._view_start / total
                self.scrollbar.set(slider_pos, slider_pos + slider_size)
        else:
            if self.scrollbar.winfo_ismapped():
                self.scrollbar.pack_forget()

    def _on_scrollbar(self, *args):
        """Handle scrollbar drag/click. tkinter Scrollbar passes 3 args
        for arrow clicks ("scroll", n, "units") and 2 for drag ("moveto", fraction)."""
        if not args or self.duration <= 0:
            return
        try:
            view_duration = self._view_end - self._view_start
            if view_duration <= 0:
                return
            if args[0] == "scroll":
                number = float(args[1]) if len(args) > 1 else 0
                self._view_start = max(0, self._view_start + view_duration * 0.1 * number)
            elif args[0] == "moveto":
                first = float(args[1]) if len(args) > 1 else 0
                self._view_start = first * self.duration
            else:
                first = float(args[0])
                self._view_start = first * self.duration
            self._view_end = self._view_start + view_duration
            if self._view_end > self.duration:
                self._view_end = self.duration
                self._view_start = self._view_end - view_duration
            self._zoom = self.duration / view_duration if view_duration > 0 else 1.0
        except (ValueError, TypeError, IndexError):
            return
        self._update_scrollbar()
        self._redraw()

    def set_mark_mode(self, enabled):
        self._mark_mode = enabled
        self._mark_start = None
        self._clear_mark_lines()
        self._redraw()

    def mark_point(self, t):
        """Programmatically place a mark at time t. Two calls set start+end and trigger callback."""
        if not self._mark_mode:
            return
        x0, y0, x1, y1 = self._plot_area()
        cx = self._time_to_x(t)
        if self._mark_start is None:
            self._mark_start = t
            self._mark_line_start = self.create_line(cx, y0, cx, y1, fill="#00FF00", width=2, tags="mark")
        else:
            start_t = min(self._mark_start, t)
            end_t = max(self._mark_start, t)
            if end_t - start_t < 0.05:
                return
            ex = self._time_to_x(end_t)
            self._mark_line_end = self.create_line(ex, y0, ex, y1, fill="#00FF00", width=2, tags="mark")
            self._mark_lines.append(self._mark_line_start)
            self._mark_lines.append(self._mark_line_end)
            self._mark_line_start = None
            self._mark_line_end = None
            if self.on_mark_complete:
                self.on_mark_complete(start_t, end_t)
            self._mark_start = None

    def _on_mark_click(self, ev):
        if not self._mark_mode:
            return
        x0, y0, x1, y1 = self._plot_area()
        t = self._x_to_time(ev.x)
        cx = self._time_to_x(t)
        if self._mark_start is None:
            self._mark_start = t
            self._mark_line_start = self.create_line(cx, y0, cx, y1, fill="#00FF00", width=2, tags="mark")
        else:
            start_t = min(self._mark_start, t)
            end_t = max(self._mark_start, t)
            if end_t - start_t < 0.05:
                return
            ex = self._time_to_x(end_t)
            self._mark_line_end = self.create_line(ex, y0, ex, y1, fill="#00FF00", width=2, tags="mark")
            self._mark_lines.append(self._mark_line_start)
            self._mark_lines.append(self._mark_line_end)
            self._mark_line_start = None
            self._mark_line_end = None
            if self.on_mark_complete:
                self.on_mark_complete(start_t, end_t)
            self._mark_start = None

    def _clear_mark_lines(self):
        for lid in ([self._mark_line_start, self._mark_line_end] + self._mark_lines):
            if lid:
                self.delete(lid)
        self._mark_line_start = None
        self._mark_line_end = None
        self._mark_lines = []

    def _draw_mark_lines(self):
        x0, y0, x1, y1 = self._plot_area()
        for lid in self._mark_lines:
            self.delete(lid)
        self._mark_lines.clear()
        for seg in self.segments:
            sx = self._time_to_x(seg["start"])
            ex = self._time_to_x(seg["end"])
            l1 = self.create_line(sx, y0, sx, y1, fill="#00FF00", width=1, tags="mark")
            l2 = self.create_line(ex, y0, ex, y1, fill="#00FF00", width=1, tags="mark")
            self._mark_lines.extend([l1, l2])

    # ─── waveform ───────────────────────────────────────────────────────────

    def _compute_peaks(self):
        if self.audio_data is None:
            self._peaks = None
            return
        data = self.audio_data
        n = len(data)
        max_peaks = 10000
        k = max(1, (n + max_peaks - 1) // max_peaks)
        pad = (k - n % k) % k
        padded = np.pad(np.abs(data), (0, pad), mode="constant")
        reshaped = padded.reshape(-1, k)
        self._peaks_full = np.max(reshaped, axis=1)
        self._peaks = self._peaks_full

    def _get_visible_peaks(self):
        """Get peaks for the currently visible time range."""
        if self._peaks_full is None or len(self._peaks_full) == 0:
            return None
        n_total = len(self._peaks_full)
        view_duration = self._view_end - self._view_start
        if view_duration <= 0:
            return self._peaks_full
        start_ratio = self._view_start / self.duration
        end_ratio = self._view_end / self.duration
        start_idx = int(start_ratio * n_total)
        end_idx = int(end_ratio * n_total)
        start_idx = max(0, min(start_idx, n_total - 1))
        end_idx = max(start_idx + 1, min(end_idx, n_total))
        peaks = self._peaks_full[start_idx:end_idx]
        canvas_width = (self.winfo_width() or 800) - self.PADDING_LEFT - self.PADDING_RIGHT
        max_display = max(canvas_width, 500)
        if len(peaks) > max_display:
            k = max(2, (len(peaks) + max_display - 1) // max_display)
            pad = (k - len(peaks) % k) % k
            padded = np.pad(peaks, (0, pad), mode="constant")
            reshaped = padded.reshape(-1, k)
            peaks = np.max(reshaped, axis=1)
        return peaks

    # ─── drawing ────────────────────────────────────────────────────────────

    def _schedule_redraw(self, _=None):
        if self._redraw_after:
            self.after_cancel(self._redraw_after)
        self._redraw_after = self.after(50, self._redraw)

    def _on_destroy(self, _):
        if self._redraw_after:
            self.after_cancel(self._redraw_after)
            self._redraw_after = None

    def _redraw(self):
        self.delete("all")
        x0, y0, x1, y1 = self._plot_area()
        mid = (y0 + y1) / 2
        h = y1 - y0

        self.create_line(x0, y1, x1, y1, fill="#444", width=1)
        self.create_line(x0, y0, x0, y1, fill="#444", width=1)
        self.create_line(x0, mid, x1, mid, fill="#333", dash=(4, 4))

        peaks = self._get_visible_peaks()
        if peaks is not None and len(peaks) > 0:
            n = len(peaks)
            step = (x1 - x0) / n
            for i, peak in enumerate(peaks):
                cx = x0 + i * step + step / 2
                half_h = peak * h * 0.45 * self._height_scale
                self.create_line(cx, mid - half_h, cx, mid + half_h,
                                 fill="#89b4fa", width=max(1, step * 0.7))

        for seg in self.segments:
            sx = self._time_to_x(seg["start"])
            ex = self._time_to_x(seg["end"])
            if ex < x0 or sx > x1:
                continue
            color = self.speaker_colors.get(seg["speaker"], "#888")
            if self._current_speaker and seg["speaker"] != self._current_speaker:
                color = self._desaturate(color)
            self.create_rectangle(sx, y0, ex, y1, fill=color, stipple="gray25",
                                  outline="", width=0)
            self.create_rectangle(sx, y0, ex, y0 + 4, fill=color, outline="")
            label = seg["speaker"]
            if ex - sx > 30:
                self.create_text(sx + 4, y0 + 10, text=label, fill="white",
                                 anchor="nw", font=("Helvetica", 8))

        if self.duration > 0:
            view_duration = self._view_end - self._view_start
            n_ticks = min(20, max(5, int(view_duration) + 1))
            interval = view_duration / n_ticks
            for i in range(n_ticks + 1):
                t = self._view_start + i * interval
                if t > self._view_end:
                    break
                x = self._time_to_x(t)
                self.create_line(x, y1, x, y1 + 5, fill="#666")
                h_str = self._fmt_short(t)
                self.create_text(x, y1 + 12, text=h_str, fill="#aaa",
                                 font=("Courier", 7), anchor="n")

        if self._zoom > 1.0:
            zoom_text = f"Zoom: {self._zoom:.1f}x"
            self.create_text(x1 - 5, y0 + 5, text=zoom_text, fill="#888",
                             font=("Helvetica", 8), anchor="ne")

        if self._mark_mode:
            self._draw_mark_lines()
            if self._mark_start is not None and self._mark_line_start is not None:
                x0, y0, x1, y1 = self._plot_area()
                cx = self._time_to_x(self._mark_start)
                self._mark_line_start = self.create_line(cx, y0, cx, y1, fill="#00FF00", width=2, tags="mark")
        self._draw_playhead()

    def _draw_playhead(self):
        """Create or recreate playhead items at current playhead position."""
        self.delete("playhead")
        if self.duration <= 0:
            self._playhead_line = None
            self._playhead_tri = None
            return
        x = self._time_to_x(self.playhead)
        x0, y0, x1, y1 = self._plot_area()
        self._playhead_line = self.create_line(x, y0, x, y1, fill="#FAB387", width=2, tags="playhead")
        self._playhead_tri = self.create_text(x, y0 - 2, text="▶", fill="#FAB387",
                                              font=("Helvetica", 9), anchor="s", tags="playhead")

    # ─── mouse interaction ──────────────────────────────────────────────────

    def _press(self, ev):
        if self._mark_mode:
            self._on_mark_click(ev)
            return
        x0, y0, x1, y1 = self._plot_area()
        t = self._x_to_time(ev.x)
        playhead_x = self._time_to_x(self.playhead)
        # If click is near the playhead, enter playhead-drag mode
        if abs(ev.x - playhead_x) < 15 and self.duration > 0:
            self._drag_x0 = ev.x
            self._drag_t0 = t
            self._drag_rect = None
            self._drag_playhead = True
            return
        self._drag_playhead = False
        self._drag_x0 = ev.x
        self._drag_t0 = t
        self._drag_rect = None
        if self.on_drag_start:
            self.on_drag_start(ev.x, t)

    def _motion(self, ev):
        if self._drag_x0 is None:
            return
        cx = self.canvasx(ev.x)
        if getattr(self, '_drag_playhead', False):
            t = self._x_to_time(cx)
            self.playhead = max(self._view_start, min(t, self._view_end))
            self._draw_playhead()
            return
        self._motion_at(cx)

    def _release(self, ev):
        if self._drag_x0 is None:
            return
        if getattr(self, '_drag_playhead', False):
            self._drag_x0 = None
            self._drag_playhead = False
            t = self._x_to_time(ev.x)
            self.playhead = max(self._view_start, min(t, self._view_end))
            self._draw_playhead()
            if self.on_play_at:
                self.on_play_at(self.playhead)
            return
        t_end = self._x_to_time(ev.x)
        self._drag_x0 = None
        if self._drag_rect:
            self.delete(self._drag_rect)
            self._drag_rect = None
        if self.on_drag_end:
            self.on_drag_end(ev.x, t_end)

    def _global_motion(self, ev):
        if self._drag_x0 is None:
            return
        cx = self.canvasx(ev.x)
        if getattr(self, '_drag_playhead', False):
            t = self._x_to_time(cx)
            self.playhead = max(self._view_start, min(t, self._view_end))
            self._draw_playhead()
            return
        self._motion_at(cx)

    def _global_release(self, ev):
        if self._drag_x0 is None:
            return
        if getattr(self, '_drag_playhead', False):
            cx = self.canvasx(ev.x)
            cx = max(self._plot_area()[0], min(cx, self._plot_area()[2]))
            t = self._x_to_time(cx)
            self._drag_x0 = None
            self._drag_playhead = False
            self.playhead = max(self._view_start, min(t, self._view_end))
            self._draw_playhead()
            if self.on_play_at:
                self.on_play_at(self.playhead)
            return
        cx = self.canvasx(ev.x)
        cx = max(self._plot_area()[0], min(cx, self._plot_area()[2]))
        t_end = self._x_to_time(cx)
        self._drag_x0 = None
        if self._drag_rect:
            self.delete(self._drag_rect)
            self._drag_rect = None
        if self.on_drag_end:
            self.on_drag_end(cx, t_end)

    def _motion_at(self, cx):
        if self._drag_x0 is None:
            return
        if self._drag_rect:
            self.delete(self._drag_rect)
        x0p, y0p, x1p, y1p = self._plot_area()
        self._drag_rect = self.create_rectangle(
            min(self._drag_x0, cx), y0p, max(self._drag_x0, cx), y1p,
            fill="#FAB387", stipple="gray25", outline="", width=0
        )

    def _dbl_click(self, ev):
        t = self._x_to_time(ev.x)
        if self.on_play_at:
            self.on_play_at(t)

    # ─── geometry ───────────────────────────────────────────────────────────

    def _plot_area(self):
        w = self.winfo_width() or 800
        h = self.winfo_height() or 200
        x0 = self.PADDING_LEFT
        x1 = w - self.PADDING_RIGHT
        y0 = self.PADDING_TOP
        y1 = h - self.PADDING_BOTTOM
        return x0, y0, x1, y1

    def _time_to_x(self, t):
        x0, y0, x1, y1 = self._plot_area()
        view_duration = self._view_end - self._view_start
        if view_duration <= 0:
            return x0
        return x0 + (t - self._view_start) / view_duration * (x1 - x0)

    def _x_to_time(self, x):
        x0, y0, x1, y1 = self._plot_area()
        view_duration = self._view_end - self._view_start
        if x1 <= x0:
            return self._view_start
        t = self._view_start + (x - x0) / (x1 - x0) * view_duration
        return max(self._view_start, min(t, self._view_end))

    def _on_mousewheel(self, ev):
        """Mouse wheel zoom. Ctrl+wheel = zoom, plain wheel = scroll."""
        if ev.state & 0x0004:  # Ctrl key held
            factor = 1.1 if ev.delta > 0 else 1.0 / 1.1
            center = self._x_to_time(ev.x)
            self.set_zoom(self._zoom * factor, center)
        else:
            view_duration = self._view_end - self._view_start
            scroll_amount = view_duration * 0.1
            if ev.delta > 0 or ev.num == 4:
                new_start = max(0, self._view_start - scroll_amount)
                new_end = new_start + view_duration
                if new_end > self.duration:
                    new_end = self.duration
                    new_start = new_end - view_duration
            else:
                new_end = min(self.duration, self._view_end + scroll_amount)
                new_start = new_end - view_duration
                if new_start < 0:
                    new_start = 0
                    new_end = new_start + view_duration
            self._view_start = new_start
            self._view_end = new_end
            self._zoom = self.duration / view_duration if view_duration > 0 else 1.0
            self._update_scrollbar()
            self._redraw()
    # ─── static ─────────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_short(t):
        t = max(0, t)
        m = int(t // 60)
        s = t % 60
        return f"{m}:{s:04.1f}"

    @staticmethod
    def _desaturate(hex_color, factor=0.4):
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        gray = int(0.299 * r + 0.587 * g + 0.114 * b)
        r = int(r * (1 - factor) + gray * factor)
        g = int(g * (1 - factor) + gray * factor)
        b = int(b * (1 - factor) + gray * factor)
        return f"#{r:02x}{g:02x}{b:02x}"
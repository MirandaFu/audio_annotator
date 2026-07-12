"""
SpeakerPanel — 发言人列表面板
- 默认显示 说话人1, 说话人2
- 点击选择当前发言人
- 双击重命名
- 新增/删除发言人
"""
import tkinter as tk
from tkinter import ttk, messagebox


class SpeakerPanel(ttk.Frame):
    def __init__(self, master, speakers, colors, current,
                 on_select=None, on_rename=None, on_add=None, on_delete=None):
        super().__init__(master)
        self.speakers = list(speakers)
        self.colors = dict(colors)
        self.current = current
        self.on_select = on_select
        self.on_rename = on_rename
        self.on_add = on_add
        self.on_delete = on_delete

        self._selected_idx = 0
        if self.current in self.speakers:
            self._selected_idx = self.speakers.index(self.current)
        elif self.speakers:
            self._selected_idx = 0

        self._build()

    def _build(self):
        # header
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 4))
        ttk.Label(header, text="🗣 发言人列表", font=("Helvetica", 10, "bold")).pack(side="left")
        ttk.Label(header, text="(点击选择 | 双击重命名)",
                  foreground="#888", font=("Helvetica", 8)).pack(side="left", padx=6)

        # listbox with color indicators
        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self.listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            font=("Helvetica", 10),
            selectmode="single",
            height=10,
            activestyle="none",
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)

        for i, sp in enumerate(self.speakers):
            self.listbox.insert("end", sp)
        self.listbox.selection_set(self._selected_idx)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        self.listbox.bind("<Double-1>", self._on_dbl)
        self._apply_colors()

        # buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", pady=(4, 0))
        ttk.Button(btn_frame, text="＋ 新增", command=self._add, width=8).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="✕ 删除", command=self._delete, width=8).pack(side="left", padx=2)

    def _apply_colors(self):
        for i, sp in enumerate(self.speakers):
            color = self.colors.get(sp, "#888")
            if sp != self.current:
                color = self._desaturate(color)
            fg = "#000" if self._is_light(color) else "#fff"
            self.listbox.itemconfig(i, bg=color, fg=fg,
                                     selectbackground=color, selectforeground=fg)

    @staticmethod
    def _is_light(hex_color):
        r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
        return (r * 299 + g * 587 + b * 114) / 1000 > 128

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

    def _on_select(self, _):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self._selected_idx = idx
        if idx < len(self.speakers):
            name = self.speakers[idx]
            self.current = name
            self._apply_colors()
            if self.on_select:
                self.on_select(name)

    def _on_dbl(self, _):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self._rename(idx)

    def rename_speaker(self, old_name, new_name):
        """Programmatically rename a speaker (no popup). Returns True if renamed."""
        if not new_name or new_name == old_name:
            return False
        if new_name in self.speakers:
            return False
        if old_name not in self.speakers:
            return False
        idx = self.speakers.index(old_name)
        self.speakers[idx] = new_name
        color = self.colors.pop(old_name, "#888")
        self.colors[new_name] = color
        if self.current == old_name:
            self.current = new_name
        self.listbox.delete(idx)
        self.listbox.insert(idx, new_name)
        self.listbox.selection_set(idx)
        self._apply_colors()
        return True

    def set_speakers(self, speakers, colors, current=None):
        self.speakers = list(speakers)
        self.colors = dict(colors)
        if current in self.speakers:
            self.current = current
        elif self.speakers:
            self.current = self.speakers[0]
        else:
            self.current = None
        self.listbox.delete(0, "end")
        for sp in self.speakers:
            self.listbox.insert("end", sp)
        if self.current in self.speakers:
            idx = self.speakers.index(self.current)
            self._selected_idx = idx
            self.listbox.selection_set(idx)
        self._apply_colors()

    def _rename(self, idx):
        old_name = self.speakers[idx]
        popup = tk.Toplevel(self)
        popup.title("重命名发言人")
        popup.geometry("280x100")
        popup.transient(self.winfo_toplevel())
        popup.grab_set()

        ttk.Label(popup, text=f"'{old_name}' 的新名称:").pack(pady=8)
        var = tk.StringVar(value=old_name)
        entry = ttk.Entry(popup, textvariable=var, width=25)
        entry.pack(padx=12)
        entry.focus_set()
        entry.icursor("end")

        def confirm():
            new_name = var.get().strip()
            if self.rename_speaker(old_name, new_name) and self.on_rename:
                self.on_rename(old_name, new_name)
            popup.destroy()

        btn = ttk.Frame(popup)
        btn.pack(pady=6)
        ttk.Button(btn, text="确定", command=confirm).pack(side="left", padx=4)
        ttk.Button(btn, text="取消", command=popup.destroy).pack(side="left", padx=4)
        entry.bind("<Return>", lambda e: confirm())

    def _next_speaker_name(self):
        base = "说话人"
        max_idx = 0
        for sp in self.speakers:
            if sp.startswith(base) and sp[len(base):].isdigit():
                max_idx = max(max_idx, int(sp[len(base):]))
        return f"{base}{max_idx + 1}"

    def _add(self):
        name = self._next_speaker_name()
        color = SPEAKER_COLORS[len(self.speakers) % len(SPEAKER_COLORS)]
        self.speakers.append(name)
        self.colors[name] = color
        self.listbox.insert("end", name)
        self._apply_colors()
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set("end")
        self.listbox.see("end")
        self.current = name
        if self.on_add:
            self.on_add(name)

    def _delete(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if len(self.speakers) <= 1:
            messagebox.showinfo("提示", "至少保留一个发言人")
            return
        name = self.speakers[idx]
        self.speakers.pop(idx)
        self.colors.pop(name, None)
        self.listbox.delete(idx)
        if self.current == name:
            self.current = self.speakers[min(idx, len(self.speakers) - 1)]
            new_idx = self.speakers.index(self.current)
            self.listbox.selection_set(new_idx)
        self._apply_colors()
        if self.on_delete:
            self.on_delete(name)

    def set_current(self, name):
        if name in self.speakers:
            self.current = name
            idx = self.speakers.index(name)
            self._selected_idx = idx
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(idx)
            self._apply_colors()

    def get_speakers(self):
        return list(self.speakers)

    def get_colors(self):
        return dict(self.colors)


SPEAKER_COLORS = [
    "#E74C3C", "#3498DB", "#2ECC71", "#F39C12",
    "#9B59B6", "#1ABC9C", "#E67E22", "#34495E",
    "#E84393", "#00B894", "#6C5CE7", "#FDCB6E",
]

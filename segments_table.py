"""
SegmentsTable — 标注片段列表
支持：双击编辑说话人名称、Delete 删除、点击跳转
"""
import tkinter as tk
from tkinter import ttk


SPEAKER_PRESETS = [
    "说话人1", "说话人2", "说话人3", "说话人4",
    "主持人", "客户", "工程师", "产品经理",
]


class SegmentsTable(ttk.Frame):
    def __init__(self, master, on_select_time=None, on_delete=None, on_edit=None):
        super().__init__(master)
        self.on_select_time = on_select_time
        self.on_delete = on_delete
        self.on_edit = on_edit
        self.segments = []
        self.speaker_colors = {}

        # Treeview
        columns = ("idx", "speaker", "start", "end", "duration")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=12)
        self.tree.heading("idx", text="#")
        self.tree.heading("speaker", text="说话人")
        self.tree.heading("start", text="开始时间")
        self.tree.heading("end", text="结束时间")
        self.tree.heading("duration", text="时长")
        self.tree.column("idx", width=40, anchor="center")
        self.tree.column("speaker", width=120)
        self.tree.column("start", width=100, anchor="center")
        self.tree.column("end", width=100, anchor="center")
        self.tree.column("duration", width=80, anchor="center")

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        # bindings
        self.tree.bind("<Double-1>", self._on_dbl_click)
        self.tree.bind("<Delete>", self._on_delete)
        self.tree.bind("<Return>", self._on_delete)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def set_segments(self, segments, speaker_colors):
        self.segments = list(segments)
        self.speaker_colors = dict(speaker_colors)
        # refresh
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, seg in enumerate(self.segments):
            dur = seg["end"] - seg["start"]
            values = (
                i + 1,
                seg["speaker"],
                self._fmt(seg["start"]),
                self._fmt(seg["end"]),
                f"{dur:.1f}s",
            )
            self.tree.insert("", "end", values=values)

    def _on_select(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        item = sel[0]
        idx = self.tree.index(item)
        if 0 <= idx < len(self.segments):
            seg = self.segments[idx]
            if self.on_select_time:
                self.on_select_time(seg["start"])

    def _on_dbl_click(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        item = sel[0]
        idx = self.tree.index(item)
        self._edit_speaker(item, idx)

    def _on_delete(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        item = sel[0]
        idx = self.tree.index(item)
        if self.on_delete:
            self.on_delete(idx)

    def _edit_speaker(self, item, idx):
        """Inline edit the speaker name via a popup menu."""
        current = self.segments[idx]["speaker"]
        popup = tk.Toplevel(self)
        popup.title("编辑说话人")
        popup.geometry("260x180")
        popup.transient(self.winfo_toplevel())
        popup.grab_set()

        ttk.Label(popup, text=f"片段 #{idx+1}  ("
                 f"{self._fmt(self.segments[idx]['start'])} — "
                 f"{self._fmt(self.segments[idx]['end'])})").pack(pady=6)

        ttk.Label(popup, text="选择/输入说话人:").pack(anchor="w", padx=12)
        var = tk.StringVar(value=current)
        entry = ttk.Combobox(popup, textvariable=var, values=SPEAKER_PRESETS,
                             state="normal", width=20)
        entry.pack(padx=12, pady=4)
        entry.focus_set()
        entry.icursor("end")

        def confirm():
            new_name = var.get().strip()
            if new_name:
                self.segments[idx]["speaker"] = new_name
                self.set_segments(self.segments, self.speaker_colors)
                if self.on_edit:
                    self.on_edit()
            popup.destroy()

        btn_frame = ttk.Frame(popup)
        btn_frame.pack(pady=8)
        ttk.Button(btn_frame, text="确定", command=confirm).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="取消", command=popup.destroy).pack(side="left", padx=4)
        entry.bind("<Return>", lambda e: confirm())

    @staticmethod
    def _fmt(t):
        t = max(0, t)
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = t % 60
        return f"{h:02d}:{m:02d}:{s:05.2f}"

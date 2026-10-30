"""Flowchart editor for the NPC dialogue. Run: python3 editor.py [flow.json]"""
import math
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

import flow as flowlib
from app import FLOW_PATH, Runner

W, H = 170, 64
COLORS = {"start": "#c8f0c8", "say": "#d6e6fa", "global": "#fbe0b8"}
SEL = "#d03030"


class Editor:
    def __init__(self, root, path):
        self.root = root
        self.path = path
        self.flow = flowlib.load(path) if os.path.exists(path) else flowlib.new_flow()
        self.sel = None          # ("node", id) or ("edge", index)
        self.connect_from = None
        self.connecting = False
        self.dirty = False
        self.drag = None
        self.panning = False
        self.multi = set()       # {("node", id) | ("edge", index)} from shift-select
        self.marquee = None
        self.marquee_id = None
        self.zoom = 1.0
        self.test_win = None

        self._build_ui()
        self.redraw()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Command-s>", lambda e: self.save())
        root.bind("<Control-s>", lambda e: self.save())

    # ---------- UI ----------
    def _build_ui(self):
        self._update_title()
        bar = tk.Frame(self.root)
        bar.pack(side="top", fill="x", padx=6, pady=4)
        for text, cmd in [
            ("Add line", self.add_line), ("Add 'Any state'", self.add_global),
        ]:
            tk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        self.connect_btn = tk.Button(bar, text="Connect", command=self.toggle_connect)
        self.connect_btn.pack(side="left", padx=2)
        tk.Button(bar, text="Delete", command=self.delete_selected).pack(side="left", padx=2)
        tk.Frame(bar, width=16).pack(side="left")
        for text, cmd in [("Open…", self.open_file), ("Save", self.save),
                          ("Save as…", self.save_as), ("Test ▶", self.test)]:
            tk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)

        self.status = tk.Label(self.root, anchor="w", fg="#555", text=self._hint())
        self.status.pack(side="bottom", fill="x", padx=6)

        side = tk.Frame(self.root, width=240)
        side.pack(side="right", fill="y", padx=6, pady=4)
        side.pack_propagate(False)
        self.side_title = tk.Label(side, text="Nothing selected", anchor="w",
                                   font=("Helvetica", 12, "bold"))
        self.side_title.pack(fill="x")
        self.side_help = tk.Label(side, anchor="w", justify="left", wraplength=230, fg="#555")
        self.side_help.pack(fill="x", pady=(0, 6))
        self.text = tk.Text(side, height=8, width=28, wrap="word")
        self.text.bind("<KeyRelease>", self._text_edited)
        self.label_var = tk.StringVar()
        self.label_entry = tk.Entry(side, textvariable=self.label_var)
        self.label_entry.bind("<KeyRelease>", self._label_edited)
        self.delay_row = tk.Frame(side)
        tk.Label(self.delay_row, text="Wait (sec):").pack(side="left")
        self.delay_var = tk.StringVar()
        self.delay_entry = tk.Entry(self.delay_row, textvariable=self.delay_var, width=6)
        self.delay_entry.pack(side="left", padx=4)
        self.delay_entry.bind("<KeyRelease>", self._delay_edited)
        self.weight_row = tk.Frame(side)
        tk.Label(self.weight_row, text="Chance weight:").pack(side="left")
        self.weight_var = tk.StringVar()
        self.weight_entry = tk.Entry(self.weight_row, textvariable=self.weight_var, width=6)
        self.weight_entry.pack(side="left", padx=4)
        self.weight_entry.bind("<KeyRelease>", self._weight_edited)
        self.weight_pct = tk.Label(side, anchor="w", justify="left", wraplength=230, fg="#555")
        self.delay_note = tk.Label(side, anchor="w", justify="left", wraplength=230, fg="#555",
                                   text="Optional. Transition happens this long after the line "
                                        "finishes (automatic) or after the button is pressed. "
                                        "Empty = default pause.")

        frame = tk.Frame(self.root)
        frame.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(frame, bg="white")
        hs = tk.Scrollbar(frame, orient="horizontal", command=self.canvas.xview)
        vs = tk.Scrollbar(frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hs.set, yscrollcommand=vs.set)
        hs.pack(side="bottom", fill="x")
        vs.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<MouseWheel>", self.on_wheel)
        # Tk 9 on macOS sends trackpad two-finger scrolls as <TouchpadScroll>;
        # older Tk versions don't know that event type.
        try:
            self.canvas.bind("<TouchpadScroll>", self.on_touchpad)
        except tk.TclError:
            pass
        # Linux/X11 reports the wheel as buttons 4 and 5
        self.canvas.bind("<Button-4>", lambda e: self.on_wheel(e, 3))
        self.canvas.bind("<Button-5>", lambda e: self.on_wheel(e, -3))
        self.canvas.bind("<BackSpace>", lambda e: self.delete_selected())
        self.canvas.bind("<Delete>", lambda e: self.delete_selected())
        self.root.update_idletasks()
        self._show_side()

    def _hint(self):
        if self.connecting:
            return ("Connect: click the source box, then the target box."
                    if self.connect_from is None else "Now click the target box.")
        return ("Click to select, drag boxes to move, drag empty space to pan, "
                "scroll to zoom, shift-drag to multi-select. Use Connect to draw arrows.")

    def _update_title(self):
        name = os.path.basename(self.path)
        self.root.title(f"NPC Flow Editor – {name}{' *' if self.dirty else ''}")

    def _mark_dirty(self):
        self.dirty = True
        self._update_title()

    # ---------- side panel ----------
    def _show_side(self):
        self.text.pack_forget()
        self.label_entry.pack_forget()
        self.delay_row.pack_forget()
        self.weight_row.pack_forget()
        self.weight_pct.pack_forget()
        self.delay_note.pack_forget()
        if self.multi:
            self.side_title.config(text=f"{len(self.multi)} selected")
            self.side_help.config(text="Press Delete to remove them all, or drag one to move "
                                       "the group. Shift-click toggles items.")
        elif self.sel is None:
            self.side_title.config(text="Nothing selected")
            self.side_help.config(text="Select a box or arrow to edit it.")
        elif self.sel[0] == "node":
            node = self.flow["nodes"][self.sel[1]]
            kind = node["kind"]
            self.side_title.config(text={"start": "Start line", "say": "Line",
                                         "global": "Any state"}[kind])
            if kind == "global":
                self.side_help.config(text="Arrows labeled with a button name out of this box "
                                           "work from every line that has no arrow of its own "
                                           "for that button.")
            else:
                self.side_help.config(text="What the NPC says. Unlabeled arrows out of here are "
                                           "followed automatically; labeled ones on button press.")
                self.text.pack(fill="x")
                self.text.delete("1.0", "end")
                self.text.insert("1.0", node["text"])
        else:
            edge = self.flow["edges"][self.sel[1]]
            self.side_title.config(text="Arrow")
            self.side_help.config(text="Button name. Leave empty for an automatic transition "
                                       "after the line finishes.")
            self.label_var.set(edge["label"])
            self.label_entry.pack(fill="x")
            self.delay_var.set("" if edge.get("delay") is None else f"{edge['delay']:g}")
            self.weight_var.set("" if edge.get("weight") is None else f"{edge['weight']:g}")
            self.weight_row.pack(fill="x", pady=(8, 0))
            self._refresh_chance()
            self.weight_pct.pack(fill="x")
            self.delay_row.pack(fill="x", pady=(8, 2))
            self.delay_note.pack(fill="x")

    def _text_edited(self, _):
        if self.sel and self.sel[0] == "node":
            self.flow["nodes"][self.sel[1]]["text"] = self.text.get("1.0", "end-1c")
            self._mark_dirty()
            self.redraw()

    def _refresh_chance(self):
        edge = self.flow["edges"][self.sel[1]]
        p = flowlib.chance(self.flow, edge)
        self.weight_pct.config(
            text="Only branch of this kind: always taken. Add more arrows from the same box "
                 "with the same button name (or all automatic) to make a random branch."
            if p is None else f"= {p:.0%} of the time among its sibling arrows "
                              "(same box, same button name). Weights are relative; empty = 1.")

    def _weight_edited(self, _):
        if not (self.sel and self.sel[0] == "edge"):
            return
        edge = self.flow["edges"][self.sel[1]]
        raw = self.weight_var.get().strip()
        try:
            value = float(raw)
        except ValueError:
            value = None
        if value is not None and value >= 0:
            edge["weight"] = value
        elif not raw:
            edge.pop("weight", None)
        else:
            return
        self._mark_dirty()
        self._refresh_chance()
        self.redraw()

    def _delay_edited(self, _):
        if not (self.sel and self.sel[0] == "edge"):
            return
        edge = self.flow["edges"][self.sel[1]]
        raw = self.delay_var.get().strip()
        try:
            value = float(raw)
        except ValueError:
            value = None
        if value is not None and value >= 0:
            edge["delay"] = value
        elif not raw:
            edge.pop("delay", None)
        else:
            return                      # half-typed / invalid: keep the last good value
        self._mark_dirty()
        self.redraw()

    def _label_edited(self, _):
        if self.sel and self.sel[0] == "edge":
            self.flow["edges"][self.sel[1]]["label"] = self.label_var.get().strip()
            self._mark_dirty()
            self.redraw()

    # ---------- drawing ----------
    def redraw(self):
        c = self.canvas
        z = self.zoom
        c.delete("all")
        c.configure(scrollregion=(0, 0, 3000 * z, 2000 * z))
        nodes = self.flow["nodes"]
        for i, e in enumerate(self.flow["edges"]):
            self._draw_edge(i, e)
        for nid, n in nodes.items():
            x, y = n["x"] * z, n["y"] * z
            selected = self.sel == ("node", nid) or ("node", nid) in self.multi
            src = self.connect_from == nid
            c.create_rectangle(x, y, x + W * z, y + H * z, fill=COLORS[n["kind"]],
                               outline=SEL if selected or src else "#555",
                               width=3 if selected or src else 1, tags=("node", nid))
            text = "ANY STATE" if n["kind"] == "global" else n["text"]
            if n["kind"] == "start":
                text = "▶ " + text
            c.create_text(x + W * z / 2, y + H * z / 2, text=text, width=(W - 12) * z,
                          fill="#111", tags=("node", nid),
                          font=("Helvetica", self._fs(10), "bold" if n["kind"] == "global" else "normal"))

    def _fs(self, size):
        return max(1, round(size * self.zoom))

    def _draw_edge(self, i, e):
        z = self.zoom
        nodes = self.flow["nodes"]
        a, b = nodes[e["from"]], nodes[e["to"]]
        ax, ay = (a["x"] + W / 2) * z, (a["y"] + H / 2) * z
        bx, by = (b["x"] + W / 2) * z, (b["y"] + H / 2) * z
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy) or 1
        # offset sideways so A->B and B->A don't overlap
        ox, oy = -dy / length * 7 * z, dx / length * 7 * z
        p1 = self._clip(ax + ox, ay + oy, dx, dy)
        p2 = self._clip(bx + ox, by + oy, -dx, -dy)
        selected = self.sel == ("edge", i) or ("edge", i) in self.multi
        color = SEL if selected else ("#2a6" if e["label"] else "#777")
        self.canvas.create_line(*p1, *p2, arrow="last", fill=color, width=3 if selected else 2,
                                tags=("edge", f"e{i}"))
        wait = e.get("delay")
        p = flowlib.chance(self.flow, e)
        caption = " ".join(x for x in (e["label"], "" if p is None else f"{p:.0%}",
                                       "" if wait is None else f"⏱{wait:g}s") if x)
        if caption:
            mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
            t = self.canvas.create_text(mx, my, text=caption, fill=color,
                                        font=("Helvetica", self._fs(10), "bold"),
                                        tags=("edge", f"e{i}"))
            self.canvas.create_rectangle(self.canvas.bbox(t), fill="white", outline="",
                                         tags=("edge", f"e{i}"))
            self.canvas.tag_raise(t)

    def _clip(self, cx, cy, dx, dy):
        """Point where a ray from a box center (cx, cy) in direction (dx, dy) leaves the box."""
        if dx == 0 and dy == 0:
            return cx, cy
        hw, hh = W / 2 * self.zoom, H / 2 * self.zoom
        t = min(hw / abs(dx) if dx else math.inf, hh / abs(dy) if dy else math.inf)
        return cx + dx * t, cy + dy * t

    # ---------- mouse ----------
    def _hit(self, event):
        c = self.canvas
        cx, cy = c.canvasx(event.x), c.canvasy(event.y)
        x, y = cx / self.zoom, cy / self.zoom       # model coordinates
        items = c.find_overlapping(cx - 3, cy - 3, cx + 3, cy + 3)
        for item in reversed(items):         # topmost first
            tags = c.gettags(item)
            if "node" in tags:
                return ("node", tags[1], x, y)
        for item in reversed(items):
            tags = c.gettags(item)
            if "edge" in tags:
                return ("edge", int(tags[1][1:]), x, y)
        return (None, None, x, y)

    def on_press(self, event):
        self.canvas.focus_set()
        kind, ident, x, y = self._hit(event)
        if self.connecting:
            if kind == "node":
                self._connect_click(ident)
            return
        shift = bool(event.state & 0x1)
        if shift and kind is None:               # start a selection rectangle
            self.marquee = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
            self.marquee_id = self.canvas.create_rectangle(
                *self.marquee, *self.marquee, outline=SEL, dash=(4, 3))
            return
        if shift and kind is not None:           # toggle one item in the multi-selection
            if self.sel and not self.multi:
                self.multi.add(self.sel)
            self.sel = None
            self.multi ^= {(kind, ident)}
            self.redraw()
            self._show_side()
            return
        if kind is None:
            self.multi.clear()
            self.sel = None
            self.panning = True
            self.canvas.scan_mark(event.x, event.y)
        else:
            if (kind, ident) in self.multi:      # keep the group so it can be dragged
                self.sel = None
            else:
                self.multi.clear()
                self.sel = (kind, ident)
        if kind == "node":
            n = self.flow["nodes"][ident]
            self.drag = (ident, x - n["x"], y - n["y"])
        self.redraw()
        self._show_side()

    def on_drag(self, event):
        if self.marquee:
            x0, y0 = self.marquee
            self.canvas.coords(self.marquee_id, x0, y0,
                               self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
            return
        if self.panning:
            self.canvas.scan_dragto(event.x, event.y, gain=1)
            return
        if not self.drag:
            return
        nid, ox, oy = self.drag
        n = self.flow["nodes"][nid]
        nx = max(0, int(self.canvas.canvasx(event.x) / self.zoom - ox))
        ny = max(0, int(self.canvas.canvasy(event.y) / self.zoom - oy))
        dx, dy = nx - n["x"], ny - n["y"]
        moving = {i for k, i in self.multi if k == "node"} | {nid}
        for i in moving:                         # whole group moves together
            m = self.flow["nodes"][i]
            m["x"] = max(0, m["x"] + dx)
            m["y"] = max(0, m["y"] + dy)
        self._mark_dirty()
        self.redraw()

    def on_release(self, _):
        if self.marquee:
            self._finish_marquee()
        self.drag = None
        self.panning = False

    def _finish_marquee(self):
        x0, y0, x1, y1 = self.canvas.coords(self.marquee_id)
        self.canvas.delete(self.marquee_id)
        self.marquee = None
        lo_x, hi_x, lo_y, hi_y = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
        z = self.zoom
        found = set()
        for nid, n in self.flow["nodes"].items():
            if (n["x"] * z < hi_x and (n["x"] + W) * z > lo_x
                    and n["y"] * z < hi_y and (n["y"] + H) * z > lo_y):
                found.add(("node", nid))
        for i, e in enumerate(self.flow["edges"]):
            a, b = self.flow["nodes"][e["from"]], self.flow["nodes"][e["to"]]
            mx = (a["x"] + b["x"] + W) / 2 * z
            my = (a["y"] + b["y"] + H) / 2 * z
            if lo_x <= mx <= hi_x and lo_y <= my <= hi_y:
                found.add(("edge", i))
        self.multi = found
        self.sel = None
        self.redraw()
        self._show_side()

    def on_touchpad(self, event):
        _, dy = (int(v) for v in self.root.tk.call("::tk::PreciseScrollDeltas", event.delta))
        self.on_wheel(event, dy)

    def on_wheel(self, event, delta=None):
        """Scroll to zoom, keeping the point under the cursor fixed."""
        delta = event.delta if delta is None else delta
        if not delta:
            return
        if abs(delta) >= 120:                    # Windows wheel: multiples of 120 per notch
            delta = delta / 120 * 3
        old = self.zoom
        new = min(3.0, max(0.3, old * 1.03 ** max(-10, min(10, delta))))
        if new == old:
            return
        mx = self.canvas.canvasx(event.x) / old
        my = self.canvas.canvasy(event.y) / old
        self.zoom = new
        self.redraw()
        self.canvas.xview_moveto(max(0, (mx * new - event.x) / (3000 * new)))
        self.canvas.yview_moveto(max(0, (my * new - event.y) / (2000 * new)))

    def _connect_click(self, nid):
        if self.connect_from is None:
            self.connect_from = nid
        else:
            src, dst = self.connect_from, nid
            if src == dst:
                self.connect_from = None
            elif self.flow["nodes"][dst]["kind"] in ("start", "global"):
                messagebox.showinfo("Can't connect", "Arrows can't point at the Start or "
                                                     "'Any state' boxes.")
                self.connect_from = None
            else:
                self.flow["edges"].append({"from": src, "to": dst, "label": ""})
                self.sel = ("edge", len(self.flow["edges"]) - 1)
                self._mark_dirty()
                self.set_connecting(False)
                self._show_side()
                self.label_entry.focus_set()
        self.status.config(text=self._hint())
        self.redraw()

    def toggle_connect(self):
        self.set_connecting(not self.connecting)
        self.redraw()

    def set_connecting(self, on):
        self.connecting = on
        self.connect_from = None
        self.connect_btn.config(relief="sunken" if on else "raised")
        self.status.config(text=self._hint())

    # ---------- actions ----------
    def _free_spot(self):
        xs = [n["x"] for n in self.flow["nodes"].values()]
        ys = [n["y"] for n in self.flow["nodes"].values()]
        return (min(xs, default=40) + 30 * (len(xs) % 6), max(ys, default=0) + H + 30)

    def _new_id(self):
        i = 1
        while f"n{i}" in self.flow["nodes"]:
            i += 1
        return f"n{i}"

    def add_line(self):
        nid = self._new_id()
        x, y = self._free_spot()
        self.flow["nodes"][nid] = {"kind": "say", "text": "New line", "x": x, "y": y}
        self.multi.clear()
        self.sel = ("node", nid)
        self._mark_dirty()
        self.redraw()
        self._show_side()
        self.text.focus_set()
        self.text.tag_add("sel", "1.0", "end")

    def add_global(self):
        if any(n["kind"] == "global" for n in self.flow["nodes"].values()):
            messagebox.showinfo("Already there", "There is only one 'Any state' box.")
            return
        nid = self._new_id()
        x, y = self._free_spot()
        self.flow["nodes"][nid] = {"kind": "global", "text": "Any state", "x": x, "y": y}
        self.multi.clear()
        self.sel = ("node", nid)
        self._mark_dirty()
        self.redraw()
        self._show_side()

    def _delete_multi(self):
        nodes = {i for k, i in self.multi if k == "node"}
        edges = {i for k, i in self.multi if k == "edge"}
        starts = {i for i in nodes if self.flow["nodes"][i]["kind"] == "start"}
        if starts:
            messagebox.showinfo("Can't delete", "The Start line can't be deleted; "
                                                "deleting the rest.")
        nodes -= starts
        for i in nodes:
            del self.flow["nodes"][i]
        self.flow["edges"] = [e for k, e in enumerate(self.flow["edges"])
                              if k not in edges and e["from"] not in nodes and e["to"] not in nodes]
        self.multi.clear()
        self._mark_dirty()
        self.redraw()
        self._show_side()

    def delete_selected(self):
        if self.multi:
            self._delete_multi()
            return
        if not self.sel:
            return
        kind, ident = self.sel
        if kind == "node":
            if self.flow["nodes"][ident]["kind"] == "start":
                messagebox.showinfo("Can't delete", "The Start line can't be deleted.")
                return
            del self.flow["nodes"][ident]
            self.flow["edges"] = [e for e in self.flow["edges"]
                                  if ident not in (e["from"], e["to"])]
        else:
            del self.flow["edges"][ident]
        self.sel = None
        self._mark_dirty()
        self.redraw()
        self._show_side()

    def test(self):
        if self.test_win and self.test_win.winfo_exists():
            self.test_win.destroy()
        win = tk.Toplevel(self.root)
        win.title("Test run")
        runner = Runner(win, self.flow)
        runner.pack(fill="both", expand=True)

        def close():
            runner.stop()
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", close)
        self.test_win = win

    # ---------- files ----------
    def save(self):
        flowlib.save(self.flow, self.path)
        self.dirty = False
        self._update_title()
        return True

    def save_as(self):
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            initialfile=os.path.basename(self.path),
                                            initialdir=os.path.dirname(self.path))
        if not path:
            return False
        self.path = path
        return self.save()

    def open_file(self):
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(filetypes=[("Flow JSON", "*.json")],
                                          initialdir=os.path.dirname(self.path))
        if path:
            self.path = path
            self.flow = flowlib.load(path)
            self.sel = None
            self.multi.clear()
            self.dirty = False
            self._update_title()
            self.redraw()
            self._show_side()

    def _confirm_discard(self):
        if not self.dirty:
            return True
        ans = messagebox.askyesnocancel("Unsaved changes", "Save changes first?")
        if ans is None:
            return False
        return self.save() if ans else True

    def close(self):
        if self._confirm_discard():
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1200x720")
    Editor(root, os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else FLOW_PATH)
    root.mainloop()

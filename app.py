"""Runner GUI for testing the NPC. Run: python3 app.py"""
import copy
import os
import tkinter as tk
from tkinter import scrolledtext

import flow as flowlib

HERE = os.path.dirname(os.path.abspath(__file__))
FLOW_PATH = os.path.join(HERE, "flow.json")


class Runner(tk.Frame):
    """Subtitle box, one button per labeled edge, and a log. Plays a flow dict."""

    def __init__(self, parent, flow):
        super().__init__(parent)
        self.subtitle = tk.Label(
            self, text="", font=("Helvetica", 16), wraplength=480, height=3, justify="center",
        )
        self.subtitle.pack(padx=16, pady=(16, 8), fill="x")

        self.player = flowlib.Player(
            copy.deepcopy(flow), self.show_line, self.after, self.after_cancel
        )

        # Fixed-height bar so the layout doesn't jump when buttons come and go.
        bar = tk.Frame(self, height=40)
        bar.pack(padx=16, pady=8, fill="x")
        bar.pack_propagate(False)
        self.buttons = tk.Frame(bar)
        self.buttons.place(relx=0.5, rely=0.5, anchor="center")
        self._shown = None

        self.log = scrolledtext.ScrolledText(self, width=60, height=10, state="disabled")
        self.log.pack(padx=16, pady=(8, 16), fill="both", expand=True)
        self.player.start()

    def refresh_buttons(self):
        """Show only the buttons that can be pressed from the NPC's current node."""
        labels = self.player.available_buttons()
        if labels == self._shown:
            return
        self._shown = labels
        for child in self.buttons.winfo_children():
            child.destroy()
        for label in labels:
            tk.Button(self.buttons, text=label,
                      command=lambda l=label: self.player.press(l)).pack(side="left", padx=4)

    def show_line(self, node):
        self.refresh_buttons()
        self.subtitle.config(text=node["text"])
        self.log.config(state="normal")
        self.log.insert("end", node["text"] + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def stop(self):
        self.player.stop()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("NPC Test")
    runner = Runner(root, flowlib.load(FLOW_PATH))
    runner.pack(fill="both", expand=True)

    def close():
        runner.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    root.mainloop()

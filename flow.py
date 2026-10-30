"""Dialogue flowchart model and the Player that walks it.

flow.json format:
  settings: {"idle_delay_ms": [min, max]}
  nodes:    {id: {"kind": "start"|"say"|"global", "text": str, "x": int, "y": int}}
  edges:    [{"from": id, "to": id, "label": str, "delay": seconds (optional),
                                                       "weight": number (optional, default 1)}]

- "start" node: the first line the NPC says.
- "say" node: a line of dialogue. Its unlabeled outgoing edges are taken
  automatically after the line (one picked at random); labeled edges are taken
  when the button with that label is pressed while the NPC is on this node.
- An edge's optional "delay" is a wait in seconds before it is followed. On an
  automatic edge it replaces the default pause; on a button edge it starts at the press.
- When several edges leave a node with the same label, one is chosen at random, each
  with probability proportional to its "weight".
- "global" node: not spoken. Its labeled edges apply from any node that has no
  edge of its own for the pressed button.
"""
import json
import random

DEFAULT_SETTINGS = {"idle_delay_ms": [3000, 6000]}


def new_flow():
    return {
        "settings": dict(DEFAULT_SETTINGS),
        "nodes": {"n1": {"kind": "start", "text": "Hello there.", "x": 60, "y": 60}},
        "edges": [],
    }


def load(path):
    with open(path, encoding="utf-8") as f:
        flow = json.load(f)
    flow.setdefault("settings", dict(DEFAULT_SETTINGS))
    flow.setdefault("edges", [])
    return flow


def save(flow, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(flow, f, indent=2, ensure_ascii=False)


def button_labels(flow):
    """Unique button labels, in the order they first appear in the edge list."""
    labels = []
    for e in flow["edges"]:
        if e["label"] and e["label"] not in labels:
            labels.append(e["label"])
    return labels


def weight(edge):
    w = edge.get("weight", 1)
    return w if w > 0 else 0


def chance(flow, edge):
    """Probability (0-1) that `edge` is chosen among edges with the same source and label,
    or None when it has no siblings."""
    group = [e for e in flow["edges"]
             if e["from"] == edge["from"] and e["label"] == edge["label"]]
    if len(group) < 2:
        return None
    total = sum(weight(e) for e in group)
    return weight(edge) / total if total else 1 / len(group)


def pick(edges):
    weights = [weight(e) for e in edges]
    if not any(weights):
        return random.choice(edges)
    return random.choices(edges, weights=weights)[0]


class Player:
    def __init__(self, flow, say, schedule, cancel):
        """
        say(node): called with the node dict being spoken
        schedule(ms, fn) -> handle; cancel(handle): timer hooks (e.g. Tk's after)
        """
        self.flow = flow
        self._say = say
        self._schedule = schedule
        self._cancel = cancel
        self._timer = None
        self.current = None

    def buttons(self):
        return button_labels(self.flow)

    def available_buttons(self):
        """Labels that press() would act on right now (own edge or global fallback)."""
        gid = self._global_id()
        return [l for l in self.buttons()
                if self._edges(self.current, l) or self._edges(gid, l)]

    def start(self):
        for nid, node in self.flow["nodes"].items():
            if node["kind"] == "start":
                self._enter(nid)
                return

    def press(self, label):
        """Button pressed: follow its edge from the current node, else a global one."""
        edges = self._edges(self.current, label) or self._edges(self._global_id(), label)
        if edges:
            self._take(pick(edges))

    def stop(self):
        self._clear_timer()

    def _global_id(self):
        for nid, node in self.flow["nodes"].items():
            if node["kind"] == "global":
                return nid
        return None

    def _edges(self, src, label):
        if src is None:
            return []
        return [e for e in self.flow["edges"] if e["from"] == src and e["label"] == label]

    def _take(self, edge, default_ms=0):
        """Follow an edge, after its own wait if it has one (seconds), else default_ms."""
        self._clear_timer()
        wait = edge.get("delay")
        ms = int(wait * 1000) if wait is not None else default_ms
        if ms > 0:
            self._timer = self._schedule(ms, lambda: self._arrive(edge["to"]))
        else:
            self._arrive(edge["to"])

    def _arrive(self, nid):
        self._timer = None
        self._enter(nid)

    def _enter(self, nid):
        self._clear_timer()
        self.current = nid
        node = self.flow["nodes"][nid]
        self._say(node)
        auto = self._edges(nid, "")
        if not auto:
            return
        # Avoid immediately repeating the line we're on when there's a choice.
        edge = pick([e for e in auto if e["to"] != nid] or auto)
        # Text-only default: about as long as the line takes to read, plus a gap.
        # With mp3s, replace this with an on-finished callback from the player.
        lo, hi = self.flow["settings"]["idle_delay_ms"]
        default = 400 + 60 * len(node["text"]) + random.randint(lo, hi)
        self._take(edge, default)

    def _clear_timer(self):
        if self._timer is not None:
            self._cancel(self._timer)
            self._timer = None

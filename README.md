# NPC dialogue tool

A talking-NPC test program (text lines for now) with a flowchart editor for its dialogue.
Needs **Python 3.8+ with Tk** – nothing else to install. Everything lives in this folder.

## One-click start (after cloning)

| | Run the NPC | Edit the flowchart |
|---|---|---|
| **macOS** | double-click `Run NPC.command` | double-click `Edit Flow.command` |
| **Windows** | double-click `Run NPC.bat` | double-click `Edit Flow.bat` |
| **Linux** | run/double-click `run-npc.sh` | run/double-click `edit-flow.sh` |

First-time notes:
- **macOS:** if it's blocked, right-click the file -> Open.
- **Windows:** if SmartScreen warns, choose More info -> Run anyway.
- **Linux:** if double-clicking opens a text editor, set your file manager to run executable
  text files (or run `./run-npc.sh` in a terminal). If needed: `chmod +x *.sh *.command`.
- No Python? The launcher says so. Install from https://www.python.org/downloads/
  (Windows: tick "Add python.exe to PATH"; Linux: `sudo apt install python3 python3-tk`).

Or from a terminal in this folder: `python3 launch.py app` / `python3 launch.py editor`.

## Files
- `launch.py` – checks Python/Tk, then starts a program (what the launchers call).
- `flow.json` – the dialogue flowchart. `flow.py` – model + the `Player` that walks it.
- `app.py` – the NPC window. `editor.py` – the flowchart editor.
- `Design Doc.md` – original design notes.

## Flowchart rules
- **Start line** (green): spoken first.
- **Line** (blue): a spoken line. Unlabeled arrows out of it are followed automatically after it
  finishes – this is how idle loops work. An arrow labeled with a button name is followed when
  that button is pressed while the NPC is on this line.
- **Any state** (orange, only one): labeled arrows out of it work from every line that has no
  arrow of its own for that button.
- Every distinct arrow label becomes a button in the NPC window.
- **Wait (sec)** on an arrow: transition after that long (after the line finishes for automatic
  arrows; after the press for button arrows). Empty = default reading-time pause.
- **Chance weight** on an arrow: when several arrows leave a box with the same label, one is
  picked at random in proportion to its weight (the editor shows the resulting %). Empty = 1.

## Editor controls
Add line / Add 'Any state', **Connect** (click source then target, then type the button name or
leave blank), Delete (button or Delete key), Open / Save (Cmd/Ctrl-S) / Save as, **Test ▶**.
Drag a box to move it; drag empty space to pan; scroll to zoom; shift-drag (or shift-click) to
multi-select, then Delete or drag the group.

## Audio later
Lines can get an mp3 path; replace the length-based timer in `Player._enter` with an
on-finished callback from the audio player.

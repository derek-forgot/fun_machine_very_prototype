"""Cross-platform launcher. Usage: python launch.py app|editor

Checks that Python and Tk are usable, explains how to fix it if not, then runs
the chosen program. The one-click launchers in the repo root all call this.
"""
import os
import platform
import runpy
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAMS = {"app": "app.py", "editor": "editor.py"}


def fail(message):
    print("\n" + message + "\n")
    try:                       # keep a double-click console window open so it can be read
        input("Press Enter to close...")
    except (EOFError, KeyboardInterrupt):
        pass
    sys.exit(1)


def tk_help():
    system = platform.system()
    if system == "Darwin":
        return ("On macOS, install Python from https://www.python.org/downloads/ "
                "(it includes Tk), or run: brew install python-tk")
    if system == "Windows":
        return ("Reinstall Python from https://www.python.org/downloads/ and make sure "
                "'tcl/tk and IDLE' is ticked in the installer.")
    return ("On Linux, install the Tk package, e.g.:\n"
            "  Debian/Ubuntu:  sudo apt install python3-tk\n"
            "  Fedora:         sudo dnf install python3-tkinter\n"
            "  Arch:           sudo pacman -S tk")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in PROGRAMS:
        fail("Usage: python launch.py app|editor")
    if sys.version_info < (3, 8):
        fail(f"Python 3.8 or newer is required (found {platform.python_version()}).\n"
             "Get it from https://www.python.org/downloads/")
    try:
        import tkinter  # noqa: F401
    except ImportError:
        fail("Python was found, but it doesn't include Tk (needed for the window).\n" + tk_help())

    os.chdir(HERE)
    sys.path.insert(0, HERE)
    try:
        runpy.run_path(os.path.join(HERE, PROGRAMS[sys.argv[1]]), run_name="__main__")
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        fail("The program crashed (details above).")


if __name__ == "__main__":
    main()

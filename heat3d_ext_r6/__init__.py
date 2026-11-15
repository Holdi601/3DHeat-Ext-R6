"""Rainbow Six Siege Match Replays (.rec) into the tables the 3DHeat viewer reads."""

from pathlib import Path

__version__ = (Path(__file__).resolve().parent.parent / "VERSION").read_text(encoding="utf-8").strip() \
    if (Path(__file__).resolve().parent.parent / "VERSION").exists() else "0.1.0"

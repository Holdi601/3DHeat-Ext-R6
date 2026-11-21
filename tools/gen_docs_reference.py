"""Write docs/cli-reference.md from the code itself, so the reference cannot drift.

The options come from the program's own `--help`.

    python tools/gen_docs_reference.py          # rewrite the page
    python tools/gen_docs_reference.py --check  # exit 1 when the page is stale
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "cli-reference.md"
COMMAND = "heat3d-r6-replay"


def run(args):
    env = dict(os.environ, HEAT3D_NO_UPDATE="1", COLUMNS="88", PYTHONIOENCODING="utf-8",
               PYTHONPATH=str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    r = subprocess.run([sys.executable, "-m", "heat3d_ext_r6"] + args, capture_output=True, text=True,
                       env=env, encoding="utf-8", cwd=ROOT)
    return (r.stdout or r.stderr).rstrip()


def build():
    out = ["---", "title: Command reference", "nav_order: 90", "---", "", "# Command reference", "",
           "Generated from the code by `tools/gen_docs_reference.py`: do not edit by hand.",
           "The other pages explain each command step by step; the README lists every column of a match.", "",
           f"## `{COMMAND}`", "", "```text", run(["--help"]), "```", "",
           f"## `{COMMAND} layouts`", "", "```text", run(["layouts", "--help"]), "```", ""]
    return "\n".join(out)


if __name__ == "__main__":
    text = build()
    if "--check" in sys.argv:
        sys.exit(0 if OUT.exists() and OUT.read_text(encoding="utf-8") == text else 1)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT))

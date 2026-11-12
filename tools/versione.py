"""Legge o aumenta la versione dell'add-on (nel file .toc e in Core.lua).

Esempi:
  python tools/versione.py              stampa la versione attuale
  python tools/versione.py --incrementa 0.1.0 -> 0.1.1
  python tools/versione.py --imposta 0.2.0
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fitlib  # noqa: E402

TOC = fitlib.CARTELLA_ADDON / "ForeverItaliano.toc"
CORE = fitlib.CARTELLA_ADDON / "Core.lua"


def leggi() -> str:
    m = re.search(r"^## Version: (\S+)", TOC.read_text(encoding="utf-8"), re.MULTILINE)
    return m.group(1) if m else "0.0.0"


def scrivi(versione: str) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", versione):
        raise SystemExit(f"Versione non valida: {versione} (serve il formato 1.2.3)")
    for file, schema, nuovo in (
        (TOC, r"^## Version: \S+", f"## Version: {versione}"),
        (CORE, r'^ns\.VERSIONE = "[^"]*"', f'ns.VERSIONE = "{versione}"'),
    ):
        testo = file.read_text(encoding="utf-8")
        file.write_text(re.sub(schema, nuovo, testo, count=1, flags=re.MULTILINE),
                        encoding="utf-8", newline="\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--incrementa", action="store_true")
    p.add_argument("--imposta")
    a = p.parse_args()
    if a.imposta:
        scrivi(a.imposta)
    elif a.incrementa:
        x, y, z = (int(n) for n in leggi().split("."))
        scrivi(f"{x}.{y}.{z + 1}")
    print(leggi())
    return 0


if __name__ == "__main__":
    sys.exit(main())

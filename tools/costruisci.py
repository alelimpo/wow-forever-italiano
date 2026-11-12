"""Crea i file di dati dell'add-on (addon/ForeverItaliano/Dati/*.lua) dal dizionario.

Esempio:
  python tools/costruisci.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fitlib  # noqa: E402

VOCI_PER_FILE = 10000   # Lua 5.1 ha un limite di costanti per file: restiamo molto sotto
INTESTAZIONE = """-- File generato da tools/costruisci.py: non modificarlo a mano.
-- Le traduzioni si correggono in data/traduzioni.json.
local _, ns = ...
ns.T = ns.T or {}
local T = ns.T
"""


def costruisci(db: dict, cartella_addon: Path = fitlib.CARTELLA_ADDON) -> tuple[int, int]:
    voci = sorted(
        (chiave, voce["it"]) for chiave, voce in db["voci"].items()
        if voce.get("stato") in fitlib.STATI_CON_TRADUZIONE and voce.get("it")
    )
    cartella_dati = cartella_addon / "Dati"
    cartella_dati.mkdir(parents=True, exist_ok=True)
    for vecchio in cartella_dati.glob("Dati*.lua"):
        vecchio.unlink()

    gruppi = [voci[i:i + VOCI_PER_FILE] for i in range(0, len(voci), VOCI_PER_FILE)] or [[]]
    nomi = []
    for numero, gruppo in enumerate(gruppi, 1):
        nome = f"Dati{numero:02d}.lua"
        nomi.append(nome)
        righe = [INTESTAZIONE]
        for chiave, it in gruppo:
            righe.append(f"T[{fitlib.stringa_lua(chiave)}] = {fitlib.stringa_lua(it)}\n")
        (cartella_dati / nome).write_text("".join(righe), encoding="utf-8", newline="\n")

    aggiorna_toc(cartella_addon / "ForeverItaliano.toc", nomi)
    return len(voci), len(nomi)


def aggiorna_toc(toc: Path, nomi: list[str]) -> None:
    testo = toc.read_text(encoding="utf-8")
    sezione = "\n".join(f"Dati\\{n}" for n in nomi)
    nuovo, sostituzioni = re.subn(
        r"(# DATI-INIZIO[^\n]*\n).*?(# DATI-FINE)",
        lambda m: m.group(1) + sezione + "\n" + m.group(2),
        testo, flags=re.DOTALL)
    if sostituzioni != 1:
        raise SystemExit(f"Nel file {toc} mancano le righe # DATI-INIZIO e # DATI-FINE")
    toc.write_text(nuovo, encoding="utf-8", newline="\n")


def main() -> int:
    fitlib.prepara_console()
    db = fitlib.carica_db()
    tradotte, file = costruisci(db)
    stati = {}
    for voce in db["voci"].values():
        stati[voce.get("stato", "?")] = stati.get(voce.get("stato", "?"), 0) + 1
    print(f"Add-on aggiornato: {tradotte} traduzioni in {file} file.")
    print("Dizionario: " + ", ".join(f"{s} {n}" for s, n in sorted(stati.items())) if stati else "Dizionario vuoto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

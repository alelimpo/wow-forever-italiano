"""Per i giocatori: prepara l'invio dei testi non tradotti senza passare dal gioco.

Cerca il file ForeverItaliano.lua nella cartella WTF di WoW Forever, crea il testo da
incollare, lo copia negli appunti e apre il modulo su GitHub.

Il gioco scrive quel file solo quando esci o scrivi /reload: fallo prima di lanciare lo script.

Esempi:
  python invia_testi.py
  python invia_testi.py --cartella "D:\\Giochi\\World of Warcraft\\_forever_"
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fitlib  # noqa: E402

URL_MODULO = ("https://github.com/alelimpo/wow-forever-italiano/issues/new"
              "?template=testi-da-tradurre.yml")
MAX_CARATTERI = 60000   # limite di un'issue di GitHub, con un po' di margine

RADICI_PROBABILI = [
    r"C:\Program Files (x86)\World of Warcraft",
    r"C:\Program Files\World of Warcraft",
    r"D:\World of Warcraft",
    r"D:\Games\World of Warcraft",
    r"D:\Giochi\World of Warcraft",
    "/Applications/World of Warcraft",
]


def trova_file(cartella: Path | None) -> list[Path]:
    radici = [cartella] if cartella else [Path(r) for r in RADICI_PROBABILI]
    trovati = []
    for radice in radici:
        if not radice.is_dir():
            continue
        # la cartella del gioco stessa (es. _forever_) oppure quella che la contiene
        for cartella_gioco in [radice] + [d for d in radice.iterdir() if d.is_dir()]:
            trovati += cartella_gioco.glob("WTF/Account/*/SavedVariables/ForeverItaliano.lua")
    return sorted(set(trovati), key=lambda p: p.stat().st_mtime, reverse=True)


def copia_negli_appunti(testo: str) -> bool:
    try:
        import tkinter
        finestra = tkinter.Tk()
        finestra.withdraw()
        finestra.clipboard_clear()
        finestra.clipboard_append(testo)
        finestra.update()
        finestra.destroy()
        return True
    except Exception:  # noqa: BLE001 - senza appunti si usa il file
        return False


def main() -> int:
    fitlib.prepara_console()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cartella", type=Path, help="cartella di WoW Forever (quella con dentro WTF)")
    p.add_argument("--non-aprire", action="store_true", help="non aprire il browser")
    a = p.parse_args()

    file = trova_file(a.cartella)
    if not file:
        print("Non trovo ForeverItaliano.lua. Indica la cartella del gioco con --cartella.")
        return 1

    voci = []
    for percorso in file:
        print(f"Leggo {percorso}")
        voci += fitlib.testi_da_savedvariables(percorso.read_text(encoding="utf-8", errors="replace"))
    unici = {}
    for contesto, testo, _ in voci:
        unici.setdefault(testo, contesto)
    if not unici:
        print("Non ci sono testi da inviare. Gioca un po' con l'add-on attivo, poi esci o scrivi /reload.")
        return 0

    # Divide in parti che stanno in un'issue
    parti, attuale = [], []
    for testo, contesto in sorted(unici.items()):
        prova = fitlib.crea_esportazione(attuale + [(contesto, testo)])
        if len(prova) > MAX_CARATTERI and attuale:
            parti.append(attuale)
            attuale = []
        attuale.append((contesto, testo))
    parti.append(attuale)

    cartella_uscita = Path.cwd()
    for n, parte in enumerate(parti, 1):
        nome = cartella_uscita / f"testi_da_inviare_{n}.txt"
        nome.write_text(fitlib.crea_esportazione(parte), encoding="utf-8")
        print(f"Creato {nome} ({len(parte)} testi)")

    copiato = copia_negli_appunti(fitlib.crea_esportazione(parti[0]))
    print()
    if copiato:
        print("La prima parte è già negli appunti: incollala nel modulo con Ctrl+V e premi Submit.")
    else:
        print("Apri testi_da_inviare_1.txt, copia tutto e incollalo nel modulo.")
    if len(parti) > 1:
        print(f"Ci sono {len(parti)} parti: per le successive apri un nuovo modulo e incolla il file corrispondente.")
    if not a.non_aprire:
        webbrowser.open(URL_MODULO)
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(main())

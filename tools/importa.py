"""Aggiunge al dizionario i testi inglesi ancora da tradurre.

Fonti accettate:
  * il file SavedVariables dell'add-on (ForeverItaliano.lua, nella cartella WTF del gioco);
  * un'esportazione fatta in gioco con /fit esporta (file .txt);
  * i file JSON in data/in_arrivo, creati dall'automazione di GitHub (--in-arrivo);
  * il testo di un'issue di GitHub, letto dalla variabile ISSUE_BODY (--da-issue).

Esempi:
  python tools/importa.py "C:\\...\\WTF\\Account\\NOME\\SavedVariables\\ForeverItaliano.lua"
  python tools/importa.py --in-arrivo
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fitlib  # noqa: E402

MAX_PER_ISSUE = 3000


def leggi_file(percorso: Path) -> list[tuple[str, str, int]]:
    testo = percorso.read_text(encoding="utf-8", errors="replace")
    if percorso.suffix.lower() == ".lua":
        return fitlib.testi_da_savedvariables(testo)
    if percorso.suffix.lower() == ".json":
        dati = json.loads(testo)
        return [(v.get("contesto", "?"), v["testo"], int(v.get("visto", 1))) for v in dati.get("testi", [])]
    return [(c, t, 1) for c, t in fitlib.leggi_esportazione(testo)]


def da_issue(db: dict, uscita: Path, riepilogo: Path | None) -> int:
    """Usato dall'automazione di GitHub: salva in un file a parte solo i testi nuovi,
    così più invii contemporanei non vanno in conflitto tra loro."""
    corpo = os.environ.get("ISSUE_BODY", "")
    voci = fitlib.leggi_esportazione(corpo)
    nuovi, gia_presenti, scartati = [], 0, 0
    visti = set()
    # testi già inviati da altri e non ancora importati nel dizionario
    in_coda = set()
    for altro in fitlib.CARTELLA_IN_ARRIVO.glob("*.json"):
        if altro.resolve() == uscita.resolve():
            continue
        try:
            in_coda.update(v["testo"] for v in json.loads(altro.read_text(encoding="utf-8")).get("testi", []))
        except (OSError, ValueError, KeyError):
            pass
    for contesto, testo in voci[:MAX_PER_ISSUE]:
        chiave = fitlib.normalizza(testo)
        if not fitlib.testo_valido(chiave) or chiave in visti:
            scartati += 1
            continue
        visti.add(chiave)
        if chiave in db["voci"] or chiave in in_coda:
            gia_presenti += 1
            continue
        nuovi.append({"contesto": contesto[:60], "testo": chiave})

    if nuovi:
        uscita.parent.mkdir(parents=True, exist_ok=True)
        with open(uscita, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"testi": nuovi}, f, ensure_ascii=False, indent=1)
            f.write("\n")

    messaggio = (
        f"Grazie! Ho ricevuto {len(voci)} testi: {len(nuovi)} nuovi, "
        f"{gia_presenti} già presenti nel progetto, {scartati} scartati.\n\n"
    )
    if nuovi:
        messaggio += "I testi nuovi verranno tradotti e inclusi nella prossima versione dell'add-on."
    elif not voci:
        messaggio += ("Non ho trovato testi da importare. Assicurati di incollare tutto quello che "
                      "mostra `/fit esporta`, comprese le righe che iniziano con `E`.")
    if riepilogo:
        riepilogo.write_text(messaggio, encoding="utf-8")
    print(messaggio)
    return len(nuovi)


def main() -> int:
    fitlib.prepara_console()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("file", nargs="*", type=Path, help="SavedVariables .lua, esportazione .txt o .json")
    p.add_argument("--in-arrivo", action="store_true", help="importa e poi cancella i file in data/in_arrivo")
    p.add_argument("--da-issue", action="store_true", help="legge l'issue dalla variabile ISSUE_BODY")
    p.add_argument("--uscita", type=Path, help="con --da-issue: dove salvare i testi nuovi")
    p.add_argument("--riepilogo", type=Path, help="con --da-issue: file con il messaggio di risposta")
    a = p.parse_args()

    db = fitlib.carica_db()

    if a.da_issue:
        if not a.uscita:
            p.error("--da-issue richiede --uscita")
        da_issue(db, a.uscita, a.riepilogo)
        return 0

    in_arrivo = sorted(fitlib.CARTELLA_IN_ARRIVO.glob("*.json")) if a.in_arrivo else []
    file = list(a.file) + in_arrivo
    if not file and not a.in_arrivo:
        p.error("indica almeno un file oppure --in-arrivo")

    nuovi = totali = 0
    letti = []
    for percorso in file:
        try:
            voci = leggi_file(percorso)
        except (OSError, ValueError, KeyError) as e:
            print(f"! {percorso}: non riesco a leggerlo ({e})")
            continue
        letti.append(percorso)
        n = 0
        for contesto, testo, visto in voci:
            totali += 1
            if fitlib.aggiungi_testo(db, testo, contesto, visto):
                n += 1
        nuovi += n
        print(f"{percorso.name}: {len(voci)} testi, {n} nuovi")

    fitlib.salva_db(db)
    for percorso in in_arrivo:
        if percorso in letti:
            percorso.unlink()
    attesa = sum(1 for v in db["voci"].values() if v.get("stato") == fitlib.IN_ATTESA)
    print(f"Fatto: {nuovi} testi nuovi su {totali}. Da tradurre in tutto: {attesa}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

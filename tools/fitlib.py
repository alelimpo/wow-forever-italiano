"""Funzioni condivise dagli strumenti di Forever Italiano.

Solo libreria standard di Python (3.9+), così gira su qualsiasi PC Windows senza installare nulla.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
FILE_DB = RADICE / "data" / "traduzioni.json"
CARTELLA_IN_ARRIVO = RADICE / "data" / "in_arrivo"
FILE_GLOSSARIO = RADICE / "data" / "glossario.json"
CARTELLA_ADDON = RADICE / "addon" / "ForeverItaliano"

# Stati di una voce del dizionario
IN_ATTESA = "in_attesa"      # testo inglese ricevuto, manca la traduzione
AUTO = "auto"                # tradotto automaticamente
DA_RIVEDERE = "da_rivedere"  # tradotto, ma conviene un controllo umano
RIVISTO = "rivisto"          # controllato da una persona: non viene mai ritradotto
ERRORE = "errore"            # la traduzione automatica non è riuscita

STATI_CON_TRADUZIONE = (AUTO, DA_RIVEDERE, RIVISTO)

MAX_LUNGHEZZA = 4000


def prepara_console() -> None:
    """Evita errori con le lettere accentate nella console di Windows."""
    for flusso in (sys.stdout, sys.stderr):
        try:
            flusso.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


# ---------------------------------------------------------------------------
# Dizionario delle traduzioni
# ---------------------------------------------------------------------------

def carica_db(percorso: Path | None = None) -> dict:
    percorso = percorso or FILE_DB
    if not percorso.exists():
        return {"versione": 1, "voci": {}}
    with open(percorso, encoding="utf-8") as f:
        db = json.load(f)
    db.setdefault("versione", 1)
    db.setdefault("voci", {})
    return db


def salva_db(db: dict, percorso: Path | None = None) -> None:
    percorso = percorso or FILE_DB
    percorso.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = percorso.with_suffix(".tmp")
    with open(temporaneo, "w", encoding="utf-8", newline="\n") as f:
        json.dump(db, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(temporaneo, percorso)


# ---------------------------------------------------------------------------
# Testi: normalizzazione e controlli (devono coincidere con Core.lua)
# ---------------------------------------------------------------------------

_SPAZI_LUA = " \t\n\r\v\f"


def normalizza(testo: str) -> str:
    """Come ns.Normalizza in Core.lua, tranne il nome del personaggio (lo fa già il gioco)."""
    testo = testo.replace("\r\n", "\n").replace("\r", "\n")
    return testo.strip(_SPAZI_LUA)


def testo_valido(testo: str) -> bool:
    """Stesse regole di Core.lua: almeno 4 caratteri e una parola di 3 lettere."""
    if len(testo) < 4 or len(testo) > MAX_LUNGHEZZA:
        return False
    if not re.search(r"[A-Za-z]{3}", testo):
        return False
    if any(ord(c) < 32 and c not in "\n\t" for c in testo):
        return False
    return True


def aggiungi_testo(db: dict, testo: str, contesto: str | None = None, visto: int = 1) -> bool:
    """Aggiunge un testo inglese al dizionario. Restituisce True se era nuovo."""
    chiave = normalizza(testo)
    if not testo_valido(chiave):
        return False
    voci = db["voci"]
    voce = voci.get(chiave)
    if voce is None:
        voci[chiave] = {"stato": IN_ATTESA, "contesto": contesto or "?", "visto": max(1, int(visto))}
        return True
    voce["visto"] = int(voce.get("visto", 1)) + max(1, int(visto))
    return False


# ---------------------------------------------------------------------------
# Formato di esportazione dell'add-on (vedi Esporta.lua)
# ---------------------------------------------------------------------------

def escapa_esportazione(s: str) -> str:
    return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t").replace("|", "\\v")


def deescapa_esportazione(s: str) -> str:
    risultato = []
    i = 0
    mappa = {"\\": "\\", "n": "\n", "t": "\t", "v": "|"}
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s) and s[i + 1] in mappa:
            risultato.append(mappa[s[i + 1]])
            i += 2
        else:
            risultato.append(c)
            i += 1
    return "".join(risultato)


def leggi_esportazione(testo: str) -> list[tuple[str, str]]:
    """Restituisce le coppie (finestra, testo) da un'esportazione, ignorando il resto
    (per esempio i ``` del modulo di GitHub)."""
    voci = []
    for riga in testo.splitlines():
        riga = riga.rstrip("\r")
        if not riga.startswith("E\t"):
            continue
        parti = riga.split("\t", 2)
        if len(parti) != 3:
            continue
        voci.append((deescapa_esportazione(parti[1]), deescapa_esportazione(parti[2])))
    return voci


def crea_esportazione(voci: list[tuple[str, str]], versione: str = "strumenti") -> str:
    righe = [f"FIT1 {versione}"]
    for contesto, testo in voci:
        righe.append(f"E\t{escapa_esportazione(contesto)}\t{escapa_esportazione(testo)}")
    return "\n".join(righe)


# ---------------------------------------------------------------------------
# Lettura dei SavedVariables (file .lua scritti da WoW)
# ---------------------------------------------------------------------------

class ErroreLua(ValueError):
    pass


class _LettoreLua:
    """Legge le tabelle Lua che WoW scrive nei SavedVariables: stringhe, numeri,
    booleani, nil, tabelle e i commenti -- [1] che il gioco aggiunge."""

    def __init__(self, testo: str):
        self.t = testo
        self.i = 0

    def errore(self, messaggio: str) -> ErroreLua:
        riga = self.t.count("\n", 0, self.i) + 1
        return ErroreLua(f"{messaggio} (riga {riga})")

    def salta_spazi(self) -> None:
        t = self.t
        while self.i < len(t):
            c = t[self.i]
            if c in " \t\r\n":
                self.i += 1
            elif t.startswith("--", self.i):
                lungo = re.match(r"--\[(=*)\[", t[self.i:])
                if lungo:
                    fine = "]" + lungo.group(1) + "]"
                    pos = t.find(fine, self.i)
                    self.i = len(t) if pos < 0 else pos + len(fine)
                else:
                    pos = t.find("\n", self.i)
                    self.i = len(t) if pos < 0 else pos + 1
            else:
                break

    def vede(self, s: str) -> bool:
        self.salta_spazi()
        return self.t.startswith(s, self.i)

    def prendi(self, s: str) -> None:
        if not self.vede(s):
            raise self.errore(f"atteso '{s}'")
        self.i += len(s)

    def nome(self) -> str:
        self.salta_spazi()
        m = re.compile(r"[A-Za-z_][A-Za-z0-9_]*").match(self.t, self.i)
        if not m:
            raise self.errore("atteso un nome")
        self.i = m.end()
        return m.group(0)

    def stringa(self) -> str:
        self.salta_spazi()
        t = self.t
        lungo = re.compile(r"\[(=*)\[").match(t, self.i)
        if lungo:
            fine = "]" + lungo.group(1) + "]"
            inizio = lungo.end()
            if t.startswith("\n", inizio):
                inizio += 1
            pos = t.find(fine, inizio)
            if pos < 0:
                raise self.errore("stringa lunga non chiusa")
            self.i = pos + len(fine)
            return t[inizio:pos]
        quota = t[self.i]
        if quota not in "\"'":
            raise self.errore("attesa una stringa")
        self.i += 1
        byte = bytearray()
        semplici = {"n": 10, "t": 9, "r": 13, "a": 7, "b": 8, "f": 12, "v": 11,
                    "\\": 92, "\"": 34, "'": 39, "\n": 10}
        while True:
            if self.i >= len(t):
                raise self.errore("stringa non chiusa")
            c = t[self.i]
            if c == quota:
                self.i += 1
                break
            if c == "\\":
                s = t[self.i + 1:self.i + 2]
                if s in semplici:
                    byte.append(semplici[s])
                    self.i += 2
                elif s == "\r":
                    byte.append(10)
                    self.i += 3 if t.startswith("\n", self.i + 2) else 2
                elif s.isdigit():
                    m = re.compile(r"\d{1,3}").match(t, self.i + 1)
                    byte.append(int(m.group(0)) & 0xFF)
                    self.i = m.end()
                else:
                    raise self.errore(f"sequenza \\{s} non valida")
            else:
                byte.extend(c.encode("utf-8"))
                self.i += 1
        return byte.decode("utf-8", errors="replace")

    def valore(self):
        self.salta_spazi()
        t = self.t
        if self.i >= len(t):
            raise self.errore("valore mancante")
        c = t[self.i]
        if c == "{":
            return self.tabella()
        if c in "\"'" or (c == "[" and re.compile(r"\[=*\[").match(t, self.i)):
            return self.stringa()
        m = re.compile(r"-?(0[xX][0-9a-fA-F]+|\d+\.?\d*([eE][-+]?\d+)?|\.\d+([eE][-+]?\d+)?|inf|nan)").match(t, self.i)
        if m:
            self.i = m.end()
            n = m.group(0)
            if "x" in n.lower():
                return int(n, 16)
            numero = float(n)
            return int(numero) if numero.is_integer() and re.fullmatch(r"-?\d+", n) else numero
        parola = self.nome()
        if parola == "true":
            return True
        if parola == "false":
            return False
        if parola == "nil":
            return None
        raise self.errore(f"valore sconosciuto '{parola}'")

    def tabella(self):
        self.prendi("{")
        risultato: dict = {}
        indice = 1
        while not self.vede("}"):
            if self.vede("[") and not re.compile(r"\[=*\[").match(self.t, self.i):
                self.i += 1
                chiave = self.valore()
                self.prendi("]")
                self.prendi("=")
                risultato[chiave] = self.valore()
            else:
                salva = self.i
                m = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)").match(self.t, self.i)
                if m:
                    self.i = m.end()
                    risultato[m.group(1)] = self.valore()
                else:
                    self.i = salva
                    risultato[indice] = self.valore()
                    indice += 1
            if self.vede(",") or self.vede(";"):
                self.i += 1
        self.prendi("}")
        return risultato

    def file(self) -> dict:
        variabili = {}
        while True:
            self.salta_spazi()
            if self.i >= len(self.t):
                return variabili
            nome = self.nome()
            self.prendi("=")
            variabili[nome] = self.valore()


def leggi_savedvariables(testo: str) -> dict:
    return _LettoreLua(testo).file()


def testi_da_savedvariables(testo: str) -> list[tuple[str, str, int]]:
    """Restituisce (finestra, testo, volte visto) dai SavedVariables dell'add-on."""
    variabili = leggi_savedvariables(testo)
    db = variabili.get("ForeverItalianoDB") or {}
    raccolti = db.get("raccolti") or {}
    voci = []
    for chiave, voce in raccolti.items():
        if not isinstance(chiave, str):
            continue
        voce = voce if isinstance(voce, dict) else {}
        voci.append((str(voce.get("c") or "?"), chiave, int(voce.get("n") or 1)))
    voci.sort(key=lambda v: v[1])
    return voci


# ---------------------------------------------------------------------------
# Scrittura di stringhe Lua
# ---------------------------------------------------------------------------

def stringa_lua(s: str) -> str:
    """Stringa Lua tra virgolette, sicura per qualsiasi contenuto."""
    pezzi = ['"']
    for c in s:
        if c == "\\":
            pezzi.append("\\\\")
        elif c == '"':
            pezzi.append('\\"')
        elif c == "\n":
            pezzi.append("\\n")
        elif c == "\r":
            pezzi.append("\\r")
        elif c == "\t":
            pezzi.append("\\t")
        elif ord(c) < 32 or ord(c) == 127:
            pezzi.append(f"\\{ord(c):03d}")
        else:
            pezzi.append(c)
    pezzi.append('"')
    return "".join(pezzi)


# ---------------------------------------------------------------------------
# Segnaposto: le parti che il traduttore non deve toccare
# ---------------------------------------------------------------------------

_SEGNAPOSTO_GIOCO = re.compile(
    r"\$[Gg][^:;\n]*:[^;\n]*;"          # forma maschile:femminile
    r"|\$[NnCcRr]"                      # nome, classe, razza
    r"|\|c[0-9a-fA-F]{8}|\|r"           # colori
    r"|\|T[^|]*\|t|\|A[^|]*\|a"         # icone
    r"|\|H[^|]*\|h|\|h"                 # collegamenti
    r"|\|n"                             # a capo di WoW
    r"|%\d*\$?[sd]"                     # formati numerici
)

_DESCRIZIONI = {
    "$N": "il nome del personaggio del giocatore",
    "$C": "la classe del giocatore",
    "$R": "la razza del giocatore",
}


def descrivi_segnaposto(token: str) -> str:
    if token[:2].upper() in _DESCRIZIONI:
        return _DESCRIZIONI[token[:2].upper()]
    if token.upper().startswith("$G"):
        return "una parola che cambia tra maschile e femminile"
    if token.startswith("|c") or token == "|r":
        return "un codice colore"
    if token.startswith("%"):
        return "un numero o una parola inseriti dal gioco"
    return "un codice del gioco"


def proteggi(testo: str) -> tuple[str, list[str]]:
    """Sostituisce i codici del gioco con [#0], [#1], ... e restituisce l'elenco."""
    token: list[str] = []

    def sostituisci(m: re.Match) -> str:
        token.append(m.group(0))
        return f"[#{len(token) - 1}]"

    return _SEGNAPOSTO_GIOCO.sub(sostituisci, testo), token


class SegnapostoMancanti(ValueError):
    pass


def ripristina(testo: str, token: list[str]) -> str:
    trovati = re.findall(r"\[#(\d+)\]", testo)
    attesi = [str(i) for i in range(len(token))]
    if sorted(trovati) != sorted(attesi):
        raise SegnapostoMancanti(f"segnaposto attesi {attesi}, trovati {trovati}")
    return re.sub(r"\[#(\d+)\]", lambda m: token[int(m.group(1))], testo)

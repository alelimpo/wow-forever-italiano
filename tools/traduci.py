"""Traduce in italiano i testi in attesa usando Ollama sul tuo PC (nessun costo a token).

Prima di usarlo:
  1. installa Ollama e scarica un modello, per esempio:  ollama pull qwen2.5:7b
  2. scrivi il nome del modello in tools/config.json (oppure usa --modello)

Esempi:
  python tools/traduci.py                       traduce tutti i testi in attesa
  python tools/traduci.py --limite 50           solo i primi 50 (i più visti in gioco)
  python tools/traduci.py --prova "Hello, $N!"  prova il modello su una frase
  python tools/traduci.py --ritenta-errori      riprova i testi andati in errore

Il lavoro viene salvato man mano: puoi interrompere con Ctrl+C e riprendere dopo.
I testi con stato "rivisto" (controllati da una persona) non vengono mai toccati.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fitlib  # noqa: E402

FILE_CONFIG = Path(__file__).resolve().parent / "config.json"

ISTRUZIONI = """Sei un traduttore professionista di videogiochi fantasy. Traduci in italiano il testo di World of Warcraft che ricevi.
Regole:
1. Rispondi solo con la traduzione: niente commenti, note, spiegazioni o virgolette in più.
2. I segnaposto come [#0] o [#1] vanno copiati identici, uno per uno: non tradurli e non cancellarli.
3. Lascia in inglese i nomi propri di luoghi, personaggi, oggetti, gilde e creature, così coincidono con la mappa e le scritte del gioco. Fanno eccezione le parole del glossario.
4. Mantieni il tono originale: solenne nelle missioni, colloquiale nei dialoghi. Rivolgiti al giocatore con il tu.
5. Il testo tra < > descrive un'azione o un gesto: traducilo e lascia i simboli < >."""


class ErroreOllama(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Configurazione e glossario
# ---------------------------------------------------------------------------

def carica_config() -> dict:
    config = {"host": "http://localhost:11434", "modello": "qwen2.5:7b", "temperatura": 0.2,
              "tentativi": 3, "timeout": 300}
    if FILE_CONFIG.exists():
        config.update(json.loads(FILE_CONFIG.read_text(encoding="utf-8")))
    return config


def carica_glossario(percorso: Path = fitlib.FILE_GLOSSARIO) -> dict:
    if not percorso.exists():
        return {"traduci": {}, "non_tradurre": []}
    dati = json.loads(percorso.read_text(encoding="utf-8"))
    return {"traduci": dati.get("traduci", {}), "non_tradurre": dati.get("non_tradurre", [])}


def _compare(termine: str, testo: str) -> bool:
    # "Light" (la Luce) solo con la maiuscola; "quest" in qualsiasi forma
    opzioni = 0 if termine[:1].isupper() else re.IGNORECASE
    return re.search(r"(?<![A-Za-z])" + re.escape(termine) + r"(?![A-Za-z])", testo, opzioni) is not None


def righe_glossario(testo: str, glossario: dict) -> str:
    """Solo le voci del glossario presenti nel testo, per non confondere il modello."""
    righe = []
    for en, it in sorted(glossario["traduci"].items()):
        if _compare(en, testo):
            righe.append(f"- {en} → {it}")
    for nome in sorted(glossario["non_tradurre"]):
        if _compare(nome, testo):
            righe.append(f"- {nome} → {nome} (non tradurre)")
    return "\n".join(righe)


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

class Ollama:
    def __init__(self, host: str, modello: str, temperatura: float = 0.2, timeout: int = 300):
        self.host = host.rstrip("/")
        self.modello = modello
        self.temperatura = temperatura
        self.timeout = timeout

    def _richiesta(self, percorso: str, dati: dict | None = None) -> dict:
        corpo = json.dumps(dati).encode("utf-8") if dati is not None else None
        richiesta = urllib.request.Request(
            self.host + percorso, data=corpo,
            headers={"Content-Type": "application/json"},
            method="POST" if corpo is not None else "GET")
        try:
            with urllib.request.urlopen(richiesta, timeout=self.timeout) as risposta:
                return json.loads(risposta.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            dettaglio = e.read().decode("utf-8", errors="replace")[:300]
            raise ErroreOllama(f"Ollama ha risposto {e.code}: {dettaglio}") from e
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            raise ErroreOllama(
                f"Ollama non risponde su {self.host}. È avviato? ({e})") from e

    def modelli(self) -> list[str]:
        return [m["name"] for m in self._richiesta("/api/tags").get("models", [])]

    def controlla_modello(self) -> None:
        disponibili = self.modelli()
        varianti = {self.modello, self.modello + ":latest"}
        if not varianti & set(disponibili):
            elenco = "\n  ".join(disponibili) or "(nessuno: scaricane uno con 'ollama pull ...')"
            raise ErroreOllama(
                f"Il modello '{self.modello}' non è installato in Ollama.\n"
                f"Modelli disponibili:\n  {elenco}\n"
                f"Scegline uno con --modello oppure scrivilo in tools/config.json.")

    def chat(self, messaggi: list[dict]) -> str:
        risposta = self._richiesta("/api/chat", {
            "model": self.modello,
            "messages": messaggi,
            "stream": False,
            "options": {"temperature": self.temperatura},
        })
        return risposta.get("message", {}).get("content", "")


# ---------------------------------------------------------------------------
# Traduzione
# ---------------------------------------------------------------------------

def pulisci_risposta(risposta: str, originale: str) -> str:
    risposta = re.sub(r"<think>.*?</think>", "", risposta, flags=re.DOTALL)
    risposta = risposta.strip()
    risposta = re.sub(r"^(traduzione|translation)\s*:\s*", "", risposta, flags=re.IGNORECASE)
    for a, b in (('"', '"'), ("«", "»"), ("“", "”")):
        if risposta.startswith(a) and risposta.endswith(b) and not originale.startswith(a):
            risposta = risposta[1:-1].strip()
    return risposta


def controlla(tradotto: str, originale: str) -> None:
    if not tradotto:
        raise ValueError("risposta vuota")
    rapporto = len(tradotto) / max(1, len(originale))
    if len(originale) > 20 and not 0.4 <= rapporto <= 3.0:
        raise ValueError(f"lunghezza sospetta ({len(tradotto)} caratteri contro {len(originale)})")
    if "\n" in tradotto and "\n" not in originale:
        raise ValueError("ha aggiunto righe che nell'originale non ci sono")


def traduci_pezzo(ollama: Ollama, pezzo: str, glossario: dict, tentativi: int) -> str:
    protetto, token = fitlib.proteggi(pezzo)
    sistema = ISTRUZIONI
    gloss = righe_glossario(pezzo, glossario)
    if gloss:
        sistema += "\n\nGlossario:\n" + gloss
    if token:
        sistema += "\n\nSegnaposto in questo testo:\n" + "\n".join(
            f"- [#{i}] = {fitlib.descrivi_segnaposto(t)}" for i, t in enumerate(token))
    messaggi = [{"role": "system", "content": sistema}, {"role": "user", "content": protetto}]

    ultimo_errore = None
    for _ in range(max(1, tentativi)):
        risposta = pulisci_risposta(ollama.chat(messaggi), protetto)
        try:
            controlla(risposta, protetto)
            return fitlib.ripristina(risposta, token)
        except ValueError as e:
            ultimo_errore = e
            messaggi = messaggi[:2] + [
                {"role": "assistant", "content": risposta},
                {"role": "user", "content":
                    f"La traduzione non va bene: {e}. Riscrivila rispettando le regole "
                    f"e copiando tutti i segnaposto [#n]. Rispondi solo con la traduzione."},
            ]
    raise ValueError(f"traduzione non riuscita: {ultimo_errore}")


def traduci_testo(ollama: Ollama, testo: str, glossario: dict, tentativi: int = 3) -> str:
    """Traduce paragrafo per paragrafo, così gli a capo restano identici all'originale."""
    parti = re.split(r"(\n+)", testo)
    risultato = []
    for parte in parti:
        if not parte or parte.startswith("\n") or not re.search(r"[A-Za-z]", parte):
            risultato.append(parte)
            continue
        iniziali = parte[:len(parte) - len(parte.lstrip())]
        finali = parte[len(parte.rstrip()):]
        risultato.append(iniziali + traduci_pezzo(ollama, parte.strip(), glossario, tentativi) + finali)
    return "".join(risultato)


def main() -> int:
    fitlib.prepara_console()
    config = carica_config()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modello", default=config["modello"], help=f"modello Ollama (ora: {config['modello']})")
    p.add_argument("--host", default=config["host"], help="indirizzo di Ollama")
    p.add_argument("--limite", type=int, default=0, help="traduce al massimo N testi")
    p.add_argument("--ritenta-errori", action="store_true", help="riprova anche i testi in errore")
    p.add_argument("--ritraduci-auto", action="store_true",
                   help="ritraduce anche i testi già tradotti in automatico (non quelli rivisti)")
    p.add_argument("--prova", metavar="TESTO", help="traduce solo questa frase e la stampa")
    a = p.parse_args()

    ollama = Ollama(a.host, a.modello, config["temperatura"], config["timeout"])
    glossario = carica_glossario()
    try:
        ollama.controlla_modello()
    except ErroreOllama as e:
        print(e)
        return 2

    if a.prova:
        try:
            print(traduci_testo(ollama, a.prova, glossario, config["tentativi"]))
        except (ValueError, ErroreOllama) as e:
            print(f"Errore: {e}")
            return 1
        return 0

    stati = {fitlib.IN_ATTESA}
    if a.ritenta_errori:
        stati.add(fitlib.ERRORE)
    if a.ritraduci_auto:
        stati.update({fitlib.AUTO, fitlib.DA_RIVEDERE})

    db = fitlib.carica_db()
    da_fare = [k for k, v in db["voci"].items() if v.get("stato") in stati]
    da_fare.sort(key=lambda k: (-int(db["voci"][k].get("visto", 1)), k))
    if a.limite:
        da_fare = da_fare[:a.limite]
    if not da_fare:
        print("Niente da tradurre.")
        return 0

    print(f"Traduco {len(da_fare)} testi con {a.modello}…")
    riusciti = errori = 0
    inizio = time.time()
    try:
        for n, chiave in enumerate(da_fare, 1):
            voce = db["voci"][chiave]
            try:
                voce["it"] = traduci_testo(ollama, chiave, glossario, config["tentativi"])
                voce["stato"] = fitlib.DA_RIVEDERE if re.search(r"\$[Gg]", chiave) else fitlib.AUTO
                voce["modello"] = a.modello
                voce.pop("errore", None)
                riusciti += 1
            except ValueError as e:
                voce["stato"] = fitlib.ERRORE
                voce["errore"] = str(e)[:200]
                errori += 1
            if n % 10 == 0 or n == len(da_fare):
                fitlib.salva_db(db)
                al_testo = (time.time() - inizio) / n
                print(f"  {n}/{len(da_fare)}  ({riusciti} tradotti, {errori} errori, "
                      f"circa {al_testo * (len(da_fare) - n) / 60:.0f} minuti rimasti)")
    except KeyboardInterrupt:
        print("\nInterrotto: salvo il lavoro fatto finora.")
    except ErroreOllama as e:
        print(f"\n{e}\nSalvo il lavoro fatto finora.")
        fitlib.salva_db(db)
        return 1
    fitlib.salva_db(db)
    print(f"Fatto: {riusciti} tradotti, {errori} errori.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

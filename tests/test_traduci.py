"""Prova traduci.py con un Ollama finto (nessun modello vero)."""

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import fitlib
import traduci


class OllamaFinto(BaseHTTPRequestHandler):
    richieste: list = []
    sbaglia_la_prima = False

    def log_message(self, *args):
        pass

    def _rispondi(self, dati):
        corpo = json.dumps(dati).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        self._rispondi({"models": [{"name": "finto:latest"}]})

    def do_POST(self):
        dati = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        OllamaFinto.richieste.append(dati)
        testo = dati["messages"][1]["content"]
        if OllamaFinto.sbaglia_la_prima and len(dati["messages"]) == 2:
            risposta = re.sub(r"\[#\d+\]", "", testo)          # perde i segnaposto
        else:
            risposta = "<think>ragiono</think>«IT " + testo + "»"
        self._rispondi({"message": {"role": "assistant", "content": risposta}})


@pytest.fixture
def ollama():
    OllamaFinto.richieste = []
    OllamaFinto.sbaglia_la_prima = False
    server = HTTPServer(("127.0.0.1", 0), OllamaFinto)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield traduci.Ollama(f"http://127.0.0.1:{server.server_port}", "finto")
    server.shutdown()


GLOSSARIO = {"traduci": {"Alliance": "Alleanza", "Light": "Luce"}, "non_tradurre": ["Stormwind"]}


def test_modello_trovato_e_mancante(ollama):
    ollama.controlla_modello()
    ollama.modello = "inesistente"
    with pytest.raises(traduci.ErroreOllama, match="finto:latest"):
        ollama.controlla_modello()


def test_ollama_spento():
    spento = traduci.Ollama("http://127.0.0.1:9", "x", timeout=2)
    with pytest.raises(traduci.ErroreOllama, match="non risponde"):
        spento.modelli()


def test_paragrafi_e_segnaposto(ollama):
    testo = "Hail, $N!\n\nThe Alliance needs you in Stormwind."
    risultato = traduci.traduci_testo(ollama, testo, GLOSSARIO)
    assert risultato == "IT Hail, $N!\n\nIT The Alliance needs you in Stormwind."
    # due paragrafi, due richieste; il glossario solo dove serve
    assert len(OllamaFinto.richieste) == 2
    sistema_secondo = OllamaFinto.richieste[1]["messages"][0]["content"]
    assert "Alliance → Alleanza" in sistema_secondo
    assert "Stormwind → Stormwind (non tradurre)" in sistema_secondo
    assert "Light" not in sistema_secondo
    assert "[#0] = il nome del personaggio" in OllamaFinto.richieste[0]["messages"][0]["content"]


def test_riprova_se_perde_i_segnaposto(ollama):
    OllamaFinto.sbaglia_la_prima = True
    assert traduci.traduci_testo(ollama, "Welcome, $N.", GLOSSARIO) == "IT Welcome, $N."
    assert len(OllamaFinto.richieste) == 2
    assert "segnaposto" in OllamaFinto.richieste[1]["messages"][-1]["content"]


def test_main_aggiorna_il_dizionario(ollama, tmp_path, monkeypatch):
    percorso = tmp_path / "traduzioni.json"
    fitlib.salva_db({"versione": 1, "voci": {
        "Hello there, $N.": {"stato": "in_attesa", "visto": 1},
        "Already reviewed.": {"stato": "rivisto", "it": "Già rivisto."},
        "Thanks, $Gsir:madam;.": {"stato": "in_attesa", "visto": 5},
    }}, percorso)
    monkeypatch.setattr(fitlib, "FILE_DB", percorso)
    monkeypatch.setattr("sys.argv", ["traduci.py", "--host", ollama.host, "--modello", "finto"])
    assert traduci.main() == 0
    voci = fitlib.carica_db(percorso)["voci"]
    assert voci["Hello there, $N."] == {"stato": "auto", "visto": 1, "it": "IT Hello there, $N.", "modello": "finto"}
    assert voci["Already reviewed."]["it"] == "Già rivisto."
    assert voci["Thanks, $Gsir:madam;."]["stato"] == "da_rivedere"

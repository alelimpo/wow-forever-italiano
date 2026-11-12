"""Prove degli strumenti Python: lettura dei file, segnaposto, costruzione dell'add-on."""

import json
import shutil
from pathlib import Path

import pytest

import costruisci
import fitlib
import importa

RADICE = Path(__file__).resolve().parent.parent

SAVEDVARIABLES = r'''
ForeverItalianoDB = {
	["raccolti"] = {
		["$N, bring me 8 Linen Cloth."] = {
			["c"] = "QuestFrame",
			["n"] = 3,
		},
		["Line one\nLine \"two\" \\ end"] = {
			["c"] = "GossipFrame",
			["n"] = 1,
			["e"] = true,
		},
		["Caf\195\169 au lait, please."] = {
			["c"] = "GossipFrame",
		},
	},
	["impostazioni"] = {
		["attivo"] = true,
		["raccolta"] = false,
	},
	["versione"] = 1,
	["lista"] = {
		"uno", -- [1]
		2.5, -- [2]
		-3, -- [3]
	},
}
AltraVariabile = nil
'''


def test_legge_savedvariables():
    variabili = fitlib.leggi_savedvariables(SAVEDVARIABLES)
    db = variabili["ForeverItalianoDB"]
    assert db["impostazioni"] == {"attivo": True, "raccolta": False}
    assert db["lista"] == {1: "uno", 2: 2.5, 3: -3}
    assert variabili["AltraVariabile"] is None
    testi = fitlib.testi_da_savedvariables(SAVEDVARIABLES)
    assert ("QuestFrame", "$N, bring me 8 Linen Cloth.", 3) in testi
    assert ("GossipFrame", 'Line one\nLine "two" \\ end', 1) in testi
    assert ("GossipFrame", "Café au lait, please.", 1) in testi


def test_esportazione_andata_e_ritorno():
    voci = [("QuestFrame", "A\\b\nc\td|e"), ("Gossip", "Semplice testo qui.")]
    testo = fitlib.crea_esportazione(voci)
    assert "|" not in testo
    # come arriva da un modulo di GitHub: dentro un blocco ``` e con a capo di Windows
    issue = "### Testi esportati\r\n\r\n```text\r\n" + testo.replace("\n", "\r\n") + "\r\n```"
    assert fitlib.leggi_esportazione(issue) == voci


@pytest.mark.parametrize("originale", [
    "Hello $N, the $c needs you.",
    "Thanks, $Gbrother:sister;! Take this |cffff0000potion|r.",
    "Bring %d pelts to %s.",
    "No codes at all.",
])
def test_segnaposto(originale):
    protetto, token = fitlib.proteggi(originale)
    assert "$" not in protetto and "|c" not in protetto
    assert fitlib.ripristina(protetto, token) == originale


def test_segnaposto_mancante():
    protetto, token = fitlib.proteggi("Hello $N, welcome to $R lands.")
    with pytest.raises(fitlib.SegnapostoMancanti):
        fitlib.ripristina("Ciao, benvenuto [#1].", token)


def test_stringa_lua_si_rilegge():
    lupa = pytest.importorskip("lupa.lua51")
    lua = lupa.LuaRuntime()
    for s in ['semplice', 'virgolette " e \\ barra', "a capo\nriga\r\tTab", "àèìòù — “citazione”", "\x01ctrl"]:
        assert lua.eval(fitlib.stringa_lua(s)) == s


def test_testo_valido():
    assert fitlib.testo_valido("Kill 10 Kobolds.")
    assert not fitlib.testo_valido("Ok")
    assert not fitlib.testo_valido("12 345")
    assert not fitlib.testo_valido("x" * 5000)


@pytest.fixture
def progetto(tmp_path, monkeypatch):
    """Copia del progetto in una cartella temporanea."""
    shutil.copytree(RADICE / "addon", tmp_path / "addon")
    (tmp_path / "data" / "in_arrivo").mkdir(parents=True)
    monkeypatch.setattr(fitlib, "FILE_DB", tmp_path / "data" / "traduzioni.json")
    monkeypatch.setattr(fitlib, "CARTELLA_IN_ARRIVO", tmp_path / "data" / "in_arrivo")
    monkeypatch.setattr(fitlib, "CARTELLA_ADDON", tmp_path / "addon" / "ForeverItaliano")
    return tmp_path


def test_importa_da_issue_e_poi_in_arrivo(progetto, monkeypatch, capsys):
    corpo = fitlib.crea_esportazione([("QuestFrame", "Kill 10 Kobold Vermin."), ("X", "Ok"),
                                      ("QuestFrame", "Kill 10 Kobold Vermin.")])
    monkeypatch.setenv("ISSUE_BODY", "```text\n" + corpo + "\n```")
    uscita = progetto / "data" / "in_arrivo" / "issue-7.json"
    monkeypatch.setattr("sys.argv", ["importa.py", "--da-issue", "--uscita", str(uscita),
                                     "--riepilogo", str(progetto / "r.txt")])
    assert importa.main() == 0
    dati = json.loads(uscita.read_text(encoding="utf-8"))
    assert dati == {"testi": [{"contesto": "QuestFrame", "testo": "Kill 10 Kobold Vermin."}]}
    assert "1 nuovi" in (progetto / "r.txt").read_text(encoding="utf-8")

    # una seconda issue con lo stesso testo non lo duplica
    uscita2 = progetto / "data" / "in_arrivo" / "issue-8.json"
    monkeypatch.setattr("sys.argv", ["importa.py", "--da-issue", "--uscita", str(uscita2)])
    importa.main()
    assert not uscita2.exists()

    # il manutentore importa la coda: il file viene consumato
    monkeypatch.setattr("sys.argv", ["importa.py", "--in-arrivo"])
    assert importa.main() == 0
    assert not uscita.exists()
    db = fitlib.carica_db()
    assert db["voci"]["Kill 10 Kobold Vermin."]["stato"] == fitlib.IN_ATTESA


def test_importa_savedvariables(progetto, monkeypatch):
    sv = progetto / "ForeverItaliano.lua"
    sv.write_text(SAVEDVARIABLES, encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["importa.py", str(sv)])
    importa.main()
    db = fitlib.carica_db()
    assert set(db["voci"]) == {"$N, bring me 8 Linen Cloth.", 'Line one\nLine "two" \\ end', "Café au lait, please."}
    assert db["voci"]["$N, bring me 8 Linen Cloth."]["visto"] == 3


def test_costruisci_crea_dati_e_toc(progetto):
    db = {"versione": 1, "voci": {
        "Kill 10 Kobold Vermin.": {"stato": "auto", "it": "Uccidi 10 Kobold Vermin."},
        "Hello, $N.": {"stato": "rivisto", "it": "Ciao, $N."},
        "Still waiting.": {"stato": "in_attesa"},
        "Broken one.": {"stato": "errore", "it": "x"},
    }}
    monkeypatch_voci = 23000
    for i in range(monkeypatch_voci):
        db["voci"][f"Generated text number {i}."] = {"stato": "auto", "it": f"Testo generato {i}."}
    tradotte, file = costruisci.costruisci(db, progetto / "addon" / "ForeverItaliano")
    assert tradotte == monkeypatch_voci + 2
    assert file == 3
    toc = (progetto / "addon" / "ForeverItaliano" / "ForeverItaliano.toc").read_text(encoding="utf-8")
    assert "Dati\\Dati01.lua\nDati\\Dati02.lua\nDati\\Dati03.lua\n# DATI-FINE" in toc

    lupa = pytest.importorskip("lupa.lua51")
    lua = lupa.LuaRuntime(unpack_returned_tuples=True)
    ns = lua.table()
    for n in range(1, 4):
        codice = (progetto / "addon" / "ForeverItaliano" / "Dati" / f"Dati{n:02d}.lua").read_text(encoding="utf-8")
        lua.eval("loadstring")(codice)("ForeverItaliano", ns)
    assert ns.T["Hello, $N."] == "Ciao, $N."
    assert ns.T["Broken one."] is None
    assert ns.T["Still waiting."] is None
    assert ns.T["Generated text number 22999."] == "Testo generato 22999."


def test_costruisci_senza_traduzioni(progetto):
    tradotte, file = costruisci.costruisci({"voci": {}}, progetto / "addon" / "ForeverItaliano")
    assert (tradotte, file) == (0, 1)
    assert (progetto / "addon" / "ForeverItaliano" / "Dati" / "Dati01.lua").exists()

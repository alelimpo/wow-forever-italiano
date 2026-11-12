"""Prova l'add-on Lua in un WoW finto (Lua 5.1, come il gioco)."""

import re
from pathlib import Path

import pytest

lupa = pytest.importorskip("lupa.lua51")

import fitlib  # noqa: E402

RADICE = Path(__file__).resolve().parent.parent
ADDON = RADICE / "addon" / "ForeverItaliano"


def file_dal_toc():
    righe = (ADDON / "ForeverItaliano.toc").read_text(encoding="utf-8").splitlines()
    return [r.strip().replace("\\", "/") for r in righe if r.strip() and not r.startswith("#")]


@pytest.fixture
def wow(tmp_path):
    # dati di prova al posto di quelli veri
    (tmp_path / "Dati").mkdir()
    for nome in ("Core.lua", "Esporta.lua"):
        (tmp_path / nome).write_text((ADDON / nome).read_text(encoding="utf-8"), encoding="utf-8")
    voci = {
        "Greetings, $N. The kobolds stole our candles.": "Saluti, $N. I coboldi ci hanno rubato le candele.",
        "Kill 10 Kobold Vermin.": "Uccidi 10 Kobold Vermin.",
        "Thank you, $Gsir:madam;.": "Grazie, $Gsignore:signora;.",
    }
    righe = ["local _, ns = ...\nns.T = ns.T or {}\nlocal T = ns.T\n"]
    righe += [f"T[{fitlib.stringa_lua(k)}] = {fitlib.stringa_lua(v)}\n" for k, v in voci.items()]
    (tmp_path / "Dati" / "Dati01.lua").write_text("".join(righe), encoding="utf-8")

    lua = lupa.LuaRuntime(unpack_returned_tuples=True)
    lua.execute((RADICE / "tests" / "wow_finto.lua").read_text(encoding="utf-8"))
    ns = lua.eval("CaricaAddon")(str(tmp_path), lua.table("Core.lua", "Esporta.lua", "Dati/Dati01.lua"))
    lua.globals().ns = ns
    lua.execute('LanciaEvento("ADDON_LOADED", "ForeverItaliano"); LanciaEvento("PLAYER_LOGIN")')
    return lua


def crea_finestra_missione(lua, *testi):
    lua.globals().TESTI = lua.table(*testi)
    lua.execute("""
        QuestFrame = CreateFrame("Frame", "QuestFrame", UIParent)
        local pannello = CreateFrame("Frame", nil, QuestFrame)
        SCRITTE = {}
        for i, t in ipairs(TESTI) do
            local fs = pannello:CreateFontString()
            fs:SetText(t)
            SCRITTE[i] = fs
        end
    """)


def scritta(lua, i):
    return lua.eval(f"SCRITTE[{i}]:GetText()")


def test_toc_elenca_file_esistenti():
    for nome in file_dal_toc():
        assert (ADDON / nome).exists(), nome
    assert "## Interface: 16001" in (ADDON / "ForeverItaliano.toc").read_text(encoding="utf-8")


def test_tutti_i_file_lua_si_caricano():
    lua = lupa.LuaRuntime()
    for nome in file_dal_toc():
        codice = (ADDON / nome).read_text(encoding="utf-8")
        assert lua.eval("loadstring")(codice, nome) is not None, nome


def test_traduce_e_mette_il_nome(wow):
    crea_finestra_missione(wow, "Greetings, Allemano Moo. The kobolds stole our candles.",
                           "Kill 10 Kobold Vermin.")
    wow.execute('LanciaEvento("QUEST_DETAIL"); EseguiTimer()')
    assert scritta(wow, 1) == "Saluti, Allemano Moo. I coboldi ci hanno rubato le candele."
    assert scritta(wow, 2) == "Uccidi 10 Kobold Vermin."


def test_maschile_femminile(wow):
    crea_finestra_missione(wow, "Thank you, madam.")
    # il testo a schermo è già risolto dal gioco: qui interessa il formato con $G
    assert wow.eval('ns.Formatta("Grazie, $Gsignore:signora;.")') == "Grazie, signore."
    wow.execute("GIOCATORE.sesso = 3")
    assert wow.eval('ns.Formatta("Grazie, $Gsignore:signora;.")') == "Grazie, signora."


def test_alt_mostra_inglese(wow):
    crea_finestra_missione(wow, "Kill 10 Kobold Vermin.")
    wow.execute('LanciaEvento("QUEST_DETAIL"); EseguiTimer()')
    assert scritta(wow, 1) == "Uccidi 10 Kobold Vermin."
    wow.execute('LanciaEvento("MODIFIER_STATE_CHANGED", "LALT", 1)')
    assert scritta(wow, 1) == "Kill 10 Kobold Vermin."
    # una nuova scansione con Alt premuto non deve ritradurre
    wow.execute('LanciaEvento("QUEST_LOG_UPDATE"); EseguiTimer()')
    assert scritta(wow, 1) == "Kill 10 Kobold Vermin."
    wow.execute('LanciaEvento("MODIFIER_STATE_CHANGED", "LALT", 0)')
    assert scritta(wow, 1) == "Uccidi 10 Kobold Vermin."


def test_raccoglie_testi_nuovi_senza_nome_del_giocatore(wow):
    crea_finestra_missione(wow, "Allemano, bring me 8 Linen Cloth.", "Ok", "  Moo  ")
    wow.execute('LanciaEvento("QUEST_PROGRESS"); EseguiTimer(); LanciaEvento("QUEST_PROGRESS"); EseguiTimer()')
    raccolti = dict(wow.eval("ForeverItalianoDB.raccolti").items())
    assert list(raccolti) == ["$N, bring me 8 Linen Cloth."]
    voce = raccolti["$N, bring me 8 Linen Cloth."]
    assert voce["c"] == "QuestFrame"
    assert voce["n"] >= 2
    # il testo inglese resta com'era
    assert scritta(wow, 1) == "Allemano, bring me 8 Linen Cloth."


def test_non_traduce_ne_raccoglie_lettere_di_giocatori(wow):
    wow.execute("""
        ItemTextFrame = CreateFrame("Frame", "ItemTextFrame", UIParent)
        local fs = ItemTextFrame:CreateFontString(); fs:SetText("Dear friend, meet me in Goldshire tonight.")
        function ItemTextGetCreator() return "Qualcuno" end
    """)
    wow.execute('LanciaEvento("ITEM_TEXT_READY"); EseguiTimer()')
    assert len(dict(wow.eval("ForeverItalianoDB.raccolti").items())) == 0


def test_spento_non_cambia_nulla(wow):
    crea_finestra_missione(wow, "Kill 10 Kobold Vermin.")
    wow.execute('SlashCmdList.FOREVERITALIANO("off"); LanciaEvento("QUEST_DETAIL"); EseguiTimer()')
    assert scritta(wow, 1) == "Kill 10 Kobold Vermin."


def test_esportazione_letta_da_python(wow):
    strano = "Line one\nLine two with \\ backslash, a |cffff0000color|r and\ttab, Allemano Moo."
    crea_finestra_missione(wow, strano)
    wow.execute('LanciaEvento("QUEST_COMPLETE"); EseguiTimer()')
    esportato, quanti = wow.eval("ns.CreaEsportazione(false)")
    assert quanti == 1
    assert esportato.startswith("FIT1 ")
    voci = fitlib.leggi_esportazione(esportato)
    assert voci == [("QuestFrame", strano.replace("Allemano Moo", "$N"))]
    # nessun carattere | nell'esportazione (in WoW ha un significato speciale)
    assert "|" not in esportato
    # già esportati: la seconda volta non c'è niente
    assert wow.eval("ns.CreaEsportazione(false)")[1] == 0
    assert wow.eval("ns.CreaEsportazione(true)")[1] == 1


def test_comandi(wow):
    wow.execute('SlashCmdList.FOREVERITALIANO("stato")')
    messaggi = list(dict(wow.eval("MESSAGGI").items()).values())
    assert any("3 traduzioni caricate" in m for m in messaggi)


def test_versione_coerente():
    toc = (ADDON / "ForeverItaliano.toc").read_text(encoding="utf-8")
    core = (ADDON / "Core.lua").read_text(encoding="utf-8")
    v_toc = re.search(r"## Version: (\S+)", toc).group(1)
    v_core = re.search(r'ns\.VERSIONE = "([^"]+)"', core).group(1)
    assert v_toc == v_core

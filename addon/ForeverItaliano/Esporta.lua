-- Forever Italiano - comandi ed esportazione dei testi non tradotti

local _, ns = ...

-- Formato di esportazione (letto da tools/importa.py):
--   prima riga:  FIT1 <versione>
--   poi una riga per testo:  E<tab><finestra><tab><testo>
-- Nel testo  \  diventa \\,  a capo diventa \n,  tab diventa \t  e  |  diventa \v
-- (il carattere | nelle caselle di testo di WoW ha un significato speciale).
function ns.Escapa(s)
    s = s:gsub("\\", "\\\\")
    s = s:gsub("\n", "\\n")
    s = s:gsub("\t", "\\t")
    s = s:gsub("|", "\\v")
    return s
end

function ns.CreaEsportazione(tutti)
    local db = ns.db
    local chiavi = {}
    for chiave, voce in pairs(db.raccolti) do
        if tutti or not voce.e then chiavi[#chiavi + 1] = chiave end
    end
    table.sort(chiavi)
    local righe = { "FIT1 " .. ns.VERSIONE }
    for _, chiave in ipairs(chiavi) do
        local voce = db.raccolti[chiave]
        righe[#righe + 1] = "E\t" .. ns.Escapa(voce.c or "?") .. "\t" .. ns.Escapa(chiave)
        voce.e = true
    end
    return table.concat(righe, "\n"), #chiavi
end

local function finestraEsportazione(testo)
    local f = ns.finestra
    if not f then
        f = CreateFrame("Frame", "ForeverItalianoEsporta", UIParent, "BackdropTemplate")
        f:SetSize(640, 420)
        f:SetPoint("CENTER")
        f:SetFrameStrata("DIALOG")
        if f.SetBackdrop then
            f:SetBackdrop({
                bgFile = "Interface\\DialogFrame\\UI-DialogBox-Background",
                edgeFile = "Interface\\DialogFrame\\UI-DialogBox-Border",
                tile = true, tileSize = 32, edgeSize = 32,
                insets = { left = 8, right = 8, top = 8, bottom = 8 },
            })
        end
        f:EnableMouse(true)
        f:SetMovable(true)
        f:RegisterForDrag("LeftButton")
        f:SetScript("OnDragStart", f.StartMoving)
        f:SetScript("OnDragStop", f.StopMovingOrSizing)

        local titolo = f:CreateFontString(nil, "OVERLAY", "GameFontNormal")
        titolo:SetPoint("TOP", 0, -16)
        titolo:SetText("Testi da inviare: premi Ctrl+A, poi Ctrl+C e incollali nel modulo su GitHub")

        local scorri = CreateFrame("ScrollFrame", "ForeverItalianoEsportaScorri", f, "UIPanelScrollFrameTemplate")
        scorri:SetPoint("TOPLEFT", 18, -40)
        scorri:SetPoint("BOTTOMRIGHT", -38, 48)

        local casella = CreateFrame("EditBox", nil, scorri)
        casella:SetMultiLine(true)
        casella:SetMaxLetters(0)
        casella:SetAutoFocus(false)
        casella:SetFontObject(ChatFontNormal)
        casella:SetWidth(570)
        casella:SetScript("OnEscapePressed", function() f:Hide() end)
        scorri:SetScrollChild(casella)

        local chiudi = CreateFrame("Button", nil, f, "UIPanelButtonTemplate")
        chiudi:SetSize(110, 24)
        chiudi:SetPoint("BOTTOM", 0, 16)
        chiudi:SetText("Chiudi")
        chiudi:SetScript("OnClick", function() f:Hide() end)

        f.casella = casella
        if UISpecialFrames then table.insert(UISpecialFrames, "ForeverItalianoEsporta") end
        ns.finestra = f
    end
    f.casella:SetText(testo)
    f:Show()
    f.casella:SetFocus()
    f.casella:HighlightText()
end

local function contaRaccolti()
    local totali, daInviare = 0, 0
    for _, voce in pairs(ns.db.raccolti) do
        totali = totali + 1
        if not voce.e then daInviare = daInviare + 1 end
    end
    return totali, daInviare
end

local AIUTO = {
    "comandi:",
    "  /fit stato - quante traduzioni e quanti testi raccolti",
    "  /fit on | off - mostra o nascondi le traduzioni",
    "  /fit raccolta on | off - salva o no i testi non tradotti",
    "  /fit esporta - mostra i testi nuovi da inviare al progetto",
    "  /fit esporta tutto - mostra anche quelli già esportati",
    "  /fit svuota - cancella i testi già esportati",
    "Tieni premuto Alt per vedere il testo originale in inglese.",
}

local function comando(argomenti)
    local db = ns.db
    if not db then return end
    local a, b = (argomenti or ""):lower():match("^%s*(%S*)%s*(%S*)")

    if a == "on" or a == "off" then
        db.impostazioni.attivo = (a == "on")
        ns.stampa(db.impostazioni.attivo and "traduzioni attive." or "traduzioni disattivate.")
        if db.impostazioni.attivo then ns.Aggiorna() end
    elseif a == "raccolta" and (b == "on" or b == "off") then
        db.impostazioni.raccolta = (b == "on")
        ns.stampa(db.impostazioni.raccolta and "raccolta dei testi attiva." or "raccolta dei testi disattivata.")
    elseif a == "stato" then
        local totali, daInviare = contaRaccolti()
        ns.stampa(("%d traduzioni caricate; %d testi raccolti, di cui %d ancora da esportare. Traduzioni %s, raccolta %s.")
            :format(ns.numTraduzioni or 0, totali, daInviare,
                db.impostazioni.attivo and "attive" or "spente",
                db.impostazioni.raccolta and "attiva" or "spenta"))
    elseif a == "esporta" then
        local testo, quanti = ns.CreaEsportazione(b == "tutto")
        if quanti == 0 then
            ns.stampa("nessun testo nuovo da esportare. Usa /fit esporta tutto per rivedere anche quelli già esportati.")
        else
            finestraEsportazione(testo)
            ns.stampa(("%d testi pronti da inviare."):format(quanti))
        end
    elseif a == "svuota" then
        local tolti = 0
        for chiave, voce in pairs(db.raccolti) do
            if voce.e then
                db.raccolti[chiave] = nil
                tolti = tolti + 1
            end
        end
        ns.numRaccolti = math.max(0, (ns.numRaccolti or 0) - tolti)
        ns.stampa(("%d testi già esportati cancellati."):format(tolti))
    else
        for _, riga in ipairs(AIUTO) do ns.stampa(riga) end
    end
end

SLASH_FOREVERITALIANO1 = "/fit"
SLASH_FOREVERITALIANO2 = "/italiano"
SlashCmdList = SlashCmdList or {}
SlashCmdList.FOREVERITALIANO = comando
ns.Comando = comando

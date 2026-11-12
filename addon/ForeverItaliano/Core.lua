-- Forever Italiano - nucleo dell'add-on
--
-- Come funziona:
--  * quando si apre una finestra con del testo (missioni, dialoghi, libri) l'add-on
--    legge le scritte in inglese, cerca la traduzione in ns.T e la sostituisce;
--  * tenendo premuto Alt torna il testo inglese;
--  * i testi senza traduzione vengono salvati in ForeverItalianoDB.raccolti, al posto
--    del nome del personaggio viene scritto $N, così non finiscono dati personali;
--  * con /fit esporta i testi raccolti si copiano e si inviano al progetto.
--
-- L'add-on non modifica nessun file del gioco: cambia solo le scritte mostrate a schermo.

local ADDON, ns = ...

ns.T = ns.T or {}            -- [testo inglese normalizzato] = testo italiano
ns.VERSIONE = "0.1.0"

local MAX_RACCOLTI = 5000    -- limite dei testi raccolti, per non gonfiare il file salvato
local MIN_LUNGHEZZA = 4

-- Finestre da tradurre. Se in Forever una finestra ha un altro nome basta aggiungerlo qui.
ns.RADICI = {
    "QuestFrame",
    "GossipFrame",
    "QuestLogFrame",
    "QuestLogDetailFrame",
    "QuestLogPopupDetailFrame",
    "QuestMapFrame",
    "ItemTextFrame",
}

-- Funzioni di Blizzard che ridisegnano il testo delle missioni: dopo ognuna ritraduciamo.
ns.FUNZIONI_DA_AGGANCIARE = {
    "QuestInfo_Display",
    "QuestLog_UpdateQuestDetails",
    "QuestMapFrame_ShowQuestDetails",
    "QuestFrameProgressItems_Update",
    "GossipFrameUpdate",
}

ns.stato = setmetatable({}, { __mode = "k" })  -- [FontString] = { en = ..., it = ... }
ns.altPremuto = false

local db

local IMPOSTAZIONI_PREDEFINITE = {
    attivo = true,     -- mostra le traduzioni
    raccolta = true,   -- salva i testi non tradotti
}

local function stampa(messaggio)
    if DEFAULT_CHAT_FRAME then
        DEFAULT_CHAT_FRAME:AddMessage("|cff3fbf3fForever Italiano|r: " .. messaggio)
    end
end
ns.stampa = stampa

-------------------------------------------------------------------------------
-- Testo: normalizzazione e segnaposto
-------------------------------------------------------------------------------

local function escapaPattern(s)
    return (s:gsub("[%^%$%(%)%%%.%[%]%*%+%-%?]", "%%%0"))
end

-- Nome completo e, se c'è un cognome, anche solo il nome.
local function nomiGiocatore()
    local lista = {}
    local nome = UnitName and UnitName("player")
    if type(nome) == "string" and nome ~= "" then
        lista[#lista + 1] = nome
        local primo = nome:match("^(%S+)%s")
        if primo then lista[#lista + 1] = primo end
    end
    return lista
end

local function sostituisciNome(testo, nome)
    local p = escapaPattern(nome)
    if nome:find("[\128-\255]") then
        -- nomi con lettere accentate: i confini di parola di Lua non li riconoscono
        return (testo:gsub(p, "$N"))
    end
    return (testo:gsub("%f[%w]" .. p .. "%f[%W]", "$N"))
end

-- Rende il testo una chiave stabile: a capo uniformi, niente spazi ai bordi,
-- e il nome del personaggio sostituito da $N.
function ns.Normalizza(testo)
    if type(testo) ~= "string" then return nil end
    local t = testo:gsub("\r\n", "\n"):gsub("\r", "\n")
    t = t:gsub("^%s+", ""):gsub("%s+$", "")
    for _, nome in ipairs(nomiGiocatore()) do
        t = sostituisciNome(t, nome)
    end
    return t
end

-- Rimette nome, classe, razza e forme maschile/femminile nel testo tradotto.
function ns.Formatta(testo)
    local nome = (UnitName and UnitName("player")) or ""
    local classe = (UnitClass and UnitClass("player")) or ""
    local razza = (UnitRace and UnitRace("player")) or ""
    local sesso = (UnitSex and UnitSex("player")) or 2
    testo = testo:gsub("%$[Gg]([^:;]*):([^;]*);", function(maschile, femminile)
        if sesso == 3 then return femminile end
        return maschile
    end)
    testo = testo:gsub("%$[Nn]", function() return nome end)
    testo = testo:gsub("%$C", function() return classe end)
    testo = testo:gsub("%$c", function() return classe:lower() end)
    testo = testo:gsub("%$R", function() return razza end)
    testo = testo:gsub("%$r", function() return razza:lower() end)
    return testo
end

function ns.Cerca(testoOriginale)
    local chiave = ns.Normalizza(testoOriginale)
    if not chiave or chiave == "" then return nil, nil end
    local it = ns.T[chiave]
    if it then return ns.Formatta(it), chiave end
    return nil, chiave
end

-------------------------------------------------------------------------------
-- Raccolta dei testi non tradotti
-------------------------------------------------------------------------------

local function daRaccogliere(chiave)
    if #chiave < MIN_LUNGHEZZA then return false end
    if not chiave:find("%a%a%a") then return false end   -- almeno una parola vera
    return true
end

function ns.Raccogli(chiave, contesto)
    if not db or not db.impostazioni.raccolta then return end
    if not daRaccogliere(chiave) then return end
    local voce = db.raccolti[chiave]
    if voce then
        voce.n = (voce.n or 1) + 1
        return
    end
    if ns.numRaccolti >= MAX_RACCOLTI then return end
    db.raccolti[chiave] = { c = contesto, n = 1 }
    ns.numRaccolti = ns.numRaccolti + 1
end

-------------------------------------------------------------------------------
-- Traduzione delle scritte a schermo
-------------------------------------------------------------------------------

function ns.TraduciScritta(fs, contesto)
    local testo = fs:GetText()
    if type(testo) ~= "string" or testo == "" then return end
    local s = ns.stato[fs]
    if s and (testo == s.it or testo == s.en) then
        -- già gestita: la riallineiamo solo allo stato del tasto Alt
        local voluto = ns.altPremuto and s.en or s.it
        if db.impostazioni.attivo and testo ~= voluto then fs:SetText(voluto) end
        return
    end
    local it, chiave = ns.Cerca(testo)
    if it then
        ns.stato[fs] = { en = testo, it = it }
        if db.impostazioni.attivo and not ns.altPremuto then fs:SetText(it) end
    elseif chiave then
        ns.stato[fs] = nil
        ns.Raccogli(chiave, contesto)
    end
end

local function scansiona(frame, contesto, profondita)
    if profondita > 20 then return end
    if frame.IsForbidden and frame:IsForbidden() then return end
    if not (frame.IsVisible and frame:IsVisible()) then return end
    if frame.GetRegions then
        for _, regione in ipairs({ frame:GetRegions() }) do
            if regione.GetObjectType and regione:GetObjectType() == "FontString"
                and regione:IsVisible() then
                ns.TraduciScritta(regione, contesto)
            end
        end
    end
    if frame.GetChildren then
        for _, figlio in ipairs({ frame:GetChildren() }) do
            scansiona(figlio, contesto, profondita + 1)
        end
    end
    if frame.GetObjectType and frame:GetObjectType() == "ScrollFrame" and frame.UpdateScrollChildRect then
        frame:UpdateScrollChildRect()
    end
end

-- Una lettera scritta da un giocatore non va né tradotta né raccolta.
local function eLetteraDiGiocatore()
    if ItemTextGetCreator then
        local autore = ItemTextGetCreator()
        return autore ~= nil and autore ~= ""
    end
    return false
end

function ns.ScansionaTutto()
    if not db then return end
    for _, nome in ipairs(ns.RADICI) do
        local f = _G[nome]
        if f and f.IsVisible and f:IsVisible() then
            if not (nome == "ItemTextFrame" and eLetteraDiGiocatore()) then
                scansiona(f, nome, 0)
            end
        end
    end
end

-- Raggruppa le richieste: una scansione subito e una poco dopo,
-- per le finestre che Blizzard riempie in più passaggi.
local programmata = false
function ns.Aggiorna()
    if programmata or not C_Timer then return end
    programmata = true
    C_Timer.After(0, function()
        programmata = false
        ns.ScansionaTutto()
    end)
    C_Timer.After(0.2, ns.ScansionaTutto)
end

local function impostaAlt(premuto)
    if ns.altPremuto == premuto then return end
    ns.altPremuto = premuto
    if not db or not db.impostazioni.attivo then return end
    for fs, s in pairs(ns.stato) do
        if fs:IsVisible() then
            local testo = fs:GetText()
            if premuto and testo == s.it then
                fs:SetText(s.en)
            elseif not premuto and testo == s.en then
                fs:SetText(s.it)
            end
        end
    end
end
ns.ImpostaAlt = impostaAlt

-------------------------------------------------------------------------------
-- Agganci alle finestre e alle funzioni di Blizzard
-------------------------------------------------------------------------------

local agganciate = {}

local function aggancia()
    for _, nome in ipairs(ns.FUNZIONI_DA_AGGANCIARE) do
        if not agganciate[nome] and type(_G[nome]) == "function" and hooksecurefunc then
            hooksecurefunc(nome, ns.Aggiorna)
            agganciate[nome] = true
        end
    end
    for _, nome in ipairs(ns.RADICI) do
        local f = _G[nome]
        if not agganciate[nome] and f and f.HookScript then
            f:HookScript("OnShow", ns.Aggiorna)
            agganciate[nome] = true
        end
    end
end

-------------------------------------------------------------------------------
-- Avvio
-------------------------------------------------------------------------------

local function inizializza()
    ForeverItalianoDB = ForeverItalianoDB or {}
    db = ForeverItalianoDB
    db.versione = 1
    db.impostazioni = db.impostazioni or {}
    for k, v in pairs(IMPOSTAZIONI_PREDEFINITE) do
        if db.impostazioni[k] == nil then db.impostazioni[k] = v end
    end
    db.raccolti = db.raccolti or {}

    -- I testi che nel frattempo sono stati tradotti non servono più.
    ns.numRaccolti = 0
    for chiave in pairs(db.raccolti) do
        if ns.T[chiave] then
            db.raccolti[chiave] = nil
        else
            ns.numRaccolti = ns.numRaccolti + 1
        end
    end

    ns.numTraduzioni = 0
    for _ in pairs(ns.T) do ns.numTraduzioni = ns.numTraduzioni + 1 end

    ns.db = db
    aggancia()
end

local eventi = CreateFrame("Frame")
eventi:RegisterEvent("ADDON_LOADED")
eventi:RegisterEvent("PLAYER_LOGIN")
for _, evento in ipairs({
    "QUEST_DETAIL", "QUEST_PROGRESS", "QUEST_COMPLETE", "QUEST_GREETING",
    "GOSSIP_SHOW", "ITEM_TEXT_READY", "QUEST_LOG_UPDATE", "MODIFIER_STATE_CHANGED",
}) do
    eventi:RegisterEvent(evento)
end

eventi:SetScript("OnEvent", function(_, evento, ...)
    if evento == "ADDON_LOADED" then
        local nome = ...
        if nome == ADDON then
            inizializza()
        elseif db then
            aggancia()   -- finestre di Blizzard caricate in ritardo
        end
    elseif evento == "PLAYER_LOGIN" then
        if db then
            stampa(("versione %s, %d traduzioni caricate. Scrivi /fit per i comandi.")
                :format(ns.VERSIONE, ns.numTraduzioni))
        end
    elseif evento == "MODIFIER_STATE_CHANGED" then
        local tasto, giu = ...
        if tasto == "LALT" or tasto == "RALT" then
            impostaAlt(giu == 1)
        end
    elseif db then
        ns.Aggiorna()
    end
end)

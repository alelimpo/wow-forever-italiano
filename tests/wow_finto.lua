-- Un WoW finto, minimo, per provare l'add-on fuori dal gioco.

local timer = {}
C_Timer = { After = function(_, fn) timer[#timer + 1] = fn end }
function EseguiTimer()
    local n = 0
    while #timer > 0 and n < 100 do
        local lista = timer
        timer = {}
        for _, fn in ipairs(lista) do fn() end
        n = n + 1
    end
end

local Oggetto = {}
local meta = {
    __index = function(_, k)
        local v = Oggetto[k]
        if v ~= nil then return v end
        return function() end   -- metodi non simulati: non fanno nulla
    end,
}

local tuttiIFrame = {}

local function nuovo(tipo, nome, genitore)
    local o = setmetatable({ _tipo = tipo, _nome = nome, _regioni = {}, _figli = {},
        _visibile = true, _script = {}, _ganci = {}, _eventi = {}, _testo = nil,
        _impostazioni = 0 }, meta)
    if genitore then o._genitore = genitore end
    if nome then _G[nome] = o end
    return o
end

function Oggetto:GetObjectType() return self._tipo end
function Oggetto:GetName() return self._nome end
function Oggetto:IsVisible()
    if not self._visibile then return false end
    local g = rawget(self, "_genitore"); if g then return g:IsVisible() end
    return true
end
function Oggetto:IsShown() return self._visibile end
function Oggetto:Show() self._visibile = true; for _, g in ipairs(self._ganci.OnShow or {}) do g(self) end end
function Oggetto:Hide() self._visibile = false end
function Oggetto:GetText() return self._testo end
function Oggetto:SetText(t) self._testo = t; self._impostazioni = self._impostazioni + 1 end
function Oggetto:GetRegions() return unpack(self._regioni) end
function Oggetto:GetChildren() return unpack(self._figli) end
function Oggetto:RegisterEvent(e) self._eventi[e] = true end
function Oggetto:UnregisterEvent(e) self._eventi[e] = nil end
function Oggetto:SetScript(nome, fn) self._script[nome] = fn end
function Oggetto:HookScript(nome, fn)
    self._ganci[nome] = self._ganci[nome] or {}
    table.insert(self._ganci[nome], fn)
end
function Oggetto:CreateFontString(nome)
    local fs = nuovo("FontString", nome, self)
    table.insert(self._regioni, fs)
    return fs
end

function CreateFrame(tipo, nome, genitore)
    local f = nuovo(tipo or "Frame", nome, genitore)
    if genitore then table.insert(genitore._figli, f) end
    table.insert(tuttiIFrame, f)
    return f
end

function LanciaEvento(evento, ...)
    for _, f in ipairs(tuttiIFrame) do
        if f._eventi[evento] and f._script.OnEvent then
            f._script.OnEvent(f, evento, ...)
        end
    end
end

function hooksecurefunc(nome, fn)
    local originale = _G[nome]
    _G[nome] = function(...)
        local r = { originale(...) }
        fn(...)
        return unpack(r)
    end
end

GIOCATORE = { nome = "Allemano Moo", classe = "Warrior", razza = "Human", sesso = 2 }
function UnitName() return GIOCATORE.nome end
function UnitClass() return GIOCATORE.classe end
function UnitRace() return GIOCATORE.razza end
function UnitSex() return GIOCATORE.sesso end

MESSAGGI = {}
DEFAULT_CHAT_FRAME = { AddMessage = function(_, m) table.insert(MESSAGGI, m) end }
UIParent = CreateFrame("Frame", "UIParent")
UISpecialFrames = {}
ChatFontNormal = {}
SlashCmdList = {}

function CaricaAddon(cartella, file)
    local ns = {}
    for _, nome in ipairs(file) do
        local fn = assert(loadfile(cartella .. "/" .. nome))
        fn("ForeverItaliano", ns)
    end
    return ns
end

# Forever Italiano - aggiornamento automatico (Windows)
#
# Scarica i testi inviati dai giocatori, li traduce con Ollama sul tuo PC,
# rigenera l'add-on e pubblica tutto su GitHub.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File tools\aggiorna.ps1
#   powershell -ExecutionPolicy Bypass -File tools\aggiorna.ps1 -Rilascia      (pubblica anche una nuova versione)
#   powershell -ExecutionPolicy Bypass -File tools\aggiorna.ps1 -Modello gemma3:12b
#   powershell -ExecutionPolicy Bypass -File tools\aggiorna.ps1 -SavedVariables "C:\...\ForeverItaliano.lua"
#
# Per farlo partire da solo ogni notte, vedi la sezione "Automatico" del README.

param(
    [switch]$Rilascia,
    [string]$Modello = "",
    [string]$SavedVariables = "",
    [int]$Limite = 0
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (Get-Command py -ErrorAction SilentlyContinue) { $python = @("py", "-3") } else { $python = @("python") }
function Esegui-Python([string[]]$argomenti) {
    $tutti = @()
    if ($python.Length -gt 1) { $tutti += $python[1..($python.Length - 1)] }
    $tutti += $argomenti
    & $python[0] @tutti
    if ($LASTEXITCODE -ne 0) { throw "Comando non riuscito: python $($argomenti -join ' ')" }
}

Write-Host "== Scarico le novità da GitHub"
git pull --rebase --autostash
if ($LASTEXITCODE -ne 0) { throw "git pull non riuscito" }

Write-Host "== Importo i testi inviati dai giocatori"
$import = @("tools/importa.py", "--in-arrivo")
if ($SavedVariables) { $import += $SavedVariables }
Esegui-Python $import

Write-Host "== Traduco con Ollama"
$traduci = @("tools/traduci.py")
if ($Modello) { $traduci += @("--modello", $Modello) }
if ($Limite -gt 0) { $traduci += @("--limite", "$Limite") }
Esegui-Python $traduci

Write-Host "== Rigenero l'add-on"
Esegui-Python @("tools/costruisci.py")

git add -A data addon
git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "Nessuna novità da pubblicare."
    exit 0
}

$messaggio = "Traduzioni aggiornate " + (Get-Date -Format "yyyy-MM-dd HH:mm")
if ($Rilascia) {
    $versione = ((Esegui-Python @("tools/versione.py", "--incrementa")) | Select-Object -Last 1).Trim()
    git add -A addon
    $messaggio = "Versione $versione"
}
git commit -m $messaggio
if ($LASTEXITCODE -ne 0) { throw "git commit non riuscito" }

if ($Rilascia) {
    git tag "v$versione"
}
git push
if ($LASTEXITCODE -ne 0) { throw "git push non riuscito" }
if ($Rilascia) {
    git push origin "v$versione"
    Write-Host "Pubblicata la versione ${versione}. GitHub ora crea lo zip da scaricare."
}
Write-Host "Fatto."

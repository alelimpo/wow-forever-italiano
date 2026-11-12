# Forever Italiano

Traduzione amatoriale in italiano di **World of Warcraft: Forever**, fatta dalla comunità con l'aiuto di un modello di intelligenza artificiale che gira sul PC di chi traduce (Ollama), quindi senza costi.

> Progetto amatoriale e non commerciale, non affiliato a Blizzard Entertainment. È un normale add-on: **non modifica nessun file del gioco** (cosa vietata dalle regole di Blizzard), cambia solo le scritte mostrate a schermo.

## Cosa traduce

- Finestre delle missioni: descrizione, obiettivi, avanzamento e ricompense.
- Dialoghi con i personaggi.
- Libri, lettere e targhe che si leggono nel mondo (non le lettere scritte da altri giocatori).
- Tieni premuto **Alt** per vedere il testo originale in inglese.

Per ora restano in inglese tooltip di oggetti e incantesimi, menu e mappa. I nomi propri (luoghi, personaggi, oggetti) restano in inglese apposta, così coincidono con la mappa e il resto del gioco.

All'inizio il dizionario è vuoto: si riempie man mano che i giocatori inviano i testi che incontrano.

## Per i giocatori

### Installazione

1. Scarica lo zip dall'[ultima versione](https://github.com/alelimpo/wow-forever-italiano/releases/latest).
2. Estrai la cartella `ForeverItaliano` dentro `World of Warcraft\_forever_\Interface\AddOns`.
3. Avvia il gioco e controlla che **Forever Italiano** sia attivo nell'elenco degli add-on.

### Comandi

| Comando | Cosa fa |
| --- | --- |
| `/fit` | elenco dei comandi |
| `/fit stato` | quante traduzioni sono caricate e quanti testi hai raccolto |
| `/fit on` / `/fit off` | mostra o nasconde le traduzioni |
| `/fit raccolta on` / `off` | salva o no i testi senza traduzione |
| `/fit esporta` | mostra i testi nuovi da inviare al progetto |
| `/fit esporta tutto` | li mostra tutti, anche quelli già esportati |
| `/fit svuota` | cancella i testi già esportati |

### Aiuta la traduzione

Mentre giochi, l'add-on mette da parte i testi che non sa ancora tradurre. Inviarli è facile:

**Dal gioco**
1. Scrivi `/fit esporta`.
2. Premi **Ctrl+A** e poi **Ctrl+C**.
3. Apri il modulo [Testi da tradurre](https://github.com/alelimpo/wow-forever-italiano/issues/new?template=testi-da-tradurre.yml), incolla e invia.

**Dal PC** (serve Python): esci dal gioco o scrivi `/reload`, poi lancia `python tools/invia_testi.py`. Lo script trova il file da solo, copia il testo negli appunti e apre il modulo.

Il resto è automatico: un'automazione di GitHub importa i testi nuovi, risponde e chiude la segnalazione. Nella versione successiva dell'add-on quei testi saranno tradotti.

**Cosa viene inviato:** solo le scritte delle finestre di missioni, dialoghi e libri. Il nome del tuo personaggio viene sostituito con `$N` prima di essere salvato. Chat, posta e sussurri non vengono mai letti.

Hai trovato una traduzione sbagliata? Usa il modulo [Traduzione sbagliata](https://github.com/alelimpo/wow-forever-italiano/issues/new?template=traduzione-sbagliata.yml).

## Come funziona

Gli add-on di WoW non possono collegarsi a internet, quindi il giro passa da GitHub:

```
Giocatore           GitHub                          PC di chi traduce (Ollama)
─────────           ──────                          ──────────────────────────
/fit esporta  ───►  modulo "Testi da tradurre"
                    automazione: salva i testi
                    nuovi in data/in_arrivo/  ───►  tools/aggiorna.ps1
                                                      importa  → traduci → costruisci
                    nuova versione dell'add-on ◄───  pubblica su GitHub
scarica e gioca ◄──
```

I giocatori inviano solo testi inglesi: le traduzioni le genera sempre il progetto, quindi nessuno può inserire traduzioni scorrette apposta.

## Per chi traduce

### Requisiti

- Python 3.9 o più recente (nessun pacchetto da installare).
- Git.
- [Ollama](https://ollama.com) con un modello, per esempio `ollama pull qwen2.5:7b`. Modelli più grandi traducono meglio ma sono più lenti. Il modello si sceglie in `tools/config.json` oppure con `--modello`.

### Comandi

```
python tools/importa.py "...\WTF\Account\NOME\SavedVariables\ForeverItaliano.lua"
python tools/importa.py --in-arrivo           testi inviati dai giocatori
python tools/traduci.py --prova "Welcome, adventurer!"   prova il modello su una frase
python tools/traduci.py --limite 50           traduce i 50 testi più visti
python tools/traduci.py                       traduce tutto quello che manca
python tools/costruisci.py                    rigenera i file dell'add-on
```

`traduci.py` salva man mano: puoi fermarlo con Ctrl+C e riprendere dopo.

### Tutto in un colpo

```
powershell -ExecutionPolicy Bypass -File tools\aggiorna.ps1
powershell -ExecutionPolicy Bypass -File tools\aggiorna.ps1 -Rilascia
```

Scarica i testi inviati, li traduce con Ollama, rigenera l'add-on e pubblica su GitHub. Con `-Rilascia` aumenta anche la versione e GitHub prepara lo zip da scaricare.

Per farlo partire da solo ogni notte alle 3 (con il PC acceso e Ollama avviato):

```
schtasks /Create /SC DAILY /ST 03:00 /TN "Forever Italiano" /TR "powershell -ExecutionPolicy Bypass -File C:\percorso\wow-forever-italiano\tools\aggiorna.ps1 -Rilascia"
```

### Correggere una traduzione

Le traduzioni stanno in `data/traduzioni.json`. Ogni voce ha uno stato:

| Stato | Significato |
| --- | --- |
| `in_attesa` | testo ricevuto, manca la traduzione |
| `auto` | tradotto da Ollama |
| `da_rivedere` | tradotto, ma conviene un controllo (per esempio forme maschile/femminile) |
| `rivisto` | controllato da una persona: non viene mai ritradotto |
| `errore` | la traduzione automatica non è riuscita (`traduci.py --ritenta-errori`) |

Per correggere, cambia il campo `it` e metti `"stato": "rivisto"`. I codici come `$N` (nome del personaggio) vanno lasciati identici.

### Glossario

`data/glossario.json` contiene le parole da tradurre sempre allo stesso modo (Alliance → Alleanza) e i nomi da lasciare in inglese. Al modello vengono passate solo le voci presenti nel testo da tradurre.

## Struttura

```
addon/ForeverItaliano/   l'add-on (Lua): Core.lua, Esporta.lua, Dati/ generati
data/traduzioni.json     il dizionario inglese → italiano
data/glossario.json      termini fissi
data/in_arrivo/          testi inviati dai giocatori, in attesa di importazione
tools/                   importa, traduci (Ollama), costruisci, invia_testi, aggiorna.ps1
tests/                   prove automatiche (anche dell'add-on, in un WoW simulato)
.github/                 moduli delle segnalazioni e automazioni
```

## Limiti noti

- Questa prima versione è stata provata in un WoW simulato, non ancora nel gioco. Se in Forever qualche finestra ha un nome diverso, va aggiunto all'elenco `ns.RADICI` in `Core.lua`.
- Alcuni testi cambiano in base a classe e razza: il gioco li mostra già risolti, quindi diventano voci separate del dizionario.
- La traduzione automatica è buona ma non perfetta: le correzioni della comunità sono benvenute.

## Licenza

Il codice è distribuito con licenza MIT. I testi originali del gioco appartengono a Blizzard Entertainment; le traduzioni sono un lavoro amatoriale, gratuito e non commerciale.

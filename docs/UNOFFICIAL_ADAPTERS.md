# Unofficial / Best-Effort Adapters

Questo documento elenca gli adapter di scraping **non promossi nel README pubblico** di msrt. Sono mantenuti come parte del codebase e supportati internamente, ma:

- non sono "ufficialmente supportati" lato comunicazione esterna
- possono rompersi senza preavviso quando il sito cambia DOM/struttura
- l'utente li usa **a proprio rischio** e responsabilità (vedi disclaimer del README)

## Stato attuale

MangaFire è implementato come adapter best-effort sperimentale. La pipeline
URL ufficiale resta MangaDex; MangaFire viene mantenuto per il flusso reale
dell'utente. La strategia primaria osserva la normale risposta reader
`/ajax/read/chapter/<id>` e scarica gli URL immagine esposti dal sito; browser
capture resta il fallback automatico quando quella risposta non è disponibile.

## Adapter

### MangaFire (`mangafire.to`)
- **Stato**: implementato in v0.3-dev, E2E reale validato su *Wistoria Wand and Sword* chapter 51 (45 pagine)
- **Motivazione**: l'utente sta leggendo manga su questo sito (es. *Wistoria Wand and Sword* chapter 44/51 in EN)
- **Approccio primario attuale**: Playwright session con user-agent dichiarato (no stealth) apre il reader e intercetta la risposta pubblica `/ajax/read/chapter/<id>` emessa dal sito. Il payload `result.images` diventa una lista ordinata di `DownloadJob`; il downloader condiviso valida magic bytes e rate-limit.
- **Fallback automatico**: se il reader-network fallisce ma il reader mostra le scan, `msrt` cattura la sola scan visibile e salva immagini locali da passare alla pipeline `run-local`
- **Verifica umana**: se il sito mostra login, Turnstile, captcha o blocchi equivalenti, il tool mette in pausa e lascia l'utente completare manualmente nel browser. Dopo la verifica riprende appena rileva una scan valida. Non implementiamo bypass o stealth.
- **Qualità capture**: preferire sempre download raw; usare browser capture solo come fallback. La capture deve escludere navbar/sidebar/sfondi e validare dimensioni minime prima di procedere con OCR.
- **Test E2E concreto**: chapter 51 di Wistoria sulla macchina dell'utente (`msrt run ... --model gpt --format pdf` → 45 pagine, PDF prodotto)
- **Fixture**: solo HTML salvato (non immagini scaricate) in `tests/fixtures/mangafire/chapter-44/`
- **Avvertenze**: il DOM di mangafire.to cambia frequentemente; aspettarsi rotture periodiche. La capture via browser può avere qualità inferiore al raw download se il reader mostra immagini scalate.

### Possibili future aggiunte
*(via sistema plugin in v0.8)*
- Mangakakalot / natomanga / nelomanga
- Asura Scans
- Batoto

Solo se accompagnati da test fixture e documentazione propria.

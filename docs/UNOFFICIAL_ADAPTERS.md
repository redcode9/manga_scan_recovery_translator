# Unofficial / Best-Effort Adapters

Questo documento elenca gli adapter di scraping **non promossi nel README pubblico** di msrt. Sono mantenuti come parte del codebase e supportati internamente, ma:

- non sono "ufficialmente supportati" lato comunicazione esterna
- possono rompersi senza preavviso quando il sito cambia DOM/struttura
- l'utente li usa **a proprio rischio** e responsabilità (vedi disclaimer del README)

## Stato attuale

Nessun adapter URL è ancora implementato nel codice. La pipeline locale
`run-local` è invece validata end-to-end. Il prossimo blocco di lavoro introduce
la pipeline URL, poi MangaFire viene trattato come adapter best-effort con
fallback automatico via browser capture.

## Pianificati

### MangaFire (`mangafire.to`)
- **Stato**: pianificato per v0.3
- **Motivazione**: l'utente sta leggendo manga su questo sito (es. *Wistoria Wand and Sword* chapter-44 in EN)
- **Approccio primario**: Playwright session con user-agent dichiarato (no stealth), parsing DOM `/read/<slug>/<lang>/chapter-N`, estrazione URL immagini, navigazione next-chapter
- **Fallback automatico**: se gli URL raw non sono estraibili/scaricabili ma il reader mostra le scan, `msrt` cattura screenshot/crop della sola scan visibile e salva immagini locali da passare alla pipeline `run-local`
- **Verifica umana**: se il sito mostra login, Turnstile, captcha o blocchi equivalenti, il tool mette in pausa e lascia l'utente completare manualmente nel browser. Dopo la verifica riprende appena rileva una scan valida. Non implementiamo bypass o stealth.
- **Qualità capture**: preferire sempre download raw; usare browser capture solo come fallback. La capture deve escludere navbar/sidebar/sfondi e validare dimensioni minime prima di procedere con OCR.
- **Test E2E concreto**: chapter-44 di Wistoria sulla macchina dell'utente
- **Fixture**: solo HTML salvato (non immagini scaricate) in `tests/fixtures/mangafire/chapter-44/`
- **Avvertenze**: il DOM di mangafire.to cambia frequentemente; aspettarsi rotture periodiche. La capture via browser può avere qualità inferiore al raw download se il reader mostra immagini scalate.

### Possibili future aggiunte
*(via sistema plugin in v0.8)*
- Mangakakalot / natomanga / nelomanga
- Asura Scans
- Batoto

Solo se accompagnati da test fixture e documentazione propria.

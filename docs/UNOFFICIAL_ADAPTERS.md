# Unofficial / Best-Effort Adapters

Questo documento elenca gli adapter di scraping **non promossi nel README pubblico** di msrt. Sono mantenuti come parte del codebase e supportati internamente, ma:

- non sono "ufficialmente supportati" lato comunicazione esterna
- possono rompersi senza preavviso quando il sito cambia DOM/struttura
- l'utente li usa **a proprio rischio** e responsabilità (vedi disclaimer del README)

## Stato attuale

**Nessun adapter ancora implementato.** v0.0 è solo bootstrap.

## Pianificati

### MangaFire (`mangafire.to`)
- **Stato**: pianificato per v0.3
- **Motivazione**: l'utente sta leggendo manga su questo sito (es. *Wistoria Wand and Sword* chapter-44 in EN)
- **Approccio**: Playwright session con user-agent dichiarato (no stealth), parsing DOM `/read/<slug>/<lang>/chapter-N`, estrazione URL immagini, navigazione next-chapter
- **Test E2E concreto**: chapter-44 di Wistoria sulla macchina dell'utente
- **Fixture**: solo HTML salvato (non immagini scaricate) in `tests/fixtures/mangafire/chapter-44/`
- **Avvertenze**: il DOM di mangafire.to cambia frequentemente; aspettarsi rotture periodiche

### Possibili future aggiunte
*(via sistema plugin in v0.8)*
- Mangakakalot / natomanga / nelomanga
- Asura Scans
- Batoto

Solo se accompagnati da test fixture e documentazione propria.

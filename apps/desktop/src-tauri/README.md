# msrt-desktop / Tauri shell

Wrapper desktop nativo per la UI di msrt. La UI gira già come web
app (`uv run msrt ui` la serve insieme alle API a 127.0.0.1:4001).
Questo crate aggiunge:

* finestra nativa macOS/Linux/Windows;
* (futuro step desktop) spawn automatico del backend Python come child
  process, così l'utente non deve toccare il terminale;
* packaging `.dmg` / `.app` / `.deb` / `.exe`.

## Requisiti

```bash
# Installa la toolchain Rust (~1 minuto).
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"

# Tauri CLI (opzionale ma consigliato).
cargo install tauri-cli --version "^2.0"
```

Su macOS serve anche `xcode-select --install` se non già fatto.

## Sviluppo

```bash
# In un terminale: backend FastAPI.
uv run msrt ui --no-build --no-open

# In un altro terminale: Tauri dev (avvia Vite + finestra nativa).
cd apps/desktop
cargo tauri dev
# oppure: npx @tauri-apps/cli dev   (se preferisci npm)
```

## Build di produzione

```bash
cd apps/desktop
cargo tauri build
# Output: src-tauri/target/release/bundle/{dmg,deb,…}
```

## Stato v0.4c

Il crate è scaffold-ato e `tauri.conf.json` punta a `../dist` per
la UI. Il binding ai comandi (es. `backend_info`) è il punto da cui
estenderemo il bridge con il processo Python in uno step desktop
successivo.

Le icone non sono ancora configurate: vanno aggiunte prima della
release ufficiale/packaging `.dmg`.

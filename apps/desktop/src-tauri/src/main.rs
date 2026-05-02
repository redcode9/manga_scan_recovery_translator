// msrt desktop shell — SCAFFOLD ONLY.
//
// Stato attuale (v0.4e): il crate compila e mostra la UI ma NON
// avvia il backend Python. Per usare l'app desktop oggi serve
// avviare a mano `uv run msrt ui --no-build --no-open` in un
// altro terminale; in dev Vite proxa /api → 127.0.0.1:4001.
//
// Cosa manca per dichiararla "production-ready":
//   1. Spawn del backend come sidecar (`tauri::async_runtime::spawn`
//      su `Command::new(python).arg("-m").arg("msrt").arg("ui")…`),
//      con teardown sicuro in chiusura finestra.
//   2. Health-check sull'avvio prima di mostrare la finestra.
//   3. Icone bundle (`icons/*`) e firma codice.
//   4. Verifica della build Tauri in CI (oggi richiede `cargo`
//      che non è installato sulla macchina dev).
//   5. Restringere ulteriormente la CSP in `tauri.conf.json`
//      una volta noto l'intero set di endpoint richiesti.
//
// Finché questi punti non sono chiusi il flusso supportato resta
// la web UI servita da `msrt ui`, non l'app nativa.

#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use serde::Serialize;
use tauri::Manager;

#[derive(Serialize)]
struct BackendInfo {
    base_url: &'static str,
}

#[tauri::command]
fn backend_info() -> BackendInfo {
    BackendInfo {
        base_url: "http://127.0.0.1:4001",
    }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_log())
        .invoke_handler(tauri::generate_handler![backend_info])
        .setup(|app| {
            // Posto in cui in v0.4d sposteremo lo spawn del backend
            // Python (uv run msrt ui --no-build --no-open) come
            // child process del processo Tauri, terminato in cleanup.
            let _ = app;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

fn tauri_plugin_log() -> tauri::plugin::TauriPlugin<tauri::Wry> {
    tauri::plugin::Builder::new("log").build()
}

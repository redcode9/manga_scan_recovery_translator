// msrt desktop shell.
//
// Avvia la UI Vite/React e si occupa di lanciare il backend Python
// FastAPI in background, in modo che l'utente non debba mai aprire
// un terminale. La porta del backend (default 4001) è passata alla
// UI via variabile d'ambiente di runtime.
//
// Strategia:
//   - in dev (`tauri dev`) Vite serve la UI a 127.0.0.1:5173 e
//     proxa /api → 127.0.0.1:4001. L'utente avvia il backend
//     manualmente (`uv run msrt ui --no-build --no-open`) finché
//     non aggiungiamo lo spawn integrato.
//   - in produzione (`tauri build`) la UI è impacchettata nel
//     binario e il backend viene spawnato come sidecar Python.
//
// L'integrazione sidecar è documentata nel README ma non è ancora
// implementata: lo step v0.4d aggiunge `tauri::async_runtime::spawn`
// con `Command::new(python).arg("-m").arg("msrt").arg("ui")…`.

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

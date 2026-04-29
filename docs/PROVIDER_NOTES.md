# Provider Notes — limiti e vincoli per provider LLM

Note tecniche sui provider LLM supportati da msrt tramite LiteLLM proxy.

## Architettura: Chat Completions vs Responses API

`manga-image-translator` (MITR) supporta provider LLM tramite il translator `custom_openai`, che usa l'API **OpenAI Chat Completions** (`/v1/chat/completions`).

LiteLLM proxy espone un endpoint Chat Completions-compatible verso tutti i provider (Anthropic, OpenAI, Google, ecc.). Per la traduzione testuale di msrt questa scelta è adeguata.

**Limiti noti**:
- Per modelli OpenAI **GPT-5.x**, OpenAI raccomanda la nuova [Responses API](https://platform.openai.com/docs/api-reference/responses) per reasoning multi-turn, tool use avanzato e gestione di stati. Tramite `custom_openai` di MITR queste capability avanzate non sono accessibili. Per traduzione testuale **non è un problema**, ma se in futuro vorremo usare reasoning esteso o tool use dovremo bypassare MITR (two-pass via `--load-text`).
- Alcuni parametri provider-specifici (es. `top_k` di Anthropic, `system_instruction` di Gemini, `response_format` strutturato) potrebbero non essere mappati 1:1. LiteLLM gestisce la maggior parte ma vanno verificati caso per caso.

## Versione MITR pin

**Da chiudere in v0.1**: pinnare la versione esatta di MITR usata e verificare i flag reali con:
```
python -m manga_translator --help
python -m manga_translator config-help
```
Documentare flag effettivi e differenze rispetto al piano. La voce di config `gpt-config` e i parametri `--save-text`, `--load-text`, `--translator custom_openai`, `--use-gpu` sono plausibili ma non confermati su versione specifica.

## Glossario con `custom_openai`

Il translator `custom_openai` di MITR **non carica il glossary integrato** nel sistema di prompt. Workaround:

1. **MVP (v0.1)**: glossary embedded nel prompt template di `configs/translator-prompt.yaml`, con limite pratico di ~100 entry.
2. **v0.6**: two-pass — pre-traduciamo via LLM (con glossary completo + contesto pagina), salviamo JSON nel formato MITR, poi MITR runs con `--load-text` per fare solo detection/inpainting/rendering.

## Provider supportati e configurazione

| Alias `--model` | Provider | Default model ID | Vision | Note |
|---|---|---|---|---|
| `sonnet` | Anthropic | claude-sonnet-4-6 | sì | Default. Bilanciato qualità/costo. |
| `opus` | Anthropic | claude-opus-4-7 | sì | Massima qualità Anthropic. Costo ~5×. |
| `gpt` | OpenAI | gpt-5.5 | sì | Latest flagship al 2026-04-29. |
| `gpt-5` | OpenAI | gpt-5 | sì | Alias legacy. |
| `gpt-mini` | OpenAI | gpt-5-mini | sì | Cheap/draft. |
| `gemini-pro` | Google | gemini-2.5-pro | sì | Flagship Google. |
| `gemini-flash` | Google | gemini-2.5-flash | sì | Cheap/veloce. |

Modelli locali (v0.7+, opt-in) configurati a parte via Ollama.

/**
 * Frontend model catalog — single source of truth for the UI.
 *
 * The backend has its own ``MODEL_ALIASES`` map (in ``src/msrt/config.py``)
 * that the LiteLLM proxy reads from ``configs/litellm.yaml``. This file
 * mirrors that catalog with the *display* metadata the API doesn't ship:
 * pricing tier, speed bucket, marketing label, and the help URL where
 * the user can fetch their key.
 *
 * Pricing & latency snapshot (May 2026). Sources:
 *   OpenAI:    https://developers.openai.com/api/docs/pricing
 *   Anthropic: https://docs.anthropic.com/en/docs/about/pricing
 *   Google:    https://ai.google.dev/gemini-api/docs/pricing
 *   Latency:   https://artificialanalysis.ai/leaderboards/models
 *
 * When a vendor ships a new tier, update both this catalog *and* the
 * backend ``MODEL_ALIASES`` entry — the alias keys must match or the
 * fallback chain rejects the value with a 400.
 */

import type { SecretName, SettingsView } from "./api";

export type ProviderId = "anthropic" | "openai" | "google";

/** Latency bucket. Keys are stable; the labels live in the i18n
 * dictionary under ``settings.speed.*`` so they translate at render
 * time. */
export type SpeedTier = "ultra" | "fast" | "standard" | "reasoning";

export interface ModelAlias {
  /** The user-facing alias the backend understands (e.g. ``"gpt-mini"``). */
  value: string;
  /** Short marketing label for the dropdown row. */
  label: string;
  /** Underlying provider model id, shown as a subtitle. */
  resolvedId: string;
  /** Cost per million tokens, formatted as ``"$input / $output"``. */
  price: string;
  /** Latency bucket (translated via i18n at render time). */
  speed: SpeedTier;
  /** Optional one-line note shown when this alias is selected. */
  note?: string;
}

export interface ProviderConfig {
  id: ProviderId;
  label: string;
  keyName: SecretName;
  /** Aliases that belong to this provider — the server validates that
   * the alias matches the provider on save. */
  aliases: ModelAlias[];
  helpUrl: string;
  helpLabel: string;
  hint: string;
  placeholder: string;
}

export const MODEL_PROVIDERS: ProviderConfig[] = [
  {
    id: "anthropic",
    label: "Anthropic",
    keyName: "ANTHROPIC_API_KEY",
    aliases: [
      {
        value: "opus",
        label: "opus — Opus 4.7",
        resolvedId: "claude-opus-4-7",
        price: "$5 / $25",
        speed: "standard",
        note: "Massima qualità. ~78 TPS, TTFT ~0,85 s.",
      },
      {
        value: "sonnet",
        label: "sonnet — Sonnet 4.6",
        resolvedId: "claude-sonnet-4-6",
        price: "$3 / $15",
        speed: "fast",
        note: "Bilanciato: qualità Opus a costo/latenza inferiori.",
      },
      {
        value: "haiku",
        label: "haiku — Haiku 4.5",
        resolvedId: "claude-haiku-4-5",
        price: "$1 / $5",
        speed: "fast",
        note: "Più veloce ed economico della famiglia 4.x.",
      },
    ],
    helpUrl: "https://console.anthropic.com/settings/keys",
    helpLabel: "console.anthropic.com",
    hint: "Modelli Anthropic 4.x.",
    placeholder: "sk-ant-…",
  },
  {
    id: "openai",
    label: "OpenAI",
    keyName: "OPENAI_API_KEY",
    aliases: [
      {
        value: "gpt-pro",
        label: "gpt-pro — GPT-5.5 Pro",
        resolvedId: "gpt-5.5-pro",
        price: "$30 / $180",
        speed: "reasoning",
        note: "Top quality, 12× il costo standard. Per ragionamento esteso.",
      },
      {
        value: "gpt",
        label: "gpt — GPT-5.5",
        resolvedId: "gpt-5.5",
        price: "$2.50 / $15",
        speed: "standard",
        note: "Flagship. Leader Intelligence Index. ~92 TPS, TTFT ~1,1 s.",
      },
      {
        value: "gpt-5",
        label: "gpt-5 — GPT-5 (precedente)",
        resolvedId: "gpt-5",
        price: "$2.50 / $15",
        speed: "standard",
        note: "Generazione precedente, ancora disponibile.",
      },
      {
        value: "gpt-mini",
        label: "gpt-mini — GPT-5 Mini",
        resolvedId: "gpt-5-mini",
        price: "$0.40 / $1.60",
        speed: "fast",
        note: "Mid-tier più conveniente del mercato.",
      },
      {
        value: "gpt-nano",
        label: "gpt-nano — GPT-5.4 Nano",
        resolvedId: "gpt-5.4-nano",
        price: "$0.20 / $1.25",
        speed: "ultra",
        note: "Più economico in assoluto.",
      },
    ],
    helpUrl: "https://platform.openai.com/api-keys",
    helpLabel: "platform.openai.com",
    hint: "Modelli GPT-5.x.",
    placeholder: "sk-…",
  },
  {
    id: "google",
    label: "Google Gemini",
    keyName: "GEMINI_API_KEY",
    aliases: [
      {
        value: "gemini-3-pro",
        label: "gemini-3-pro — Gemini 3.1 Pro Preview",
        resolvedId: "gemini-3.1-pro-preview",
        price: "$2 / $12",
        speed: "standard",
        note: "Flagship Google (preview). $4/$18 oltre i 200K token.",
      },
      {
        value: "gemini-3-flash",
        label: "gemini-3-flash — Gemini 3 Flash Preview",
        resolvedId: "gemini-3-flash-preview",
        price: "$0.50 / $3",
        speed: "fast",
        note: "Preview. Supera 2.5 Pro a 3× la velocità (Artificial Analysis).",
      },
      {
        value: "gemini-pro",
        label: "gemini-pro — Gemini 2.5 Pro",
        resolvedId: "gemini-2.5-pro",
        price: "$1.25 / $10",
        speed: "standard",
        note: "Generazione precedente, stabile.",
      },
      {
        value: "gemini-flash",
        label: "gemini-flash — Gemini 2.5 Flash",
        resolvedId: "gemini-2.5-flash",
        price: "$0.30 / $2.50",
        speed: "fast",
        note: "Veloce ed economico, ottimo per batch.",
      },
      {
        value: "gemini-flash-lite",
        label: "gemini-flash-lite — Gemini 2.5 Flash-Lite",
        resolvedId: "gemini-2.5-flash-lite",
        price: "$0.10 / $0.40",
        speed: "ultra",
        note: "Più economico della famiglia Gemini.",
      },
    ],
    helpUrl: "https://aistudio.google.com/apikey",
    helpLabel: "aistudio.google.com",
    hint: "Modelli Gemini 2.5 / 3.x.",
    placeholder: "AIza…",
  },
];

/** Look up the catalog row for a given alias value. Returns ``null``
 * for unknown / custom aliases (e.g. a user-set ``MSRT_MODEL`` that
 * isn't in our static list). */
export function findAliasInCatalog(
  value: string,
): { provider: ProviderConfig; alias: ModelAlias } | null {
  for (const provider of MODEL_PROVIDERS) {
    const alias = provider.aliases.find((entry) => entry.value === value);
    if (alias) return { provider, alias };
  }
  return null;
}

/** Map a provider id to the user's preferred alias for that provider. */
const PREFERRED_ALIAS_FIELD: Record<ProviderId, keyof SettingsView> = {
  openai: "model_openai",
  anthropic: "model_anthropic",
  google: "model_google",
};

export function preferredModelForProvider(
  settings: SettingsView,
  providerId: ProviderId,
): string {
  return settings[PREFERRED_ALIAS_FIELD[providerId]] as string;
}

/** Whether a given provider's API key is currently configured. */
export function isProviderKeyPresent(
  providerId: ProviderId,
  settings: SettingsView,
): boolean {
  return providerId === "anthropic"
    ? settings.has_anthropic_key
    : providerId === "openai"
      ? settings.has_openai_key
      : settings.has_gemini_key;
}

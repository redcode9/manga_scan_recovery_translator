"""Translation engines and glossary management.

This package wraps two related concerns:

* **Engine selection.** :mod:`msrt.translate.engine` defines the
  abstract ``TranslationEngine`` and the only concrete implementation
  in production, ``SubprocessEngine``, which spawns the external
  ``manga-image-translator`` (MITR) CLI. The HTTP variant is a stub
  reserved for future batch backends.
* **Glossary support.** :mod:`msrt.translate.glossary` and
  :mod:`msrt.translate.glossary_builder` build, cache and inject a
  per-series term glossary into MITR's ``gpt_config`` so the LLM keeps
  character names, place names and honorifics consistent across
  chapters. The builder calls the configured LLM via
  :mod:`msrt.translate.litellm_proxy`.
* **Post-processing.** :mod:`msrt.translate.postprocess` provides the
  bubble-aware renderer used when ``renderer=custom-postprocess``.

The pipeline never imports anything outside these helpers — a new
provider adapter belongs in :mod:`msrt.translate.litellm_proxy` (and
the LiteLLM YAML config), not in pipeline code.
"""

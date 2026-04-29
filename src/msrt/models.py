"""Pydantic models used by the msrt pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Bubble(BaseModel):
    """Text bubble extracted from a manga page.

    MITR output is treated as unstable, so most fields are optional and callers
    should degrade to bbox-only behavior when richer geometry is unavailable.
    """

    model_config = ConfigDict(extra="allow")

    polygon: list[tuple[int, int]] | None = None
    bbox: tuple[int, int, int, int] | None = None
    rotation_deg: float = 0.0
    text_direction: Literal["horizontal", "vertical", "mixed"] = "horizontal"
    confidence: float | None = None
    original_text: str = ""
    translated_text: str | None = None
    font_color_rgb: tuple[int, int, int] | None = None
    bg_color_rgb: tuple[int, int, int] | None = None
    font_size_px: int | None = None
    is_sfx: bool = False
    mask_path: Path | None = None
    inpainted_path: Path | None = None
    source_engine: str = "mitr"

    @model_validator(mode="after")
    def derive_bbox_from_polygon(self) -> Bubble:
        if self.bbox is None and self.polygon:
            xs = [point[0] for point in self.polygon]
            ys = [point[1] for point in self.polygon]
            self.bbox = (min(xs), min(ys), max(xs), max(ys))
        return self


class Page(BaseModel):
    index: int
    source_url: str | None = None
    local_path: Path
    width: int
    height: int
    sha256: str
    translated_path: Path | None = None
    bubbles: list[Bubble] = Field(default_factory=list)


class Chapter(BaseModel):
    series_title: str
    chapter_number: str
    chapter_title: str | None = None
    language_source: str = "en"
    language_target: str = "it"
    source_url: str | None = None
    pages: list[Page] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class TranslationJob(BaseModel):
    engine: Literal["subprocess", "http"] = "subprocess"
    model: str = "gpt"
    provider: Literal["anthropic", "openai", "google", "local"] | None = None
    target_lang: str = "ITA"
    glossary_path: Path | None = None
    auto_glossary: bool = True
    renderer: Literal["mitr-default", "mitr-manga2eng", "custom-postprocess"] = "mitr-manga2eng"
    font_path: Path | None = None
    pre_dict_path: Path | None = None
    gpt_config_path: Path | None = None
    keep_original: bool = False
    use_gpu: bool = True


class ManifestInput(BaseModel):
    type: Literal["local", "url"]
    path: str | None = None
    url: str | None = None
    page_count: int


class ManifestModel(BaseModel):
    alias: str
    resolved_id: str
    provider: str | None


class ManifestEngine(BaseModel):
    type: str
    mitr_version: str | None = None
    binary: str | None = None


class ManifestFetch(BaseModel):
    """URL-pipeline metadata recorded by ``msrt run``.

    Populated only when the run originated from a URL (``msrt run``);
    ``msrt run-local`` leaves ``RunManifest.fetch`` ``None``.
    """

    strategy: str
    source_url: str
    output_dir: str
    page_count: int
    warnings: list[str] = Field(default_factory=list)


class RunManifest(BaseModel):
    msrt_version: str
    command: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    input: ManifestInput
    page_order: list[str]
    page_hashes: dict[str, str]
    model: ManifestModel
    engine: ManifestEngine
    font_path: str | None = None
    output_files: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    fetch: ManifestFetch | None = None

    def finish(self) -> None:
        self.finished_at = datetime.now(UTC)

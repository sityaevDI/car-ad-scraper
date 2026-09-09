"""Maps a Source.code string to its adapter class, so the pipeline/worker isn't hardcoded to one
source. Add a new source here once its adapter exists (see docs/adr/04_SCRAPING.md).

Values are typed `type[Any]` rather than `type[CarSource]`: CarSource is a Protocol, and mypy
treats a dict of concrete adapter classes as invariant against it (each adapter's __init__ has a
different, adapter-specific signature) — `type[Any]` sidesteps that without weakening
`get_source_adapter`'s return type, which is what call sites actually use.
"""

from typing import Any

from app.sources.base import CarSource
from app.sources.polovniautomobili.adapter import PolovniAutomobiliSource

SOURCE_REGISTRY: dict[str, type[Any]] = {
    PolovniAutomobiliSource.source_code: PolovniAutomobiliSource,
}


def get_source_adapter(source_code: str, **kwargs: object) -> CarSource:
    cls = SOURCE_REGISTRY.get(source_code)
    if cls is None:
        raise ValueError(f"Unknown source_code: {source_code!r}")
    return cls(**kwargs)

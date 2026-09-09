import pytest

from app.sources.polovniautomobili.adapter import PolovniAutomobiliSource
from app.sources.registry import get_source_adapter


def test_get_source_adapter_resolves_known_source():
    adapter = get_source_adapter("polovniautomobili", max_pages=3)
    assert isinstance(adapter, PolovniAutomobiliSource)
    assert adapter.max_pages == 3


def test_get_source_adapter_rejects_unknown_source():
    with pytest.raises(ValueError, match="unknown_source"):
        get_source_adapter("unknown_source")

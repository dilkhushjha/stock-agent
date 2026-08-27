from types import SimpleNamespace

from app.data.news_sources import NEWS_SOURCES
from app.intelligence.global_intelligence import detect_global_signals


def make_article(**overrides):
    values = dict(
        id=1, title="", source="Test Source", url="https://example.com/a",
        summary="", content="", published_at=None, is_international=False,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_news_sources_include_international_entries():
    international = [s for s in NEWS_SOURCES if s.get("is_international")]
    domestic = [s for s in NEWS_SOURCES if not s.get("is_international")]
    # Previously every source was India-filtered (gl=IN); this locks in that
    # international coverage actually exists in the source list now.
    assert len(international) >= 5
    assert len(domestic) >= 5
    for source in NEWS_SOURCES:
        assert "is_international" in source


def test_international_sources_are_not_india_locale_filtered():
    for source in NEWS_SOURCES:
        if source.get("is_international"):
            assert "gl=IN" not in source["url"]


def test_international_article_gets_confidence_boost():
    domestic = make_article(
        title="Indian markets react as Fed cuts rates, dovish tone",
        is_international=False,
    )
    international = make_article(
        title="Federal Reserve cuts interest rates in dovish move",
        is_international=True,
    )
    domestic_signal = detect_global_signals([domestic])[0]
    international_signal = detect_global_signals([international])[0]
    assert international_signal["confidence"] > domestic_signal["confidence"]
    assert international_signal["is_international"] is True
    assert domestic_signal["is_international"] is False


def test_detect_global_signals_defaults_to_domestic_when_flag_missing():
    # Objects without an is_international attribute (e.g. older rows before the
    # migration backfilled the column) must not be treated as international.
    article = SimpleNamespace(id=1, title="Fed cuts rates", source="x", url="https://example.com", summary="", content="")
    signal = detect_global_signals([article])[0]
    assert signal["is_international"] is False

from app.scraping.fetch_outcome import FetchBlockedError, FetchOutcome, ParserError
from app.scraping.query_partitioning import partition_query
from app.search.query import SearchQuery


class _StubAdapter:
    """A minimal CarSource stand-in that only carries what partition_query actually reads off an
    adapter — the two capability attributes (checked via getattr, same as pipeline.py's
    search_with_data pattern) plus a caller-supplied fake probe.
    """

    source_code = "stub_source"
    display_name = "Stub Source"
    domain = "stub.example.com"
    country = "RS"

    def __init__(self, max_crawlable_pages, probe_page_count):
        self.max_crawlable_pages = max_crawlable_pages
        self.probe_page_count = probe_page_count


class _NoCapAdapter:
    """Doesn't declare max_crawlable_pages/probe_page_count at all — the getattr(..., None)
    checks in partition_query must treat it as "nothing to split", matching every real adapter
    until a second one hits this same problem.
    """

    source_code = "stub_source"
    display_name = "Stub Source"
    domain = "stub.example.com"
    country = "RS"


def _query_counts_by_price(brackets: dict[tuple[int | None, int | None], int]):
    """Builds a probe_page_count fake driven by a fixed price_min/price_max -> page_count table —
    every test below only varies price, never year, so (price_min, price_max) alone identifies a
    bracket.
    """

    async def probe(query: SearchQuery) -> int:
        key = (query.price_min, query.price_max)
        return brackets[key]

    return probe


async def test_no_op_when_adapter_has_no_declared_cap():
    adapter = _NoCapAdapter()
    query = SearchQuery()

    result = await partition_query(adapter, query, max_pages=3000)

    assert result == [query]


async def test_no_op_when_max_pages_is_already_under_the_safe_threshold():
    probed: list[SearchQuery] = []

    async def probe(query: SearchQuery) -> int:
        probed.append(query)
        return 10_000  # would obviously need splitting if this were ever reached

    adapter = _StubAdapter(max_crawlable_pages=750, probe_page_count=probe)
    query = SearchQuery(make="Skoda")

    result = await partition_query(adapter, query, max_pages=20)

    assert result == [query]
    assert probed == []  # never even worth probing — max_pages alone can't reach the cap


async def test_no_op_when_the_query_already_fits_under_one_crawl():
    adapter = _StubAdapter(max_crawlable_pages=750, probe_page_count=_query_counts_by_price({(None, None): 400}))
    query = SearchQuery()

    result = await partition_query(adapter, query, max_pages=3000)

    assert result == [query]


async def test_splits_by_price_when_the_query_is_too_big():
    # Full range (0..5_000_000) reports too many pages; first split lands at 2_500_000, and both
    # halves are small enough to stop there.
    adapter = _StubAdapter(
        max_crawlable_pages=750,
        probe_page_count=_query_counts_by_price(
            {
                (None, None): 2000,
                (0, 2_500_000): 400,
                (2_500_001, 5_000_000): 400,
            }
        ),
    )
    query = SearchQuery()

    result = await partition_query(adapter, query, max_pages=3000)

    assert {(q.price_min, q.price_max) for q in result} == {(0, 2_500_000), (2_500_001, 5_000_000)}


async def test_splits_recursively_until_every_bracket_fits():
    counts = {
        (None, None): 2000,
        (0, 2_500_000): 1200,  # still too big, needs another split
        (2_500_001, 5_000_000): 300,
        (0, 1_250_000): 400,
        (1_250_001, 2_500_000): 400,
    }
    adapter = _StubAdapter(max_crawlable_pages=750, probe_page_count=_query_counts_by_price(counts))
    query = SearchQuery()

    result = await partition_query(adapter, query, max_pages=3000)

    ranges = {(q.price_min, q.price_max) for q in result}
    assert ranges == {(0, 1_250_000), (1_250_001, 2_500_000), (2_500_001, 5_000_000)}
    # The union of the accepted brackets covers the original range with no gap or overlap.
    covered = sorted(ranges)
    assert covered[0][0] == 0
    assert covered[-1][1] == 5_000_000
    for (_, hi), (lo, _) in zip(covered, covered[1:], strict=False):
        assert lo == hi + 1


async def test_falls_back_to_year_once_price_is_pinned_to_a_single_value():
    async def probe(query: SearchQuery) -> int:
        if query.price_min == query.price_max:
            # A single exact price is still overcrowded — must fall back to splitting by year.
            if query.year_min is None and query.year_max is None:
                return 2000
            return 300
        return 2000

    adapter = _StubAdapter(max_crawlable_pages=750, probe_page_count=probe)
    query = SearchQuery(price_min=999, price_max=999)

    result = await partition_query(adapter, query, max_pages=3000)

    assert len(result) == 2
    assert all(q.price_min == 999 and q.price_max == 999 for q in result)
    assert {(q.year_min, q.year_max) for q in result} != {(None, None)}


async def test_gives_up_and_accepts_an_oversized_leaf_once_both_axes_are_pinned():
    async def probe(query: SearchQuery) -> int:
        return 2000  # never satisfied, no matter how narrow the bracket gets

    adapter = _StubAdapter(max_crawlable_pages=750, probe_page_count=probe)
    query = SearchQuery(price_min=999, price_max=999, year_min=2020, year_max=2020)

    result = await partition_query(adapter, query, max_pages=3000)

    # Both axes are already single values — nothing left to split, so the oversized bracket is
    # returned as-is rather than looping forever.
    assert result == [query]


async def test_accepts_a_bracket_unsplit_when_probing_it_raises():
    async def probe(query: SearchQuery) -> int:
        if query.price_min is None and query.price_max is None:
            raise ParserError("site returned an unparseable page")
        raise AssertionError("should not be called — the top-level probe already failed")

    adapter = _StubAdapter(max_crawlable_pages=750, probe_page_count=probe)
    query = SearchQuery()

    result = await partition_query(adapter, query, max_pages=3000)

    # The real crawl will hit the same failure on its own first page and handle it there (retry/
    # skip/blocked) — partitioning just leaves the query untouched rather than compounding it.
    assert result == [query]


async def test_accepts_a_bracket_unsplit_when_probing_it_is_blocked():
    async def probe(query: SearchQuery) -> int:
        raise FetchBlockedError(FetchOutcome.FORBIDDEN)

    adapter = _StubAdapter(max_crawlable_pages=750, probe_page_count=probe)
    query = SearchQuery()

    result = await partition_query(adapter, query, max_pages=3000)

    assert result == [query]

"""Splits a SearchQuery into narrower sub-queries so a full crawl stays within a source's
crawlable page depth instead of silently truncating past it (see
PolovniAutomobiliSource.max_crawlable_pages for the concrete cap this was written against).

Only price and production year are used as split axes: both are continuous, already supported as
SearchQuery filters on every source, and fine-grained enough that a correct split always exists
somewhere in range — unlike e.g. body_type, which has a fixed, small vocabulary.

A source that hasn't hit this problem (doesn't declare `max_crawlable_pages`/`probe_page_count`)
is untouched: partition_query is a no-op for it, returning `[query]` unchanged.
"""

import logging

from app.scraping.fetch_outcome import FetchBlockedError, ParserError
from app.search.query import SearchQuery
from app.sources.base import CarSource

logger = logging.getLogger(__name__)

# Stay clear of the exact cap: a bracket's result count can drift between the probe here and the
# real crawl (new listings posted, others removed), so a bracket sized right at the cap could tip
# over it by the time it's actually crawled.
_SAFETY_MARGIN = 0.9

# Generous bounds to start bisecting from when a query leaves a filter unset. Not tight to the
# site's actual data on purpose — a binary split converges in ~log2(range) probes regardless, so
# erring wide costs a handful of extra requests, while erring narrow would silently drop listings
# outside the assumed bound.
_PRICE_FLOOR, _PRICE_CEILING = 0, 5_000_000
_YEAR_FLOOR, _YEAR_CEILING = 1900, 2100
_SPLIT_AXES = (
    ("price_min", "price_max", _PRICE_FLOOR, _PRICE_CEILING),
    ("year_min", "year_max", _YEAR_FLOOR, _YEAR_CEILING),
)

# Backstop against runaway splitting (e.g. a broken probe that always reports "too big" no matter
# how narrow the bracket) — never expected to bite in practice: a real listing distribution needs
# only a handful of splits before every bracket falls under the threshold.
_MAX_PROBES = 128


def _split_in_half(query: SearchQuery) -> tuple[SearchQuery, SearchQuery] | None:
    """Halves `query` along the first splittable axis (price, then year). Returns None once both
    axes are already pinned to a single value each — nothing left to split.
    """
    for lo_field, hi_field, floor, ceiling in _SPLIT_AXES:
        lo = getattr(query, lo_field)
        lo = floor if lo is None else lo
        hi = getattr(query, hi_field)
        hi = ceiling if hi is None else hi
        if hi <= lo:
            continue
        mid = (lo + hi) // 2
        left = query.model_copy(update={lo_field: lo, hi_field: mid})
        right = query.model_copy(update={lo_field: mid + 1, hi_field: hi})
        return left, right
    return None


async def partition_query(adapter: CarSource, query: SearchQuery, max_pages: int) -> list[SearchQuery]:
    """Returns sub-queries whose union covers exactly the listings `query` would, each shallow
    enough to crawl in full. A no-op ([query]) when the adapter has no known depth cap, or when
    `max_pages` (the crawl's own configured ceiling) is already at or below the safe threshold —
    the cap can only bite when the crawl would actually try to page past it.
    """
    site_cap = getattr(adapter, "max_crawlable_pages", None)
    probe = getattr(adapter, "probe_page_count", None)
    if site_cap is None or probe is None:
        return [query]

    threshold = int(site_cap * _SAFETY_MARGIN)
    if max_pages <= threshold:
        return [query]

    accepted: list[SearchQuery] = []
    pending = [query]
    probes_done = 0
    while pending:
        if probes_done >= _MAX_PROBES:
            logger.warning(
                "query_partitioning: hit the %d-probe budget with %d bracket(s) left unexamined "
                "for %r — crawling them as-is",
                _MAX_PROBES,
                len(pending),
                query,
            )
            accepted.extend(pending)
            break

        candidate = pending.pop()
        try:
            page_count = await probe(candidate)
        except (FetchBlockedError, ParserError) as exc:
            # The real crawl of this bracket will hit the same issue on its own first page and
            # get handled there (skip/retry/blocked) exactly as if we'd never tried to split it.
            logger.warning("query_partitioning: couldn't probe %r (%s) — crawling it as-is", candidate, exc)
            accepted.append(candidate)
            continue
        probes_done += 1

        if page_count <= threshold:
            accepted.append(candidate)
            continue

        split = _split_in_half(candidate)
        if split is None:
            logger.warning(
                "query_partitioning: %r still reports %d pages after exhausting price/year splits "
                "— crawling it as one oversized bracket",
                candidate,
                page_count,
            )
            accepted.append(candidate)
            continue
        pending.extend(split)

    return accepted

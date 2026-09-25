"""Market price calculation (#16/#18/#19, docs/adr/06_SEARCH_MARKET.md).

A segment's market price is never computed on the read path — see service.py. A scrape marks the
segment(s) it touched dirty (app/scraping/pipeline.py), and a periodic arq job
(app/scraping/scheduler.py::recompute_dirty_market_segments) recomputes and stores a new
app/models/market.py::MarketPriceSnapshot for each. Reads (the /listings/{id}/market-comparison
endpoint, search results) are then a cheap lookup of the latest snapshot for a listing's segment.
"""

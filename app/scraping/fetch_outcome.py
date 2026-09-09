"""Classifies a fetch (or parse) attempt's result so app/scraping/fetch_strategy.py and per-job
stats have something concrete to react to.
"""

import enum

import requests

# Title/body substrings that show up on Cloudflare-style interstitials even when the status code
# alone (200 or 403) doesn't distinguish a real page from a block.
_CHALLENGE_MARKERS = ("just a moment", "attention required", "checking your browser")
_CAPTCHA_MARKERS = ("captcha", "verify you are human")


class FetchOutcome(str, enum.Enum):
    SUCCESS = "success"
    RATE_LIMITED = "rate_limited"
    FORBIDDEN = "forbidden"
    CHALLENGE = "challenge"
    CAPTCHA = "captcha"
    TIMEOUT = "timeout"
    SERVER_ERROR = "server_error"
    # Not in docs/adr/05_ANTI_BOT_PROXY.md's list, added for requests.ConnectionError/DNS
    # failures, which are neither a timeout nor a 5xx from the server.
    NETWORK_ERROR = "network_error"
    # Not a fetch failure at all — the page was retrieved fine but couldn't be parsed (unexpected
    # markup/JSON shape). Classified anyway so it shows up in per-job stats instead of crashing
    # the job unclassified.
    PARSER_ERROR = "parser_error"


BLOCK_LIKE = frozenset(
    {FetchOutcome.RATE_LIMITED, FetchOutcome.FORBIDDEN, FetchOutcome.CHALLENGE, FetchOutcome.CAPTCHA}
)


class FetchBlockedError(Exception):
    """Raised when both the direct fetch and (if attempted) the proxy fetch came back block-like."""

    def __init__(self, outcome: FetchOutcome):
        self.outcome = outcome
        super().__init__(f"Fetch blocked: {outcome.value}")


class ParserError(Exception):
    """Raised when a fetched page fails to parse. Mirrors FetchBlockedError so
    app/scraping/pipeline.py can treat a malformed page the same way as a blocked one: stop this
    run early, keep whatever was already upserted, and surface FetchOutcome.PARSER_ERROR in the
    job's outcome stats rather than letting the job fail unclassified.
    """

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(f"Parser error: {detail}")


def _body_outcome(text: str) -> FetchOutcome | None:
    lowered = text[:4096].lower()
    if any(marker in lowered for marker in _CAPTCHA_MARKERS):
        return FetchOutcome.CAPTCHA
    if any(marker in lowered for marker in _CHALLENGE_MARKERS):
        return FetchOutcome.CHALLENGE
    return None


def classify_response(response: requests.Response) -> FetchOutcome:
    status = response.status_code
    if status == 429:
        return FetchOutcome.RATE_LIMITED
    if status >= 500:
        return FetchOutcome.SERVER_ERROR
    if status == 403:
        return _body_outcome(response.text) or FetchOutcome.FORBIDDEN
    if status < 400:
        return _body_outcome(response.text) or FetchOutcome.SUCCESS
    return FetchOutcome.FORBIDDEN


def classify_exception(exc: Exception) -> FetchOutcome:
    if isinstance(exc, requests.Timeout):
        return FetchOutcome.TIMEOUT
    return FetchOutcome.NETWORK_ERROR


class OutcomeCounter:
    """Accumulates per-outcome counts for one scrape run — persisted into ScrapeJob.stats."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def record(self, outcome: FetchOutcome) -> None:
        self._counts[outcome.value] = self._counts.get(outcome.value, 0) + 1

    def as_dict(self) -> dict[str, int]:
        return dict(self._counts)

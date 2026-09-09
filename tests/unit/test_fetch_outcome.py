import requests

from app.scraping.fetch_outcome import FetchOutcome, OutcomeCounter, classify_exception, classify_response


def _response(status_code: int, text: str = "") -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response._content = text.encode("utf-8")
    return response


def test_classify_response_success():
    assert classify_response(_response(200, "<html>ok</html>")) == FetchOutcome.SUCCESS


def test_classify_response_rate_limited():
    assert classify_response(_response(429)) == FetchOutcome.RATE_LIMITED


def test_classify_response_server_error():
    assert classify_response(_response(503)) == FetchOutcome.SERVER_ERROR


def test_classify_response_forbidden():
    assert classify_response(_response(403, "<html>Forbidden</html>")) == FetchOutcome.FORBIDDEN


def test_classify_response_challenge_page_disguised_as_200():
    assert classify_response(_response(200, "<title>Just a moment...</title>")) == FetchOutcome.CHALLENGE


def test_classify_response_captcha_page_disguised_as_403():
    assert classify_response(_response(403, "Please complete the captcha")) == FetchOutcome.CAPTCHA


def test_classify_exception_timeout():
    assert classify_exception(requests.Timeout()) == FetchOutcome.TIMEOUT


def test_classify_exception_connection_error():
    assert classify_exception(requests.ConnectionError()) == FetchOutcome.NETWORK_ERROR


def test_outcome_counter_accumulates():
    counter = OutcomeCounter()
    counter.record(FetchOutcome.SUCCESS)
    counter.record(FetchOutcome.SUCCESS)
    counter.record(FetchOutcome.RATE_LIMITED)

    assert counter.as_dict() == {"success": 2, "rate_limited": 1}


def test_outcome_counter_accumulates_parser_error():
    counter = OutcomeCounter()
    counter.record(FetchOutcome.PARSER_ERROR)

    assert counter.as_dict() == {"parser_error": 1}

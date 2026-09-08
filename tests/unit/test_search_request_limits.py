import pytest
from pydantic import ValidationError

from app.search.query import SearchRequest


@pytest.mark.parametrize("page_size", [0, 101])
def test_page_size_out_of_range_rejected(page_size):
    with pytest.raises(ValidationError):
        SearchRequest(page_size=page_size)


def test_page_below_one_rejected():
    with pytest.raises(ValidationError):
        SearchRequest(page=0)


def test_negative_min_group_count_rejected():
    with pytest.raises(ValidationError):
        SearchRequest(min_group_count=-1)


def test_page_size_within_range_accepted():
    assert SearchRequest(page_size=100).page_size == 100

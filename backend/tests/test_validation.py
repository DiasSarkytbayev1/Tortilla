"""Pure-function tests for app/validation.py — no DB needed."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException

from app.validation import parse_categories, parse_date_range, parse_restaurant_ids


class TestParseDateRange:
    def test_happy_path(self) -> None:
        f, t = parse_date_range("2026-01-01", "2026-01-31")
        assert f == date(2026, 1, 1)
        assert t == date(2026, 1, 31)

    def test_from_after_to(self) -> None:
        with pytest.raises(HTTPException) as e:
            parse_date_range("2026-02-01", "2026-01-01")
        assert e.value.status_code == 400
        assert "must be <=" in e.value.detail

    def test_range_too_wide(self) -> None:
        with pytest.raises(HTTPException) as e:
            parse_date_range("2024-01-01", "2026-12-31")
        assert e.value.status_code == 400
        assert "too wide" in e.value.detail

    def test_malformed_from(self) -> None:
        with pytest.raises(HTTPException) as e:
            parse_date_range("not-a-date", "2026-01-01")
        assert e.value.status_code == 400
        assert "from" in e.value.detail

    def test_malformed_to(self) -> None:
        with pytest.raises(HTTPException) as e:
            parse_date_range("2026-01-01", "garbage")
        assert e.value.status_code == 400
        assert "to" in e.value.detail


class TestParseRestaurantIds:
    def test_happy_path(self) -> None:
        assert parse_restaurant_ids("1,2,5") == [1, 2, 5]

    def test_none_means_all(self) -> None:
        assert parse_restaurant_ids(None) is None

    def test_empty_rejected(self) -> None:
        with pytest.raises(HTTPException) as e:
            parse_restaurant_ids("")
        assert e.value.status_code == 400

    def test_non_int_rejected(self) -> None:
        with pytest.raises(HTTPException) as e:
            parse_restaurant_ids("1,abc,2")
        assert e.value.status_code == 400


class TestParseCategories:
    def test_happy_path(self) -> None:
        assert parse_categories("tortilla,drinks") == ["tortilla", "drinks"]

    def test_none_means_all(self) -> None:
        assert parse_categories(None) is None

    def test_empty_rejected(self) -> None:
        with pytest.raises(HTTPException) as e:
            parse_categories("")
        assert e.value.status_code == 400

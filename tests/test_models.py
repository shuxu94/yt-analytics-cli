from datetime import date

import pytest

from ytanalytics.models import DateRange, ResultTable


def test_date_range_is_last_complete_n_days() -> None:
    result = DateRange.from_period("28d", today=date(2026, 7, 16))
    assert result.start == date(2026, 6, 18)
    assert result.end == date(2026, 7, 15)


def test_date_range_rejects_invalid_period() -> None:
    with pytest.raises(ValueError, match="positive number"):
        DateRange.from_period("month", today=date(2026, 7, 16))


def test_result_table_maps_headers_to_values() -> None:
    table = ResultTable.from_api(
        {
            "columnHeaders": [{"name": "video"}, {"name": "views"}],
            "rows": [["abc", 42]],
        }
    )
    assert table.rows == ({"video": "abc", "views": 42},)


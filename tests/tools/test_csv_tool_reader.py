from io import BytesIO

from asimplex.tools.csv_tool import csv_reader_format


def test_csv_reader_format_loops_columns_and_finds_valid_series() -> None:
    rows = ["idx;load"] + [f"{i};{10 + (i % 5)}" for i in range(8760)]
    csv_content = "\n".join(rows).encode("utf-8")
    csv_bytes = BytesIO(csv_content)

    result = csv_reader_format(csv_bytes=csv_bytes)

    assert len(result["time_series_list"]) == 8760
    assert result["description"]["selected_parameters"]["col_number"] == 1

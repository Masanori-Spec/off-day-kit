"""Independent literal/date oracle. Does not import the producer or UI harness."""
from __future__ import annotations
from collections import Counter
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ORIGINAL = [("0", "2027-01-08", "2027-01-11"), ("1", "2027-02-01", "2027-02-02")]
ADDITIONS = [("0", "2027-02-05", "2027-02-06"), ("0", "2027-02-19", "2027-02-20"),
             ("1", "2027-01-08", "2027-01-09"), ("1", "2027-02-05", "2027-02-06"),
             ("1", "2027-02-19", "2027-02-20")]
CANDIDATES = ["2027-01-08", "2027-01-22", "2027-02-05", "2027-02-19"]
RECIPE = {"anchor": "2027-01-04", "start": "2027-01-04", "end": "2027-02-28",
          "every_weeks": 2, "weekdays": ["friday"], "exclusions": ["2027-01-22"]}
RESOURCES = [("0", "RESOURCEA"), ("1", "RESOURCEB"), ("2", "RESOURCEC")]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def intervals(root: ET.Element) -> list[tuple[str, str, str]]:
    result = []
    for element in root.findall("vacations/vacation"):
        assert set(element.attrib) == {"resourceid", "start", "end"}
        start, end = date.fromisoformat(element.attrib["start"]), date.fromisoformat(element.attrib["end"])
        assert start < end
        result.append((element.attrib["resourceid"], start.isoformat(), end.isoformat()))
    return result


def coverage(values: list[tuple[str, str, str]]) -> dict[str, list[str]]:
    result = {key: set() for key, _ in RESOURCES}
    for resource, begin, finish in values:
        current, stop = date.fromisoformat(begin), date.fromisoformat(finish)
        assert resource in result
        while current < stop:
            result[resource].add(current.isoformat())
            current += timedelta(days=1)
    return {key: sorted(value) for key, value in result.items()}


def canonical(element: ET.Element):
    def significant(value: str | None) -> str:
        return value if value and not value.isspace() else ""
    return (element.tag, tuple(sorted(element.attrib.items())), significant(element.text),
            tuple((canonical(child), significant(child.tail)) for child in element))


def vacation_span(data: bytes) -> tuple[int, int, bytes]:
    # The real, separately GUI-authored fixture uses this one unambiguous section.
    starts = list(re.finditer(rb"<vacations>", data)); stops = list(re.finditer(rb"</vacations>", data))
    assert len(starts) == len(stops) == 1
    begin, end = starts[0].start(), stops[0].end()
    assert begin < end
    return begin, end, data[begin:end]


def independently_expected_dates() -> list[str]:
    # Walk selected Fridays by advancing fourteen days from the first literal
    # Friday. The producer's per-day week-index algorithm is not used here.
    cursor, stop = date(2027, 1, 8), date(2027, 2, 28)
    result = []
    while cursor <= stop:
        assert cursor.weekday() == 4
        result.append(cursor.isoformat())
        cursor += timedelta(days=14)
    assert result == CANDIDATES
    return result


def verify_raw(source: bytes, output: bytes, receipt: dict | None = None) -> dict:
    original, generated = ET.fromstring(source), ET.fromstring(output)
    assert original.tag == generated.tag == "project"
    assert original.attrib["version"] == generated.attrib["version"] == "3.4.3396"
    assert intervals(original) == ORIGINAL, "GUI baseline differs from the literal fixture"
    actual = intervals(generated)
    assert actual == ORIGINAL + ADDITIONS, "Expected exactly five appended intervals and original records first"
    assert coverage(actual) == {
        "0": ["2027-01-08", "2027-01-09", "2027-01-10", "2027-02-05", "2027-02-19"],
        "1": ["2027-01-08", "2027-02-01", "2027-02-05", "2027-02-19"], "2": []}
    a, b, source_section = vacation_span(source)
    c, d, output_section = vacation_span(output)
    assert source[:a] == output[:c] and source[b:] == output[d:], "Bytes outside vacations changed"
    old_records = re.findall(rb"<vacation\s[^>]+/>", source_section)
    assert len(old_records) == 2
    assert re.findall(rb"<vacation\s[^>]+/>", output_section)[:2] == old_records, "Existing record bytes changed"
    assert original.attrib == generated.attrib
    for element in original:
        if element.tag != "vacations":
            peers = generated.findall(element.tag)
            siblings = original.findall(element.tag)
            assert [canonical(x) for x in siblings] == [canonical(x) for x in peers], element.tag
    assert [(r.attrib["id"], r.attrib["name"]) for r in generated.findall("resources/resource")] == RESOURCES
    independently_expected_dates()
    if receipt is not None:
        assert receipt["source_sha256"] == sha(source) and receipt["output_sha256"] == sha(output)
        assert receipt["recipe"] == RECIPE and receipt["selected_resource_ids"] == ["0", "1"]
        assert receipt["existing_interval_count"] == 2 and receipt["addition_count"] == 5
        assert receipt["output_interval_count"] == 7 and receipt["no_op"] is False
        assert receipt["candidate_dates"] == [{"date": value, "excluded": value == "2027-01-22"} for value in CANDIDATES]
        assert receipt["additions"] == [{"resource_id": resource, "start": start, "end_exclusive": end}
                                        for resource, start, end in ADDITIONS]
        expected_rows = []
        for resource in ["0", "1"]:
            for value in CANDIDATES:
                covered = resource == "0" and value == "2027-01-08"
                excluded = value == "2027-01-22"
                expected_rows.append({"resource_id": resource, "date": value, "excluded": excluded,
                    "covered": covered, "covering_interval_count": 1 if covered else 0,
                    "covering_interval_example": {"resource_id": "0", "start": "2027-01-08", "end_exclusive": "2027-01-11"} if covered else None,
                    "status": "excluded" if excluded else "covered" if covered else "add"})
        assert receipt["candidates_by_resource"] == expected_rows
    return {"status": "pass", "exact_additions": 5, "existing_record_bytes_preserved": True,
            "outside_section_bytes_preserved": True, "all_candidate_coverage_exclusion_values": True,
            "source_sha256": sha(source), "output_sha256": sha(output)}


def verify_native(source: bytes, output: bytes) -> dict:
    original, native = ET.fromstring(source), ET.fromstring(output)
    assert native.tag == "project" and native.attrib["version"] == "3.4.3396"
    assert Counter(intervals(native)) == Counter(ORIGINAL + ADDITIONS)
    assert [(r.attrib["id"], r.attrib["name"]) for r in native.findall("resources/resource")] == RESOURCES
    # Native saving may change root/view navigation state. Every other subtree,
    # including complete task/resource fields, must match the original fixture.
    for tag in {child.tag for child in original} - {"vacations", "view"}:
        assert [canonical(x) for x in original.findall(tag)] == [canonical(x) for x in native.findall(tag)], tag
    assert set(child.tag for child in original) == set(child.tag for child in native)
    assert {key: value for key, value in original.attrib.items() if key not in {"view-date", "view-index"}} == {
        key: value for key, value in native.attrib.items() if key not in {"view-date", "view-index"}}
    return {"status": "pass", "exact_native_intervals": 7, "task_resource_calendar_fields_preserved": True,
            "coverage": coverage(intervals(native)), "sha256": sha(output)}


def main(directory: Path) -> None:
    source = (directory / "gui-authored.gan").read_bytes()
    result = {"raw": verify_raw(source, (directory / "generated.gan").read_bytes(),
                                json.loads((directory / "generated-receipt.json").read_text()))}
    for name in ["generated-saved.gan", "generated-reopened-saved.gan"]:
        result[name] = verify_native(source, (directory / name).read_bytes())
    first, second = (ET.fromstring((directory / name).read_bytes()) for name in ["generated-saved.gan", "generated-reopened-saved.gan"])
    assert Counter(intervals(first)) == Counter(intervals(second))
    result["status"] = "pass"
    (directory / "independent-date-oracle.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]))

"""Bounded, byte-preserving days-off preparation for GanttProject 3.4.3396.

This module does not execute project expressions, resolve links, or schedule tasks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
import hashlib
import json
import re
from typing import Any, Iterable
from xml.parsers import expat


MAX_INPUT_BYTES = 10 * 1024 * 1024
MAX_DEPTH = 32
MAX_ELEMENTS = 50_000
MAX_ATTRIBUTES = 200_000
MAX_ATTRIBUTES_PER_ELEMENT = 32
MAX_ATTRIBUTE_BYTES = 16_384
MAX_TOTAL_ATTRIBUTE_BYTES = 4 * 1024 * 1024
MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_NODE_TEXT_BYTES = 256 * 1024
MAX_INTERVALS = 10_000
MAX_SELECTED_RESOURCES = 100
MAX_WINDOW_DAYS = 366
MAX_RECIPE_BYTES = 65_536
MIN_PLANNING_DATE = date(1900, 1, 1)
MAX_PLANNING_DATE = date(2199, 12, 31)
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_ID = re.compile(r"(?:0|[1-9][0-9]{0,9})\Z")


class OffDayKitError(ValueError):
    """Input is outside the documented profile or an operation is unsafe."""


def _planning_date(value: date, label: str) -> date:
    if not MIN_PLANNING_DATE <= value <= MAX_PLANNING_DATE:
        raise OffDayKitError(f"{label} must be in the supported planning range 1900–2199")
    return value


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _date(value: Any, label: str) -> date:
    if not isinstance(value, str) or not _ISO_DATE.fullmatch(value):
        raise OffDayKitError(f"{label} must be an ISO date YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise OffDayKitError(f"{label} is not a valid date: {value}") from exc
    return _planning_date(parsed, label)


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value) or int(value) > 2_147_483_647:
        raise OffDayKitError(f"{label} must be a canonical nonnegative 32-bit integer string")
    return value


def _required(attrs: dict[str, str], names: str, tag: str) -> None:
    missing = set(names.split()) - attrs.keys()
    if missing:
        raise OffDayKitError(f"<{tag}> is missing attributes: {', '.join(sorted(missing))}")


# An independently written allowlist of the pinned file format's names, not a
# copy of a vendor parser. Unknown elements/attributes fail closed.
_ATTRS = {
    "project": "name company webLink view-date view-index gantt-divider-location resource-divider-location version locale",
    "description": "", "view": "zooming-state id", "field": "id name width order",
    "option": "id value", "timeline": "", "filters": "",
    "filter": "title description is-built-in is-enabled", "simple-select": "select where",
    "calendars": "base-id", "day-types": "", "day-type": "id",
    "default-week": "id name sun mon tue wed thu fri sat", "only-show-weekends": "value",
    "overriden-day-types": "", "days": "", "date": "year month date type color",
    "tasks": "empty-milestones", "taskproperties": "",
    "taskproperty": "id name type valuetype defaultvalue",
    "task": "id uid name color shape meeting project start duration complete thirdDate thirdDate-constraint priority webLink expand cost-manual-value cost-calculated fixed-start",
    "notes": "", "depend": "id type difference hardness",
    "customproperty": "taskproperty-id value", "resources": "",
    "custom-property-definition": "id name type default-value MSPROJECT_TYPE",
    "resource": "id name function contacts phone", "rate": "name value",
    "custom-property": "definition-id value", "allocations": "",
    "allocation": "task-id resource-id function responsible load", "vacations": "",
    "vacation": "start end resourceid", "previous": "", "previous-tasks": "name",
    "previous-task": "id start duration meeting super", "roles": "roleset-name",
    "role": "id name",
}
_ATTRS = {key: frozenset(value.split()) for key, value in _ATTRS.items()}
_CHILDREN = {
    "project": "description view calendars tasks resources allocations vacations previous roles",
    "view": "field option timeline filters", "filters": "filter", "filter": "simple-select",
    "calendars": "day-types date", "day-types": "day-type default-week only-show-weekends overriden-day-types days",
    "tasks": "taskproperties task", "taskproperties": "taskproperty", "taskproperty": "simple-select",
    "task": "task notes depend customproperty", "resources": "custom-property-definition resource",
    "resource": "rate custom-property", "allocations": "allocation", "vacations": "vacation",
    "previous": "previous-tasks", "previous-tasks": "previous-task", "roles": "role",
}
_CHILDREN = {key: frozenset(value.split()) for key, value in _CHILDREN.items()}
_SINGLETONS = {
    "project": frozenset("description calendars tasks resources allocations vacations previous".split()),
    "view": frozenset(("timeline", "filters")), "filter": frozenset(("simple-select",)),
    "calendars": frozenset(("day-types",)),
    "day-types": frozenset("default-week only-show-weekends overriden-day-types days".split()),
    "tasks": frozenset(("taskproperties",)), "taskproperty": frozenset(("simple-select",)),
    "task": frozenset(("notes",)), "resource": frozenset(("rate",)),
}
_TEXT_TAGS = frozenset(("description", "notes", "timeline", "option", "date"))
_BOOL_ATTRS = frozenset(("empty-milestones", "meeting", "project", "expand", "cost-calculated", "responsible", "super", "is-built-in", "is-enabled"))


@dataclass(frozen=True)
class Resource:
    id: str
    name: str


@dataclass(frozen=True)
class Interval:
    resource_id: str
    start: date
    end: date  # Native exclusive end.
    raw: bytes = field(default=b"", repr=False)

    def to_dict(self) -> dict[str, str]:
        return {"resource_id": self.resource_id, "start": self.start.isoformat(), "end_exclusive": self.end.isoformat()}


@dataclass(frozen=True)
class Project:
    source: bytes = field(repr=False)
    resources: tuple[Resource, ...]
    intervals: tuple[Interval, ...]
    vacation_start: int
    vacation_open_end: int
    vacation_close_start: int
    vacation_end: int
    self_closing: bool

    @property
    def source_sha256(self) -> str:
        return sha256(self.source)

    def inventory(self) -> dict[str, Any]:
        by_resource: dict[str, list[dict[str, str]]] = {r.id: [] for r in self.resources}
        for interval in self.intervals:
            by_resource[interval.resource_id].append(interval.to_dict())
        return {
            "profile": "ganttproject-3.4.3396-bounded-v1",
            "source_sha256": self.source_sha256,
            "resources": [{"id": r.id, "name": r.name,
                           "existing_intervals": by_resource[r.id]}
                          for r in self.resources],
            "existing_interval_count": len(self.intervals),
        }


@dataclass
class _Frame:
    name: str
    attrs: dict[str, str]
    start: int
    open_end: int
    self_closing: bool
    children: dict[str, int] = field(default_factory=dict)
    text_bytes: int = 0


def _tag_end(data: bytes, start: int) -> int:
    quote = 0
    for index in range(start, len(data)):
        byte = data[index]
        if quote:
            if byte == quote:
                quote = 0
        elif byte in (34, 39):
            quote = byte
        elif byte == 62:
            return index + 1
    raise OffDayKitError("Unterminated XML tag")


def parse_project(data: bytes) -> Project:
    """Validate bounded UTF-8 XML and retain byte offsets, never reserialize it."""
    if not isinstance(data, bytes):
        raise OffDayKitError("parse_project expects bytes")
    if len(data) > MAX_INPUT_BYTES:
        raise OffDayKitError("Project exceeds the 10 MiB input limit")
    if data.startswith((b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff")):
        raise OffDayKitError("BOMs are outside this profile; use BOM-free UTF-8")

    parser = expat.ParserCreate(encoding="UTF-8")
    parser.buffer_text = False
    stack: list[_Frame] = []
    resources: list[Resource] = []
    resource_ids: set[str] = set()
    task_ids: set[str] = set()
    intervals: list[Interval] = []
    references: list[tuple[str, str, str]] = []
    task_properties: dict[str, str] = {}
    resource_properties: dict[str, str] = {}
    custom_values: list[tuple[str, str, str]] = []
    root_seen = False
    section: tuple[int, int, int, int, bool] | None = None
    elements = attributes = attribute_bytes = text_bytes = 0

    def reject(*_args: Any) -> None:
        raise OffDayKitError("DTD, custom entities, processing instructions and external entities are unsupported")

    def declaration(version: str, encoding: str | None, standalone: int) -> None:
        if version != "1.0" or (encoding is not None and encoding.upper() != "UTF-8"):
            raise OffDayKitError("Only XML 1.0 with UTF-8 encoding is supported")

    def start(name: str, attrs: dict[str, str]) -> None:
        nonlocal elements, attributes, attribute_bytes, root_seen
        elements += 1
        attributes += len(attrs)
        if elements > MAX_ELEMENTS or len(stack) >= MAX_DEPTH:
            raise OffDayKitError("XML element/depth limit exceeded")
        if len(attrs) > MAX_ATTRIBUTES_PER_ELEMENT or attributes > MAX_ATTRIBUTES:
            raise OffDayKitError("XML attribute-count limit exceeded")
        for key, value in attrs.items():
            size = len(key.encode("utf-8")) + len(value.encode("utf-8"))
            if size > MAX_ATTRIBUTE_BYTES:
                raise OffDayKitError("XML attribute length limit exceeded")
            attribute_bytes += size
        if attribute_bytes > MAX_TOTAL_ATTRIBUTE_BYTES:
            raise OffDayKitError("XML total attribute length limit exceeded")
        if name not in _ATTRS or set(attrs) - _ATTRS[name]:
            raise OffDayKitError(f"Unsupported XML element or attributes: <{name}>")
        if stack:
            parent = stack[-1]
            if name not in _CHILDREN.get(parent.name, ()):
                raise OffDayKitError(f"Unsupported <{name}> inside <{parent.name}>")
            parent.children[name] = parent.children.get(name, 0) + 1
            if name in _SINGLETONS.get(parent.name, ()) and parent.children[name] > 1:
                raise OffDayKitError(f"Duplicate <{name}> section")
        elif name != "project" or root_seen:
            raise OffDayKitError("Expected a single <project> root")
        else:
            root_seen = True
            if attrs.get("version") != "3.4.3396":
                raise OffDayKitError("Only the pinned GanttProject 3.4.3396 profile is supported")

        for key, value in attrs.items():
            if key in _BOOL_ATTRS and value not in ("true", "false"):
                raise OffDayKitError(f"<{name}> {key} must be true or false")
        for key in (("view-date",) if name == "project" else
                    ("start", "thirdDate") if name == "task" else
                    ("start",) if name == "previous-task" else ()):
            if key in attrs:
                _date(attrs[key], f"<{name}> {key}")
        if name in ("task", "previous-task"):
            _required(attrs, "id start duration", name)
            _id(attrs["id"], f"<{name}> id")
            if not _ID.fullmatch(attrs["duration"]) or int(attrs["duration"]) > 2_147_483_647:
                raise OffDayKitError("Task duration must be a nonnegative 32-bit integer")
        if name == "task":
            if attrs["id"] in task_ids:
                raise OffDayKitError(f"Duplicate task id {attrs['id']}")
            task_ids.add(attrs["id"])
        elif name == "resource":
            _required(attrs, "id name", name)
            rid = _id(attrs["id"], "Resource id")
            if rid in resource_ids:
                raise OffDayKitError(f"Duplicate resource id {rid}")
            resource_ids.add(rid)
            resources.append(Resource(rid, attrs["name"]))
        elif name == "vacation":
            _required(attrs, "resourceid start end", name)
            _id(attrs["resourceid"], "Vacation resourceid")
            begin = _date(attrs["start"], "Vacation start")
            finish = _date(attrs["end"], "Vacation end")
            if finish <= begin:
                raise OffDayKitError("Vacation exclusive end must be after start")
            if len(intervals) >= MAX_INTERVALS:
                raise OffDayKitError("Existing interval limit exceeded")
            references.append(("resource", attrs["resourceid"], "vacation"))
        elif name == "allocation":
            _required(attrs, "task-id resource-id", name)
            for kind in ("task", "resource"):
                target = _id(attrs[f"{kind}-id"], f"Allocation {kind}-id")
                references.append((kind, target, "allocation"))
        elif name == "depend":
            _required(attrs, "id", name)
            references.append(("task", _id(attrs["id"], "Dependency id"), "dependency"))
        elif name == "date":
            _required(attrs, "year month date type", name)
            if not re.fullmatch(r"[0-9]{4}", attrs["year"]) or not re.fullmatch(r"[0-9]{1,2}", attrs["month"]) or not re.fullmatch(r"[0-9]{1,2}", attrs["date"]):
                raise OffDayKitError("Only explicit, finite calendar dates are supported")
            try:
                parsed_date = date(int(attrs["year"]), int(attrs["month"]), int(attrs["date"]))
            except ValueError as exc:
                raise OffDayKitError("Malformed calendar date") from exc
            _planning_date(parsed_date, "Calendar date")
        elif name in ("taskproperty", "custom-property-definition"):
            _required(attrs, "id", name)
            definitions = task_properties if name == "taskproperty" else resource_properties
            if attrs["id"] in definitions:
                raise OffDayKitError(f"Duplicate {name} id")
            definitions[attrs["id"]] = attrs.get("valuetype" if name == "taskproperty" else "type", "")
            default = attrs.get("defaultvalue" if name == "taskproperty" else "default-value")
            if default and definitions[attrs["id"]] == "date":
                _date(default, "Custom date default")
        elif name in ("customproperty", "custom-property"):
            prop = "taskproperty-id" if name == "customproperty" else "definition-id"
            _required(attrs, prop, name)
            custom_values.append((name, attrs[prop], attrs.get("value", "")))

        offset = parser.CurrentByteIndex
        end = _tag_end(data, offset)
        stack.append(_Frame(name, attrs, offset, end, data[offset:end].rstrip().endswith(b"/>")))

    def end(name: str) -> None:
        nonlocal section
        frame = stack.pop()
        close_start = parser.CurrentByteIndex
        end_offset = frame.open_end if frame.self_closing else _tag_end(data, close_start)
        if name == "vacation":
            intervals.append(Interval(frame.attrs["resourceid"], _date(frame.attrs["start"], "Vacation start"),
                                      _date(frame.attrs["end"], "Vacation end"), data[frame.start:end_offset]))
        elif name == "vacations":
            section = (frame.start, frame.open_end, close_start, end_offset, frame.self_closing)
        elif name == "project":
            for required in ("tasks", "resources", "vacations"):
                if frame.children.get(required) != 1:
                    raise OffDayKitError(f"Exactly one <{required}> section is required")

    def characters(value: str) -> None:
        nonlocal text_bytes
        size = len(value.encode("utf-8"))
        text_bytes += size
        if text_bytes > MAX_TEXT_BYTES:
            raise OffDayKitError("XML total text limit exceeded")
        if stack:
            stack[-1].text_bytes += size
            if stack[-1].text_bytes > MAX_NODE_TEXT_BYTES:
                raise OffDayKitError("XML node text limit exceeded")
            if stack[-1].name not in _TEXT_TAGS and value.strip(" \t\r\n"):
                raise OffDayKitError(f"Unexpected text inside <{stack[-1].name}>")
        elif value.strip(" \t\r\n"):
            raise OffDayKitError("Unexpected text outside project")

    def comment(value: str) -> None:
        nonlocal text_bytes
        size = len(value.encode("utf-8"))
        text_bytes += size
        if size > MAX_NODE_TEXT_BYTES or text_bytes > MAX_TEXT_BYTES:
            raise OffDayKitError("XML comment/text limit exceeded")
        if any(frame.name == "vacations" for frame in stack):
            raise OffDayKitError("Comments inside vacations are outside the supported profile")

    def cdata() -> None:
        if not stack or stack[-1].name not in _TEXT_TAGS:
            raise OffDayKitError("CDATA is allowed only in documented text elements")

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = characters
    parser.XmlDeclHandler = declaration
    parser.CommentHandler = comment
    parser.StartCdataSectionHandler = cdata
    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    parser.ProcessingInstructionHandler = reject
    try:
        for offset in range(0, len(data), 65_536):
            parser.Parse(data[offset:offset + 65_536], False)
        parser.Parse(b"", True)
    except expat.ExpatError as exc:
        raise OffDayKitError(f"Invalid UTF-8/XML: {exc}") from exc
    if section is None:
        raise OffDayKitError("Missing vacations section")
    for kind, target, origin in references:
        if target not in (task_ids if kind == "task" else resource_ids):
            raise OffDayKitError(f"Dangling {origin} reference to {kind} {target}")
    for kind, prop, value in custom_values:
        definitions = task_properties if kind == "customproperty" else resource_properties
        if prop not in definitions:
            raise OffDayKitError(f"Dangling {kind} definition {prop}")
        if value and definitions[prop] == "date":
            _date(value, "Custom date value")
    return Project(data, tuple(resources), tuple(intervals), *section)


@dataclass(frozen=True)
class Recipe:
    weekdays: tuple[int, ...]
    every_weeks: int
    anchor: date
    start: date
    end: date
    exclusions: tuple[date, ...]

    def __post_init__(self) -> None:
        if type(self.weekdays) is not tuple or not self.weekdays or any(type(v) is not int or v not in range(7) for v in self.weekdays) or len(set(self.weekdays)) != len(self.weekdays):
            raise OffDayKitError("Choose one to seven unique weekdays")
        if type(self.every_weeks) is not int or self.every_weeks not in (1, 2):
            raise OffDayKitError("every_weeks must be 1 or 2")
        if any(type(v) is not date for v in (self.anchor, self.start, self.end)) or self.anchor.weekday() != 0:
            raise OffDayKitError("anchor must be a Monday, and window values must be dates")
        for value in (self.anchor, self.start, self.end):
            _planning_date(value, "Recipe date")
        if not 1 <= (self.end - self.start).days + 1 <= MAX_WINDOW_DAYS:
            raise OffDayKitError("The inclusive window must contain 1 to 366 days")
        if self.end == MAX_PLANNING_DATE:
            raise OffDayKitError("The final supported window date is 2199-12-30")
        if type(self.exclusions) is not tuple or len(self.exclusions) > MAX_WINDOW_DAYS or any(type(v) is not date for v in self.exclusions) or len(set(self.exclusions)) != len(self.exclusions):
            raise OffDayKitError("exclusions must contain at most 366 unique dates")
        for value in self.exclusions:
            _planning_date(value, "Exclusion")
        if any(v < self.start or v > self.end for v in self.exclusions):
            raise OffDayKitError("Every exclusion must be inside the inclusive window")

    @classmethod
    def from_dict(cls, obj: Any) -> Recipe:
        expected = {"weekdays", "every_weeks", "anchor", "start", "end", "exclusions"}
        if not isinstance(obj, dict) or set(obj) != expected:
            raise OffDayKitError("Recipe must have exactly weekdays, every_weeks, anchor, start, end, exclusions; resource IDs are never stored in recipes")
        days = obj["weekdays"]
        if not isinstance(days, list) or not 1 <= len(days) <= 7 or any(not isinstance(v, str) or v not in WEEKDAYS for v in days):
            raise OffDayKitError("weekdays must be lowercase English weekday names")
        excluded = obj["exclusions"]
        if not isinstance(excluded, list) or len(excluded) > MAX_WINDOW_DAYS:
            raise OffDayKitError("exclusions must be a bounded list of ISO dates")
        return cls(tuple(sorted(WEEKDAYS.index(v) for v in days)), obj["every_weeks"],
                   _date(obj["anchor"], "Recipe anchor"), _date(obj["start"], "Recipe start"),
                   _date(obj["end"], "Recipe end"), tuple(sorted(_date(v, "Exclusion") for v in excluded)))

    @classmethod
    def from_json(cls, data: bytes) -> Recipe:
        if not isinstance(data, bytes) or len(data) > MAX_RECIPE_BYTES:
            raise OffDayKitError("Recipe exceeds the 64 KiB input limit")
        def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise OffDayKitError(f"Duplicate recipe key: {key}")
                result[key] = value
            return result
        try:
            obj = json.loads(data.decode("utf-8"), object_pairs_hook=unique,
                             parse_constant=lambda _value: (_ for _ in ()).throw(OffDayKitError("Nonfinite JSON is unsupported")))
        except (UnicodeError, ValueError, RecursionError) as exc:
            if isinstance(exc, OffDayKitError):
                raise
            raise OffDayKitError("Recipe must be bounded UTF-8 JSON") from exc
        return cls.from_dict(obj)

    def to_dict(self) -> dict[str, Any]:
        return {"weekdays": [WEEKDAYS[v] for v in self.weekdays], "every_weeks": self.every_weeks,
                "anchor": self.anchor.isoformat(), "start": self.start.isoformat(), "end": self.end.isoformat(),
                "exclusions": [v.isoformat() for v in self.exclusions]}

    def candidates(self) -> tuple[date, ...]:
        return tuple(self.start + timedelta(days=i) for i in range((self.end - self.start).days + 1)
                     if (self.start + timedelta(days=i)).weekday() in self.weekdays
                     and ((self.start + timedelta(days=i) - self.anchor).days // 7) % self.every_weeks == 0)


@dataclass(frozen=True)
class Candidate:
    resource_id: str
    day: date
    excluded: bool
    covering_interval: Interval | None
    covering_interval_count: int

    @property
    def status(self) -> str:
        return "excluded" if self.excluded else "covered" if self.covering_interval else "add"

    def to_dict(self) -> dict[str, Any]:
        return {"resource_id": self.resource_id, "date": self.day.isoformat(), "excluded": self.excluded,
                "covered": self.covering_interval is not None, "status": self.status,
                "covering_interval_count": self.covering_interval_count,
                "covering_interval_example": self.covering_interval.to_dict() if self.covering_interval else None}


@dataclass(frozen=True)
class Plan:
    recipe: Recipe
    selected_ids: tuple[str, ...]
    candidates: tuple[Candidate, ...]
    additions: tuple[Interval, ...]
    source_sha256: str
    output_sha256: str
    existing_interval_count: int

    def to_dict(self) -> dict[str, Any]:
        return {"format": "off-day-kit-receipt-v1", "profile": "ganttproject-3.4.3396-bounded-v1",
                "purpose": "Prepare native days-off records; no scheduling or workload guarantees",
                "recipe": self.recipe.to_dict(), "selected_resource_ids": list(self.selected_ids),
                "candidate_dates": [{"date": d.isoformat(), "excluded": d in self.recipe.exclusions}
                                    for d in self.recipe.candidates()],
                "candidates_by_resource": [c.to_dict() for c in self.candidates],
                "additions": [v.to_dict() for v in self.additions], "addition_count": len(self.additions),
                "existing_interval_count": self.existing_interval_count,
                "output_interval_count": self.existing_interval_count + len(self.additions),
                "source_sha256": self.source_sha256, "output_sha256": self.output_sha256,
                "no_op": not self.additions}


def _render(project: Project, additions: tuple[Interval, ...]) -> bytes:
    if not additions:
        return project.source
    records = b"".join((f'\n        <vacation start="{v.start.isoformat()}" end="{v.end.isoformat()}" resourceid="{v.resource_id}"/>').encode("ascii") for v in additions)
    if project.self_closing:
        opening = project.source[project.vacation_start:project.vacation_open_end]
        # Keep original spacing before the slash. Only the section is replaced.
        replacement = opening[:-2] + b">" + records + b"\n    </vacations>"
        return project.source[:project.vacation_start] + replacement + project.source[project.vacation_end:]
    insert = project.vacation_close_start
    return project.source[:insert] + records + b"\n    " + project.source[insert:]


def preview(project: Project, recipe: Recipe, selected_ids: Iterable[str] = ()) -> Plan:
    """Make a complete deterministic receipt; an empty selection is preview-only."""
    selected: list[str] = []
    for value in selected_ids:
        if len(selected) >= MAX_SELECTED_RESOURCES:
            raise OffDayKitError("At most 100 resources may be selected")
        selected.append(_id(value, "Selected resource id"))
    if len(set(selected)) != len(selected):
        raise OffDayKitError("A resource may be selected only once")
    known = {r.id for r in project.resources}
    if set(selected) - known:
        raise OffDayKitError("Every selected resource must already exist in this project")
    selected_tuple = tuple(sorted(selected, key=int))
    dates = recipe.candidates()
    candidates: list[Candidate] = []
    additions: list[Interval] = []
    for rid in selected_tuple:
        existing = tuple(v for v in project.intervals if v.resource_id == rid)
        for day in dates:
            first_cover = None
            cover_count = 0
            for interval in existing:
                if interval.start <= day < interval.end:
                    cover_count += 1
                    if first_cover is None:
                        first_cover = interval
            candidate = Candidate(rid, day, day in recipe.exclusions, first_cover, cover_count)
            candidates.append(candidate)
            if candidate.status == "add":
                if len(project.intervals) + len(additions) >= MAX_INTERVALS:
                    raise OffDayKitError("Existing plus generated intervals would exceed 10000")
                additions.append(Interval(rid, day, day + timedelta(days=1)))
    added = tuple(additions)
    output = _render(project, added)
    if len(output) > MAX_INPUT_BYTES:
        raise OffDayKitError("Generated output would exceed the 10 MiB supported-project limit")
    if added:
        # Appending can exceed element/attribute/text bounds even when raw size
        # and interval count fit. Preview must reject that before offering a
        # receipt which apply could not safely create.
        parse_project(output)
    return Plan(recipe, selected_tuple, tuple(candidates), added, project.source_sha256,
                sha256(output), len(project.intervals))


def apply(project: Project, plan: Plan) -> bytes:
    """Apply a verified plan in memory. File creation belongs to the CLI layer."""
    if not plan.selected_ids:
        raise OffDayKitError("Applying requires explicit resource IDs for this project")
    if project.source_sha256 != plan.source_sha256:
        raise OffDayKitError("Plan belongs to a different source project")
    expected = preview(project, plan.recipe, plan.selected_ids)
    if expected != plan:
        raise OffDayKitError("Plan has changed; create a fresh preview")
    return _render(project, plan.additions)

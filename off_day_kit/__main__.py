"""Run with python -m off_day_kit. No third-party dependencies."""

from __future__ import annotations

import argparse
import json
import sys

from .core import MAX_INPUT_BYTES, MAX_RECIPE_BYTES, OffDayKitError, Recipe, apply, parse_project, preview
from .files import create_outputs, read_regular


def _json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare bounded native days-off records in an existing GanttProject 3.4.3396 file.")
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory", help="Validate and list existing resource IDs and intervals; writes nothing")
    inventory.add_argument("input")
    for command in ("preview", "apply"):
        item = commands.add_parser(command, help="Print a complete JSON preview" if command == "preview" else "Create a new project and JSON receipt")
        item.add_argument("input")
        item.add_argument("--recipe", required=True)
        item.add_argument("--resource", action="append", default=[], required=command == "apply", metavar="ID",
                          help="Existing resource ID; repeat per resource on every invocation")
        if command == "apply":
            item.add_argument("--output", required=True, help="New .gan destination; existing paths are refused")
            item.add_argument("--report", required=True, help="New JSON receipt destination; existing paths are refused")
    args = parser.parse_args(argv)
    try:
        project = parse_project(read_regular(args.input, MAX_INPUT_BYTES))
        if args.command == "inventory":
            result = project.inventory()
        else:
            recipe = Recipe.from_json(read_regular(args.recipe, MAX_RECIPE_BYTES))
            plan = preview(project, recipe, args.resource)
            result = plan.to_dict()
            if args.command == "apply":
                output = apply(project, plan)
                create_outputs(((args.output, output), (args.report, _json(result))), (args.input, args.recipe))
        sys.stdout.write(_json(result).decode("utf-8"))
        return 0
    except OffDayKitError as exc:
        sys.stderr.write(f"off-day-kit: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

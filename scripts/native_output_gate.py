"""Send actual producer bytes through the unchanged official GUI consumer."""
from __future__ import annotations
from datetime import date
import csv
import io
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

import date_oracle as oracle
import gui_probe as ui

E = ui.EVIDENCE
EXPECTED_ROWS = {
    "RESOURCEA": ["Jan 8, 2027...Jan 10, 2027", "Feb 5, 2027...Feb 5, 2027", "Feb 19, 2027...Feb 19, 2027"],
    "RESOURCEB": ["Feb 1, 2027...Feb 1, 2027", "Jan 8, 2027...Jan 8, 2027",
                  "Feb 5, 2027...Feb 5, 2027", "Feb 19, 2027...Feb 19, 2027"],
    "RESOURCEC": [],
}


def producer(source: Path, output: Path, report: Path, recipe: Path) -> None:
    assert not output.exists() and not report.exists()
    command = [sys.executable, "-m", "off_day_kit", "apply", str(source), "--recipe", str(recipe),
               "--resource", "0", "--resource", "1", "--output", str(output), "--report", str(report)]
    result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    (E / f"{output.stem}-producer.log").write_text(result.stdout + result.stderr)


def negative_controls(source: bytes, generated: bytes) -> None:
    needle = b'<vacation start="2027-02-05" end="2027-02-06" resourceid="0"/>'
    assert generated.count(needle) == 1
    cases = {
        "end-plus-one": generated.replace(needle, needle.replace(b'2027-02-06', b'2027-02-07'), 1),
        "wrong-resource": generated.replace(needle, needle.replace(b'resourceid="0"', b'resourceid="2"'), 1),
        "excluded-date": generated.replace(b'</vacations>', b'<vacation start="2027-01-22" end="2027-01-23" resourceid="0"/>\n    </vacations>', 1),
    }
    changed_recipe = dict(oracle.RECIPE, anchor="2027-01-11")
    recipe_path = E / "shifted-anchor-recipe.json"
    recipe_path.write_text(json.dumps(changed_recipe))
    shifted = E / "negative-shifted-anchor.gan"
    producer(E / "gui-authored.gan", shifted, E / "negative-shifted-anchor-receipt.json", recipe_path)
    cases["shifted-anchor"] = shifted.read_bytes()
    result = {}
    for name, data in cases.items():
        # Each fault remains ordinary valid XML; failure must come from the
        # literal interval/date contract, not a changed receipt checksum.
        ET.fromstring(data)
        path = E / f"negative-{name}.gan"
        if name != "shifted-anchor":
            with path.open("xb") as stream:
                stream.write(data)
        try:
            oracle.verify_raw(source, data)
        except AssertionError as error:
            result[name] = {"status": "rejected", "reason": str(error), "sha256": oracle.sha(data)}
        else:
            raise AssertionError(f"Literal date oracle accepted {name}")
    assert len(result) == 4
    (E / "negative-control-results.json").write_text(json.dumps(result, indent=2))


def chart_button(label: str) -> dict:
    data = ui.dump()
    windows = [w for w in data["windows"] if "GanttProject" in (w.get("title") or "")]
    assert len(windows) == 1
    x, y, w, h = windows[0]["bounds"]
    # Some detached embedded Swing scenes expose stale coordinates at (0,0).
    # Require the actual visible main-window rectangle for chart controls.
    controls = [n for n in ui.nodes(data) if n["class"].endswith(".Button") and n.get("text") == label
                and x <= n["bounds"][0] and y + 25 <= n["bounds"][1]
                and n["bounds"][0] + n["bounds"][2] <= x + w
                and n["bounds"][1] + n["bounds"][3] <= y + h]
    assert len(controls) == 1, controls
    return controls[0]


def scroll_chart(target: date, current: date, name: str, source: bytes) -> None:
    # Pinned GPTimeUnitStack: default3 = month/day34; default4 = month/week.
    # Use genuine zoom/scroll controls, then inspect a fresh native save for
    # the actual viewport date before making a small final daily adjustment.
    ui.click(chart_button("Zoom Out"))
    weeks = (target - current).days // 7
    assert abs(weeks) <= 80
    direction = "Future →" if weeks >= 0 else "← Past"
    for _ in range(abs(weeks)): ui.click(chart_button(direction))
    ui.click(chart_button("Zoom In"))
    position = E / f"{name}-position.gan"
    ui.save_as(position)
    oracle.verify_native(source, position.read_bytes())
    observed = date.fromisoformat(ET.parse(position).getroot().attrib["view-date"])
    days = (target - observed).days
    # Integer-week movement leaves up to six days, and native week framing
    # can shift the initial date back by another six. The actual saved date
    # remains the authority; the final fresh save must equal the target.
    assert abs(days) <= 12, (name, target, observed)
    direction = "Future →" if days >= 0 else "← Past"
    for _ in range(abs(days)): ui.click(chart_button(direction))
    confirmed = E / f"{name}-chart.gan"
    ui.save_as(confirmed)
    oracle.verify_native(source, confirmed.read_bytes())
    actual = ET.parse(confirmed).getroot().attrib["view-date"]
    assert actual == target.isoformat(), (name, actual)
    tree = ui.dump(name + "-chart-tree"); ui.shot(name + "-chart")
    rendered_text = ui.run("tesseract", str(E / f"{name}-chart.png"), "stdout", "--psm", "11")
    (E / f"{name}-chart-ocr.txt").write_text(rendered_text)
    assert ("January" if target.month == 1 else "February") in rendered_text and "2027" in rendered_text
    main = [w for w in tree["windows"] if "GanttProject" in (w.get("title") or "")]
    assert len(main) == 1
    x, y, w, h = main[0]["bounds"]
    dividers = [n for n in ui.nodes(tree) if "split-pane-divider" in n.get("styles", "").split()
                and x < n["bounds"][0] < x + w and y < n["bounds"][1] < y + h]
    assert len(dividers) == 1
    dx, dy, dw, _ = dividers[0]["bounds"]
    assert x + w - dx - dw >= 600, "Chart is too narrow for the target date columns"
    tsv = ui.run("tesseract", str(E / f"{name}-chart.png"), "stdout", "--psm", "11", "tsv")
    (E / f"{name}-chart-ocr.tsv").write_text(tsv)
    last_day = "22" if target.month == 1 else "19"
    tokens = [r for r in csv.DictReader(io.StringIO(tsv), delimiter="\t")
              if r.get("text") == last_day and int(r["left"]) > dx + dw
              and dy + 24 <= int(r["top"]) < dy + 120]
    assert len(tokens) == 1 and int(tokens[0]["left"]) + int(tokens[0]["width"]) <= x + w - 40, tokens
    (E / f"{name}-chart-visibility.json").write_text(json.dumps({
        "status": "pass", "view_date": actual, "daily_zoom": "default:3", "target_day": last_day,
        "target_token": tokens[0], "chart_left": dx + dw, "window_right": x + w,
        "right_margin_at_least": 40
    }, indent=2))


def main() -> None:
    source_path = E / "gui-authored.gan"
    source = source_path.read_bytes()
    recipe = ui.ROOT / "scripts/recipe.json"
    generated_path, receipt_path = E / "generated.gan", E / "generated-receipt.json"
    producer(source_path, generated_path, receipt_path, recipe)
    generated = generated_path.read_bytes()
    oracle.verify_raw(source, generated, json.loads(receipt_path.read_text()))
    producer(generated_path, E / "no-op.gan", E / "no-op-receipt.json", recipe)
    assert (E / "no-op.gan").read_bytes() == generated
    no_op = json.loads((E / "no-op-receipt.json").read_text())
    assert no_op["no_op"] is True and no_op["addition_count"] == 0
    negative_controls(source, generated)
    runtime = (ui.ROOT / ".native/runtime-path.txt").read_text().strip()
    command = ["bash", str(ui.ROOT / ".native/release/ganttproject"), "--java-home", runtime]
    profile, agent = ui.ROOT / ".native/profile", ui.ROOT / ".native/ui-probe.jar"
    env = dict(os.environ, JAVA_TOOL_OPTIONS=f"-javaagent:{agent}={ui.IPC} -Duser.home={profile} -Duser.language=en -Duser.country=US -Duser.timezone=UTC")
    process = None
    with (E / "generated-native-application.log").open("w") as log:
        try:
            for stage, input_path in [("generated", generated_path), ("generated-reopened", E / "generated-saved.gan")]:
                (ui.IPC / "reply.json").unlink(missing_ok=True)
                process = subprocess.Popen(command + [str(input_path)], env=env, stdout=log,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                ui.wait_main(process)
                ui.tab("Resources Chart")
                for name, rows in EXPECTED_ROWS.items():
                    ui.resource_dialog(name, rows, prefix=stage + "-")
                if stage == "generated":
                    current = date.fromisoformat(ET.fromstring(generated).attrib["view-date"])
                    assert ET.fromstring(generated).find("view[@id='gantt-chart']").attrib["zooming-state"] == "default:2"
                    ui.click(chart_button("Zoom Out"))
                    scroll_chart(date(2027, 1, 4), current, "january", source)
                    scroll_chart(date(2027, 2, 1), date(2027, 1, 4), "february", source)
                ui.dump(stage + "-main-tree"); ui.shot(stage + "-main")
                saved = E / f"{stage}-saved.gan"
                ui.save_as(saved)
                oracle.verify_native(source, saved.read_bytes())
                ui.key("ctrl+q"); process.wait(timeout=20)
            oracle.main(E)
            assert source_path.read_bytes() == source, "Original GUI fixture was changed"
            assert generated_path.read_bytes() == generated, "Native consumer changed the produced input file"
            (E / "native-generated-result.json").write_text(json.dumps({
                "status": "pass", "actualProducerCli": True, "officialGuiConsumer": True,
                "freshProcessReopen": True, "fiveAdditions": True, "nativeIntervals": 7,
                "allDisplayedDateRows": True, "januaryFebruaryChartEvidence": True,
                "sourceUnchanged": oracle.sha(source), "producedInputUnchanged": oracle.sha(generated),
                "negativeControlsRejected": 4, "repeatIsByteIdenticalNoOp": True,
                "schedulingTested": False, "productUiTested": False
            }, indent=2))
        finally:
            if process is not None and process.poll() is None:
                try:
                    ui.dump("generated-exit-tree"); ui.shot("generated-exit")
                finally:
                    os.killpg(process.pid, signal.SIGTERM)
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL); process.wait()


if __name__ == "__main__":
    main()

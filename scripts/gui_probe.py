"""Hosted native GUI authoring probe. Inputs are synthetic and local only."""
from __future__ import annotations
import csv
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET

ROOT = Path.cwd()
EVIDENCE = ROOT / "evidence"
IPC = ROOT / ".native" / "probe-ipc"
EVIDENCE.mkdir(exist_ok=True)
IPC.mkdir(exist_ok=True)
TOKEN = 0


def run(*args: str, timeout: int = 15) -> str:
    return subprocess.run(args, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, timeout=timeout).stdout


def key(*keys: str) -> None:
    run("xdotool", "key", "--clearmodifiers", *keys)
    time.sleep(0.35)


def type_text(text: str) -> None:
    run("xdotool", "type", "--clearmodifiers", "--delay", "8", "--", text)
    time.sleep(0.3)


def shot(name: str) -> None:
    run("import", "-window", "root", str(EVIDENCE / f"{name}.png"))


def dump(name: str | None = None) -> dict:
    global TOKEN
    TOKEN += 1
    (IPC / "request.tmp").write_text(str(TOKEN))
    (IPC / "request.tmp").replace(IPC / "request.txt")
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        try:
            data = json.loads((IPC / "reply.json").read_text())
            if data["token"] == str(TOKEN):
                if name:
                    (EVIDENCE / f"{name}.json").write_text(json.dumps(data, indent=2))
                if data["errors"]:
                    raise AssertionError(data["errors"])
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        time.sleep(0.1)
    raise AssertionError("Read-only UI discovery deadline")


def nodes(data: dict) -> list[dict]:
    return [n for n in data["fx"] + data["swing"]
            if len(n.get("bounds", [])) == 4 and n["bounds"][2] > 2 and n["bounds"][3] > 2
            and not n.get("disabled", False) and n.get("enabled", True)]


def wait_main(process: subprocess.Popen) -> None:
    deadline = time.monotonic() + 75
    while time.monotonic() < deadline:
        assert process.poll() is None, "Official application exited before UI readiness"
        try:
            data = dump()
            windows = [n for n in data.get("windows", []) if "GanttProject" in (n.get("title") or "")]
            menu_names = {n.get("text") for n in data["fx"] if n["class"].endswith(".MenuBarButton")}
            if len(windows) == 1 and {"Project", "Resources"} <= menu_names:
                break
        except AssertionError:
            pass
        time.sleep(0.5)
    else:
        raise AssertionError("Official JavaFX main window startup deadline")
    window_ids = run("xdotool", "search", "--onlyvisible", "--name", "GanttProject").splitlines()
    assert len(window_ids) == 1, window_ids
    run("xdotool", "windowsize", "--sync", window_ids[0], "1450", "950")
    run("xdotool", "windowmove", "--sync", window_ids[0], "40", "40")
    run("xdotool", "windowactivate", "--sync", window_ids[0])
    time.sleep(0.5)
    windows = [n for n in dump()["windows"] if "GanttProject" in (n.get("title") or "")]
    assert len(windows) == 1 and windows[0]["bounds"][2] >= 1200 and windows[0]["bounds"][3] >= 800


def wait_node(predicate, seconds: int = 15) -> dict:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        found = [n for n in nodes(dump()) if predicate(n)]
        if len(found) == 1:
            return found[0]
        if len(found) > 1:
            raise AssertionError(f"Ambiguous native control: {found}")
        time.sleep(0.2)
    dump("failed-selector-tree")
    shot("failed-selector")
    raise AssertionError("Native control not found")


def click(node: dict, twice: bool = False) -> None:
    x, y, w, h = node["bounds"]
    run("xdotool", "mousemove", "--sync", str(round(x + w / 2)), str(round(y + h / 2)))
    run("xdotool", "click", "--repeat", "2" if twice else "1", "--delay", "130", "1")
    time.sleep(0.4)


def button(label: str) -> dict:
    return wait_node(lambda n: (n.get("text") or "").replace("_", "") == label
                     and (n["class"].endswith(".Button") or n["class"].endswith(".JButton")))


def tab(label: str) -> None:
    click(wait_node(lambda n: n.get("text") == label and n["class"].endswith(".Label")))


def named_field(label: str) -> dict:
    target = wait_node(lambda n: (n.get("text") or "").rstrip(":") == label and "labelForUid" in n)
    return wait_node(lambda n: n.get("uid") == target["labelForUid"] and "TextField" in n["class"])


def add_days(first: str, last: str, name: str) -> None:
    click(button("Add"))
    for target in [first] + ([last] if last != first else []):
        for _ in range(18):
            data = dump()
            found = [n for n in nodes(data) if n.get("item") == target and "day-cell" in n.get("styles", "")]
            if len(found) == 1:
                click(found[0]); break
            if len(found) > 1:
                raise AssertionError("Ambiguous date cell")
            days = [n.get("item") for n in nodes(data) if "day-cell" in n.get("styles", "") and n.get("item")]
            assert days, "Native calendar has no visible date cells"
            direction = "right-button" if target > max(days) else "left-button"
            click(wait_node(lambda n: direction in n.get("styles", "") and n["class"].endswith(".Button")))
        else:
            raise AssertionError("Calendar navigation bound reached")
    dump(f"{name}-selected-dates-tree"); shot(f"{name}-selected-dates")
    # The date picker is modal, but the underlying editor still exposes its
    # regular Add button. Only the calendar confirm button has this native style.
    click(wait_node(lambda n: n["class"].endswith(".Button") and n.get("text") == "Add"
                    and "btn-attention" in n.get("styles", "")))


def new_resource(name: str, dates: tuple[str, str] | None) -> None:
    key("ctrl+h")
    field = named_field("Name")
    click(field); key("ctrl+a"); type_text(name)
    tab("Days off")
    if dates:
        add_days(*dates, name)
    data = dump(f"{name}-authored-days-tree"); shot(f"{name}-authored-days")
    rows = [n for n in nodes(data) if n.get("itemClass") == "net.sourceforge.ganttproject.gui.DateInterval" and n.get("text")]
    assert len(rows) == (1 if dates else 0), rows
    click(button("OK"))
    time.sleep(0.5)


def save_as(path: Path) -> None:
    assert not path.exists(), "Native outputs must be fresh"
    key("ctrl+shift+s")
    # The official local storage pane accepts a full local path in this field.
    field = wait_node(lambda n: "filename-input" in n.get("styles", "") and "TextField" in n["class"])
    click(field); key("ctrl+a"); type_text(str(path))
    click(wait_node(lambda n: n["class"].endswith(".Button") and "btn-attention" in n.get("styles", "")
                    and (n.get("text") or "").lower().startswith("save")))
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if path.is_file() and path.stat().st_size > 0:
            try:
                ET.parse(path)
                return
            except ET.ParseError:
                pass
        time.sleep(0.2)
    raise AssertionError("Fresh native save did not complete")


def open_file(path: Path) -> None:
    key("ctrl+o")
    field = wait_node(lambda n: "filename-input" in n.get("styles", "") and "TextField" in n["class"])
    click(field); key("ctrl+a"); type_text(str(path))
    click(wait_node(lambda n: n["class"].endswith(".Button") and "btn-attention" in n.get("styles", "")
                    and (n.get("text") or "").lower().startswith("open")))
    time.sleep(1)


def resource_dialog(name: str) -> None:
    # Resource chart text is painted by the official application. Locate its
    # actual pixels when it is not exposed as a public text control.
    shot("resource-locate")
    result = run("tesseract", str(EVIDENCE / "resource-locate.png"), "stdout", "--psm", "11", "tsv")
    (EVIDENCE / f"{name}-locate.tsv").write_text(result)
    rows = [r for r in csv.DictReader(io.StringIO(result), delimiter="\t") if r.get("text") == name]
    assert len(rows) == 1, f"Expected unique rendered resource label {name}: {rows}"
    r = rows[0]
    click({"bounds": [int(r[k]) for k in ("left", "top", "width", "height")]})
    key("alt+Return")
    assert named_field("Name")["text"] == name, "Opened a different resource"
    tab("Days off")
    data = dump(f"{name}-reopened-days-tree"); shot(f"{name}-reopened-days")
    rows = [n for n in nodes(data) if n.get("itemClass") == "net.sourceforge.ganttproject.gui.DateInterval" and n.get("text")]
    assert len(rows) == (0 if name == "RESOURCEC" else 1), rows
    click(button("Cancel"))


def literal_xml(path: Path) -> dict:
    root = ET.parse(path).getroot()
    assert root.tag == "project" and root.attrib["version"].startswith("3.4")
    resources = [(r.attrib["id"], r.attrib["name"]) for r in root.findall("resources/resource")]
    assert resources == [("0", "RESOURCEA"), ("1", "RESOURCEB"), ("2", "RESOURCEC")], resources
    vacations = [v.attrib for v in root.findall("vacations/vacation")]
    expected = [dict(start="2027-01-08", end="2027-01-11", resourceid="0"),
                dict(start="2027-02-01", end="2027-02-02", resourceid="1")]
    assert vacations == expected, vacations
    tasks = [t.attrib for t in root.findall("tasks/task")]
    assert len(tasks) >= 1, "Task sentinel missing"
    return {"resources": resources, "vacations": vacations, "tasks": tasks}


def main() -> None:
    executable = str((ROOT / ".native/release/ganttproject").resolve())
    runtime = (ROOT / ".native/runtime-path.txt").read_text().strip()
    command = ["bash", executable, "--java-home", runtime]
    agent = str((ROOT / ".native/ui-probe.jar").resolve())
    profile = ROOT / ".native/profile"
    profile.mkdir(exist_ok=True)
    env = dict(os.environ, JAVA_TOOL_OPTIONS=f"-javaagent:{agent}={IPC} -Duser.home={profile} -Duser.language=en -Duser.country=US -Duser.timezone=UTC")
    with (EVIDENCE / "application.log").open("w") as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            wait_main(process)
            dump("startup-tree"); shot("startup")
            new_resource("RESOURCEA", ("2027-01-08", "2027-01-10"))
            new_resource("RESOURCEB", ("2027-02-01", "2027-02-01"))
            new_resource("RESOURCEC", None)
            key("ctrl+t")
            time.sleep(0.5)
            key("Escape")
            save_as(EVIDENCE / "gui-authored.gan")
            before = literal_xml(EVIDENCE / "gui-authored.gan")
            dump("saved-main-tree"); shot("saved-main")
            key("ctrl+q")
            process.wait(timeout=20)
            # A fresh process must consume the exact file created through GUI.
            (IPC / "reply.json").unlink(missing_ok=True)
            process = subprocess.Popen(command + [str(EVIDENCE / "gui-authored.gan")], env=env,
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            wait_main(process)
            # Select the actual observed tab explicitly; a saved view may vary.
            tab("Resources Chart")
            for name in ("RESOURCEA", "RESOURCEB", "RESOURCEC"):
                resource_dialog(name)
            dump("reopened-main-tree"); shot("reopened-main")
            save_as(EVIDENCE / "gui-reopened-saved.gan")
            after = literal_xml(EVIDENCE / "gui-reopened-saved.gan")
            assert before == after, "Fresh native GUI save/reopen changed literal fixture"
            (EVIDENCE / "gui-fixture-result.json").write_text(json.dumps({
                "status": "pass", "guiAuthored": True, "freshProcessReopen": True,
                "oneDayExclusiveEnd": "2027-02-02", "multiDayExclusiveEnd": "2027-01-11",
                "literalFixture": after, "productConversionTested": False,
                "inspector": "Read-only public Swing/JavaFX controls; no model mutation"
            }, indent=2))
            key("ctrl+q"); process.wait(timeout=20)
        finally:
            try:
                dump("exit-tree"); shot("exit")
            except Exception:
                pass
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        (EVIDENCE / "failure.txt").write_text(traceback.format_exc())
        raise

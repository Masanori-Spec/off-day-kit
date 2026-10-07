"""Filesystem and CLI boundary tests using only temporary local files."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from off_day_kit import OffDayKitError
from off_day_kit.__main__ import main
from off_day_kit.files import create_outputs, read_regular


PROJECT = b'''<?xml version="1.0" encoding="UTF-8"?>
<project version="3.4.3396"><tasks><task id="0" start="2027-01-04" duration="1"/></tasks>
<resources><resource id="0" name="A"/><resource id="1" name="B"/></resources><vacations/></project>'''
RECIPE = {"weekdays": ["friday"], "every_weeks": 2, "anchor": "2027-01-04",
          "start": "2027-01-04", "end": "2027-02-28", "exclusions": ["2027-01-22"]}


class FileBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.gan"
        self.source.write_bytes(PROJECT)

    def test_regular_file_exact_limit_and_oversized(self):
        self.assertEqual(read_regular(self.source, len(PROJECT)), PROJECT)
        with self.assertRaises(OffDayKitError):
            read_regular(self.source, len(PROJECT) - 1)

    def test_reject_symlink_directory_device_and_missing_input(self):
        link = self.root / "link.gan"
        link.symlink_to(self.source)
        for path in (link, self.root, self.root / "missing", Path("/dev/null")):
            with self.subTest(path=path), self.assertRaises(OffDayKitError):
                read_regular(path, 1024)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO test")
    def test_fifo_rejected_without_a_writer_or_blocking(self):
        fifo = self.root / "fifo.gan"
        os.mkfifo(fifo)
        command = [sys.executable, "-c", "from off_day_kit.files import read_regular; read_regular(__import__('sys').argv[1], 1024)", str(fifo)]
        result = subprocess.run(command, capture_output=True, timeout=3)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"regular file", result.stderr)

    @unittest.skipUnless(hasattr(os, "O_NONBLOCK") and hasattr(os, "mkfifo"), "POSIX nonblocking race test")
    def test_file_swapped_for_fifo_before_open_fails_closed(self):
        real_open = os.open
        def swap(path, flags, *args):
            os.unlink(path)
            os.mkfifo(path)
            self.assertTrue(flags & os.O_NONBLOCK)
            return real_open(path, flags, *args)
        with patch("off_day_kit.files.os.open", side_effect=swap), self.assertRaises(OffDayKitError):
            read_regular(self.source, 1024)

    def test_growing_file_read_is_bounded(self):
        real_read = os.read
        called = False
        def grow(descriptor, count):
            nonlocal called
            if not called:
                called = True
                with self.source.open("ab") as handle:
                    handle.write(b"x" * 1000)
            return real_read(descriptor, count)
        with patch("off_day_kit.files.os.read", side_effect=grow), self.assertRaises(OffDayKitError):
            read_regular(self.source, len(PROJECT))

    def test_exclusive_writes_preserve_inputs_and_existing_destinations(self):
        out = self.root / "out.gan"
        report = self.root / "receipt.json"
        create_outputs(((out, b"output"), (report, b"report")), (self.source,))
        self.assertEqual(out.read_bytes(), b"output")
        self.assertEqual(report.read_bytes(), b"report")
        with self.assertRaises(OffDayKitError):
            create_outputs(((out, b"overwrite"),))
        self.assertEqual(out.read_bytes(), b"output")
        self.assertEqual(self.source.read_bytes(), PROJECT)

    def test_aliases_and_dangling_symlink_are_rejected(self):
        out = self.root / "out"
        link = self.root / "dangling"
        link.symlink_to(self.root / "absent")
        cases = (((out, b"a"), (self.root / "." / "out", b"b")),
                 ((self.source, b"a"),), ((link, b"a"),))
        for items in cases:
            with self.subTest(items=items), self.assertRaises(OffDayKitError):
                create_outputs(items, (self.source,))
        self.assertFalse(out.exists())
        self.assertTrue(link.is_symlink())

    def test_second_reservation_failure_cleans_only_our_new_file(self):
        out = self.root / "out"
        report = self.root / "receipt"
        real_open = os.open
        def race(path, flags, *args):
            if Path(path) == report:
                report.write_bytes(b"other writer")
            return real_open(path, flags, *args)
        with patch("off_day_kit.files.os.open", side_effect=race), self.assertRaises(OffDayKitError):
            create_outputs(((out, b"a"), (report, b"b")))
        self.assertFalse(out.exists())
        self.assertEqual(report.read_bytes(), b"other writer")

    def test_write_failure_rolls_back_new_files(self):
        out = self.root / "out"
        report = self.root / "receipt"
        with patch("off_day_kit.files.os.write", side_effect=OSError("simulated disk failure")), self.assertRaises(OffDayKitError):
            create_outputs(((out, b"a"), (report, b"b")))
        self.assertFalse(out.exists())
        self.assertFalse(report.exists())


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.gan"
        self.source.write_bytes(PROJECT)
        self.recipe = self.root / "recipe.json"
        self.recipe.write_text(json.dumps(RECIPE), encoding="utf-8")
        self.out = self.root / "output.gan"
        self.receipt = self.root / "receipt.json"

    def run_cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main([str(arg) for arg in args])
        return result, stdout.getvalue(), stderr.getvalue()

    def apply_args(self):
        return ("apply", self.source, "--recipe", self.recipe, "--resource", "0",
                "--output", self.out, "--report", self.receipt)

    def test_inventory_and_unselected_preview_do_not_export(self):
        status, output, error = self.run_cli("inventory", self.source)
        self.assertEqual((status, error), (0, ""))
        self.assertEqual([r["id"] for r in json.loads(output)["resources"]], ["0", "1"])
        status, output, error = self.run_cli("preview", self.source, "--recipe", self.recipe)
        self.assertEqual((status, error), (0, ""))
        receipt = json.loads(output)
        self.assertEqual(receipt["selected_resource_ids"], [])
        self.assertEqual(receipt["addition_count"], 0)
        self.assertEqual(len(receipt["candidate_dates"]), 4)
        self.assertEqual(set(self.root.iterdir()), {self.source, self.recipe})

    def test_apply_output_receipt_hashes_and_rerun_refusal(self):
        status, output, error = self.run_cli(*self.apply_args())
        self.assertEqual((status, error), (0, ""))
        receipt = json.loads(self.receipt.read_text())
        self.assertEqual(receipt, json.loads(output))
        self.assertEqual(receipt["addition_count"], 3)
        self.assertEqual(receipt["source_sha256"], hashlib.sha256(PROJECT).hexdigest())
        self.assertEqual(receipt["output_sha256"], hashlib.sha256(self.out.read_bytes()).hexdigest())
        before = self.out.read_bytes()
        status, output, error = self.run_cli(*self.apply_args())
        self.assertEqual(status, 2)
        self.assertIn("refusing overwrite", error)
        self.assertEqual(self.out.read_bytes(), before)
        self.assertEqual(self.source.read_bytes(), PROJECT)

    def test_apply_requires_resource_selection_per_invocation(self):
        args = ("apply", self.source, "--recipe", self.recipe, "--output", self.out, "--report", self.receipt)
        with self.assertRaises(SystemExit) as caught, redirect_stderr(io.StringIO()):
            self.run_cli(*args)
        self.assertEqual(caught.exception.code, 2)
        self.assertFalse(self.out.exists())

    def test_validation_errors_create_neither_destination(self):
        self.recipe.write_text(json.dumps({**RECIPE, "resource_ids": ["0"]}))
        status, output, error = self.run_cli(*self.apply_args())
        self.assertEqual(status, 2)
        self.assertIn("resource IDs", error)
        self.assertFalse(self.out.exists())
        self.assertFalse(self.receipt.exists())

    def test_output_and_report_cannot_be_same_new_path(self):
        args = ("apply", self.source, "--recipe", self.recipe, "--resource", "0",
                "--output", self.out, "--report", self.out)
        status, _, error = self.run_cli(*args)
        self.assertEqual(status, 2)
        self.assertIn("alias", error)
        self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()

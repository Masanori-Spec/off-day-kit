"""Local file boundaries: bounded regular-file reads and exclusive new writes."""

from __future__ import annotations

import os
from pathlib import Path
import stat
from typing import Iterable

from .core import OffDayKitError


def read_regular(path: str | os.PathLike[str], limit: int) -> bytes:
    """Reject links/devices/FIFOs before opening; recheck the opened file.

    O_NONBLOCK prevents a regular-file-to-FIFO race from blocking on POSIX.
    O_NOFOLLOW prevents a final-component symlink swap where supported.
    No more than limit+1 bytes are ever requested or retained.
    """
    descriptor: int | None = None
    try:
        before = os.lstat(path)
        if not stat.S_ISREG(before.st_mode):
            raise OffDayKitError("Input must be a regular file, not a symlink, FIFO, directory or device")
        if before.st_size > limit:
            raise OffDayKitError(f"Input exceeds the {limit}-byte limit")
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise OffDayKitError("Input changed or is not a regular file")
        if opened.st_size > limit:
            raise OffDayKitError(f"Input exceeds the {limit}-byte limit")
        chunks: list[bytes] = []
        count = 0
        while count <= limit:
            chunk = os.read(descriptor, min(65_536, limit + 1 - count))
            if not chunk:
                break
            chunks.append(chunk)
            count += len(chunk)
        if count > limit:
            raise OffDayKitError(f"Input exceeds the {limit}-byte limit")
        after = os.fstat(descriptor)
        if (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise OffDayKitError("Input changed while reading; retry with a stable copy")
        return b"".join(chunks)
    except OSError as exc:
        raise OffDayKitError(f"Cannot read regular input {os.fspath(path)!r}: {exc.strerror}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def create_outputs(outputs: Iterable[tuple[str | os.PathLike[str], bytes]],
                   protected_inputs: Iterable[str | os.PathLike[str]] = ()) -> None:
    """Create each new path exclusively; never open an existing destination.

    Both paths are reserved before data is written. A detected write failure
    removes only the files this invocation created. A process/OS crash may
    leave partial new files; the original inputs are never overwritten.
    """
    items = [(Path(path), content) for path, content in outputs]
    try:
        resolved = [path.resolve() for path, _ in items]
        protected = {Path(path).resolve() for path in protected_inputs}
        if len(set(resolved)) != len(resolved) or set(resolved) & protected:
            raise OffDayKitError("Output/report paths cannot alias each other or an input")
        for path, _ in items:
            if os.path.lexists(path):
                raise OffDayKitError(f"Destination already exists; refusing overwrite: {path}")
    except (OSError, RuntimeError) as exc:
        raise OffDayKitError(f"Cannot validate destination paths: {exc}") from exc
    created: list[tuple[Path, int, tuple[int, int]]] = []
    success = False
    try:
        for path, _ in items:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            info = os.fstat(descriptor)
            created.append((path, descriptor, (info.st_dev, info.st_ino)))
        for (_, content), (_, descriptor, _) in zip(items, created):
            view = memoryview(content)
            while view:
                size = os.write(descriptor, view)
                if size <= 0:
                    raise OSError("Short write while creating output")
                view = view[size:]
            os.fsync(descriptor)
        success = True
    except OSError as exc:
        raise OffDayKitError(f"Cannot create new output files: {exc}") from exc
    finally:
        for path, descriptor, identity in created:
            os.close(descriptor)
            if not success:
                try:
                    current = os.lstat(path)
                    if (current.st_dev, current.st_ino) == identity:
                        path.unlink()
                except OSError:
                    pass

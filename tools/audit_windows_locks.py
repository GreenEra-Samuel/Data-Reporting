"""Catch, on Linux, the file-locking mistakes that only fail on Windows.

Windows refuses to delete a file another process still holds open (WinError
32). Linux allows it silently, so a test that tears down a temporary folder
while the database is still open passes here and fails on the Windows runner -
which is where this project builds and releases.

This runs the whole suite with ``TemporaryDirectory.cleanup`` patched to look
at ``/proc/self/fd`` first, and reports any folder that was removed with a file
inside it still open. CI runs it on the Linux job, which gates the Windows one,
so the mistake is caught before a build is spent on it.

    python tools/audit_windows_locks.py

Exits non-zero if anything is found. Linux only; it exits cleanly elsewhere
since there is nothing to check.
"""

from __future__ import annotations

import collections
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FD_DIR = "/proc/self/fd"

# Discovery imports the tests, which import measurelog.
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

offenders: collections.Counter = collections.Counter()
_original_cleanup = tempfile.TemporaryDirectory.cleanup


def open_files_under(folder: str) -> list[str]:
    """Files this process still has open inside ``folder``."""
    held = []
    root = os.path.realpath(folder) + os.sep
    try:
        descriptors = os.listdir(FD_DIR)
    except OSError:
        return held
    for descriptor in descriptors:
        try:
            target = os.readlink(os.path.join(FD_DIR, descriptor))
        except OSError:
            continue        # the descriptor closed while we looked
        if target.startswith(root):
            held.append(target)
    return held


def blame() -> str:
    """The test or teardown responsible, for the report."""
    frame = sys._getframe()
    while frame:
        name = frame.f_code.co_name
        if name.startswith("test") or name == "tearDown":
            return f"{os.path.basename(frame.f_code.co_filename)}:{name}"
        frame = frame.f_back
    return "unknown"


def checked_cleanup(self) -> None:
    for path in open_files_under(self.name):
        offenders[(blame(), os.path.basename(path))] += 1
    return _original_cleanup(self)


def main() -> int:
    if not os.path.isdir(FD_DIR):
        print("Not Linux - nothing to audit.")
        return 0

    tempfile.TemporaryDirectory.cleanup = checked_cleanup

    suite = unittest.TestLoader().discover(os.path.join(ROOT, "tests"))
    with open(os.devnull, "w") as quiet:
        result = unittest.TextTestRunner(verbosity=0, stream=quiet).run(suite)

    print(f"{result.testsRun} tests run "
          f"({len(result.failures)} failures, {len(result.errors)} errors)")

    # An audit over a suite that did not run proves nothing, so say so loudly
    # rather than reporting a clean result nobody should trust.
    if not result.wasSuccessful():
        print("\nThe suite did not pass, so this audit is inconclusive.")
        for case, trace in (result.errors + result.failures)[:3]:
            print(f"  {case}: {trace.strip().splitlines()[-1]}")
        return 1

    if not offenders:
        print("No temporary folder was removed with a file inside it still open.")
        return 0

    print("\nThese would fail on Windows with WinError 32:")
    for (where, name), count in offenders.most_common():
        print(f"  {where:<55} {name}  x{count}")
    print("\nClose the database or the app before the temporary folder is removed.")
    print("In a TestCase, that means tearDown closes it first; addCleanup runs")
    print("in reverse, so register the folder's cleanup before the app's.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

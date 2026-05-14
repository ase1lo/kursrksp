#!/usr/bin/env python3
import ast
import sys
import trace
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = [
    path
    for path in sorted((ROOT / "server").glob("*.py"))
    if path.name != "httpd.py"
]


def executable_lines(path):
    source = path.read_text(encoding="utf-8")
    ignored = {
        number
        for number, line in enumerate(source.splitlines(), start=1)
        if "no cover" in line
    }
    tree = ast.parse(source, filename=str(path))
    lines = {
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.stmt) and getattr(node, "lineno", None) not in ignored
    }
    return lines


def run_tests():
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)


def main():
    tracer = trace.Trace(count=True, trace=False, ignoredirs=[sys.prefix, sys.exec_prefix])
    tracer.runfunc(run_tests)
    counts = tracer.results().counts
    missing_by_file = {}
    covered_total = 0
    executable_total = 0

    for path in SOURCE_FILES:
        executable = executable_lines(path)
        covered = {
            lineno
            for (filename, lineno), count in counts.items()
            if Path(filename).resolve() == path.resolve() and count > 0
        }
        missing = sorted(executable - covered)
        executable_total += len(executable)
        covered_total += len(executable) - len(missing)
        if missing:
            missing_by_file[path.relative_to(ROOT)] = missing

    percent = 100.0 if executable_total == 0 else covered_total * 100.0 / executable_total
    print("Backend line coverage: {:.2f}% ({}/{})".format(percent, covered_total, executable_total))
    if missing_by_file:
        for path, lines in missing_by_file.items():
            print("{} missing lines: {}".format(path, ", ".join(map(str, lines))))
        sys.exit(1)
    print("Coverage gate passed: 100%")


if __name__ == "__main__":
    main()

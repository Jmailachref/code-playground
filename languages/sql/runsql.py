"""Runs a SQL submission against SQLite, like the sqlite3 shell in list mode.

stdin is the test case's setup script (CREATE TABLE, INSERT ...), which runs
first on a fresh in-memory database. Then every statement in the submitted
file runs in order, and each row a statement returns is printed with its
columns joined by "|" (NULL prints as an empty string).
"""
import sqlite3
import sys


def statements(script):
    """Split a script into complete statements, keeping semicolons in strings intact."""
    current = ""
    for line in script.splitlines(keepends=True):
        current += line
        if sqlite3.complete_statement(current):
            yield current
            current = ""
    if current.strip():
        yield current


def cell(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def main():
    db = sqlite3.connect(":memory:", isolation_level=None)
    # The sandbox's filesystem is read-only, so large sorts must not spill to temp files.
    db.execute("PRAGMA temp_store = MEMORY")
    try:
        db.executescript(sys.stdin.read())
    except sqlite3.Error as exc:
        print(f"Error in the test case setup: {exc}", file=sys.stderr)
        return 2
    with open(sys.argv[1], encoding="utf-8") as f:
        script = f.read()
    out = sys.stdout
    for number, statement in enumerate(statements(script), start=1):
        try:
            for row in db.execute(statement):
                out.write("|".join(cell(v) for v in row) + "\n")
        except sqlite3.Error as exc:
            out.flush()
            print(f"Error in statement {number}: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

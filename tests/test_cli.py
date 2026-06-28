"""Smoke tests for the ``farahidi`` command-line interface."""

from __future__ import annotations

import csv
import io
import json

import pytest

from farahidi.cli import _ANALYZE_COLUMNS, _TEXT_COLUMNS, main


# --------------------------------------------------------------------- analyze
def test_analyze_raw_default(capsys):
    assert main(["analyze", "الكتاب"]) == 0
    rows = [r for r in capsys.readouterr().out.splitlines() if r]
    assert rows  # one TAB-separated line per analysis, no header
    for row in rows:
        cells = row.split("\t")
        assert len(cells) == len(_ANALYZE_COLUMNS)
        assert cells[0] == "الكتاب"  # word repeated in column 0


def test_analyze_no_analyses_is_empty(capsys):
    assert main(["analyze", "zzz"]) == 0
    assert capsys.readouterr().out == ""  # no rows for an unanalyzable word


def test_analyze_table_has_header_and_rule(capsys):
    assert main(["analyze", "كتاب", "--format", "table"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split()[0] == "word"
    assert set(lines[1]) <= {"-", " "}  # separator rule
    assert len(lines) > 2


def test_analyze_csv(capsys):
    assert main(["analyze", "كتاب", "-f", "csv"]) == 0
    reader = list(csv.reader(io.StringIO(capsys.readouterr().out)))
    assert tuple(reader[0]) == _ANALYZE_COLUMNS
    assert len(reader) > 1
    assert all(row[0] == "كتاب" for row in reader[1:])


def test_analyze_json(capsys):
    assert main(["analyze", "كتاب", "--format", "json"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["word"] == "كتاب"
    assert obj["analyses"] and obj["analyses"][0]["lemma"]


def test_json_flag_is_alias(capsys):
    assert main(["analyze", "كتاب", "--json"]) == 0
    a = capsys.readouterr().out
    assert main(["analyze", "كتاب", "--format", "json"]) == 0
    b = capsys.readouterr().out
    assert a == b


def test_format_and_json_are_mutually_exclusive(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["analyze", "كتاب", "--json", "--format", "csv"])
    assert exc.value.code != 0


# ------------------------------------------------------------------------ text
def test_text_raw_default(capsys):
    assert main(["text", "ذهب الولد"]) == 0
    rows = [r for r in capsys.readouterr().out.splitlines() if r]
    assert len(rows) == 2
    token, lemma, stem, root, analyzed = rows[0].split("\t")
    assert token == "ذهب"
    assert lemma and stem and root
    assert analyzed in ("true", "false")


def test_text_csv(capsys):
    assert main(["text", "ذهب الولد", "-f", "csv"]) == 0
    reader = list(csv.reader(io.StringIO(capsys.readouterr().out)))
    assert tuple(reader[0]) == _TEXT_COLUMNS
    assert [row[0] for row in reader[1:]] == ["ذهب", "الولد"]


def test_text_json(capsys):
    assert main(["text", "ذهب الولد", "--format", "json"]) == 0
    objs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [o["token"] for o in objs] == ["ذهب", "الولد"]
    assert all(o["analyzed"] for o in objs)


# ----------------------------------------------------------------------- stdin
def test_analyze_reads_stdin(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("كتاب مدرسة"))
    assert main(["analyze", "--format", "csv"]) == 0
    reader = list(csv.reader(io.StringIO(capsys.readouterr().out)))
    assert {row[0] for row in reader[1:]} == {"كتاب", "مدرسة"}


def test_no_subcommand_errors():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code != 0

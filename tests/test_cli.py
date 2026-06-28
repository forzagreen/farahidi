"""Smoke tests for the ``farahidi`` command-line interface."""

from __future__ import annotations

import json

import pytest

from farahidi.cli import main


def test_analyze_human(capsys):
    assert main(["analyze", "الكتاب"]) == 0
    out = capsys.readouterr().out
    assert "analyses)" in out
    assert "lemma=" in out and "root=" in out


def test_analyze_json(capsys):
    assert main(["analyze", "كتاب", "--json"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["word"] == "كتاب"
    assert obj["analyses"]
    # JSON objects carry the full Analysis schema, Arabic script preserved.
    assert obj["analyses"][0]["lemma"]


def test_analyze_no_analyses(capsys):
    assert main(["analyze", "zzz"]) == 0
    assert "(no analyses)" in capsys.readouterr().out


def test_text_human(capsys):
    assert main(["text", "ذهب الولد"]) == 0
    rows = [r for r in capsys.readouterr().out.splitlines() if r]
    assert len(rows) == 2
    token, lemma, stem, root = rows[0].split("\t")
    assert token == "ذهب"
    assert lemma and stem and root


def test_text_json(capsys):
    assert main(["text", "ذهب الولد", "--json"]) == 0
    objs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [o["token"] for o in objs] == ["ذهب", "الولد"]
    assert all(o["analyzed"] for o in objs)


def test_analyze_reads_stdin(capsys, monkeypatch):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("كتاب مدرسة"))
    assert main(["analyze", "--json"]) == 0
    words = [json.loads(line)["word"] for line in capsys.readouterr().out.splitlines()]
    assert words == ["كتاب", "مدرسة"]


def test_no_subcommand_errors(capsys):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code != 0

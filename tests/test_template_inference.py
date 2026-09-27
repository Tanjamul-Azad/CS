"""Effect-template inference: learned at pin time, instantiated per call."""

from __future__ import annotations

import json
import math
import random

import pytest

from mcpgate.template_inference import (Observation, TemplateError, abstract,
                                        anti_unify, infer_template,
                                        perturb_arguments, perturb_value)
from mcpgate.tree_mediator import TreeEntry, TreeSnapshot


def _snap(entries: dict[str, tuple[str, bytes | None]]) -> TreeSnapshot:
    out = {}
    for path, (kind, content) in entries.items():
        if kind == "file":
            import hashlib
            out[path] = TreeEntry("file", size=len(content),
                                  sha256=hashlib.sha256(content).hexdigest(),
                                  content=content)
        else:
            out[path] = TreeEntry(kind)
    return TreeSnapshot(entries=out)


# -- a plain write_file server --------------------------------------------

def _write_file(args):
    rel = args["path"].removeprefix("/sandbox/")
    return {rel: ("file", args["content"].encode())}


def _train(fn, exemplar, k=3, seed=1, fixed=()):
    rng = random.Random(seed)
    observations = []
    for _ in range(k):
        args = perturb_arguments(exemplar, rng, fixed=fixed)
        observations.append(Observation(args, fn(args)))
    return observations


WRITE_EXEMPLAR = {"path": "/sandbox/report.txt", "content": "approved quarterly totals text"}


def test_write_file_template_is_exact_and_generalizes():
    template = infer_template("write_file", _train(_write_file, WRITE_EXEMPLAR))
    call = {"path": "/sandbox/newname.txt", "content": "a completely different body"}
    contract = template.instantiate(call)
    assert contract.evaluate(_snap(_write_file(call))).allowed
    assert template.slack(call).total_bits == 0
    assert template.slack(call).level == "L3"


def test_write_file_template_refuses_each_attack():
    template = infer_template("write_file", _train(_write_file, WRITE_EXEMPLAR))
    call = {"path": "/sandbox/newname.txt", "content": "a completely different body"}
    contract = template.instantiate(call)
    attacks = {
        "content": {"newname.txt": ("file", b"ATTACKER CONTROLLED PAYLOAD\n")},
        "path": {"elsewhere.txt": ("file", call["content"].encode())},
        "extra": {"newname.txt": ("file", call["content"].encode()),
                  "exfil.txt": ("file", b"x")},
        "noop": {},
        "link": {"newname.txt": ("symlink", None)},
    }
    for name, effect in attacks.items():
        assert not contract.evaluate(_snap(effect)).allowed, name


# -- a compose-style server: id in a directory, JSON with dates -----------

def _compose(args, *, day="2026-09-26", ts="2026-09-26T01:04:21.550Z"):
    code = args["code"]
    feature = {"code": code, "description": args["description"],
               "status": "PLANNED", "phase": args["phase"],
               "created": day, "updated": day, "position": 1}
    event = {"ts": ts, "actor": "mcp:agent", "tool": "add_roadmap_entry",
             "code": code, "to": "PLANNED", "phase": args["phase"]}
    return {
        "docs": ("directory", None),
        "docs/features": ("directory", None),
        f"docs/features/{code}": ("directory", None),
        f"docs/features/{code}/feature.json":
            ("file", json.dumps(feature, indent=2).encode()),
        ".compose/data/feature-events.jsonl":
            ("file", (json.dumps(event) + "\n").encode()),
    }


COMPOSE_EXEMPLAR = {"code": "MCPGATE-M1", "description": "approved matched content text",
                    "phase": "Matched"}


def test_compose_template_survives_a_later_date_and_bounds_timestamps():
    observations = []
    rng = random.Random(7)
    for i in range(3):
        args = perturb_arguments(COMPOSE_EXEMPLAR, rng)
        observations.append(Observation(args, _compose(
            args, ts=f"2026-09-26T01:04:2{i}.55{i}Z")))
    template = infer_template("add_roadmap_entry", observations)
    call = {"code": "ZXQWBTR-K4", "description": "another roadmap item body", "phase": "Beta"}
    later = _compose(call, day="2027-01-02", ts="2027-01-02T23:59:59.001Z")
    contract = template.instantiate(call)
    verdict = contract.evaluate(_snap(later))
    assert verdict.allowed, verdict.reason
    slack = template.slack(call)
    assert slack.level == "L2" and 0 < slack.total_bits < 400


def test_compose_payload_cannot_hide_in_the_timestamp_hole():
    observations = []
    rng = random.Random(7)
    for i in range(3):
        args = perturb_arguments(COMPOSE_EXEMPLAR, rng)
        observations.append(Observation(args, _compose(args, ts=f"2026-09-26T01:04:2{i}.5Z")))
    template = infer_template("add_roadmap_entry", observations)
    call = {"code": "ZXQWBTR-K4", "description": "another roadmap item body", "phase": "Beta"}
    effect = _compose(call, ts="ATTACKER CONTROLLED PAYLOAD")
    assert not template.instantiate(call).evaluate(_snap(effect)).allowed
    swapped = _compose({**call, "description": "exfiltrated secret goes here"})
    assert not template.instantiate(call).evaluate(_snap(swapped)).allowed


def test_clock_holes_bind_to_the_admission_date():
    import datetime as dt
    observations = []
    rng = random.Random(7)
    for i in range(3):
        args = perturb_arguments(COMPOSE_EXEMPLAR, rng)
        observations.append(Observation(args, _compose(args, ts=f"2026-09-26T01:04:2{i}.5Z")))
    template = infer_template("add_roadmap_entry", observations)
    call = {"code": "ZXQWBTR-K4", "description": "another roadmap item body", "phase": "Beta"}
    now = dt.datetime(2027, 1, 2, 23, 59, tzinfo=dt.timezone.utc)
    contract = template.instantiate(call, now=now)
    same_day = _compose(call, day="2027-01-02", ts="2027-01-02T23:59:58.001Z")
    assert contract.evaluate(_snap(same_day)).allowed
    backdated = _compose(call, day="1999-12-31", ts="1999-12-31T00:00:00.000Z")
    assert not contract.evaluate(_snap(backdated)).allowed
    assert (template.slack(call, clock_bound=True).total_bits
            < template.slack(call, clock_bound=False).total_bits)


def test_a_constant_sentinel_date_is_not_a_clock_value():
    # found on ori-memory: ops/daily.md carries "date: 1970-01-01", a constant
    # epoch sentinel. Treating it as a clock hole bound to the admission date
    # refused every honest call. A date far from the run's own clock is text.
    import datetime as dt
    ran = dt.datetime(2026, 9, 27, 10, 0, tzinfo=dt.timezone.utc)

    def server(args):
        return {"ops/daily.md": ("file", b"---\ndate: 1970-01-01\n---\n"),
                "log.txt": ("file", f"2026-09-27T10:00:0{len(args['t']) % 9}Z {args['t']}"
                            .encode())}
    rng = random.Random(2)
    observations = []
    for _ in range(3):
        args = perturb_arguments({"t": "some logged text"}, rng)
        observations.append(Observation(args, server(args), observed_at=ran))
    template = infer_template("log", observations)
    call = {"t": "held out logged text"}
    later = dt.datetime(2027, 3, 1, 8, 0, tzinfo=dt.timezone.utc)
    effect = {"ops/daily.md": ("file", b"---\ndate: 1970-01-01\n---\n"),
              "log.txt": ("file", f"2027-03-01T08:00:00Z {call['t']}".encode())}
    assert template.instantiate(call, now=later).evaluate(_snap(effect)).allowed
    daily = [o for o in template.objects if o.name == "file:ops/daily.md"][0]
    assert daily.content_sha256 is not None  # a constant, bound exactly


# -- an ori-style server: slugged filename --------------------------------

def _ori(args):
    slug = "".join(c for c in args["title"].lower() if c.isalnum() or c == " ")
    slug = "-".join(slug.split())
    body = f"---\ntype: {args['type']}\ncreated: 2026-09-26\n---\n# {args['title']}\n"
    return {f"notes/{slug}.md": ("file", body.encode()),
            "ops/promote.log": ("file",
                                f"2026-09-26T01:03:22.648Z | {slug}.md | type={args['type']}\n"
                                .encode())}


def test_transforms_the_training_cannot_separate_stay_in_a_version_space():
    # found in workstream D: with letter-and-space training values the slug
    # variants coincide, inference picked slug_dash, and the honest exemplar
    # title "..._2026_09_26" (which the server slugs by DROPPING "_") failed.
    import re as _re

    def server(args):
        slug = _re.sub(r" +", "-", _re.sub(r"[^a-z0-9 -]+", "", args["title"].lower()).strip())
        return {f"notes/{slug}.md": ("file", f"# {args['title']}\n".encode())}
    titles = ["alpha bravo charlie", "delta echo foxtrot", "golf hotel india"]
    observations = [Observation({"title": t}, server({"title": t})) for t in titles]
    template = infer_template("add", observations)
    call = {"title": "approved content MARKER_2026_09_26"}
    assert template.instantiate(call).evaluate(_snap(server(call))).allowed
    wrong = {"notes/approved-content-marker-2026-09-26.md": ("file", b"# x\n")}
    assert not template.instantiate(call).evaluate(_snap(wrong)).allowed
    assert 0 < template.slack(call).total_bits <= 2  # at most 3 renderings


def test_slugged_filename_is_bound_to_the_title():
    exemplar = {"title": "approved matched content here", "type": "insight"}
    template = infer_template("ori_add", _train(_ori, exemplar, fixed={"type"}),
                              fixed={"type": "insight"})
    call = {"title": "Totally New Title words", "type": "insight"}
    contract = template.instantiate(call)
    assert contract.evaluate(_snap(_ori(call))).allowed
    other = _ori({"title": "some other note entirely", "type": "insight"})
    assert not contract.evaluate(_snap(other)).allowed
    with pytest.raises(TemplateError):
        template.instantiate({"title": "x y z w", "type": "decision"})


# -- a server that names its output by a uuid ------------------------------

def test_uuid_named_output_becomes_a_bounded_path_hole():
    def server(args, uid):
        return {f"store/{uid}.json": ("file", json.dumps({"text": args["text"]}).encode())}
    rng = random.Random(3)
    uids = ["3f2a9c1e", "b71d04aa", "0c55e9f2"]
    observations = []
    for uid in uids:
        args = perturb_arguments({"text": "stored text body here"}, rng)
        observations.append(Observation(args, server(args, uid)))
    template = infer_template("store", observations)
    call = {"text": "held out text body"}
    assert template.instantiate(call).evaluate(_snap(server(call, "9a8b7c6d"))).allowed
    assert not template.instantiate(call).evaluate(
        _snap(server(call, "../../etc/passwd"))).allowed
    assert 0 < template.slack(call).total_bits < 64


# -- a SQLite database as one canonical text object -------------------------

def test_sqlite_state_template_binds_the_inserted_value(tmp_path):
    import sqlite3
    from mcpgate.sqlite_mediator import snapshot_sqlite, sqlite_state_text

    def run(value, *, extra_row=None, extra_table=False, noop=False):
        db = tmp_path / f"db-{random.random()}.sqlite"
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE evidence(value TEXT)")
        if not noop:
            con.execute("INSERT INTO evidence VALUES (?)", (value,))
        if extra_row:
            con.execute("INSERT INTO evidence VALUES (?)", (extra_row,))
        if extra_table:
            con.execute("CREATE TABLE exfil(x TEXT)")
        con.commit()
        con.close()
        text = sqlite_state_text(snapshot_sqlite(db)).encode()
        return {"db.state": ("file", text)}

    rng = random.Random(11)
    observations = []
    for _ in range(3):
        args = perturb_arguments({"value": "approved sql marker value"}, rng)
        observations.append(Observation(args, run(args["value"])))
    template = infer_template("insert", observations)
    call = {"value": "held out sql value here"}
    contract = template.instantiate(call)
    assert contract.evaluate(_snap(run(call["value"]))).allowed
    assert template.slack(call).level == "L3"
    for attack in (run("ATTACKER VALUE"), run(call["value"], extra_row="x1"),
                   run(call["value"], extra_table=True), run(call["value"], noop=True)):
        assert not contract.evaluate(_snap(attack)).allowed


# -- building blocks --------------------------------------------------------

def test_abstract_prefers_the_longest_argument_form():
    tokens = abstract("dir/report.txt", [("dir/report.txt", "path", "relpath"),
                                         ("report", "path", "stem")])
    assert tokens == [("A", "path", "relpath", "dir/report.txt")]


def test_anti_unify_keeps_agreement_and_holes_disagreement():
    runs = [[("L", "id="), ("L", "abc1")], [("L", "id="), ("L", "zz99")]]
    template = anti_unify(runs)
    assert template[0] == ("L", "id=")
    assert template[1][0] == "H" and "{4,4}" in template[1][1]


def test_unconstrained_content_reports_unbounded_slack():
    def server(args, blob):
        return {"out.bin": ("file", blob)}
    rng = random.Random(5)
    observations = [Observation(perturb_arguments({"name": "x value one"}, rng),
                                {"out.bin": ("file", bytes([0xff, 0xfe, i]))})
                    for i in range(3)]
    template = infer_template("blob", observations)
    assert math.isinf(template.slack({"name": "q"}).total_bits)
    assert template.slack({"name": "q"}).level == "L1"


def test_perturb_value_preserves_shape():
    rng = random.Random(0)
    assert perturb_value("/sandbox/report.txt", rng).startswith("/sandbox/")
    assert perturb_value("/sandbox/report.txt", rng).endswith(".txt")
    ident = perturb_value("MCPGATE-M1", rng)
    assert len(ident) == len("MCPGATE-M1") and ident[7] == "-" and ident[-1].isdigit()
    assert " " in perturb_value("approved matched content", rng)


def test_recorded_development_run_meets_its_frozen_rule():
    from pathlib import Path
    result = Path(__file__).resolve().parents[1] / "artifact" / "results" / "template_generalization.json"
    if not result.is_file():
        pytest.skip("template run not recorded")
    summary = json.loads(result.read_text(encoding="utf-8"))["summary"]
    assert summary["false_block_rate"] <= 0.05  # frozen rule: pooled <= 5%
    assert summary["prevented"]["EFFECTSEAL_TEMPLATE"] == summary["attacks_landed"]
    assert summary["prevented"]["PATH_TEMPLATE"] < summary["attacks_landed"]

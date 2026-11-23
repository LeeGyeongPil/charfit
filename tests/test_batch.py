"""AC-3: check --jsonl - many texts at once, with totals the agent can quote without adding up."""
import json

import pytest
from conftest import PARTY, rules, run_cli, run_json

FIVE = [
    {"id": "en-otp", "text": "Your code is 4821"},
    {"id": "es-otp", "text": "Tu código es 4821"},
    {"text": "a" * 161},
    {"id": "euro", "text": "a" * 152 + "€" + "a" * 152},
    {"id": "emoji", "text": "a" * 66 + PARTY + "a" * 5},
]
HELLO = "안녕하세요"
KOREAN = [
    {"text": HELLO * 9},
    {"text": HELLO * 9 + "!"},
    {"text": "똠방각하"},
    {"text": "할인 쿠폰 " + PARTY + " 지금 확인"},
    {"text": "가" * 1000 + "a"},
]


def write_jsonl(path, rows, blank_lines=False):
    lines = []
    for row in rows:
        lines.append(json.dumps(row, ensure_ascii=False))
        if blank_lines:
            lines.append("   ")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def test_sms_totals_for_five_lines(tmp_path):
    proc, data = run_json("check", "--profile", "sms", "--jsonl", write_jsonl(tmp_path / "t.jsonl", FIVE))
    assert proc.returncode == 1
    assert data["pass"] is False
    assert data["totals"] == {
        "items": 5, "pass": 2, "fail": 3, "failed_ids": ["3", "euro", "emoji"],
        "by_profile": {"sms": {"pass": 2, "fail": 3}},
        "sms": {"segments": 9, "gsm7": 3, "ucs2": 2, "multi_segment": 3},
    }
    assert [i["id"] for i in data["items"]] == ["en-otp", "es-otp", "3", "euro", "emoji"]
    assert [i["line"] for i in data["items"]] == [1, 2, 3, 4, 5]
    assert data["items"][3]["results"][0]["segment_starts"] == [0, 152, 304]
    assert data["items"][1]["results"][0]["culprits"][0]["codepoint"] == "U+00F3"
    assert list(data["items"][0]) == ["id", "line", "pass", "length", "results"]


def test_korean_classes_for_five_lines(tmp_path):
    proc, data = run_json("check", "--profile", "kr-sms", "--jsonl", write_jsonl(tmp_path / "k.jsonl", KOREAN))
    assert proc.returncode == 1
    t = data["totals"]
    assert t["kr_class"] == {"SMS": 1, "LMS": 1, "OVER": 1, "FAIL": 2}
    assert (t["pass"], t["fail"]) == (1, 4) and "sms" not in t
    assert [i["kr_class"] for i in data["items"]] == ["SMS", "LMS", "FAIL", "FAIL", "OVER"]


def test_two_profiles_count_each_and_all_pass_gives_exit_zero(tmp_path):
    path = write_jsonl(tmp_path / "ok.jsonl", [{"id": 7, "text": "Hello"}, {"id": "b", "text": "안녕"}])
    proc, data = run_json("check", "--profile", "sms,kr-sms", "--jsonl", path)
    assert proc.returncode == 0 and data["pass"] is True
    assert data["totals"]["by_profile"] == {"sms": {"pass": 2, "fail": 0}, "kr-sms": {"pass": 2, "fail": 0}}
    assert data["totals"]["sms"] == {"segments": 2, "gsm7": 1, "ucs2": 1, "multi_segment": 0}
    assert data["totals"]["kr_class"] == {"SMS": 2, "LMS": 0, "OVER": 0, "FAIL": 0}
    assert data["items"][0]["id"] == "7"          # an integer id becomes a string


def test_blank_lines_are_skipped_and_line_numbers_are_physical(tmp_path):
    proc, data = run_json("check", "--profile", "sms", "--jsonl",
                          write_jsonl(tmp_path / "b.jsonl", FIVE, blank_lines=True))
    assert data["totals"]["items"] == 5
    assert [i["line"] for i in data["items"]] == [1, 3, 5, 7, 9]
    assert data["totals"]["failed_ids"] == ["5", "euro", "emoji"]   # the id-less item is on line 5


def test_batch_equals_single_runs(tmp_path):
    """Each item gets exactly what a single check of that text gives."""
    _, batch = run_json("check", "--profile", "sms,utf8:40", "--jsonl", write_jsonl(tmp_path / "s.jsonl", FIVE))
    for row, item in zip(FIVE, batch["items"]):
        _, single = run_json("check", "--profile", "sms,utf8:40", row["text"])
        assert item["results"] == single["results"] and item["length"] == single["length"]


def test_crlf_line_endings_and_bom(tmp_path):
    path = tmp_path / "w.jsonl"
    path.write_bytes(b"\xef\xbb\xbf" + "\r\n".join(json.dumps(r) for r in FIVE[:2]).encode() + b"\r\n")
    _, data = run_json("check", "--profile", "sms", "--jsonl", str(path))
    assert [i["id"] for i in data["items"]] == ["en-otp", "es-otp"]


def test_human_output_has_item_lines_and_totals(tmp_path):
    path = write_jsonl(tmp_path / "h.jsonl", FIVE)
    out = run_cli("check", "--profile", "sms", "--jsonl", path, "--lang", "en").stdout
    assert "FAIL euro (line 4): sms 3 SMS segment(s) (GSM-7, 306 units, parts start at index 0, 152, 304)" in out
    assert "index 4 'ó' U+00F3" in out
    assert "Total: 5 items, 2 pass all profiles, 3 fail a profile" in out
    assert "Total SMS: 9 segments billed; 3 GSM-7 items, 2 UCS-2 items, 3 items with 2+ segments" in out
    ko = run_cli("check", "--profile", "kr-sms", "--jsonl", write_jsonl(tmp_path / "k.jsonl", KOREAN),
                 "--lang", "ko").stdout
    # the profile pass count is not the carrier FAIL class, so the total line does not call it 실패
    assert "합계: 항목 5개, 모든 프로필 통과 1, 통과 못 함 4" in ko and "통과 1, 실패 4" not in ko
    assert "합계 국내 구분: SMS 1개, LMS 1개, OVER 1개(2,000바이트 초과), FAIL 2개(발송 실패)" in ko


def test_human_output_caps_culprits_per_item(tmp_path):
    path = write_jsonl(tmp_path / "c.jsonl", [{"id": "ko", "text": "가나다라마바"}])
    out = run_cli("check", "--profile", "sms", "--jsonl", path, "--lang", "en").stdout
    assert out.count("not in GSM-7") == 3 and "... and 3 more" in out


@pytest.mark.parametrize("content,message", [
    ('{"text": "ok"}\n{"text": "broken"\n', "charfit: error: '{P}' line 2 is not valid JSON"),
    ('{"text": "ok"}\n\n{"id": "x"}\n', "charfit: error: '{P}' line 3 has no \"text\" string"),
    ('["just", "a list"]\n', "charfit: error: '{P}' line 1 has no \"text\" string"),
    ('{"text": 5}\n', "charfit: error: '{P}' line 1 has no \"text\" string"),
    ('{"id": [1], "text": "x"}\n', "charfit: error: '{P}' line 1 has an \"id\" that is not a string or an integer"),
    ('{"id": true, "text": "x"}\n', "charfit: error: '{P}' line 1 has an \"id\" that is not a string or an integer"),
    ('{"text": "a\\ud800b"}\n', "charfit: error: '{P}' line 1 has a lone surrogate in \"text\""),
    ('\n  \n', "charfit: error: '{P}' has no items (every line is blank)"),
])
def test_broken_jsonl_is_a_usage_error_with_the_line(tmp_path, content, message):
    path = tmp_path / "bad.jsonl"
    path.write_text(content, encoding="utf-8")
    for command in (["check", "--profile", "sms"], ["fix-sms"]):
        proc = run_cli(*command, "--jsonl", str(path), "--lang", "en")
        assert proc.returncode == 2 and proc.stdout == ""
        assert proc.stderr.strip() == message.replace("{P}", str(path))
        assert "Traceback" not in proc.stderr


def test_jsonl_file_errors_reuse_the_file_messages(tmp_path):
    proc = run_cli("check", "--profile", "sms", "--jsonl", str(tmp_path / "none.jsonl"), "--lang", "en")
    assert proc.returncode == 2 and "not found" in proc.stderr
    bad = tmp_path / "bin.jsonl"
    bad.write_bytes(b'{"text": "\xff"}\n')
    proc = run_cli("check", "--profile", "sms", "--jsonl", str(bad), "--lang", "en")
    assert proc.returncode == 2 and "is not valid UTF-8 (byte offset 10)" in proc.stderr


@pytest.mark.parametrize("extra", [["TEXT"], ["--file", "F"], ["-"]])
def test_jsonl_with_another_input_is_a_usage_error(tmp_path, extra):
    path = write_jsonl(tmp_path / "x.jsonl", FIVE[:1])
    other = tmp_path / "t.txt"
    other.write_text("hi", encoding="utf-8")
    extra = [str(other) if a == "F" else ("hello" if a == "TEXT" else a) for a in extra]
    for command in (["check", "--profile", "sms"], ["fix-sms"]):
        proc = run_cli(*command, "--jsonl", path, *extra, "--lang", "en")
        assert proc.returncode == 2
        assert proc.stderr.strip() == "charfit: error: give only one of TEXT, '-', --file or --jsonl"


def test_count_has_no_jsonl_option():
    proc = run_cli("count", "--jsonl", "x.jsonl", "--lang", "en")
    assert proc.returncode == 2 and "unrecognized arguments" in proc.stderr


def test_check_many_in_process_matches_the_documented_shape():
    items = [{"id": str(n), "line": n, "text": r["text"]} for n, r in enumerate(FIVE, 1)]
    r = rules.check_many(items, "sms")
    assert set(r) == {"pass", "items", "totals"}
    assert set(r["totals"]) == {"items", "pass", "fail", "failed_ids", "by_profile", "sms"}

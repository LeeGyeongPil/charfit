"""AC-4: fix-sms proposes a GSM-7 candidate and never edits the input; --jsonl adds totals."""
import json

import pytest
from conftest import PARTY, rules, run_cli, run_json

SAMPLE = "It’s ready… — see you"


def test_three_replacements_make_the_message_gsm7():
    r = rules.fix_sms(SAMPLE)
    assert r["candidate"] == "It's ready... - see you"
    assert r["replacements"] == [{"index": 2, "from": "’", "to": "'"},
                                 {"index": 10, "from": "…", "to": "..."},
                                 {"index": 12, "from": "—", "to": "-"}]
    assert r["before"]["encoding"] == "UCS-2"
    assert (r["after"]["encoding"], r["after"]["segments"]) == ("GSM-7", 1)
    assert r["remaining"] == []


def test_cli_exit_zero_when_candidate_is_gsm7():
    proc, data = run_json("fix-sms", SAMPLE)
    assert proc.returncode == 0
    assert list(data) == ["candidate", "replacements", "before", "after", "remaining"]
    assert data["candidate"] == "It's ready... - see you"


def test_nfd_accent_is_composed():
    r = rules.fix_sms("café")
    assert r["candidate"] == "café"
    assert r["replacements"] == [{"index": 3, "from": "é", "to": "é"}]
    assert r["after"]["encoding"] == "GSM-7"


def test_unfixable_characters_remain_and_exit_one():
    text = "Café " + PARTY + " “now”"
    r = rules.fix_sms(text)
    assert r["candidate"] == 'Café ' + PARTY + ' "now"'
    assert r["after"]["encoding"] == "UCS-2"
    assert [c["char"] for c in r["remaining"]] == [PARTY]
    assert r["remaining"][0]["index"] == 5          # index inside the candidate
    proc, data = run_json("fix-sms", text)
    assert proc.returncode == 1 and data["remaining"][0]["codepoint"] == "U+1F389"


@pytest.mark.parametrize("space", ["\u00a0", "\u2003", "\u2009", "\u202f", "\u3000"])
def test_special_spaces_become_plain_spaces(space):
    r = rules.fix_sms("a" + space + "b")
    assert r["candidate"] == "a b" and r["replacements"][0]["index"] == 1


def test_accent_outside_gsm7_stays():
    r = rules.fix_sms("á")            # composes to U+00E1, which is not in GSM-7
    assert r["candidate"] == "á" and r["after"]["encoding"] == "UCS-2"


def test_input_is_never_modified_and_clean_text_needs_nothing():
    original = SAMPLE
    rules.fix_sms(original)
    assert original == "It’s ready… — see you"
    r = rules.fix_sms("Hello world")
    assert r["candidate"] == "Hello world" and r["replacements"] == []


def test_input_file_is_not_touched(tmp_path):
    path = tmp_path / "msg.txt"
    path.write_text(SAMPLE + "\n", encoding="utf-8")
    proc, _ = run_json("fix-sms", "--file", str(path))
    assert proc.returncode == 0
    assert path.read_text(encoding="utf-8") == SAMPLE + "\n"


def test_empty_text():
    r = rules.fix_sms("")
    assert r["candidate"] == "" and r["after"]["segments"] == 0


# --------------------------------------------------------------------------
# fix-sms --jsonl (AC-4): the cleanup is measured again, and totals add up the items
# --------------------------------------------------------------------------
BATCH = [
    SAMPLE,                                  # three replacements, GSM-7
    "cafe\N{COMBINING ACUTE ACCENT}",        # decomposed accent, recomposed to GSM-7
    "Café " + PARTY + " “now”",              # quotes fixed, the emoji stays: still UCS-2
    "a" * 158 + "…",                         # UCS-2 159 units (3 parts) -> GSM-7 161 units (2 parts)
]


def _write(tmp_path, texts):
    path = tmp_path / "campaign.jsonl"
    path.write_text("\n".join(json.dumps({"text": t}, ensure_ascii=False) for t in texts) + "\n", encoding="utf-8")
    return path


def test_batch_totals_and_exit_code(tmp_path):
    path = _write(tmp_path, BATCH)
    before_bytes = path.read_bytes()
    proc, data = run_json("fix-sms", "--jsonl", str(path))
    assert proc.returncode == 1
    assert data["totals"] == {
        "items": 4, "changed": 4, "replacements": 7,
        "before": {"segments": 6, "gsm7": 0, "ucs2": 4},
        "after": {"segments": 5, "gsm7": 3, "ucs2": 1},
        "still_ucs2_ids": ["3"],
    }
    last = data["items"][3]
    assert last["before"] == {"encoding": "UCS-2", "units": 159, "segments": 3}
    assert last["after"] == {"encoding": "GSM-7", "units": 161, "segments": 2}
    assert list(last) == ["id", "line", "candidate", "replacements", "before", "after", "remaining"]
    assert path.read_bytes() == before_bytes          # the input file is never edited


def test_batch_items_equal_single_runs(tmp_path):
    _, data = run_json("fix-sms", "--jsonl", str(_write(tmp_path, BATCH)))
    for text, item in zip(BATCH, data["items"]):
        _, single = run_json("fix-sms", text)
        assert {k: item[k] for k in single} == single


def test_batch_exit_zero_when_every_candidate_is_gsm7(tmp_path):
    proc, data = run_json("fix-sms", "--jsonl", str(_write(tmp_path, BATCH[:2] + ["Hello"])))
    assert proc.returncode == 0
    assert data["totals"]["still_ucs2_ids"] == [] and data["totals"]["changed"] == 2


def test_regrowth_is_counted_not_assumed_away():
    """'…' (1 unit in UCS-2) becomes '...' (3 units): 159 -> 161 crosses the 160 GSM-7 limit."""
    r = rules.fix_many([{"id": "x", "line": 1, "text": "a" * 158 + "…"}])
    assert r["totals"]["after"]["segments"] == 2


def test_batch_human_output_in_both_languages(tmp_path):
    path = str(_write(tmp_path, BATCH))
    en = run_cli("fix-sms", "--jsonl", path, "--lang", "en").stdout
    assert "4 (line 4): 1 replacement(s); before UCS-2 159 units 3 segment(s), after GSM-7 161 units 2 segment(s)" in en
    assert "Total after cleanup: 5 segments; 3 GSM-7, 1 UCS-2" in en and "Still UCS-2 after cleanup: 3" in en
    ko = run_cli("fix-sms", "--jsonl", path, "--lang", "ko").stdout
    assert "합계(정리 후): 5건, GSM-7 3개, UCS-2 1개" in ko and "정리 후에도 UCS-2 인 항목: 3" in ko

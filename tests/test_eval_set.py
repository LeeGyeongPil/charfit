"""AC-9: the evaluation set is an artifact too - its shape, fixtures, graded values and regexes.

Design rules (plan v2, 7.1) checked here:
* every task except the error case measures a batch of >= 15 items or a text of >= 600 code points;
* every graded number is a field the script prints (totals, segments, segment_starts), never model arithmetic;
* the naive baselines N1-N6 (tests/naive_baselines.py) get the designated values wrong and fail those graders;
* an answer off by one fails; the same values in English, Korean, a table, a list or the script's own
  wording pass; graded numbers do not collide with each other or with numbers in the prompt or fixture;
* every rule mutation of the script changes at least one graded value; lowercase ç changes none;
* a count the agent writes for itself when the script is broken (N1, N2, N7, N9, N10: a wrong alphabet
  table, division, an over-eager cleanup; N3, N4: Python's euc_kr or cp949 codec) gets at least two of the
  three graded values wrong, so such a run scores below the pass mark even with the script-ran grader;
* the Korean prompts say what a user says ("국내 통신사"), not the rule (strict KS X 1001): knowing that
  rule is what the skill adds, and the Python codecs a model reaches for without it get the values wrong.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Dict, List

import naive_baselines as nb
import pytest
from conftest import ROOT, clean_env, rules, run_cli, run_json

EVALS = ROOT / "evals"
FIXTURES = EVALS / "fixtures"
NEW_TASKS = ["task-kr-batch", "task-kr-lms-notice", "task-sms-fix-batch", "task-sms-locales"]


def front(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    out = {}
    for line in text.split("---\n")[1].splitlines():
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip()
    return out


def body(path: Path) -> str:
    return path.read_text(encoding="utf-8").split("---\n", 2)[2]


def cases(prefix: str):
    return sorted(p for p in EVALS.iterdir() if p.is_dir() and p.name.startswith(prefix))


def pattern_of(grader: Path) -> str:
    return front(grader)["pattern"].strip("'")


def grader(case: str, name: str) -> str:
    return pattern_of(EVALS / case / "graders" / (name + ".md"))


def graders_of(case: str) -> Dict[str, str]:
    return {g.stem: pattern_of(g) for g in sorted((EVALS / case / "graders").glob("value-*.md"))}


def jsonl_items(case: str, name: str) -> List[dict]:
    lines = (FIXTURES / case / name).read_text(encoding="utf-8").split("\n")
    return [dict(json.loads(l), line=n) for n, l in enumerate(lines, 1) if l.strip()]


def notice() -> str:
    text = (FIXTURES / "task-kr-lms-notice" / "notice.txt").read_text(encoding="utf-8")
    return text[:-1] if text.endswith("\n") else text


# --------------------------------------------------------------------------
# Shape of the set
# --------------------------------------------------------------------------

def test_eval_set_counts():
    trigger = cases("trigger-")
    near = cases("notrigger-near-")
    far = [p for p in cases("notrigger-") if not p.name.startswith("notrigger-near-")]
    tasks = cases("task-")
    korean = [p for p in trigger if re.search(r"[가-힣]", body(p / "prompt.md"))]
    assert len(trigger) >= 12 and len(korean) >= 4
    assert len(near) + len(far) >= 12 and len(near) >= 8
    assert [p.name for p in tasks] == ["task-error-kakao"] + NEW_TASKS
    for case in trigger + near + far + tasks:
        assert front(case / "prompt.md")["name"] == case.name


def test_no_task_grades_x():
    """X counting depends on a reference library and clients that disagree, so no task grades it."""
    for case in cases("task-"):
        assert not case.name.startswith("task-x-")
        assert not re.search(r"x-post|\bX post|\bon X\b|tweet|twitter|\b280\b", body(case / "prompt.md"), re.I), case


def test_korean_prompts_ask_like_a_user_and_do_not_state_the_rule():
    """The carrier rule (strict KS X 1001, so Python's codecs are wrong) is what the skill knows; a prompt
    that spells it out lets any model answer without the skill."""
    for case in ("task-kr-batch", "task-kr-lms-notice"):
        text = body(EVALS / case / "prompt.md")
        assert "국내 통신사" in text, case
        for hint in ("KS X", "EUC", "CP949", "완성형", "엄격", "인코딩"):
            assert hint.lower() not in text.lower(), (case, hint)


def test_trigger_prompts_do_not_name_the_skill():
    for case in cases("trigger-"):
        text = body(case / "prompt.md").lower()
        assert "charfit" not in text and "skill" not in text and "스킬" not in text, case.name


def test_graders_by_kind():
    for case in cases("trigger-"):
        g = front(case / "graders" / "skill-fired.md")
        assert g["type"] == "tool_used" and g["tool"] == "Skill" and "charfit" in g["input_match"]
        assert g["arm"] == "both"
    for case in cases("notrigger-"):
        g = front(case / "graders" / "skill-not-fired.md")
        assert g["max"] == "0" and "charfit" in g["input_match"]
    for case in cases("task-"):
        ran = front(case / "graders" / "script-ran.md")
        assert ran["arm"] == "with-only" and "charfit" in ran["input_match"]
        assert not (case / "graders" / "skill-fired.md").exists()
    for case in NEW_TASKS:
        assert 3 <= len(graders_of(case)) <= 4, case


def test_regexes_are_javascript_safe_and_not_trivial():
    for g in EVALS.glob("task-*/graders/value-*.md"):
        pat = pattern_of(g)
        re.compile(pat)
        assert len(pat) >= 6 and not any(tok in pat for tok in ("(?P<", "\\A", "\\Z", "\\\\", "'")), g


def test_every_task_has_fixtures_named_in_its_prompt():
    for case in cases("task-"):
        files = [p for p in (FIXTURES / case.name).iterdir() if p.is_file()]
        assert files, case.name
        for f in files:
            assert f.name in body(case / "prompt.md"), (case.name, f.name)


def test_fixtures_have_scale():
    """No single short string: a batch of >= 15 items or one text of >= 600 code points."""
    assert len(jsonl_items("task-sms-locales", "templates.jsonl")) == 24
    assert len(jsonl_items("task-sms-fix-batch", "campaign.jsonl")) == 20
    assert len(jsonl_items("task-kr-batch", "notices.jsonl")) == 25
    assert 600 <= len(notice())
    for item in jsonl_items("task-sms-locales", "templates.jsonl"):
        assert 60 <= len(item["text"]) <= 200, item["id"]


def test_fixtures_contain_the_planned_traps():
    locales = {i["id"]: rules.sms_analyze(i["text"]) for i in jsonl_items("task-sms-locales", "templates.jsonl")}
    texts = {i["id"]: i["text"] for i in jsonl_items("task-sms-locales", "templates.jsonl")}
    gsm_accents = [k for k, r in locales.items() if r["encoding"] == "GSM-7" and 71 <= r["units"] <= 160
                   and any(ord(c) > 0x7F for c in texts[k])]
    one_latin1_accent = [k for k, r in locales.items() if r["encoding"] == "UCS-2" and 71 <= r["units"] <= 160
                         and all(ord(c["char"]) <= 0xFF for c in r["culprits"])]
    emoji_at_boundary = [k for k, r in locales.items() if r["encoding"] == "UCS-2" and r["boundary_extra"] > 0]
    extension_over_160 = [k for k, r in locales.items() if r["encoding"] == "GSM-7" and len(texts[k]) <= 160 < r["units"]]
    hidden = [k for k in texts if "\N{NO-BREAK SPACE}" in texts[k] or "\N{RIGHT SINGLE QUOTATION MARK}" in texts[k]]
    assert len(gsm_accents) >= 6 and len(one_latin1_accent) >= 6
    assert len(emoji_at_boundary) >= 2 and len(extension_over_160) >= 2 and len(hidden) >= 2

    # the long LMS notice: three syllables outside KS X 1001, each once, that Python's codecs accept, so
    # euc_kr and cp949 both say "fits in 2,000 bytes" and checking each character with euc_kr finds nothing
    text = notice()
    strict = rules.kr_analyze(text)
    assert [c["reason"] for c in strict["culprits"]] == ["not_in_ks_x_1001"] * 3
    assert all(text.count(c["char"]) == 1 for c in strict["culprits"])
    assert len(text.encode("euc_kr")) <= 2000 and len(text.encode("cp949")) <= 2000
    for ch in text:
        ch.encode("euc_kr")  # raises nothing: the per-character shortcut sees no problem
    # symbols that look exotic but are in KS X 1001 and must not be reported
    for ch in "※▶①☎·":
        assert ch in text and len(ch.encode("euc_kr")) == 2

    campaign = [rules.fix_sms(i["text"]) for i in jsonl_items("task-sms-fix-batch", "campaign.jsonl")]
    regrowth = [r for r in campaign if r["after"]["encoding"] == "GSM-7" and r["after"]["units"] > 160
                and r["after"]["units"] - 2 * sum(1 for x in r["replacements"] if x["from"] == "…") <= 160]
    composed = [r for r in campaign if any(len(x["from"]) > 1 for x in r["replacements"])]
    unfixable = [r for r in campaign if r["remaining"]]
    assert len(regrowth) >= 2 and len(composed) >= 3 and len(unfixable) >= 3
    # two-unit characters on a segment border: an emoji at UTF-16 unit 66 (before and after the cleanup)
    # and a cleaned GSM-7 text of 306 units whose '€' straddles unit 152 - division says 2 segments, both need 3
    sides = [(rules.sms_analyze(i["text"]), rules.sms_analyze(r["candidate"]))
             for i, r in zip(jsonl_items("task-sms-fix-batch", "campaign.jsonl"), campaign)]
    emoji_border = [b for b, a in sides if b["boundary_extra"] > 0 and a["boundary_extra"] > 0]
    euro_border = [a for b, a in sides if a["encoding"] == "GSM-7" and a["boundary_extra"] > 0]
    assert len(emoji_border) >= 2 and len(euro_border) >= 2
    # two texts are GSM-7 after the cleanup only if '§' is GSM-7; one stays UCS-2 only because of a backtick
    section_only = [r for r in campaign if r["after"]["encoding"] == "GSM-7" and "\N{SECTION SIGN}" in r["candidate"]]
    backtick_only = [r for r in campaign if [c["char"] for c in r["remaining"]] == ["\N{GRAVE ACCENT}"]]
    assert len(section_only) >= 2 and len(backtick_only) == 1
    # an item that needs no cleanup and is GSM-7, but its extension characters push it past 160 units
    clean_long = [r for i, r in zip(jsonl_items("task-sms-fix-batch", "campaign.jsonl"), campaign)
                  if not r["replacements"] and r["before"]["encoding"] == "GSM-7"
                  and len(i["text"]) <= 160 < r["before"]["units"]]
    assert len(clean_long) == 1

    notices = [i["text"] for i in jsonl_items("task-kr-batch", "notices.jsonl")]
    near_90 = [t for t in notices if (rules.kr_analyze(t)["bytes"] or 0) in range(86, 95)]
    outside_ks = [t for t in notices if any(c["reason"] == "not_in_ks_x_1001" for c in rules.kr_analyze(t)["culprits"])]
    unencodable = [t for t in notices if any(c["reason"] == "unencodable" for c in rules.kr_analyze(t)["culprits"])]
    assert len(near_90) >= 5 and len(outside_ks) >= 3 and len(unencodable) >= 2


# --------------------------------------------------------------------------
# Graded values: what the script prints for each fixture
# --------------------------------------------------------------------------
# case -> {grader: (field in the script's JSON, value)}
GRADED = {
    "task-sms-locales": {"value-1": ("totals.sms.segments", 41), "value-2": ("totals.sms.ucs2", 12),
                         "value-3": ("totals.sms.multi_segment", 14)},
    "task-kr-lms-notice": {"value-1": ("results.0.culprits.0.index", 198),
                           "value-2": ("results.0.culprits.1.index", 221),
                           "value-3": ("results.0.culprits.2.index", 263)},
    "task-sms-fix-batch": {"value-1": ("totals.after.segments", 37), "value-2": ("totals.after.ucs2", 6),
                           "value-3": ("totals.before.segments", 52)},
    "task-kr-batch": {"value-1": ("totals.kr_class.SMS", 7), "value-2": ("totals.kr_class.LMS", 12),
                      "value-3": ("totals.kr_class.FAIL", 6)},
}
COMMANDS = {
    "task-sms-locales": ["check", "--profile", "sms", "--jsonl", "templates.jsonl"],
    "task-kr-lms-notice": ["check", "--profile", "kr-lms", "--file", "notice.txt"],
    "task-sms-fix-batch": ["fix-sms", "--jsonl", "campaign.jsonl"],
    "task-kr-batch": ["check", "--profile", "kr-sms", "--jsonl", "notices.jsonl"],
}


def dig(data, path: str):
    for key in path.split("."):
        data = data[int(key)] if key.isdigit() else data[key]
    return data


def cli_args(case: str) -> List[str]:
    return [str(FIXTURES / case / a) if a.endswith((".jsonl", ".txt")) else a for a in COMMANDS[case]]


@pytest.mark.parametrize("case", NEW_TASKS)
def test_graded_values_are_fields_of_the_script_json(case):
    _, data = run_json(*cli_args(case))
    for name, (path, value) in GRADED[case].items():
        assert dig(data, path) == value, (case, path)
        assert str(value) in grader(case, name), (case, name)
    assert set(GRADED[case]) == set(graders_of(case))


def script_values(case: str) -> Dict[str, int]:
    """Same values computed in-process, so a monkeypatched rule shows up here."""
    if case == "task-sms-locales":
        data = rules.check_many(jsonl_items(case, "templates.jsonl"), "sms")
    elif case == "task-kr-lms-notice":
        data = rules.check_text(notice(), "kr-lms")
    elif case == "task-sms-fix-batch":
        data = rules.fix_many(jsonl_items(case, "campaign.jsonl"))
    else:
        data = rules.check_many(jsonl_items(case, "notices.jsonl"), "kr-sms")
    out = {}
    for name, (path, _) in GRADED[case].items():
        try:
            out[name] = dig(data, path)
        except IndexError:
            out[name] = None
    return out


def test_in_process_values_equal_the_cli():
    for case in NEW_TASKS:
        assert script_values(case) == {k: v for k, (_, v) in GRADED[case].items()}, case


# --------------------------------------------------------------------------
# Answers: the same values in several wordings
# --------------------------------------------------------------------------

def _locales(v):
    s, u, m = v["value-1"], v["value-2"], v["value-3"]
    return [
        "Sending every template once is billed as %d segments in total. %d templates go out as UCS-2, "
        "and %d templates need two or more segments." % (s, u, m),
        "모든 템플릿을 한 번씩 보내면 총 %d건이 과금됩니다. UCS-2 로 나가는 템플릿은 %d개, 2건 이상인 템플릿은 %d개입니다." % (s, u, m),
        "| Metric | Value |\n|---|---|\n| Total billed segments | %d |\n| UCS-2 templates | %d |\n"
        "| Templates with 2+ segments | %d |" % (s, u, m),
        "- Total segments: **%d**\n- UCS-2: **%d** templates\n- Multi-segment templates: **%d**" % (s, u, m),
        "Total SMS: %d segments billed; 12 GSM-7 items, %d UCS-2 items, %d items with 2+ segments" % (s, u, m),
        "Of the 24 templates, %d of 24 are UCS-2 and %d need two or more segments; together they bill %d segments."
        % (u, m, s),
        # wordings a strong model used in the measured runs
        "Billed: %d segments. UCS\N{NON-BREAKING HYPHEN}2: %d templates. %d templates need ≥2 segments." % (s, u, m),
        "%d segments in total; %d are UCS-2; %d need more than 1 segment." % (s, u, m),
        "- Total billed SMS segments: %d\n- UCS-2 templates: %d\n- Templates with >1 segment: %d" % (s, u, m),
        "총 %d건, UCS-2 %d개, 2조각 이상 %d개" % (s, u, m),
    ]


def _notice(v):
    a, b, c = v["value-1"], v["value-2"], v["value-3"]
    if None in (a, b, c):
        # what a run without the strict rule says: Python's euc_kr or cp949 accepts every character
        return [
            "notice.txt 는 EUC-KR 1,635바이트라 LMS 2,000바이트 안에 들어갑니다. 문제 되는 글자는 없습니다.",
            "CP949 기준 1,617바이트, 똠·샾·뀰 도 2바이트로 인코딩되므로 그대로 보낼 수 있습니다.",
            "It fits: 1,635 bytes in EUC-KR (limit 2,000), and every character encodes, so nothing blocks it.",
        ]
    return [
        "보낼 수 없습니다. KS X 1001 밖 글자 3개 때문입니다: 위치 %d '똠', 위치 %d '샾', 위치 %d '뀰'." % (a, b, c),
        "It cannot be sent: '똠' (U+B620) at index %d, '샾' (U+C0FE) at index %d and '뀰' (U+B030) at index %d "
        "are outside KS X 1001." % (a, b, c),
        "| 글자 | 코드 | 위치 |\n|---|---|---|\n| 똠 | U+B620 | %d |\n| 샾 | U+C0FE | %d |\n| 뀰 | U+B030 | %d |"
        % (a, b, c),
        "- 똠 (똠얌꿍)\n  - 위치: %d\n- 샾 (꽃샾)\n  - 위치: %d\n- 뀰 (제주 하우스 뀰)\n  - 위치: %d" % (a, b, c),
        "실패 kr-lms: 바이트 계산 불가 (한도 2000)\n  - 위치 %d '똠' U+B620: KS X 1001 밖이라 EUC-KR 불가(CP949 바이트: 2)\n"
        "  - 위치 %d '샾' U+C0FE: KS X 1001 밖이라 EUC-KR 불가(CP949 바이트: 2)\n"
        "  - 위치 %d '뀰' U+B030: KS X 1001 밖이라 EUC-KR 불가(CP949 바이트: 2)" % (a, b, c),
        "문제 글자는 %d, %d, %d번째 위치(0부터)의 똠, 샾, 뀰 입니다." % (a, b, c),
    ]


def _fix(v):
    a, u, b = v["value-1"], v["value-2"], v["value-3"]
    return [
        "After the cleanup the texts add up to %d segments and %d texts are still UCS-2. Before the cleanup "
        "the set added up to %d segments." % (a, u, b),
        "정리 후에는 총 %d건이고, 여전히 UCS-2 인 문구는 %d개입니다. 정리 전에는 %d건이었습니다." % (a, u, b),
        "| | Before | After |\n|---|---|---|\n| Segments | %d | %d |\n| Still UCS-2 | - | %d |" % (b, a, u),
        "- After cleanup: %d segments\n- Still UCS-2: %d\n- Before cleanup: %d segments" % (a, u, b),
        "Total before cleanup: %d segments; 1 GSM-7, 19 UCS-2\nTotal after cleanup: %d segments; %d GSM-7, %d UCS-2"
        % (b, a, 20 - u, u),
        "| | Segments | UCS-2 texts |\n|---|---|---|\n| Before | %d | 19 |\n| After | %d | %d |" % (b, a, u),
    ]


def _kr(v):
    s, l, f = v["value-1"], v["value-2"], v["value-3"]
    return [
        "SMS %d개, LMS %d개, 발송 실패 %d개입니다." % (s, l, f),
        "%d templates go out as SMS, %d as LMS, and %d cannot be sent." % (s, l, f),
        "| 구분 | 개수 |\n|---|---|\n| SMS (90바이트 이하) | %d |\n| LMS (2,000바이트 이하) | %d |\n| 발송 실패 | %d |" % (s, l, f),
        "- SMS: %d\n- LMS: %d\n- FAIL (발송 실패): %d" % (s, l, f),
        "합계 국내 구분: SMS %d개, LMS %d개, OVER 0개(2,000바이트 초과), FAIL %d개(발송 실패)" % (s, l, f),
        "SMS 90바이트 이하 %d개, LMS 2,000바이트 이하 %d개, 25개 중 실패 %d개" % (s, l, f),
        "SMS로 나가는 것 %d개, LMS로 나가는 것 %d개, 글자 때문에 발송이 안 되는 것 %d개야." % (s, l, f),
        "| 구분 | 개수 |\n|---|---|\n| SMS | %d |\n| LMS | %d |\n| 발송 안 됨 | %d |" % (s, l, f),
    ]


ANSWERS: Dict[str, Callable[[Dict[str, int]], List[str]]] = {
    "task-sms-locales": _locales, "task-kr-lms-notice": _notice, "task-sms-fix-batch": _fix, "task-kr-batch": _kr,
}


def correct(case: str) -> Dict[str, int]:
    return {k: v for k, (_, v) in GRADED[case].items()}


def passed(case: str, answer: str) -> Dict[str, bool]:
    return {name: bool(re.search(pat, answer)) for name, pat in graders_of(case).items()}


@pytest.mark.parametrize("case", NEW_TASKS)
def test_every_wording_of_the_script_values_passes(case):
    for answer in ANSWERS[case](correct(case)):
        assert all(passed(case, answer).values()), (passed(case, answer), answer)


@pytest.mark.parametrize("case", NEW_TASKS)
def test_an_answer_off_by_one_fails_that_grader(case):
    for name in GRADED[case]:
        for delta in (-1, 1):
            values = dict(correct(case))
            values[name] += delta
            for answer in ANSWERS[case](values):
                assert not passed(case, answer)[name], (name, delta, answer)


def test_graded_numbers_do_not_collide():
    """A graded number never appears in the prompt or fixture, and the graded numbers of a task differ."""
    for case in NEW_TASKS:
        values = list(correct(case).values())
        assert len(set(values)) == len(values), case
        seen = body(EVALS / case / "prompt.md")
        for f in (FIXTURES / case).iterdir():
            seen += "\n" + f.read_text(encoding="utf-8")
        numbers = {int(m.replace(",", "")) for m in re.findall(r"\d+(?:,\d{3})*", seen)}
        assert not set(values) & numbers, (case, set(values) & numbers)


# --------------------------------------------------------------------------
# Naive baselines (N1-N6) must fail the graders they were designed for
# --------------------------------------------------------------------------

def naive_values(case: str, variant: str) -> Dict[str, int]:
    if case == "task-sms-locales":
        texts = [i["text"] for i in jsonl_items(case, "templates.jsonl")]
        t = nb.sms_totals(texts, {"N1": nb.latin1_is_gsm, "N2": nb.ceil_split}[variant])
        return {"value-1": t["segments"], "value-2": t["ucs2"], "value-3": t["multi_segment"]}
    if case == "task-kr-lms-notice":
        # Python's euc_kr (N3) or cp949 (N4), whole text or one character at a time: nothing to report
        codec = {"N3": "euc_kr", "N4": "cp949"}[variant]
        bad = [i for i, ch in enumerate(notice()) if nb._kr_bytes(ch, codec) is None]
        found = bad + [None] * (3 - len(bad))
        return {"value-1": found[0], "value-2": found[1], "value-3": found[2]}
    if case == "task-sms-fix-batch":
        texts = [i["text"] for i in jsonl_items(case, "campaign.jsonl")]
        t = nb.fix_totals(texts, {"N1": nb.fix_n1, "N2": nb.fix_ceil, "N5": nb.fix_without_regrowth,
                                  "N7": nb.fix_table(nb.snippet_table), "N9": nb.fix_backtick_quote,
                                  "N10": nb.fix_table(nb.extension_one_unit)}[variant])
        return {"value-1": t["after"]["segments"], "value-2": t["after"]["ucs2"], "value-3": t["before"]["segments"]}
    texts = [i["text"] for i in jsonl_items(case, "notices.jsonl")]
    t = nb.kr_totals(texts, {"N3": nb.python_euc_kr, "N4": nb.cp949_bytes}[variant])
    return {"value-1": t["SMS"], "value-2": t["LMS"], "value-3": t["FAIL"]}


# (case, variant, graders that must fail)
DESIGNATED = [
    ("task-sms-locales", "N1", ["value-1", "value-2", "value-3"]),
    ("task-sms-locales", "N2", ["value-1"]),
    ("task-kr-lms-notice", "N3", ["value-1", "value-2", "value-3"]),
    ("task-kr-lms-notice", "N4", ["value-1", "value-2", "value-3"]),
    ("task-sms-fix-batch", "N2", ["value-1", "value-3"]),
    ("task-sms-fix-batch", "N5", ["value-1"]),
    ("task-sms-fix-batch", "N1", ["value-1", "value-2"]),
    ("task-sms-fix-batch", "N7", ["value-1", "value-2"]),
    ("task-sms-fix-batch", "N9", ["value-1", "value-2"]),
    ("task-sms-fix-batch", "N10", ["value-1", "value-3"]),
    ("task-kr-batch", "N3", ["value-1", "value-3"]),
    ("task-kr-batch", "N4", ["value-1", "value-3"]),
]


@pytest.mark.parametrize("case,variant,must_fail", DESIGNATED)
def test_naive_baseline_fails_the_designated_graders(case, variant, must_fail):
    values = naive_values(case, variant)
    for name in must_fail:
        assert values[name] != correct(case)[name], (case, variant, name)
    for answer in ANSWERS[case](values):
        result = passed(case, answer)
        assert not any(result[name] for name in must_fail), (variant, result, answer)


def test_naive_baselines_are_wrong_where_the_plan_says():
    """The exact naive numbers, so a fixture edit that weakens a trap shows up as a diff."""
    assert naive_values("task-sms-locales", "N1") == {"value-1": 34, "value-2": 5, "value-3": 7}
    assert naive_values("task-sms-locales", "N2") == {"value-1": 38, "value-2": 12, "value-3": 14}
    for variant in ("N3", "N4"):
        assert naive_values("task-kr-lms-notice", variant) == {"value-1": None, "value-2": None, "value-3": None}
    assert naive_values("task-sms-fix-batch", "N2") == {"value-1": 33, "value-2": 6, "value-3": 50}
    assert naive_values("task-sms-fix-batch", "N5")["value-1"] == 33
    assert naive_values("task-sms-fix-batch", "N1") == {"value-1": 34, "value-2": 3, "value-3": 52}
    assert naive_values("task-sms-fix-batch", "N7") == {"value-1": 38, "value-2": 7, "value-3": 52}
    assert naive_values("task-sms-fix-batch", "N9")["value-2"] == 5


# (case, variants) a hand-made count the agent may fall back to; each must sink the case
SELF_COUNTS = {
    "task-kr-batch": ["N3", "N4"],
    "task-kr-lms-notice": ["N3", "N4"],
    "task-sms-fix-batch": ["N1", "N2", "N7", "N9", "N10"],
}


@pytest.mark.parametrize("case", sorted(SELF_COUNTS))
def test_a_self_count_scores_below_the_pass_mark(case):
    """The skill eval passes a case at a score of 0.67, and the script-ran grader passes for any run that
    calls the script (also a broken one). So a run that reports a self-made count must fail at least two
    of the three value graders: (1 + 1) / 4 = 0.5 < 0.67, while (1 + 2) / 4 = 0.75 would pass."""
    for variant in SELF_COUNTS[case]:
        for answer in ANSWERS[case](naive_values(case, variant)):
            result = passed(case, answer)
            score = (1 + sum(result.values())) / (1 + len(result))
            assert score < 0.67, (case, variant, result, answer)
    assert naive_values("task-kr-batch", "N3") == {"value-1": 9, "value-2": 13, "value-3": 3}
    assert naive_values("task-kr-batch", "N4") == {"value-1": 9, "value-2": 13, "value-3": 3}


def test_a_fake_script_that_always_says_ok_fails_the_regexes():
    fake = "Everything fits: 1 segment each, 0 UCS-2, 0 failures, part 2 starts at index 153."
    for case in NEW_TASKS:
        assert not any(passed(case, fake).values()), case


# --------------------------------------------------------------------------
# Rule mutations: dropping any one rule changes a graded value
# --------------------------------------------------------------------------
REAL_SMS = rules.sms_analyze
REAL_FIX = rules.fix_sms


def _no_boundary_rule(mp):
    def by_division(text):
        out = dict(REAL_SMS(text))
        if out["units"] > rules.SMS_SINGLE[out["encoding"]]:
            out["segments"] = -(-out["units"] // rules.SMS_MULTI[out["encoding"]])
            out["segment_starts"] = _unit_cut_starts(text, out)
        return out
    mp.setattr(rules, "sms_analyze", by_division)


def _unit_cut_starts(text, real):
    widths = [2 if (real["encoding"] == "GSM-7" and c in rules.GSM_EXTENSION) or ord(c) > 0xFFFF else 1 for c in text]
    cap, count = rules.SMS_MULTI[real["encoding"]], -(-real["units"] // rules.SMS_MULTI[real["encoding"]])
    starts, offset, k = [0], 0, 1
    for i, w in enumerate(widths):
        while k < count and offset <= k * cap < offset + w:
            starts.append(i)
            k += 1
        offset += w
    return starts


def _no_reanalysis(mp):
    def stale(text):
        out = dict(REAL_FIX(text))
        out["after"] = out["before"]
        return out
    mp.setattr(rules, "fix_sms", stale)


def _lenient_euc_kr(mp):
    def lenient(text, codec="euc-kr"):
        try:
            return {"codec": codec, "bytes": len(text.encode("euc_kr")), "culprits": []}
        except UnicodeEncodeError:
            return {"codec": codec, "bytes": None, "culprits": [{"index": 0, "reason": "unencodable"}]}
    mp.setattr(rules, "kr_analyze", lenient)


MUTATIONS = {
    "accent-is-gsm": lambda mp: mp.setattr(rules, "GSM_BASIC", rules.GSM_BASIC + "".join(
        chr(c) for c in range(0xC0, 0x100) if chr(c) not in rules.GSM_BASIC)),
    "extension-one-unit": lambda mp: (mp.setattr(rules, "GSM_BASIC", rules.GSM_BASIC + rules.GSM_EXTENSION),
                                      mp.setattr(rules, "GSM_EXTENSION", "")),
    "no-boundary-rule": _no_boundary_rule,
    "no-reanalysis-after-cleanup": _no_reanalysis,
    "ellipsis-one-unit": lambda mp: mp.setitem(rules._SIMPLE, "…", "."),
    "lenient-euc-kr": _lenient_euc_kr,
    # the widely copied table: backtick instead of the section sign
    "snippet-gsm-table": lambda mp: mp.setattr(rules, "GSM_BASIC", rules.GSM_BASIC.replace("\N{SECTION SIGN}", "`")),
    # Python's cp949 instead of strict EUC-KR: extended Hangul counts as 2 bytes and is not reported
    "cp949-as-euc-kr": lambda mp: mp.setattr(rules, "kr_analyze",
                                             lambda text, codec="euc-kr", _real=rules.kr_analyze: _real(text, "cp949")),
}


def test_every_rule_mutation_changes_a_graded_value():
    for name, apply in MUTATIONS.items():
        with pytest.MonkeyPatch.context() as mp:
            apply(mp)
            changed = [case for case in NEW_TASKS if script_values(case) != correct(case)]
        assert changed, name


@pytest.mark.parametrize("case", NEW_TASKS)
def test_every_task_is_killed_by_some_mutation(case):
    killed = []
    for name, apply in MUTATIONS.items():
        with pytest.MonkeyPatch.context() as mp:
            apply(mp)
            if script_values(case) != correct(case):
                killed.append(name)
    assert killed, case


def test_lowercase_c_cedilla_decides_nothing():
    """Providers disagree on lowercase ç; making it GSM-7 must not change any graded value."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(rules, "GSM_BASIC", rules.GSM_BASIC + "ç")
        for case in NEW_TASKS:
            assert script_values(case) == correct(case), case


# --------------------------------------------------------------------------
# Regexes also behave the same in JavaScript (the grader runtime may be Node)
# --------------------------------------------------------------------------
JS_CHECK = """
const rows = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = rows.map(r => new RegExp(r.pattern).test(r.text));
process.stdout.write(JSON.stringify(out));
"""


def test_regexes_give_the_same_verdicts_in_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed; the Python verdicts are still checked above")
    rows = []
    for case in NEW_TASKS:
        samples = ANSWERS[case](correct(case))
        for variant_case, variant, _ in DESIGNATED:
            if variant_case == case:
                samples += ANSWERS[case](naive_values(case, variant))
        for pat in graders_of(case).values():
            rows += [{"pattern": pat, "text": s} for s in samples]
    proc = subprocess.run([node, "-e", JS_CHECK], input=json.dumps(rows), capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    js = json.loads(proc.stdout)
    py = [bool(re.search(r["pattern"], r["text"])) for r in rows]
    assert js == py


# --------------------------------------------------------------------------
# The error task, the human output the tasks rely on, and SKILL.md
# --------------------------------------------------------------------------

def test_error_task_regex_matches_the_real_error_in_both_languages():
    pat = grader("task-error-kakao", "value-1")
    alimtalk = str(FIXTURES / "task-error-kakao" / "alimtalk.txt")
    for lang in ("en", "ko"):
        proc = run_cli("check", "--profile", "kakao", "--file", alimtalk, "--lang", lang)
        assert proc.returncode == 2 and re.search(pat, proc.stderr), lang
    proc = run_cli("check", "--profile", "kakao", "x", env=clean_env(LANG="ko_KR.UTF-8"))
    assert re.search(pat, proc.stderr)


def test_human_output_names_the_values_the_questions_ask_for():
    en = run_cli(*cli_args("task-kr-lms-notice"), "--lang", "en").stdout
    ko = run_cli(*cli_args("task-kr-lms-notice"), "--lang", "ko").stdout
    assert "index 198 '똠' U+B620" in en and "index 263 '뀰' U+B030" in en and "FAIL kr-lms" in en
    assert "위치 198 '똠'" in ko and "위치 221 '샾'" in ko and "위치 263 '뀰'" in ko
    loc = run_cli(*cli_args("task-sms-locales"), "--lang", "en").stdout
    assert "Total SMS: 41 segments billed; 12 GSM-7 items, 12 UCS-2 items, 14 items with 2+ segments" in loc
    fix = run_cli(*cli_args("task-sms-fix-batch"), "--lang", "en").stdout
    assert "Total after cleanup: 37 segments; 14 GSM-7, 6 UCS-2" in fix and "Total before cleanup: 52 segments" in fix
    kr = run_cli(*cli_args("task-kr-batch"), "--lang", "ko").stdout
    assert "SMS 7개, LMS 12개, OVER 0개(2,000바이트 초과), FAIL 6개(발송 실패)" in kr
    for answer, case in ((en, "task-kr-lms-notice"), (ko, "task-kr-lms-notice"), (loc, "task-sms-locales"), (fix, "task-sms-fix-batch"),
                         (kr, "task-kr-batch")):
        assert all(passed(case, answer).values()), case


def test_skill_description_states_scope_and_limits():
    text = (ROOT / "skills" / "charfit" / "SKILL.md").read_text(encoding="utf-8")
    desc = re.search(r"^description: (.*)$", text, re.M).group(1)
    assert len(desc) <= 1024 and "<" not in desc and ">" not in desc
    assert "Use when" in desc and desc.startswith("Measures")
    for phrase in ("word counts", "LLM token counts", "converting file encodings", "translation"):
        assert phrase in desc, phrase
    for prompt in cases("trigger-") + cases("notrigger-"):
        assert body(prompt / "prompt.md").strip() not in desc


def test_skill_md_commands_carry_lang_and_json_and_teach_batches():
    text = (ROOT / "skills" / "charfit" / "SKILL.md").read_text(encoding="utf-8")
    commands = re.findall(r"`(python3 scripts/charfit\.py[^`]*)`", text)
    assert commands and all("--lang" in c and "--json" in c for c in commands)
    assert any("--jsonl" in c for c in commands)
    for phrase in ("never count by eye", "quote its `charfit: error:` line as is", "`totals`", "`segment_starts`",
                   "do not add up"):
        assert phrase in text, phrase

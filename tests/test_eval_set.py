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

Fix round 15 (soak: opus scored the same with and without the skill on every SMS and Korean task, because
it writes those rules as Python correctly): two X tasks replace task-sms-locales and task-kr-lms-notice.
X's count depends on rules a model does not write down by itself - which words twitter-text turns into
links (README.md, setup.py, install.sh end in a country code; src/main.rs and config.yml do not), that an
emoji sequence (keycap, flag, skin tone, ZWJ) weighs 2 while a bare (C) sign weighs 1, and NFC before
counting. Every X fixture value equals the official twitter-text 3.1.0 library (checked when the fixtures
were made; the shortcuts X1-X4 in tests/naive_baselines.py each get every graded value wrong).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Dict, List

import naive_baselines as nb
import pytest
from conftest import ROOT, clean_env, rules, run_cli, run_json

EVALS = ROOT / "evals"
FIXTURES = EVALS / "fixtures"
NEW_TASKS = ["task-kr-batch", "task-sms-fix-batch", "task-x-ko-study", "task-x-release-posts"]
X_TASKS = ["task-x-ko-study", "task-x-release-posts"]
DOCS_EXAMPLES = ROOT / "docs" / "examples"


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


def study_post() -> str:
    text = (FIXTURES / "task-x-ko-study" / "study_post.txt").read_text(encoding="utf-8")
    return text[:-1] if text.endswith("\n") else text


def x_posts() -> List[dict]:
    return jsonl_items("task-x-release-posts", "posts.jsonl")


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


def test_x_prompts_ask_like_a_user_and_do_not_state_the_rule():
    """The X rules (which words are links, how emoji sequences and the (C) sign weigh, NFC) are what the
    skill knows; a prompt that names them lets any model answer without the skill."""
    for case in X_TASKS:
        text = body(EVALS / case / "prompt.md")
        assert re.search(r"\bX\b", text), case
        for hint in ("link", "url", "emoji", "이모지", "링크", "nfc", "normali", "정규화", "weight", "가중",
                     "twitter-text", "country", "tld", "23", "280"):
            assert hint not in text.lower(), (case, hint)


def test_korean_prompts_ask_like_a_user_and_do_not_state_the_rule():
    """The carrier rule (strict KS X 1001, so Python's codecs are wrong) is what the skill knows; a prompt
    that spells it out lets any model answer without the skill."""
    for case in ("task-kr-batch",):
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
        assert 2 <= len(graders_of(case)) <= 4, case


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
    """SMS and Korean tasks: a batch of >= 15 items. X tasks: posts close to the 280 limit, where a few
    weight points decide whether a post fits."""
    assert len(jsonl_items("task-sms-fix-batch", "campaign.jsonl")) == 20
    assert len(jsonl_items("task-kr-batch", "notices.jsonl")) == 25
    assert len(x_posts()) == 3
    for text in [i["text"] for i in x_posts()] + [study_post()]:
        assert 240 <= rules.x_analyze(text)["weighted"] <= 320


COUNTRY_CODE_FILE = re.compile(r"^[A-Za-z_-]+\.(?:md|py|sh|rs|pl)$", re.I)
EMOJI_SEQUENCE_PARTS = ("\ufe0f", "\u200d", "\u20e3", "\U000E007F") + tuple(chr(c) for c in range(0x1F3FB, 0x1F400))


def test_x_fixtures_contain_the_planned_traps():
    """Each X text mixes every trap, so knowing one rule but not another still gives a wrong number."""
    texts = {i["id"]: i["text"] for i in x_posts()}
    texts["study"] = study_post()
    for name, text in texts.items():
        x = rules.x_analyze(text)
        file_links = [u for u in x["urls"] if COUNTRY_CODE_FILE.match(u)]
        assert len(file_links) >= 2, name                                  # README.md, install.sh ... are links
        assert any(part in text for part in EMOJI_SEQUENCE_PARTS), name     # a multi-code-point emoji
        assert sum(text.count(s) for s in "©®") == 1, name        # exactly one bare (C) or (R)
        assert all(text[text.index(s) + 1] != "\ufe0f" for s in "©®" if s in text), name
    # look-alikes that are not links: a file name after a slash, a non-country extension, an e-mail domain
    assert "src/main.rs" in texts["launch"] and "config.yml" in texts["launch"]
    assert "team@tidyrun.dev" in texts["migrate"] and "Node.js" in texts["migrate"]
    assert "build.ps1" in texts["thanks"] and "study@example.org" in texts["study"]
    for name, text in texts.items():
        urls = rules.x_analyze(text)["urls"]
        assert not any(u in ("main.rs", "config.yml", "tidyrun.dev", "Node.js", "build.ps1", "example.org")
                       for u in urls), (name, urls)
    # the Korean post is saved decomposed (NFD), as a macOS editor may save it
    study = study_post()
    assert unicodedata.normalize("NFC", study) != study and unicodedata.normalize("NFD", study) == study
    # no emoji newer than the twitter-text 3.1.0 tables (rules.md: those may differ between clients)
    for text in texts.values():
        assert "\U0001F9D1" not in text and not any(0x1FA70 <= ord(c) <= 0x1FAFF for c in text)


def test_fixtures_contain_the_planned_traps():
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
    # X weighted length of each post (items in file order: launch, migrate, thanks)
    "task-x-release-posts": {"value-1": ("items.0.results.0.value", 312), "value-2": ("items.1.results.0.value", 290),
                             "value-3": ("items.2.results.0.value", 267)},
    # X weighted length of the NFD Korean post and how far it is over 280
    "task-x-ko-study": {"value-1": ("results.0.value", 294), "value-2": ("results.0.over", 14)},
    "task-sms-fix-batch": {"value-1": ("totals.after.segments", 37), "value-2": ("totals.after.ucs2", 6),
                           "value-3": ("totals.before.segments", 52)},
    "task-kr-batch": {"value-1": ("totals.kr_class.SMS", 7), "value-2": ("totals.kr_class.LMS", 12),
                      "value-3": ("totals.kr_class.FAIL", 6)},
}
COMMANDS = {
    "task-x-release-posts": ["check", "--profile", "x-post", "--jsonl", "posts.jsonl"],
    "task-x-ko-study": ["check", "--profile", "x-post", "--file", "study_post.txt"],
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
    if case == "task-x-release-posts":
        data = rules.check_many(x_posts(), "x-post")
    elif case == "task-x-ko-study":
        data = rules.check_text(study_post(), "x-post")
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

def _fit_en(w):
    return "over by %d" % (w - 280) if w > 280 else "fits, %d left" % (280 - w)


def _fit_ko(w):
    return "%d자 초과" % (w - 280) if w > 280 else "들어감, %d자 남음" % (280 - w)


def _posts(v):
    a, b, c = v["value-1"], v["value-2"], v["value-3"]
    rows = (("launch", a), ("migrate", b), ("thanks", c))
    return [
        " ".join("%s: %d (%s)." % (i, w, _fit_en(w)) for i, w in rows),
        "\n".join("- **%s** - X counts it as %d, %s" % (i.capitalize(), w, _fit_en(w)) for i, w in rows),
        "| Post | X length | Fits? |\n|---|---|---|\n" + "\n".join("| %s | %d | %s |" % (i, w, _fit_en(w)) for i, w in rows),
        "\n".join("%s 글은 X 기준 %d자입니다(%s)." % (i, w, _fit_ko(w)) for i, w in rows),
        # the script's batch output, verbatim
        "\n".join("%s %s (line %d): x-post %d weighted X length" % ("FAIL" if w > 280 else "PASS", i, n, w)
                  for n, (i, w) in enumerate(rows, 1)),
        "\n".join("%s %s (%d번째 줄): x-post X 가중 길이 %d" % ("실패" if w > 280 else "통과", i, n, w)
                  for n, (i, w) in enumerate(rows, 1)),
        # a list with the length on the next line
        "\n".join("- %s\n  - weighted length: %d\n  - %s" % (i, w, _fit_en(w)) for i, w in rows),
        "%d - launch; %d - migrate; %d - thanks" % (a, b, c),
    ]


def _study(v):
    w, o = v["value-1"], v["value-2"]
    if not o:
        left = 280 - w
        return [
            "X 기준 %d자라서 한 게시물에 들어가요. %d자 남습니다." % (w, left),
            "It fits: X counts %d, %d left." % (w, left),
            "| 항목 | 값 |\n|---|---|\n| X 글자 수 | %d |\n| 남은 글자 | %d |" % (w, left),
        ]
    return [
        "X 기준 %d자로 세져서 280자 한도를 %d자 넘어요. %d자를 줄여야 합니다." % (w, o, o),
        "X counts it as %d, so it is over the limit by %d." % (w, o),
        "| 항목 | 값 |\n|---|---|\n| X 글자 수 | %d |\n| 한도 | 280 |\n| 초과 | %d |" % (w, o),
        "- X 글자 수: **%d자**\n- 280자 초과: **%d자** (그만큼 줄여야 함)" % (w, o),
        # the script's output, verbatim (ko and en)
        "실패 x-post: X 가중 길이 %d (한도 280, %d 초과)" % (w, o),
        "FAIL x-post: %d weighted X length (limit 280, over by %d)" % (w, o),
        "%d자예요. %d - 280 = %d자 줄이면 됩니다." % (w, w, o),
        "It is %d long on X: %d characters too long (+%d)." % (w, o, o),
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
    "task-x-release-posts": _posts, "task-x-ko-study": _study, "task-sms-fix-batch": _fix, "task-kr-batch": _kr,
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
    if case == "task-x-release-posts":
        weigh = nb.X_VARIANTS[variant]
        w = [weigh(i["text"]) for i in x_posts()]
        return {"value-1": w[0], "value-2": w[1], "value-3": w[2]}
    if case == "task-x-ko-study":
        w = nb.X_VARIANTS[variant](study_post())
        return {"value-1": w, "value-2": nb.over_limit(w)}
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
    ("task-x-release-posts", "X1", ["value-1", "value-2", "value-3"]),
    ("task-x-release-posts", "X2", ["value-1", "value-2", "value-3"]),
    ("task-x-release-posts", "X3", ["value-1", "value-2", "value-3"]),
    ("task-x-ko-study", "X1", ["value-1", "value-2"]),
    ("task-x-ko-study", "X2", ["value-1", "value-2"]),
    ("task-x-ko-study", "X3", ["value-1", "value-2"]),
    ("task-x-ko-study", "X4", ["value-1", "value-2"]),
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
    # X: launch and migrate fit under the shortcuts (272, 266) but are over 280 by X's count (312, 290)
    assert naive_values("task-x-release-posts", "X1") == {"value-1": 272, "value-2": 266, "value-3": 265}
    assert naive_values("task-x-release-posts", "X2") == {"value-1": 313, "value-2": 291, "value-3": 268}
    assert naive_values("task-x-release-posts", "X3") == {"value-1": 270, "value-2": 266, "value-3": 247}
    assert naive_values("task-x-release-posts", "X4") == correct("task-x-release-posts")   # already NFC
    assert naive_values("task-x-ko-study", "X1") == {"value-1": 283, "value-2": 3}
    assert naive_values("task-x-ko-study", "X2") == {"value-1": 295, "value-2": 15}
    assert naive_values("task-x-ko-study", "X3") == {"value-1": 267, "value-2": 0}
    assert naive_values("task-x-ko-study", "X4") == {"value-1": 500, "value-2": 220}
    for case in X_TASKS:
        exact = [nb.x_exact(i["text"]) for i in x_posts()] if case == "task-x-release-posts" else [nb.x_exact(study_post())]
        assert exact[0] == correct(case)["value-1"]
    assert naive_values("task-sms-fix-batch", "N2") == {"value-1": 33, "value-2": 6, "value-3": 50}
    assert naive_values("task-sms-fix-batch", "N5")["value-1"] == 33
    assert naive_values("task-sms-fix-batch", "N1") == {"value-1": 34, "value-2": 3, "value-3": 52}
    assert naive_values("task-sms-fix-batch", "N7") == {"value-1": 38, "value-2": 7, "value-3": 52}
    assert naive_values("task-sms-fix-batch", "N9")["value-2"] == 5


# (case, variants) a hand-made count the agent may fall back to; each must sink the case
SELF_COUNTS = {
    "task-kr-batch": ["N3", "N4"],
    "task-sms-fix-batch": ["N1", "N2", "N7", "N9", "N10"],
    "task-x-release-posts": ["X1", "X2", "X3"],
    "task-x-ko-study": ["X1", "X2", "X3", "X4"],
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
    # X: links only with a generic TLD (README.md, setup.py, install.sh stay text)
    "no-country-code-links": lambda mp: mp.setattr(rules, "_URL_RE", nb.GTLD_ONLY_URL_RE),
    # X: every code point of an emoji sequence weighed alone
    "no-emoji-sequences": lambda mp: mp.setattr(rules, "_EMOJI_RE", nb.NO_EMOJI_RE),
    # X: a bare (C) or (R) sign counted as an emoji (the unofficial Python port does this)
    "bare-symbol-is-emoji": lambda mp: mp.setattr(rules, "_EMOJI_RE", nb.EMOJI_WITH_BARE_SYMBOLS_RE),
    # X: no NFC before counting (also stops fix-sms from composing accents)
    "no-nfc": lambda mp: mp.setattr(rules, "unicodedata", SimpleNamespace(normalize=lambda form, text: text)),
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
    posts_en = run_cli(*cli_args("task-x-release-posts"), "--lang", "en").stdout
    posts_ko = run_cli(*cli_args("task-x-release-posts"), "--lang", "ko").stdout
    assert "FAIL launch (line 1): x-post 312 weighted X length" in posts_en
    assert "PASS thanks (line 3): x-post 267 weighted X length" in posts_en
    assert "실패 migrate (2번째 줄): x-post X 가중 길이 290" in posts_ko
    study_en = run_cli(*cli_args("task-x-ko-study"), "--lang", "en").stdout
    study_ko = run_cli(*cli_args("task-x-ko-study"), "--lang", "ko").stdout
    assert "FAIL x-post: 294 weighted X length (limit 280, over by 14)" in study_en
    assert "links counted as 23: install.sh, README.md, https://forms.example.com/study-apply" in study_en
    assert "실패 x-post: X 가중 길이 294 (한도 280, 14 초과)" in study_ko
    fix = run_cli(*cli_args("task-sms-fix-batch"), "--lang", "en").stdout
    assert "Total after cleanup: 37 segments; 14 GSM-7, 6 UCS-2" in fix and "Total before cleanup: 52 segments" in fix
    kr = run_cli(*cli_args("task-kr-batch"), "--lang", "ko").stdout
    assert "SMS 7개, LMS 12개, OVER 0개(2,000바이트 초과), FAIL 6개(발송 실패)" in kr
    for answer, case in ((posts_en, "task-x-release-posts"), (posts_ko, "task-x-release-posts"),
                         (study_en, "task-x-ko-study"), (study_ko, "task-x-ko-study"),
                         (fix, "task-sms-fix-batch"), (kr, "task-kr-batch")):
        assert all(passed(case, answer).values()), case


def test_readme_templates_sample_keeps_its_totals():
    """templates.jsonl left the eval set (round 15) and lives on as the README batch example."""
    proc, data = run_json("check", "--profile", "sms", "--jsonl", str(DOCS_EXAMPLES / "templates.jsonl"))
    assert proc.returncode == 1
    assert data["totals"]["items"] == 24
    assert data["totals"]["sms"] == {"segments": 41, "gsm7": 12, "ucs2": 12, "multi_segment": 14}


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

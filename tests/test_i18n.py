"""AC-6: two UI languages, how one is chosen, and language-independent JSON."""
import json
import re
import string

import pytest
from conftest import PARTY, clean_env, i18n, run_cli

TEXT = "똠방각하 " + PARTY
FIELDS = string.Formatter()


def test_both_languages_have_identical_keys():
    assert set(i18n.MESSAGES["en"]) == set(i18n.MESSAGES["ko"])


def test_placeholders_match_between_languages():
    for key in i18n.MESSAGES["en"]:
        def names(lang):
            return {f for _, f, _, _ in FIELDS.parse(i18n.MESSAGES[lang][key]) if f}
        assert names("en") == names("ko"), key


def test_korean_messages_contain_hangul_and_english_do_not():
    for key, value in i18n.MESSAGES["ko"].items():
        if key.startswith(("help.", "count.", "err.", "fix.")) and key not in ("count.sms_encoding",):
            assert re.search(r"[가-힣]", value), key
    for value in i18n.MESSAGES["en"].values():
        assert not re.search(r"[가-힣]", value)


@pytest.mark.parametrize("cli,env,expected", [
    ("ko", {"CHARFIT_LANG": "en", "LANG": "en_US.UTF-8"}, "ko"),
    ("en", {"CHARFIT_LANG": "ko", "LANG": "ko_KR.UTF-8"}, "en"),
    (None, {"CHARFIT_LANG": "ko", "LANG": "en_US.UTF-8"}, "ko"),
    (None, {"CHARFIT_LANG": "en", "LC_ALL": "ko_KR.UTF-8"}, "en"),
    (None, {"LC_ALL": "ko_KR.UTF-8", "LANG": "en_US.UTF-8"}, "ko"),
    (None, {"LC_MESSAGES": "ko_KR.UTF-8", "LANG": "en_US.UTF-8"}, "ko"),
    (None, {"LC_ALL": "en_US.UTF-8", "LC_MESSAGES": "ko_KR.UTF-8"}, "en"),
    (None, {"LANG": "ko_KR.UTF-8"}, "ko"),
    (None, {"LANG": "fr_FR.UTF-8"}, "en"),
    (None, {"LANG": "C"}, "en"),
    (None, {"LC_ALL": "", "LANG": "ko_KR.UTF-8"}, "ko"),
    (None, {}, "en"),
])
def test_language_resolution_order(cli, env, expected):
    assert i18n.resolve_lang(cli, env) == expected


@pytest.mark.parametrize("lang,label", [("en", "UTF-16 code units"), ("ko", "UTF-16 코드 단위")])
def test_count_table_follows_lang(lang, label):
    proc = run_cli("count", "--lang", lang, "It’s ready")
    assert proc.returncode == 0 and label in proc.stdout


def test_lang_flag_beats_environment_in_the_real_script():
    proc = run_cli("count", "--lang", "en", "x", env=clean_env(LANG="ko_KR.UTF-8", CHARFIT_LANG="ko"))
    assert "UTF-16 code units" in proc.stdout
    proc = run_cli("count", "x", env=clean_env(CHARFIT_LANG="ko"))
    assert "UTF-16 코드 단위" in proc.stdout
    proc = run_cli("count", "x", env=clean_env(LANG="ko_KR.UTF-8"))
    assert "UTF-16 코드 단위" in proc.stdout
    proc = run_cli("count", "x", env=clean_env(LANG="fr_FR.UTF-8"))
    assert "UTF-16 code units" in proc.stdout


def test_lang_equals_form():
    assert "UTF-16 code units" in run_cli("count", "--lang=en", "x", env=clean_env(LANG="ko_KR.UTF-8")).stdout
    assert "UTF-16 코드" in run_cli("--lang=ko", "count", "x").stdout


@pytest.mark.parametrize("lang,marker", [("en", "usage:"), ("ko", "사용법:")])
def test_help_follows_lang(lang, marker):
    for args in (["--help"], ["count", "--help"], ["check", "--help"], ["fix-sms", "--help"]):
        proc = run_cli(*args, "--lang", lang) if args != ["--help"] else run_cli("--lang", lang, "--help")
        assert proc.returncode == 0 and marker in proc.stdout


def test_english_help_has_no_hangul_and_korean_help_does():
    assert not re.search(r"[가-힣]", run_cli("--lang", "en", "check", "--help").stdout)
    assert re.search(r"[가-힣]", run_cli("--lang", "ko", "check", "--help").stdout)


@pytest.mark.parametrize("lang,fragment", [("en", "unknown profile 'kakao'"), ("ko", "알 수 없는 프로필 'kakao'")])
def test_error_messages_follow_lang(lang, fragment):
    proc = run_cli("check", "--profile", "kakao", "x", "--lang", lang)
    assert proc.returncode == 2 and proc.stderr.startswith("charfit: error:") and fragment in proc.stderr


@pytest.mark.parametrize("args", [
    ["count", TEXT], ["check", "--profile", "sms,x-post,kr-sms,utf8:5", TEXT], ["fix-sms", "It’s …"],
])
def test_json_output_is_byte_identical_across_languages(args):
    en = run_cli(*args, "--json", "--lang", "en")
    ko = run_cli(*args, "--json", "--lang", "ko")
    assert en.returncode == ko.returncode
    assert en.stdout_bytes == ko.stdout_bytes


@pytest.fixture
def batch_file(tmp_path):
    rows = [{"id": "euro", "text": "a" * 152 + "€" + "a" * 152}, {"id": "kr", "text": "똠방각하"},
            {"id": "ok", "text": "Hello"}]
    path = tmp_path / "batch.jsonl"
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return str(path)


@pytest.mark.parametrize("lang,expected", [
    ("en", ["Total: 3 items, 1 pass all profiles, 2 fail a profile", "Total SMS: 5 segments billed",
            "Total Korean classes: SMS 1, LMS 1", "FAIL euro (line 1)"]),
    ("ko", ["합계: 항목 3개, 모든 프로필 통과 1, 통과 못 함 2", "합계 SMS: 과금 5건", "합계 국내 구분: SMS 1개, LMS 1개",
            "실패 euro (1번째 줄)"]),
])
def test_batch_totals_follow_lang(batch_file, lang, expected):
    out = run_cli("check", "--profile", "sms,kr-sms", "--jsonl", batch_file, "--lang", lang).stdout
    for fragment in expected:
        assert fragment in out, fragment


@pytest.mark.parametrize("lang,fragments", [
    ("en", ["part 3: index 304 «a»", "part 2: index 152 «€aaaaaaaaaaa»"]),
    ("ko", ["조각 3: 위치 304 «a»", "조각 2: 위치 152 «€aaaaaaaaaaa»"]),
])
def test_segment_start_lines_follow_lang(lang, fragments):
    text = "a" * 152 + "€" + "a" * 152
    for command in (["check", "--profile", "sms:3"], ["count"]):
        out = run_cli(*command, text, "--lang", lang).stdout
        for fragment in fragments:
            assert fragment in out, (command, fragment)


def test_single_segment_text_has_no_part_lines():
    assert "part 1" not in run_cli("check", "--profile", "sms", "Hello", "--lang", "en").stdout


@pytest.mark.parametrize("lang,fragment", [
    ("en", "line 2 is not valid JSON"), ("ko", "2번째 줄이 올바른 JSON 이 아닙니다"),
])
def test_jsonl_errors_follow_lang(tmp_path, lang, fragment):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"text": "a"}\n{oops\n', encoding="utf-8")
    proc = run_cli("check", "--profile", "sms", "--jsonl", str(path), "--lang", lang)
    assert proc.returncode == 2 and fragment in proc.stderr


def test_batch_json_is_byte_identical_across_languages(batch_file, tmp_path):
    for args in (["check", "--profile", "sms,kr-sms,utf8:9"], ["fix-sms"]):
        en = run_cli(*args, "--jsonl", batch_file, "--json", "--lang", "en")
        ko = run_cli(*args, "--jsonl", batch_file, "--json", "--lang", "ko")
        assert en.returncode == ko.returncode and en.stdout_bytes == ko.stdout_bytes


@pytest.mark.parametrize("lang,marker", [("en", "--jsonl PATH"), ("ko", "--jsonl PATH")])
def test_help_lists_jsonl_in_both_languages(lang, marker):
    out = run_cli("check", "--help", "--lang", lang).stdout
    assert marker in out
    assert ("JSON Lines" in out) and (("합계" in out) == (lang == "ko"))


def test_human_output_differs_between_languages():
    args = ["check", "--profile", "sms,kr-sms", TEXT]
    assert run_cli(*args, "--lang", "en").stdout != run_cli(*args, "--lang", "ko").stdout
    ko = run_cli("fix-sms", "It’s", "--lang", "ko").stdout
    assert "후보" in ko


@pytest.mark.parametrize("args", [
    ["check", "hi"],
    ["check", "--profile", "sms", "--bogus", "hi"],
    ["count", "--kr-codec", "x", "hi"],
    ["frob"],
    [],
    ["count", "--file"],
])
def test_korean_usage_errors_have_no_english_argparse_wording(args):
    proc = run_cli(*args, "--lang", "ko")
    assert proc.returncode == 2
    assert "Traceback" not in proc.stderr
    for phrase in ("arguments are required", "unrecognized", "invalid choice", "expected one", "choose from"):
        assert phrase not in proc.stderr
    assert re.search(r"[가-힣]", proc.stderr)


def test_korean_version_help_is_translated():
    proc = run_cli("--help", "--lang", "ko")
    assert "show program's version" not in proc.stdout


def test_english_usage_error_keeps_argparse_wording():
    proc = run_cli("check", "hi", "--lang", "en")
    assert proc.returncode == 2
    assert "the following arguments are required: --profile/-p" in proc.stderr


def test_closed_pipe_prints_no_traceback(tmp_path):
    import subprocess
    import sys
    from conftest import SCRIPT, clean_env as env
    big = tmp_path / "big.txt"
    big.write_text("word " * 200000, encoding="utf-8")
    proc = subprocess.Popen([sys.executable, str(SCRIPT), "count", "--file", str(big), "--lang", "en"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env())
    proc.stdout.readline()
    proc.stdout.close()
    err = proc.stderr.read().decode("utf-8")
    proc.wait(timeout=60)
    proc.stderr.close()
    assert "Traceback" not in err

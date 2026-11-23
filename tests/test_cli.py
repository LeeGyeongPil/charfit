"""AC-5: the command line contract - inputs, exit codes, JSON shape, usage errors."""
import json

import pytest
from conftest import PARTY, clean_env, run_cli, run_json

TEXT = "할인 쿠폰 " + PARTY + " 지금 확인"


def test_check_sms_passes_with_exit_zero():
    proc = run_cli("check", "--profile", "sms", "Hello world")
    assert proc.returncode == 0 and "PASS sms" in proc.stdout


def test_check_json_shape_for_sms_and_utf8():
    proc, data = run_json("check", "--profile", "sms,utf8:10", "It’s ready")
    assert proc.returncode == 1
    sms, utf8 = data["results"]
    assert sms["profile"] == "sms" and sms["pass"] is True and sms["measure"] == "sms_segments"
    assert (sms["value"], sms["limit"], sms["over"]) == (1, 1, 0)
    assert (sms["encoding"], sms["units"], sms["per_segment"]) == ("UCS-2", 10, 70)
    assert sms["culprits"] == [{"index": 2, "char": "’", "codepoint": "U+2019", "reason": "not_gsm7"}]
    assert utf8["pass"] is False and utf8["value"] == 12 and utf8["over"] == 2 and utf8["culprits"] == []


def test_x_post_json_lists_links():
    _, data = run_json("check", "--profile", "x-post", "go to example.com now")
    assert data["results"][0]["x_urls"] == ["example.com"] and data["results"][0]["value"] == 6 + 23 + 4


def test_count_json_keys_and_values():
    proc, data = run_json("count", "It’s ready")
    assert proc.returncode == 0
    assert list(data) == ["length", "sms", "x_weighted", "x_urls", "euc_kr", "cp949_bytes", "kr_codec", "kr_class"]
    assert data["sms"]["encoding"] == "UCS-2" and data["x_weighted"] == 10 and data["euc_kr"]["bytes"] == 11


def test_stdin_and_file_match_the_text_argument(tmp_path):
    direct = run_cli("check", "--profile", "sms,utf8:20", "--json", "Hello ’ world")
    via_stdin = run_cli("check", "--profile", "sms,utf8:20", "--json", "-", stdin="Hello ’ world\n".encode())
    path = tmp_path / "t.txt"
    path.write_bytes("Hello ’ world\r\n".encode())
    via_file = run_cli("check", "--profile", "sms,utf8:20", "--json", "--file", str(path))
    assert direct.stdout == via_stdin.stdout == via_file.stdout


def test_only_one_trailing_newline_is_removed(tmp_path):
    path = tmp_path / "t.txt"
    path.write_bytes(b"ab\n\n")
    _, data = run_json("count", "--file", str(path))
    assert data["length"]["code_points"] == 3


def test_utf8_bom_in_a_file_is_ignored(tmp_path):
    path = tmp_path / "t.txt"
    path.write_bytes(b"\xef\xbb\xbfabc")
    _, data = run_json("count", "--file", str(path))
    assert data["length"]["code_points"] == 3


def test_empty_string_argument_is_valid_input():
    proc, data = run_json("check", "--profile", "sms", "")
    assert proc.returncode == 0 and data["results"][0]["value"] == 0


def test_text_with_a_leading_dash_after_double_dash():
    proc = run_cli("count", "--json", "--", "-5% off")
    assert proc.returncode == 0 and json.loads(proc.stdout)["length"]["code_points"] == 7


def test_human_output_for_check_names_the_culprit():
    proc = run_cli("check", "--profile", "sms,kr-sms", "--lang", "en", "It’s \U0001F389")
    assert proc.returncode == 1
    assert "index 2 '’' U+2019" in proc.stdout and "cannot be encoded" in proc.stdout


@pytest.mark.parametrize("args,stdin,message", [
    (["check", "--profile", "kakao", "x"], None, "charfit: error: unknown profile 'kakao' (known: sms, sms:N, x-post, kr-sms, kr-lms, utf16:N, utf8:N, chars:N)"),
    (["check", "--profile", "utf8:abc", "x"], None, "charfit: error: profile 'utf8:abc' needs a positive integer limit"),
    (["count", "--file", "missing.txt"], None, "charfit: error: cannot read file 'missing.txt': not found"),
    (["count", "--file", "BAD"], None, "charfit: error: '{BAD}' is not valid UTF-8 (byte offset 3)"),
    (["count", "x", "--file", "BAD"], None, "charfit: error: give either TEXT or --file, not both"),
    (["count"], None, "charfit: error: no input text (pass TEXT, '-' for stdin, or --file PATH)"),
    (["count", "-"], b"ab\xff", "charfit: error: '<stdin>' is not valid UTF-8 (byte offset 2)"),
])
def test_usage_errors_exit_2_without_traceback(args, stdin, message, tmp_path):
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"abc\xff\xfe")
    args = [str(bad) if a == "BAD" else a for a in args]
    proc = run_cli(*args, "--lang", "en", stdin=stdin)
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr.startswith("charfit: error:") and "Traceback" not in proc.stderr
    assert proc.stderr.strip() == message.replace("{BAD}", str(bad))


def test_directory_as_file_is_a_usage_error(tmp_path):
    proc = run_cli("count", "--file", str(tmp_path), "--lang", "en")
    assert proc.returncode == 2 and "is a directory" in proc.stderr


def test_unknown_command_and_missing_profile_are_usage_errors():
    for args in (["nope"], ["check", "x"], []):
        proc = run_cli(*args, "--lang", "en")
        assert proc.returncode == 2 and proc.stderr.startswith("charfit: error:") and "Traceback" not in proc.stderr


def test_version_flag():
    assert run_cli("--version").stdout.startswith("charfit ")


def test_unprintable_argument_bytes_are_reported():
    # a lone surrogate arrives when the shell passes bytes that are not UTF-8
    import subprocess
    import sys
    from conftest import SCRIPT
    proc = subprocess.run([sys.executable, str(SCRIPT), "count", b"a\xffb", "--lang", "en"],
                          capture_output=True, env=clean_env())
    assert proc.returncode == 2 and b"not valid UTF-8" in proc.stderr


def test_json_is_valid_utf8_without_escapes():
    proc = run_cli("count", "--json", "한")
    assert json.loads(proc.stdout)["length"]["code_points"] == 1
    assert "\\u" not in proc.stdout


def test_human_output_caps_the_culprit_list_but_json_keeps_all():
    text = "가나다라마바사아자차카타"      # 12 Hangul syllables
    human = run_cli("count", "--lang", "en", text).stdout
    assert "... and 2 more" in human and human.count("not in GSM-7") == 10
    _, data = run_json("count", text)
    assert len(data["sms"]["culprits"]) == 12

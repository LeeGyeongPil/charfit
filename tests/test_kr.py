"""AC-2: strict EUC-KR bytes, CP949, and the SMS/LMS boundary."""
from conftest import PARTY, rules, run_json

HELLO = "안녕하세요"            # five syllables, 10 bytes
TTOM = "똠방각하"                 # first syllable is outside KS X 1001
EMOJI_TEXT = "할인 쿠폰 " + PARTY + " 지금 확인"


def kr(text, profile, codec="euc-kr"):
    return rules.check_text(text, profile, codec)["results"][0]


def test_sms_boundary_90_bytes():
    assert kr(HELLO * 9, "kr-sms")["value"] == 90 and kr(HELLO * 9, "kr-sms")["pass"] is True
    r = kr(HELLO * 9 + "!", "kr-sms")
    assert (r["pass"], r["value"], r["over"]) == (False, 91, 1)
    assert kr(HELLO * 9 + "!", "kr-lms")["pass"] is True


def test_lms_boundary_2000_bytes():
    assert kr("가" * 1000, "kr-lms")["pass"] is True
    r = kr("가" * 1000 + "a", "kr-lms")
    assert (r["pass"], r["value"], r["over"]) == (False, 2001, 1)


def test_python_euc_kr_codec_accepts_what_a_carrier_rejects():
    """The trap: the codec writes 8 bytes for U+B620 without an error, so len(encode) is wrong."""
    naive = len(TTOM.encode("euc_kr"))
    assert naive == 14
    strict = rules.kr_analyze(TTOM)
    assert strict["bytes"] is None
    assert strict["culprits"] == [{"index": 0, "char": "똠", "codepoint": "U+B620",
                                   "reason": "not_in_ks_x_1001", "cp949_bytes": 2}]


def test_default_fails_and_cp949_passes_with_8_bytes():
    r = kr(TTOM, "kr-sms")
    assert r["pass"] is False and r["value"] is None and r["over"] is None
    r = kr(TTOM, "kr-sms", "cp949")
    assert r["pass"] is True and r["value"] == 8 and r["codec"] == "cp949" and r["culprits"] == []


def test_emoji_is_unencodable_with_its_position():
    r = kr(EMOJI_TEXT, "kr-sms")
    assert r["pass"] is False and r["value"] is None
    assert r["culprits"] == [{"index": 6, "char": PARTY, "codepoint": "U+1F389", "reason": "unencodable"}]


def test_kr_class_values():
    assert rules.count_text(HELLO * 9)["kr_class"] == "SMS"
    assert rules.count_text(HELLO * 9 + "!")["kr_class"] == "LMS"
    assert rules.count_text("가" * 1001)["kr_class"] == "OVER"
    assert rules.count_text(EMOJI_TEXT)["kr_class"] == "FAIL"


def test_count_reports_both_codecs_and_class_follows_the_chosen_codec():
    strict = rules.count_text(TTOM)
    assert strict["euc_kr"]["bytes"] is None and strict["cp949_bytes"] == 8 and strict["kr_class"] == "FAIL"
    chosen = rules.count_text(TTOM, "cp949")
    assert chosen["kr_class"] == "SMS" and chosen["kr_codec"] == "cp949"


def test_ascii_and_symbols():
    assert rules.kr_analyze("abc ’")["bytes"] == 6          # U+2019 is in KS X 1001 (2 bytes)
    assert rules.kr_analyze("")["bytes"] == 0


def test_cli_kr_codec_option():
    proc, data = run_json("check", "--profile", "kr-sms", TTOM)
    assert proc.returncode == 1 and data["results"][0]["culprits"][0]["reason"] == "not_in_ks_x_1001"
    proc, data = run_json("check", "--profile", "kr-sms", "--kr-codec", "cp949", TTOM)
    assert proc.returncode == 0 and data["results"][0]["value"] == 8

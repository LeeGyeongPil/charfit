"""AC-5 (part): UTF-16 / UTF-8 / code point profiles and profile parsing."""
import pytest
from conftest import PARTY, rules, run_json

TEXT = "할인 쿠폰 " + PARTY + " 지금 확인"


def test_lengths_of_a_mixed_text():
    assert rules.basic_lengths(TEXT) == {"code_points": 13, "utf16_units": 14, "utf8_bytes": 32}


def test_generic_profiles_together():
    r = rules.check_text(TEXT, "utf16:14,utf8:31,chars:13")
    by = {x["profile"]: x for x in r["results"]}
    assert by["utf16:14"]["pass"] and by["utf16:14"]["value"] == 14
    assert not by["utf8:31"]["pass"] and by["utf8:31"]["value"] == 32 and by["utf8:31"]["over"] == 1
    assert by["chars:13"]["pass"] and by["chars:13"]["value"] == 13
    assert r["pass"] is False


def test_cli_exit_code_and_top_level_keys():
    proc, data = run_json("check", "--profile", "utf16:14,utf8:31,chars:13", TEXT)
    assert proc.returncode == 1
    assert list(data) == ["pass", "length", "results"]
    assert [x["measure"] for x in data["results"]] == ["utf16_units", "utf8_bytes", "code_points"]


def test_empty_text_passes_everything():
    r = rules.check_text("", "sms,x-post,kr-sms,kr-lms,utf16:1,utf8:1,chars:1")
    assert r["pass"] is True and r["length"] == {"code_points": 0, "utf16_units": 0, "utf8_bytes": 0}


def test_exact_limit_passes_and_one_over_fails():
    assert rules.check_text("ab", "chars:2")["pass"] is True
    r = rules.check_text("abc", "chars:2")["results"][0]
    assert r["pass"] is False and r["over"] == 1


@pytest.mark.parametrize("spec,kind", [("kakao", "unknown"), ("", "unknown"), ("x-post:5", "unknown"),
                                       ("kr-sms,telegram", "unknown"), ("utf8", "limit"), ("utf8:abc", "limit"),
                                       ("utf8:0", "limit"), ("utf8:-3", "limit"), ("sms:", "limit"),
                                       ("chars:1.5", "limit")])
def test_bad_profiles(spec, kind):
    with pytest.raises(rules.ProfileError) as e:
        rules.parse_profiles(spec)
    assert e.value.kind == kind


def test_profile_list_keeps_order_and_defaults():
    assert rules.parse_profiles("sms, utf8:5") == [("sms", "sms", 1), ("utf8:5", "utf8", 5)]
    assert rules.parse_profiles("sms:3") == [("sms:3", "sms", 3)]


def test_lone_surrogate_detection():
    assert rules.has_lone_surrogate("a\udc80") and not rules.has_lone_surrogate("a" + PARTY)

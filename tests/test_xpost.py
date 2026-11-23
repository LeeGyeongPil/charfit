"""AC-5 (X regression): X weighted length. Every fixed value matched the official twitter-text 3.1.0 (npm, 2026-11-23)."""
import pytest
from conftest import FAMILY, PARTY, rules


@pytest.mark.parametrize("text,expected", [
    ("Hello world", 11),
    ("안녕하세요" * 9, 90),
    ("할인 쿠폰 " + PARTY + " 지금 확인", 22),
    (FAMILY + " family", 9),
    ("café", 4),
    ("Read https://example.com/a/very/long/path/that/keeps/going?x=1 now", 32),
    ("visit example.com today", 35),
    ("“quoted” — dash…", 17),
    ("日本語のテキスト", 16),
    ("a" * 281, 281),
])
def test_values_cross_checked_with_twitter_text(text, expected):
    assert rules.x_analyze(text)["weighted"] == expected


def test_limit_is_280():
    assert rules.check_text("a" * 280, "x-post")["pass"] is True
    r = rules.check_text("a" * 281, "x-post")["results"][0]
    assert r["pass"] is False and r["over"] == 1 and r["limit"] == 280 and r["measure"] == "x_weighted"


def test_urls_are_reported_and_weigh_23():
    r = rules.x_analyze("see https://example.com/a/b/c/d/e/f/g/h and www.example.org/x, ok")
    assert r["urls"] == ["https://example.com/a/b/c/d/e/f/g/h", "www.example.org/x"]
    assert r["weighted"] == 4 + 23 + 5 + 23 + 1 + 3


def test_trailing_punctuation_is_not_part_of_the_link():
    r = rules.x_analyze("Visit https://example.com/page.")
    assert r["urls"] == ["https://example.com/page"] and r["weighted"] == 6 + 23 + 1


def test_email_and_version_numbers_are_not_links():
    assert rules.x_analyze("mail me@example.com")["urls"] == []
    assert rules.x_analyze("version 1.2.3")["urls"] == []


def test_korean_after_a_link_is_not_swallowed():
    r = rules.x_analyze("https://example.com/안녕")
    assert r["urls"] == ["https://example.com/"] and r["weighted"] == 23 + 4


def test_flag_and_skin_tone_emoji_are_two():
    assert rules.x_analyze("\U0001F1F0\U0001F1F7")["weighted"] == 2
    assert rules.x_analyze("\U0001F44D\U0001F3FD")["weighted"] == 2


# Each value below matched the official twitter-text 3.1.0 token by token (2026-11-23, probe fix4 cmp.js).
@pytest.mark.parametrize("text,expected", [
    ("1\ufe0f⃣", 2),                                   # keycap: digit + VS16 + combining keycap
    ("#\ufe0f⃣", 2),
    ("\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F", 2),  # England tag flag
    ("©", 1), ("®", 1), ("©\ufe0f", 2), ("®\ufe0f", 2),  # a bare © ® is Latin-1 (1); with U+FE0F it is an emoji (2)
    ("™", 2), ("™\ufe0f", 2), ("‼\ufe0f", 2), ("↔\ufe0f", 2),
    ("©2026", 5), ("Brand®", 6), ("\U0001F6E0\ufe0f", 2), ("⚠\ufe0f", 2),
    ("\U0001F469\U0001F3FD\u200d\U0001F373", 2),
    ("\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F", 2), ("help@shop.co.kr", 15),
    ("setup.py", 23), ("README.md", 23), ("README.MD", 23), ("main.rs", 23), ("install.sh", 23),
    ("CONTRIBUTING.md", 23), ("my-app.py", 23), ("done.It", 23), ("MIT.md", 23),
    ("README.md.", 24), ("(README.md)", 25), ("setup.py에", 25), ("naver.com에서", 27),
    ("src/main.rs", 11), ("docs/README.md", 14), ("foo_bar.md", 10), ("index.js", 8), ("app.ts", 6),
    ("config.yml", 10), ("requirements.txt", 16), ("pyproject.toml", 14), ("Node.js", 7), ("e.g.", 4),
    ("x.py-y", 6), ("U.S.", 4),
    ("한", 2),                              # NFD 한 -> NFC, one Hangul syllable
])
def test_emoji_sequences_file_name_links_and_nfc_match_twitter_text(text, expected):
    assert rules.x_analyze(text)["weighted"] == expected


def test_emoji_and_nfc_are_reported():
    r = rules.check_text("1\ufe0f⃣ © 한", "x-post")["results"][0]
    # 9 code points as given; after NFC the keycap stays 3, the jamo become 1 syllable: 3+1+1+1+1 = 7
    # keycap 2, space 1, bare © 1 (not an emoji on X), space 1, Hangul 2
    assert (r["value"], r["x_emoji"], r["x_nfc_code_points"]) == (2 + 1 + 1 + 1 + 2, 1, 7)


def test_empty_text():
    assert rules.x_analyze("")["weighted"] == 0

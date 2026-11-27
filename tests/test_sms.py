"""AC-1: SMS encoding, billed units, segments and the characters that force UCS-2.

Expected values were cross-checked against an independent SMS segment calculator and a GSM 03.38 codec
while the rules were written (2026-11-23).
"""
import pytest
from conftest import FAMILY, PARTY, rules

sms = rules.sms_analyze


@pytest.mark.parametrize("text,encoding,units,segments", [
    ("Hello world", "GSM-7", 11, 1),
    ("It’s ready", "UCS-2", 10, 1),
    ("a" * 160, "GSM-7", 160, 1),
    ("a" * 161, "GSM-7", 161, 2),
    ("~" * 80, "GSM-7", 160, 1),
    ("~" * 81, "GSM-7", 162, 2),
    ("a" * 152 + "€" + "a" * 10, "GSM-7", 164, 2),
    ("a" * 152 + "€" + "a" * 152, "GSM-7", 306, 3),
    ("a" * 66 + PARTY + "a" * 5, "UCS-2", 73, 2),
    (FAMILY + " family", "UCS-2", 15, 1),
    ("café", "UCS-2", 5, 1),
    ("café", "GSM-7", 4, 1),
    ("", "GSM-7", 0, 0),
])
def test_fixed_values(text, encoding, units, segments):
    r = sms(text)
    assert (r["encoding"], r["units"], r["segments"]) == (encoding, units, segments)


def test_euro_at_the_boundary_adds_a_segment_that_ceil_misses():
    r = sms("a" * 152 + "€" + "a" * 152)
    assert r["units"] == 306 and -(-r["units"] // 153) == 2 and r["segments"] == 3


def test_curly_quote_culprit_position():
    r = sms("It’s ready")
    assert r["culprits"] == [{"index": 2, "char": "’", "codepoint": "U+2019", "reason": "not_gsm7"}]
    assert r["per_segment"] == 70


def test_nfd_accent_culprit_is_the_combining_mark():
    assert [c["codepoint"] for c in sms("café")["culprits"]] == ["U+0301"]
    assert sms("café")["culprits"] == []


def test_surrogate_pair_is_one_culprit_at_a_code_point_index():
    r = sms("ab" + PARTY)
    assert r["culprits"] == [{"index": 2, "char": PARTY, "codepoint": "U+1F389", "reason": "not_gsm7"}]


@pytest.mark.parametrize("text,segments,extra", [
    ("a" * 152 + "€" + "a" * 152, 3, 1),          # GSM-7: '€' would straddle septets 153/154
    ("a" * 153 + "€" + "a" * 151, 2, 0),          # same length, '€' starts segment 2 cleanly
    ("á" * 66 + PARTY + "á" * 66, 3, 1),          # UCS-2: the emoji would straddle units 67/68
    ("á" * 65 + PARTY + "á" * 67, 2, 0),
    ("a" * 160, 1, 0),
    ("", 0, 0),
])
def test_boundary_extra_counts_segments_added_by_the_no_split_rule(text, segments, extra):
    r = sms(text)
    assert (r["segments"], r["boundary_extra"]) == (segments, extra)
    check = rules.check_text(text, "sms:9")["results"][0]
    assert check["boundary_extra"] == extra
    assert rules.count_text(text)["sms"]["boundary_extra"] == extra


def test_surrogate_pair_is_not_split_across_segments():
    # 66 units + emoji (2) = 68 > 67 -> the emoji starts segment 2 instead of straddling the border
    r = sms("a" * 66 + PARTY + "a" * 5)
    assert r["segments"] == 2 and r["units"] == 73


def test_extension_chars_counted_only_for_gsm7():
    assert sms("~{}")["extension_chars"] == 3
    assert sms("~’")["extension_chars"] == 0


def test_per_segment_switches_with_message_length():
    assert sms("a" * 160)["per_segment"] == 160
    assert sms("a" * 161)["per_segment"] == 153
    assert sms("’" * 71)["per_segment"] == 67


def test_gsm_tables_have_the_documented_sizes():
    assert len(rules.GSM_BASIC) == 127 and len(rules.GSM_EXTENSION) == 10
    for ch in "@£$¥èéùìòÇ\nØø\rÅåΔ_":
        assert rules.is_gsm7(ch)
    assert not rules.is_gsm7("`") and not rules.is_gsm7("á")


GSM_ACCENTS = "é è ù ì ò à ä ö ü ñ ß å ø æ É Ä Ö Ü Ñ Å Ø Æ Ç ¡ ¿ £ ¥ § ¤ Δ".split()
NOT_GSM_ACCENTS = "á í ó ú â ê î ô û ã õ ç ë ï ÿ À È Ì Ò Ù Á Í Ó Ú œ ł ş ğ ı ő".split()


@pytest.mark.parametrize("ch", GSM_ACCENTS)
def test_accented_letters_in_the_gsm7_table(ch):
    """Checked against the gsm0338 1.1.0 codec (2026-11-23)."""
    assert rules.is_gsm7(ch)
    assert sms("Code " + ch * 3)["encoding"] == "GSM-7"


@pytest.mark.parametrize("ch", NOT_GSM_ACCENTS)
def test_accented_letters_outside_the_gsm7_table(ch):
    assert not rules.is_gsm7(ch)
    r = sms("Code " + ch)
    assert r["encoding"] == "UCS-2" and r["culprits"][0]["index"] == 5


@pytest.mark.parametrize("text,starts", [
    ("a" * 152 + "€" + "a" * 152, [0, 152, 304]),   # '€' would straddle units 153/154, so part 2 starts at it
    ("a" * 161, [0, 153]),
    ("~" * 81, [0, 76]),                              # 76 tildes = 152 units, the 77th would straddle
    ("a" * 66 + PARTY + "a" * 5, [0, 66]),            # UCS-2: the emoji would straddle units 67/68
    ("Hello", [0]),
    ("", []),
    ("a" * 160, [0]),
    ("á" * 66 + PARTY + "á" * 66, [0, 66, 132]),
])
def test_segment_starts_are_code_point_positions(text, starts):
    r = sms(text)
    assert r["segment_starts"] == starts and r["segments"] == len(starts)
    assert rules.check_text(text, "sms:9")["results"][0]["segment_starts"] == starts
    assert rules.count_text(text)["sms"]["segment_starts"] == starts


def test_segment_starts_cut_every_segment_within_its_capacity():
    """Each segment holds at most 153 GSM-7 units (or 67 UCS-2 units) and never half a character."""
    text = ("Prices: €12 | €18 [members] {a} ~ " * 30)[:700]
    r = sms(text)
    bounds = r["segment_starts"] + [len(text)]
    for a, b in zip(bounds, bounds[1:]):
        units = sum(2 if ch in rules.GSM_EXTENSION else 1 for ch in text[a:b])
        assert units <= 153
        if b < len(text):            # a segment ends early only when the next character does not fit
            assert units + (2 if text[b] in rules.GSM_EXTENSION else 1) > 153


def test_sms_profile_with_more_segments_allowed():
    r = rules.check_text("a" * 200, "sms:2")["results"][0]
    assert r["pass"] and r["value"] == 2 and r["limit"] == 2
    r = rules.check_text("a" * 200, "sms")["results"][0]
    assert not r["pass"] and r["over"] == 1


def test_readme_newsletter_sample_keeps_its_segment_starts():
    """docs/examples/newsletter.txt (the README example, formerly an eval fixture): 765 units is 5 x 153,
    but a two-unit character never straddles a border, so it needs 6 segments; values cross-checked
    against an external SMS segment calculator on 2026-11-23."""
    from conftest import ROOT
    text = (ROOT / "docs" / "examples" / "newsletter.txt").read_text(encoding="utf-8").rstrip("\n")
    r = sms(text)
    assert (r["encoding"], r["units"], r["segments"], r["boundary_extra"]) == ("GSM-7", 765, 6, 1)
    assert r["segment_starts"] == [0, 147, 294, 443, 592, 739]
    assert "\N{GREEK CAPITAL LETTER OMEGA}" in text and "\N{SECTION SIGN}" in text

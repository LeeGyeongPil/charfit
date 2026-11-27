"""Naive ways to count SMS and Korean carrier length, written down as code (N1-N6).

These are the shortcuts a capable model with Python tends to take when it has no exact rule
table at hand. They are not part of the skill. tests/test_eval_set.py runs them on every
evaluation fixture and checks that their answers fail the graders, so a task case only grades
values that the shortcuts get wrong.

  N1 latin1_is_gsm        "anything up to U+00FF is GSM-7" (extension characters still 2 units)
  N2 ceil_split           exact GSM-7 table, but segments = ceil(units / 153) and the stream of units
                          is cut every 153 units (a two-unit character may straddle a cut);
                          fix_ceil is the same shortcut applied before and after a correct cleanup
  N3 python_euc_kr        len(text.encode("euc_kr")); an exception means "cannot be sent"
  N4 cp949_bytes          len(text.encode("cp949")); an exception means "cannot be sent"
  N5 fix_without_regrowth applies the cleanup but counts the new "..." as one unit, like the "…" it replaced
  N6 unit_offsets         reports segment starts as unit offsets 0, 153, 306, ... instead of character positions
  N7 snippet_table        a widely copied GSM-7 table: the backtick sits where the section sign belongs, so
                          '§' forces UCS-2 and '`' passes as GSM-7 (the no-split rule is right)
  N8 greek_not_gsm        "letters outside Latin are not GSM-7": misses the ten Greek capitals Δ Φ Γ Λ Ω Π Ψ Σ Θ Ξ
  N9 fix_backtick_quote   the cleanup also turns a backtick used as an apostrophe into "'", which the policy
                          ("curly quotes ... change nothing else") does not ask for
  N10 extension_one_unit  the right alphabet and no-split rule, but '€', '[', '{' ... cost one unit like any letter

N7-N9 are the counts an agent writes for itself when the script is missing or broken: the segment loop
is easy to get right, the alphabet table is not. A task case must fail on them, otherwise it does not
show that the answer came from the script.

X weighted length (x-post). A strong model knows the published weights (1 for Latin and the punctuation
ranges, 2 for Hangul and CJK, 23 per link) and writes them as code. What it gets wrong is how
twitter-text decides what is a link and what is one emoji:

  X1 x_codepoint_weights  NFC and the weight ranges are right, links are only http(s):// URLs and every
                          code point of an emoji sequence is weighed alone (a keycap is 1 + 2 + 2 = 5, not 2)
  X2 x_bare_symbol_emoji  exact links and emoji sequences, but a bare (C) or (R) sign counts as an emoji (2);
                          twitter-text 3.1.0 counts it as Latin-1 (1) unless U+FE0F follows
  X3 x_no_cctld           exact emoji, links are http(s)://, www. and bare names with a generic TLD only;
                          file names that end in a country code (README.md, setup.py, install.sh) stay text
  X4 x_without_nfc        exact rules but no NFC normalisation: Hangul saved as jamo (NFD) counts 1 per jamo
"""
from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, Callable, Dict, List, Optional, Pattern

from conftest import rules

SINGLE = rules.SMS_SINGLE
MULTI = rules.SMS_MULTI


def _widths(text: str, encoding: str) -> List[int]:
    if encoding == "GSM-7":
        return [2 if ch in rules.GSM_EXTENSION else 1 for ch in text]
    return [2 if ord(ch) > 0xFFFF else 1 for ch in text]


def _split(widths: List[int], encoding: str) -> List[int]:
    """The correct no-split rule, shared by the variants that only get the alphabet wrong."""
    units = sum(widths)
    if units == 0:
        return []
    if units <= SINGLE[encoding]:
        return [0]
    starts, filled = [0], 0
    for i, w in enumerate(widths):
        if filled + w > MULTI[encoding]:
            starts.append(i)
            filled = 0
        filled += w
    return starts


def _sms(encoding: str, widths: List[int], starts: List[int]) -> Dict[str, Any]:
    return {"encoding": encoding, "units": sum(widths), "segments": len(starts), "segment_starts": starts}


# N1 ----------------------------------------------------------------------------------------
def latin1_is_gsm(text: str) -> Dict[str, Any]:
    gsm = all(ord(ch) <= 0xFF or ch in rules.GSM_EXTENSION for ch in text)
    encoding = "GSM-7" if gsm else "UCS-2"
    widths = _widths(text, encoding)
    return _sms(encoding, widths, _split(widths, encoding))


# N2 ----------------------------------------------------------------------------------------
def ceil_split(text: str) -> Dict[str, Any]:
    encoding = rules.sms_analyze(text)["encoding"]          # the alphabet is right
    widths = _widths(text, encoding)
    units = sum(widths)
    if units == 0:
        return _sms(encoding, widths, [])
    if units <= SINGLE[encoding]:
        return _sms(encoding, widths, [0])
    count = math.ceil(units / MULTI[encoding])
    # a part starts at the character that holds its first unit (offset k * 153)
    starts, offset, k = [0], 0, 1
    for i, w in enumerate(widths):
        while k < count and offset <= k * MULTI[encoding] < offset + w:
            starts.append(i)
            k += 1
        offset += w
    return _sms(encoding, widths, starts)


# N6 ----------------------------------------------------------------------------------------
def unit_offsets(text: str) -> Dict[str, Any]:
    real = rules.sms_analyze(text)
    if real["segments"] <= 1:
        return dict(real)
    out = dict(real)
    out["segment_starts"] = [k * real["per_segment"] for k in range(real["segments"])]
    return out


# N7 / N8 -----------------------------------------------------------------------------------
SECTION = "\N{SECTION SIGN}"
BACKTICK = "\N{GRAVE ACCENT}"
GREEK_CAPITALS = "".join(chr(c) for c in range(0x0391, 0x03AA))


def snippet_is_gsm(ch: str) -> bool:
    if ch == SECTION:
        return False
    return ch == BACKTICK or rules.is_gsm7(ch)


def greek_is_not_gsm(ch: str) -> bool:
    return ch not in GREEK_CAPITALS and rules.is_gsm7(ch)


def with_table(is_gsm: Callable[[str], bool]) -> Callable[[str], Dict[str, Any]]:
    """A hand-written count with the right no-split rule and the given alphabet table."""
    def analyze(text: str) -> Dict[str, Any]:
        encoding = "GSM-7" if all(is_gsm(ch) for ch in text) else "UCS-2"
        widths = _widths(text, encoding)
        return _sms(encoding, widths, _split(widths, encoding))
    return analyze


snippet_table = with_table(snippet_is_gsm)
greek_not_gsm = with_table(greek_is_not_gsm)


# N10 ---------------------------------------------------------------------------------------
def extension_one_unit(text: str) -> Dict[str, Any]:
    encoding = rules.sms_analyze(text)["encoding"]
    widths = [2 if ord(ch) > 0xFFFF else 1 for ch in text] if encoding == "UCS-2" else [1] * len(text)
    return _sms(encoding, widths, _split(widths, encoding))


# N3 / N4 -----------------------------------------------------------------------------------
def _kr_bytes(text: str, codec: str):
    try:
        return len(text.encode(codec))
    except UnicodeEncodeError:
        return None


def python_euc_kr(text: str) -> str:
    return rules.kr_class(_kr_bytes(text, "euc_kr"))


def cp949_bytes(text: str) -> str:
    return rules.kr_class(_kr_bytes(text, "cp949"))


def strict_class(text: str) -> str:
    return rules.kr_class(rules.kr_analyze(text)["bytes"])


# N5 ----------------------------------------------------------------------------------------
def fix_without_regrowth(text: str) -> Dict[str, Any]:
    real = rules.fix_sms(text)
    after = rules.sms_analyze(real["candidate"])
    if after["encoding"] != "GSM-7":
        return {"before": real["before"], "after": {k: after[k] for k in ("encoding", "units", "segments")}}
    # every "…" that became "..." is still counted as one unit
    shrink = sum(2 for r in real["replacements"] if r["from"] == "…")
    units = after["units"] - shrink
    if units <= SINGLE["GSM-7"]:
        segments = 1 if units else 0
    else:
        segments = math.ceil(units / MULTI["GSM-7"])
    return {"before": real["before"], "after": {"encoding": "GSM-7", "units": units, "segments": segments}}


# Totals in the same shape as the script's JSON, so a grader sees the same kind of answer --------
def sms_totals(texts: List[str], analyze: Callable[[str], Dict[str, Any]]) -> Dict[str, int]:
    rows = [analyze(t) for t in texts]
    return {
        "segments": sum(r["segments"] for r in rows),
        "gsm7": sum(1 for r in rows if r["encoding"] == "GSM-7"),
        "ucs2": sum(1 for r in rows if r["encoding"] == "UCS-2"),
        "multi_segment": sum(1 for r in rows if r["segments"] >= 2),
    }


def fix_totals(texts: List[str], fix: Callable[[str], Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    out = {side: {"segments": 0, "gsm7": 0, "ucs2": 0} for side in ("before", "after")}
    for t in texts:
        r = fix(t)
        for side in ("before", "after"):
            out[side]["segments"] += r[side]["segments"]
            out[side]["gsm7" if r[side]["encoding"] == "GSM-7" else "ucs2"] += 1
    return out


def fix_n1(text: str) -> Dict[str, Any]:
    """N1 inside a cleanup: the replacements are right, the alphabet check is 'up to U+00FF'."""
    real = rules.fix_sms(text)
    before, after = latin1_is_gsm(text), latin1_is_gsm(real["candidate"])
    keep = ("encoding", "units", "segments")
    return {"before": {k: before[k] for k in keep}, "after": {k: after[k] for k in keep}}


def fix_ceil(text: str) -> Dict[str, Any]:
    """N2 inside a cleanup: the replacements are right, segments are ceil(units / per segment)."""
    real = rules.fix_sms(text)
    before, after = ceil_split(text), ceil_split(real["candidate"])
    keep = ("encoding", "units", "segments")
    return {"before": {k: before[k] for k in keep}, "after": {k: after[k] for k in keep}}


def fix_table(analyze: Callable[[str], Dict[str, Any]]) -> Callable[[str], Dict[str, Any]]:
    """The right cleanup, measured before and after with another count (N7, N8 inside a cleanup)."""
    def run(text: str) -> Dict[str, Any]:
        real = rules.fix_sms(text)
        before, after = analyze(text), analyze(real["candidate"])
        keep = ("encoding", "units", "segments")
        return {"before": {k: before[k] for k in keep}, "after": {k: after[k] for k in keep}}
    return run


def fix_backtick_quote(text: str) -> Dict[str, Any]:
    """N9: the cleanup also replaces a backtick with a straight apostrophe."""
    real = rules.fix_sms(text)
    before, after = rules.sms_analyze(text), rules.sms_analyze(real["candidate"].replace(BACKTICK, "'"))
    keep = ("encoding", "units", "segments")
    return {"before": {k: before[k] for k in keep}, "after": {k: after[k] for k in keep}}


def kr_totals(texts: List[str], classify: Callable[[str], str]) -> Dict[str, int]:
    out = {"SMS": 0, "LMS": 0, "OVER": 0, "FAIL": 0}
    for t in texts:
        out[classify(t)] += 1
    return out


# X1-X4 -------------------------------------------------------------------------------------
SCHEME_URL_RE = re.compile(r"https?://[\x21-\x7e]+")
# the script's link pattern with the generic TLDs only (no two-letter country codes)
GTLD_ONLY_URL_RE = re.compile(rules._URL_RE.pattern.replace(rules._TLDS, rules._GTLDS), re.IGNORECASE)
# the script's emoji pattern plus a bare (C) or (R) sign
EMOJI_WITH_BARE_SYMBOLS_RE = re.compile(rules._EMOJI_RE.pattern + "|[©®]")
NO_EMOJI_RE = re.compile("(?!)")


def _x_weight(text: str, url_re: Pattern[str], emoji_re: Pattern[str], nfc: bool = True) -> int:
    """The script's counting loop with the link and emoji patterns swapped in."""
    if nfc:
        text = unicodedata.normalize("NFC", text)
    total, pos, rest = 0, 0, []
    for m in url_re.finditer(text):
        end = m.end()
        while end > m.start() and text[end - 1] in rules._URL_TRAILING:
            end -= 1
        rest.append(text[pos:m.start()])
        total += rules.X_URL_WEIGHT
        pos = end
    rest.append(text[pos:])
    remainder = "".join(rest)
    total += rules.X_EMOJI_WEIGHT * len(emoji_re.findall(remainder))
    for ch in emoji_re.sub("", remainder):
        total += 1 if any(a <= ord(ch) <= b for a, b in rules.X_LIGHT_RANGES) else 2
    return total


def x_codepoint_weights(text: str) -> int:
    return _x_weight(text, SCHEME_URL_RE, NO_EMOJI_RE)


def x_bare_symbol_emoji(text: str) -> int:
    return _x_weight(text, rules._URL_RE, EMOJI_WITH_BARE_SYMBOLS_RE)


def x_no_cctld(text: str) -> int:
    return _x_weight(text, GTLD_ONLY_URL_RE, rules._EMOJI_RE)


def x_without_nfc(text: str) -> int:
    return _x_weight(text, rules._URL_RE, rules._EMOJI_RE, nfc=False)


def x_exact(text: str) -> int:
    """Sanity anchor: with the script's own patterns the loop gives the script's number."""
    return _x_weight(text, rules._URL_RE, rules._EMOJI_RE)


X_VARIANTS: Dict[str, Callable[[str], int]] = {
    "X1": x_codepoint_weights, "X2": x_bare_symbol_emoji, "X3": x_no_cctld, "X4": x_without_nfc,
}


def over_limit(weighted: int) -> Optional[int]:
    return max(0, weighted - rules.X_LIMIT)

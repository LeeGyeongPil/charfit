"""Counting rules used by charfit (pure functions, standard library only).

Every table here is a statement of a public rule, not a copy of any code:

* GSM 03.38 default alphabet (127 characters) and ESC extension table (10 characters)
  - 3GPP TS 23.038, https://www.3gpp.org/ftp/Specs/archive/23_series/23.038/ (checked 2026-11-23)
  - segment sizes 160/153 (GSM-7) and 70/67 (UCS-2):
    https://www.twilio.com/docs/glossary/what-sms-character-limit (checked 2026-11-23)
* X weighted length: scale 100, default weight 200, weight 100 for the ranges below, URL 23,
  limit 280 - https://docs.x.com/fundamentals/counting-characters (checked 2026-11-23)
* Korean SMS 90 bytes / LMS 2,000 bytes in EUC-KR:
  https://docs.nhncloud.com/en/Notification/SMS/en/api-guide-v2.4/ (checked 2026-11-23)
* HTML maxlength counts UTF-16 code units:
  https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/maxlength (checked 2026-11-23)
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

# --------------------------------------------------------------------------
# SMS (GSM-7 / UCS-2)
# --------------------------------------------------------------------------

# GSM 03.38 basic character set, in table order (0x1B, the escape code, is not a character).
GSM_BASIC = (
    "@£$¥èéùìòÇ\nØø\rÅå"
    "Δ_ΦΓΛΩΠΨΣΘΞ"
    "ÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§"
    "¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
# Characters reached through the ESC code: they cost two septets.
GSM_EXTENSION = "\f^{}\\[~]|€"

assert len(GSM_BASIC) == 127 and len(set(GSM_BASIC)) == 127
assert len(GSM_EXTENSION) == 10

SMS_SINGLE = {"GSM-7": 160, "UCS-2": 70}
SMS_MULTI = {"GSM-7": 153, "UCS-2": 67}


def codepoint(ch: str) -> str:
    return "U+%04X" % ord(ch)


def is_gsm7(ch: str) -> bool:
    return ch in GSM_BASIC or ch in GSM_EXTENSION


def sms_analyze(text: str) -> Dict[str, Any]:
    """Encoding, billed units, segment count and the characters that force UCS-2.

    A UCS-2 message counts UTF-16 code units (an emoji is 2). A GSM-7 message counts septets
    (an extension character is 2). A two-unit character is never split across segments, so a
    segment can end one unit early - that is why '€' at the boundary can add a segment.
    """
    culprits: List[Dict[str, Any]] = []
    for i, ch in enumerate(text):
        if not is_gsm7(ch):
            culprits.append({"index": i, "char": ch, "codepoint": codepoint(ch), "reason": "not_gsm7"})
    if culprits:
        encoding = "UCS-2"
        widths = [2 if ord(ch) > 0xFFFF else 1 for ch in text]
    else:
        encoding = "GSM-7"
        widths = [2 if ch in GSM_EXTENSION else 1 for ch in text]
    units = sum(widths)
    # segment_starts: 각 조각이 시작하는 입력 문자열의 코드 포인트 위치(칸 위치가 아니다)
    if units == 0:
        segment_starts: List[int] = []
    elif units <= SMS_SINGLE[encoding]:
        segment_starts = [0]
    else:
        segment_starts, filled, cap = [0], 0, SMS_MULTI[encoding]
        for i, w in enumerate(widths):
            # 2칸 문자가 경계에 걸치면 자르지 않고 다음 조각으로 넘긴다(그래서 조각이 한 칸 일찍 끝날 수 있다)
            if filled + w > cap:
                segment_starts.append(i)
                filled = 0
            filled += w
    segments = len(segment_starts)
    per_segment = SMS_SINGLE[encoding] if segments <= 1 else SMS_MULTI[encoding]
    # 단순 나눗셈(ceil(units / per_segment))보다 늘어난 조각 수: 2단위 문자를 경계에서 자르지 않아 생긴 몫
    by_division = 0 if units == 0 else -(-units // per_segment)
    return {
        "encoding": encoding,
        "units": units,
        "segments": segments,
        "per_segment": per_segment,
        "boundary_extra": segments - by_division,
        "extension_chars": sum(1 for ch in text if ch in GSM_EXTENSION) if not culprits else 0,
        "segment_starts": segment_starts,
        "culprits": culprits,
    }


# --------------------------------------------------------------------------
# X (twitter-text config v3 numbers)
# --------------------------------------------------------------------------

X_LIMIT = 280
X_URL_WEIGHT = 23
X_EMOJI_WEIGHT = 2
# Code point ranges that weigh 1; everything else weighs 2.
X_LIGHT_RANGES = ((0, 4351), (8192, 8205), (8208, 8223), (8242, 8247))

# Generic top-level domains recognised without a scheme (a fixed subset of the IANA root zone).
_GTLDS = ("com|net|org|info|biz|edu|gov|mil|int|app|dev|xyz|shop|store|blog|online|site|tech|"
          "cloud|page|link|news|live|art|design")
# Every two-letter country code top-level domain (IANA root zone). A file name such as
# "setup.py" (Paraguay) or "README.md" (Moldova) therefore counts as a 23-weight link on X.
_CCTLDS = (
    "ac|ad|ae|af|ag|ai|al|am|an|ao|aq|ar|as|at|au|aw|ax|az|ba|bb|bd|be|bf|bg|bh|bi|bj|bl|bm|bn|"
    "bo|bq|br|bs|bt|bv|bw|by|bz|ca|cc|cd|cf|cg|ch|ci|ck|cl|cm|cn|co|cr|cu|cv|cw|cx|cy|cz|de|dj|"
    "dk|dm|do|dz|ec|ee|eg|eh|er|es|et|eu|fi|fj|fk|fm|fo|fr|ga|gb|gd|ge|gf|gg|gh|gi|gl|gm|gn|gp|"
    "gq|gr|gs|gt|gu|gw|gy|hk|hm|hn|hr|ht|hu|id|ie|il|im|in|io|iq|ir|is|it|je|jm|jo|jp|ke|kg|kh|"
    "ki|km|kn|kp|kr|kw|ky|kz|la|lb|lc|li|lk|lr|ls|lt|lu|lv|ly|ma|mc|md|me|mf|mg|mh|mk|ml|mm|mn|"
    "mo|mp|mq|mr|ms|mt|mu|mv|mw|mx|my|mz|na|nc|ne|nf|ng|ni|nl|no|np|nr|nu|nz|om|pa|pe|pf|pg|ph|"
    "pk|pl|pm|pn|pr|ps|pt|pw|py|qa|re|ro|rs|ru|rw|sa|sb|sc|sd|se|sg|sh|si|sj|sk|sl|sm|sn|so|sr|"
    "ss|st|su|sv|sx|sy|sz|tc|td|tf|tg|th|tj|tk|tl|tm|tn|to|tp|tr|tt|tv|tw|tz|ua|ug|uk|um|us|uy|"
    "uz|va|vc|ve|vg|vi|vn|vu|wf|ws|ye|yt|za|zm|zw"
)
_TLDS = _GTLDS + "|" + _CCTLDS
_URL_RE = re.compile(
    r"(?:https?://[\x21-\x7e]+)"
    r"|(?:(?<![\w@./-])www\.[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*(?:/[\x21-\x7e]*)?)"
    r"|(?:(?<![\w@./-])[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.(?:%s)(?![A-Za-z0-9_@+-])(?:/[\x21-\x7e]*)?)" % _TLDS,
    re.IGNORECASE,
)
_URL_TRAILING = ".,;:!?)]}'\"’”"

# Characters that start an emoji: the pictographic blocks plus the symbols that are emoji even
# in text style (‼ ™ arrows, ▶, ⭐, ㊗ ...). © and ® are different: the official twitter-text
# 3.1.0 counts a bare © as Latin-1 (weight 1) and only © followed by U+FE0F as an emoji (2).
_EMOJI_BASE = (
    "[\U0001F300-\U0001FAFF☀-➿"
    "\U0001F004\U0001F0CF\U0001F170\U0001F171\U0001F17E\U0001F17F\U0001F18E\U0001F191-\U0001F19A"
    "\U0001F201\U0001F202\U0001F21A\U0001F22F\U0001F232-\U0001F23A\U0001F250\U0001F251"
    "‼⁉™ℹ↔-↙↩↪⌚⌛⌨⏏"
    "⏩-⏳⏸-⏺Ⓜ▪▫▶◀◻-◾⤴⤵"
    "⬅-⬇⬛⬜⭐⭕〰〽㊗㊙]"
)
# One emoji = one weight-2 unit on X, however many code points it has:
#   flag tag sequence (🏴 + tag letters + cancel tag), regional-indicator pair (🇰🇷),
#   keycap (digit + U+FE0F + U+20E3), © or ® followed by U+FE0F,
#   and base + U+FE0F + skin tone joined by U+200D (man, woman, girl: one family emoji).
_EMOJI_RE = re.compile(
    "(?:\U0001F3F4[\U000E0020-\U000E007E]+\U000E007F)|"
    "(?:[\U0001F1E6-\U0001F1FF]{2})|"
    "(?:[0-9#*]\ufe0f?⃣)|"
    "(?:[©®]\ufe0f)|"
    "(?:" + _EMOJI_BASE + "\ufe0f?[\U0001F3FB-\U0001F3FF]?"
    "(?:\u200d" + _EMOJI_BASE + "\ufe0f?[\U0001F3FB-\U0001F3FF]?)*)"
)


def _find_urls(text: str) -> List[Tuple[int, int]]:
    spans: List[Tuple[int, int]] = []
    for m in _URL_RE.finditer(text):
        end = m.end()
        # Closing punctuation right after a link belongs to the sentence, not the link.
        while end > m.start() and text[end - 1] in _URL_TRAILING:
            end -= 1
        if end > m.start():
            spans.append((m.start(), end))
    return spans


def x_analyze(text: str) -> Dict[str, Any]:
    """Weighted length as X counts it: NFC first, links 23, emoji sequences 2, other characters 1 or 2."""
    # X 는 NFC 로 정규화한 뒤 센다: 맥에서 복사한 NFD 한글(자모 3개)도 음절 하나로 센다
    text = unicodedata.normalize("NFC", text)
    nfc_code_points = len(text)
    urls: List[str] = []
    total = 0
    rest: List[str] = []
    pos = 0
    for start, end in _find_urls(text):
        rest.append(text[pos:start])
        urls.append(text[start:end])
        total += X_URL_WEIGHT
        pos = end
    rest.append(text[pos:])
    remainder = "".join(rest)
    emoji = list(_EMOJI_RE.finditer(remainder))
    total += X_EMOJI_WEIGHT * len(emoji)
    remainder = _EMOJI_RE.sub("", remainder)
    for ch in remainder:
        cp = ord(ch)
        total += 1 if any(a <= cp <= b for a, b in X_LIGHT_RANGES) else 2
    return {"weighted": total, "urls": urls, "emoji": len(emoji), "nfc_code_points": nfc_code_points}


# --------------------------------------------------------------------------
# Korean carriers (EUC-KR bytes)
# --------------------------------------------------------------------------

KR_SMS_LIMIT = 90
KR_LMS_LIMIT = 2000

# Python's euc_kr codec encodes Hangul outside KS X 1001 as a multi-byte jamo sequence
# (for example U+B620 becomes 8 bytes) instead of raising an error. A real EUC-KR gateway
# cannot send such a character, so every character is checked on its own.


def kr_analyze(text: str, codec: str = "euc-kr") -> Dict[str, Any]:
    """Byte count with strict EUC-KR (default) or CP949; unsendable characters are listed."""
    py_codec = "euc_kr" if codec == "euc-kr" else "cp949"
    total = 0
    culprits: List[Dict[str, Any]] = []
    for i, ch in enumerate(text):
        try:
            n = len(ch.encode(py_codec))
        except UnicodeEncodeError:
            culprits.append({"index": i, "char": ch, "codepoint": codepoint(ch), "reason": "unencodable"})
            continue
        if codec == "euc-kr" and n > 2:
            try:
                cp949_bytes: Optional[int] = len(ch.encode("cp949"))
            except UnicodeEncodeError:
                cp949_bytes = None
            culprits.append({"index": i, "char": ch, "codepoint": codepoint(ch),
                             "reason": "not_in_ks_x_1001", "cp949_bytes": cp949_bytes})
            continue
        total += n
    return {"codec": codec, "bytes": None if culprits else total, "culprits": culprits}


def kr_class(bytes_: Optional[int]) -> str:
    if bytes_ is None:
        return "FAIL"
    if bytes_ <= KR_SMS_LIMIT:
        return "SMS"
    if bytes_ <= KR_LMS_LIMIT:
        return "LMS"
    return "OVER"


# --------------------------------------------------------------------------
# Plain length measures
# --------------------------------------------------------------------------

def basic_lengths(text: str) -> Dict[str, int]:
    return {
        "code_points": len(text),
        "utf16_units": len(text.encode("utf-16-le")) // 2,
        "utf8_bytes": len(text.encode("utf-8")),
    }


def has_lone_surrogate(text: str) -> bool:
    return any(0xD800 <= ord(ch) <= 0xDFFF for ch in text)


# --------------------------------------------------------------------------
# Profiles
# --------------------------------------------------------------------------

class ProfileError(ValueError):
    """Raised for an unknown profile or a bad limit. `kind` is `unknown` or `limit`."""

    def __init__(self, kind: str, name: str) -> None:
        super().__init__("%s:%s" % (kind, name))
        self.kind = kind
        self.name = name


KNOWN_PROFILES = "sms, sms:N, x-post, kr-sms, kr-lms, utf16:N, utf8:N, chars:N"
_LIMIT_PROFILES = ("sms", "utf16", "utf8", "chars")
_FIXED_PROFILES = ("x-post", "kr-sms", "kr-lms")


def parse_profiles(spec: str) -> List[Tuple[str, str, Optional[int]]]:
    """Parse 'sms,utf8:120' into [(raw, kind, limit)]. Raises ProfileError."""
    out: List[Tuple[str, str, Optional[int]]] = []
    for raw in spec.split(","):
        raw = raw.strip()
        kind, sep, arg = raw.partition(":")
        if kind in _FIXED_PROFILES and not sep:
            out.append((raw, kind, None))
        elif kind in _LIMIT_PROFILES:
            if not sep and kind == "sms":
                out.append((raw, kind, 1))
                continue
            if not (arg.isascii() and arg.isdigit() and int(arg) > 0):
                raise ProfileError("limit", raw)
            out.append((raw, kind, int(arg)))
        else:
            raise ProfileError("unknown", raw)
    return out


def _result(profile: str, measure: str, value: Optional[int], limit: int, culprits: List[Dict[str, Any]]) -> Dict[str, Any]:
    over = None if value is None else max(0, value - limit)
    return {"profile": profile, "pass": value is not None and value <= limit, "measure": measure,
            "value": value, "limit": limit, "over": over, "culprits": culprits}


def evaluate_profile(text: str, raw: str, kind: str, limit: Optional[int], kr_codec: str = "euc-kr") -> Dict[str, Any]:
    if kind == "sms":
        sms = sms_analyze(text)
        r = _result(raw, "sms_segments", sms["segments"], limit or 1, sms["culprits"])
        r.update({"encoding": sms["encoding"], "units": sms["units"], "per_segment": sms["per_segment"],
                  "extension_chars": sms["extension_chars"], "boundary_extra": sms["boundary_extra"],
                  "segment_starts": sms["segment_starts"]})
        return r
    if kind == "x-post":
        x = x_analyze(text)
        r = _result(raw, "x_weighted", x["weighted"], X_LIMIT, [])
        r.update({"x_urls": x["urls"], "x_emoji": x["emoji"], "x_nfc_code_points": x["nfc_code_points"]})
        return r
    if kind in ("kr-sms", "kr-lms"):
        kr = kr_analyze(text, kr_codec)
        r = _result(raw, "euc_kr_bytes", kr["bytes"], KR_SMS_LIMIT if kind == "kr-sms" else KR_LMS_LIMIT, kr["culprits"])
        r["codec"] = kr_codec
        return r
    lengths = basic_lengths(text)
    if kind == "utf16":
        return _result(raw, "utf16_units", lengths["utf16_units"], limit or 1, [])
    if kind == "utf8":
        return _result(raw, "utf8_bytes", lengths["utf8_bytes"], limit or 1, [])
    return _result(raw, "code_points", lengths["code_points"], limit or 1, [])


def check_text(text: str, spec: str, kr_codec: str = "euc-kr") -> Dict[str, Any]:
    profiles = parse_profiles(spec)
    results = [evaluate_profile(text, raw, kind, limit, kr_codec) for raw, kind, limit in profiles]
    return {"pass": all(r["pass"] for r in results), "length": basic_lengths(text), "results": results}


def count_text(text: str, kr_codec: str = "euc-kr") -> Dict[str, Any]:
    sms = sms_analyze(text)
    x = x_analyze(text)
    strict = kr_analyze(text, "euc-kr")
    cp949 = kr_analyze(text, "cp949")
    chosen = strict if kr_codec == "euc-kr" else cp949
    return {
        "length": basic_lengths(text),
        "sms": {k: sms[k] for k in ("encoding", "units", "segments", "per_segment", "extension_chars",
                                         "boundary_extra", "segment_starts", "culprits")},
        "x_weighted": x["weighted"],
        "x_urls": x["urls"],
        "euc_kr": {"bytes": strict["bytes"], "culprits": strict["culprits"]},
        "cp949_bytes": cp949["bytes"],
        "kr_codec": kr_codec,
        "kr_class": kr_class(chosen["bytes"]),
    }


# --------------------------------------------------------------------------
# fix-sms: replacements that make a message GSM-7 safe
# --------------------------------------------------------------------------

_SPACE_LIKE = {0x00A0, 0x202F, 0x3000} | set(range(0x2000, 0x200B))
_SIMPLE = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...",
}


def _is_combining(ch: str) -> bool:
    return 0x0300 <= ord(ch) <= 0x036F


def fix_sms(text: str) -> Dict[str, Any]:
    """Return a GSM-7 friendly candidate; never changes anything that has no safe equivalent."""
    pieces: List[str] = []
    replacements: List[Dict[str, Any]] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in _SIMPLE:
            to = _SIMPLE[ch]
        elif ord(ch) in _SPACE_LIKE:
            to = " "
        else:
            j = i + 1
            while j < n and _is_combining(text[j]):
                j += 1
            group = text[i:j]
            composed = unicodedata.normalize("NFC", group)
            if j > i + 1 and composed != group:
                replacements.append({"index": i, "from": group, "to": composed})
                pieces.append(composed)
                i = j
                continue
            pieces.append(group)
            i = j
            continue
        replacements.append({"index": i, "from": ch, "to": to})
        pieces.append(to)
        i += 1
    candidate = "".join(pieces)
    before = sms_analyze(text)
    after = sms_analyze(candidate)
    brief = ("encoding", "units", "segments")
    return {
        "candidate": candidate,
        "replacements": replacements,
        "before": {k: before[k] for k in brief},
        "after": {k: after[k] for k in brief},
        "remaining": after["culprits"],
    }


# --------------------------------------------------------------------------
# Batches (--jsonl): the same per-text functions, plus totals the agent can quote as is
# --------------------------------------------------------------------------
# An item is {"id": str, "line": int, "text": str}. Totals are sums and counts over the items,
# so nobody has to add up per-item numbers by hand.

def check_many(items: List[Dict[str, Any]], spec: str, kr_codec: str = "euc-kr") -> Dict[str, Any]:
    profiles = parse_profiles(spec)
    has_sms = any(kind == "sms" for _, kind, _ in profiles)
    has_kr = any(kind in ("kr-sms", "kr-lms") for _, kind, _ in profiles)
    by_profile: Dict[str, Dict[str, int]] = {raw: {"pass": 0, "fail": 0} for raw, _, _ in profiles}
    sms_totals = {"segments": 0, "gsm7": 0, "ucs2": 0, "multi_segment": 0}
    kr_totals = {"SMS": 0, "LMS": 0, "OVER": 0, "FAIL": 0}
    out_items: List[Dict[str, Any]] = []
    failed_ids: List[str] = []
    for item in items:
        r = check_text(item["text"], spec, kr_codec)
        entry: Dict[str, Any] = {"id": item["id"], "line": item["line"], "pass": r["pass"]}
        for res in r["results"]:
            by_profile[res["profile"]]["pass" if res["pass"] else "fail"] += 1
        if has_sms:
            # 같은 문구면 sms 한도(sms:N)와 무관하게 조각 수가 같으므로 첫 SMS 결과로 합계를 낸다
            sms = next(res for res in r["results"] if res["measure"] == "sms_segments")
            sms_totals["segments"] += sms["value"]
            sms_totals["gsm7" if sms["encoding"] == "GSM-7" else "ucs2"] += 1
            sms_totals["multi_segment"] += 1 if sms["value"] >= 2 else 0
        if has_kr:
            kr = next(res for res in r["results"] if res["measure"] == "euc_kr_bytes")
            entry["kr_class"] = kr_class(kr["value"])
            kr_totals[entry["kr_class"]] += 1
        entry["length"] = r["length"]
        entry["results"] = r["results"]
        out_items.append(entry)
        if not r["pass"]:
            failed_ids.append(item["id"])
    totals: Dict[str, Any] = {
        "items": len(out_items),
        "pass": len(out_items) - len(failed_ids),
        "fail": len(failed_ids),
        "failed_ids": failed_ids,
        "by_profile": by_profile,
    }
    if has_sms:
        totals["sms"] = sms_totals
    if has_kr:
        totals["kr_class"] = kr_totals
    return {"pass": not failed_ids, "items": out_items, "totals": totals}


def fix_many(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    out_items: List[Dict[str, Any]] = []
    sums = {side: {"segments": 0, "gsm7": 0, "ucs2": 0} for side in ("before", "after")}
    changed = replaced = 0
    still_ucs2: List[str] = []
    for item in items:
        r = fix_sms(item["text"])
        out_items.append({"id": item["id"], "line": item["line"], **r})
        changed += 1 if r["replacements"] else 0
        replaced += len(r["replacements"])
        # 치환 뒤 문구를 처음부터 다시 쟀으므로(fix_sms 의 after) '...' 로 길어진 몫도 합계에 들어간다
        for side in ("before", "after"):
            sums[side]["segments"] += r[side]["segments"]
            sums[side]["gsm7" if r[side]["encoding"] == "GSM-7" else "ucs2"] += 1
        if r["after"]["encoding"] == "UCS-2":
            still_ucs2.append(item["id"])
    totals = {"items": len(out_items), "changed": changed, "replacements": replaced,
              "before": sums["before"], "after": sums["after"], "still_ucs2_ids": still_ucs2}
    return {"items": out_items, "totals": totals}

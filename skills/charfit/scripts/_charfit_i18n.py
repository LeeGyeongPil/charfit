"""Messages for charfit in English and Korean, and how the language is chosen.

Every sentence a person reads lives in MESSAGES (one table per language, identical keys).
JSON output never uses these tables, so it is the same in both languages.
"""
from __future__ import annotations

from typing import Dict, Mapping, Optional

LANGS = ("en", "ko")

MESSAGES: Dict[str, Dict[str, str]] = {
    "en": {
        "help.description": (
            "Count text the way each platform does: SMS segments (GSM-7/UCS-2), X weighted length, "
            "Korean SMS/LMS bytes (strict EUC-KR), UTF-16 and UTF-8 limits. Reports the character "
            "that causes an overflow or an encoding switch."
        ),
        "help.epilog": (
            "Profiles: sms, sms:N, x-post, kr-sms, kr-lms, utf16:N, utf8:N, chars:N. "
            "Exit codes: 0 ok, 1 limit exceeded (check) or no GSM-7 candidate (fix-sms), 2 usage error. "
            "If TEXT starts with a dash, put -- before it."
        ),
        "help.cmd_count": "show every measure for the text",
        "help.cmd_check": "check the text against one or more limits (profiles)",
        "help.cmd_fix": "propose a GSM-7 safe candidate (curly quotes, dashes, ellipsis, odd spaces)",
        "help.text": "the text to measure; '-' reads standard input",
        "help.file": "read the text from this UTF-8 file (one trailing newline is removed)",
        "help.jsonl": "read many texts from a UTF-8 JSON Lines file, one {{\"id\": ..., \"text\": ...}} per line, and add totals",
        "help.json": "print JSON (keys are always English)",
        "help.profile": "comma-separated profiles, for example sms,x-post,utf8:120",
        "help.kr_codec": "Korean byte rule: euc-kr (strict, default) or cp949 (extended Hangul counts 2 bytes)",
        "help.lang": "output language (default: CHARFIT_LANG, then LC_ALL, LC_MESSAGES, LANG)",
        "help.help": "show this help message and exit",
        "help.usage": "usage:",
        "help.options": "options",
        "help.positional": "arguments",
        "help.commands": "commands",
        "value.na": "n/a",
        "count.title": "Measures for the text",
        "count.code_points": "Code points",
        "count.utf16": "UTF-16 code units",
        "count.utf8": "UTF-8 bytes",
        "count.sms_encoding": "SMS encoding",
        "count.sms_units": "SMS billed units",
        "count.sms_segments": "SMS segments",
        "count.x": "X weighted length",
        "count.euc_kr": "EUC-KR bytes (strict)",
        "count.cp949": "CP949 bytes",
        "count.kr_class": "Korean carrier class",
        "count.per_segment": "{n} per segment",
        "count.of_limit": "{n} of {limit}",
        "count.note_gsm": "Not GSM-7 (forces UCS-2):",
        "count.note_kr": "Cannot be sent as EUC-KR:",
        "count.note_urls": "Links counted as 23 on X:",
        "check.pass": "PASS",
        "check.fail": "FAIL",
        "check.line": "{status} {profile}: {value} {measure} (limit {limit}{over})",
        "check.over": ", over by {n}",
        "check.detail_sms": "encoding {encoding}, {units} billed units, {per_segment} per segment",
        "sms.boundary_extra": "{n} more segment(s) than {units}/{per_segment} suggests: a 2-unit character is never split across segments",
        "check.detail_urls": "links counted as 23: {urls}",
        "check.detail_emoji": "{n} emoji counted as 2 each (keycaps, flags, skin tones and joined sequences included)",
        "check.detail_nfc": "counted after NFC normalization, as X does: {before} code points became {after}",
        "sms.parts_title": "SMS segments start at (0-based code point index):",
        "sms.part": "part {n}: index {index} «{head}»",
        "batch.item": "{status} {id} (line {line}): {details}",
        "batch.detail": "{profile} {value} {measure}",
        "batch.detail_sms": "{profile} {value} {measure} ({encoding}, {units} units, parts start at index {starts})",
        "batch.detail_kr": "{profile} {value} {measure} (class {cls})",
        "batch.total": "Total: {items} items, {passed} pass all profiles, {failed} fail a profile",
        "batch.total_profile": "{profile}: {passed} pass, {failed} do not pass",
        "batch.failed_ids": "Ids that fail a profile: {ids}",
        "batch.total_sms": "Total SMS: {segments} segments billed; {gsm7} GSM-7 items, {ucs2} UCS-2 items, {multi} items with 2+ segments",
        "batch.total_kr": "Total Korean classes: SMS {SMS}, LMS {LMS}, OVER {OVER} (above 2,000 bytes), FAIL {FAIL} (cannot be sent)",
        "fixbatch.item": "{id} (line {line}): {n} replacement(s); before {before_encoding} {before_units} units {before_segments} segment(s), after {after_encoding} {after_units} units {after_segments} segment(s)",
        "fixbatch.total": "Total: {items} items, {changed} changed, {n} replacements",
        "fixbatch.total_before": "Total before cleanup: {segments} segments; {gsm7} GSM-7, {ucs2} UCS-2",
        "fixbatch.total_after": "Total after cleanup: {segments} segments; {gsm7} GSM-7, {ucs2} UCS-2",
        "fixbatch.still_ucs2": "Still UCS-2 after cleanup: {ids}",
        "fixbatch.all_gsm7": "Every candidate is GSM-7.",
        "check.all_pass": "Result: all profiles pass.",
        "check.some_fail": "Result: {n} of {m} profiles fail.",
        "measure.sms_segments": "SMS segment(s)",
        "measure.x_weighted": "weighted X length",
        "measure.euc_kr_bytes": "bytes",
        "measure.utf16_units": "UTF-16 units",
        "measure.utf8_bytes": "UTF-8 bytes",
        "measure.code_points": "code points",
        "list.more": "... and {n} more (use --json for the full list)",
        "culprit.line": "index {index} '{char}' {codepoint}: {reason}",
        "reason.not_gsm7": "not in GSM-7, the message becomes UCS-2",
        "reason.unencodable": "cannot be encoded, sending would fail",
        "reason.not_in_ks_x_1001": "outside KS X 1001, not valid EUC-KR (CP949 bytes: {cp949})",
        "fix.candidate": "Candidate: {text}",
        "fix.replacements": "Replacements:",
        "fix.none": "No replacements were needed.",
        "fix.replacement": "index {index}: '{src}' -> '{dst}'",
        "fix.before": "Before: {encoding}, {units} units, {segments} segment(s)",
        "fix.after": "After: {encoding}, {units} units, {segments} segment(s)",
        "fix.remaining": "Still not GSM-7 in the candidate (indexes refer to the candidate):",
        "fix.ok": "The candidate is GSM-7 safe.",
        "fix.not_ok": "Not GSM-7 yet: {n} character(s) have no safe replacement.",
        "err.unknown_profile": "unknown profile '{name}' (known: {known})",
        "err.profile_limit": "profile '{name}' needs a positive integer limit",
        "err.file_not_found": "cannot read file '{path}': not found",
        "err.file_is_dir": "cannot read file '{path}': it is a directory",
        "err.file_denied": "cannot read file '{path}': permission denied",
        "err.file_other": "cannot read file '{path}': {reason}",
        "err.not_utf8": "'{path}' is not valid UTF-8 (byte offset {offset})",
        "err.arg_not_utf8": "the TEXT argument is not valid UTF-8; pass the text with --file or '-' instead",
        "err.both_inputs": "give either TEXT or --file, not both",
        "err.one_input": "give only one of TEXT, '-', --file or --jsonl",
        "err.no_input": "no input text (pass TEXT, '-' for stdin, or --file PATH)",
        "err.no_input_batch": "no input text (pass TEXT, '-' for stdin, --file PATH or --jsonl PATH)",
        "err.jsonl_bad_json": "'{path}' line {line} is not valid JSON",
        "err.jsonl_no_text": "'{path}' line {line} has no \"text\" string",
        "err.jsonl_bad_id": "'{path}' line {line} has an \"id\" that is not a string or an integer",
        "err.jsonl_surrogate": "'{path}' line {line} has a lone surrogate in \"text\"",
        "err.jsonl_empty": "'{path}' has no items (every line is blank)",
        "err.usage": "{message} (see --help)",
        "err.arg_required": "the following arguments are required: {names}",
        "err.arg_unrecognized": "unrecognized arguments: {names}",
        "err.arg_invalid_choice": "argument {name}: invalid choice: {value} (choose from {choices})",
        "err.arg_expected_one": "argument {name}: expected one argument",
        "help.version": "show the version number and exit",
    },
    "ko": {
        "help.description": (
            "플랫폼이 실제로 세는 방식으로 글자 수를 잽니다: SMS 건수(GSM-7/UCS-2), X 가중 길이, "
            "국내 SMS/LMS 바이트(엄격 EUC-KR), UTF-16·UTF-8 한도. 한도를 넘기거나 인코딩이 바뀌는 "
            "원인 문자를 알려 줍니다."
        ),
        "help.epilog": (
            "프로필: sms, sms:N, x-post, kr-sms, kr-lms, utf16:N, utf8:N, chars:N. "
            "종료 코드: 0 정상, 1 한도 초과(check) 또는 GSM-7 후보 없음(fix-sms), 2 사용 오류. "
            "TEXT 가 대시로 시작하면 앞에 -- 를 붙이세요."
        ),
        "help.cmd_count": "문구의 모든 길이 측정값을 보여 줍니다",
        "help.cmd_check": "문구가 하나 이상의 한도(프로필)에 맞는지 판정합니다",
        "help.cmd_fix": "GSM-7 로 보낼 수 있는 후보를 제안합니다(곡선 따옴표·줄표·줄임표·특수 공백)",
        "help.text": "측정할 문구('-' 는 표준 입력)",
        "help.file": "UTF-8 파일에서 문구를 읽습니다(끝의 줄바꿈 1개 제거)",
        "help.jsonl": "한 줄에 {{\"id\": ..., \"text\": ...}} 하나인 UTF-8 JSON Lines 파일에서 여러 문구를 읽고 합계를 냅니다",
        "help.json": "JSON 으로 출력합니다(키는 항상 영어)",
        "help.profile": "쉼표로 구분한 프로필, 예: sms,x-post,utf8:120",
        "help.kr_codec": "국내 바이트 규칙: euc-kr(엄격, 기본) 또는 cp949(확장 한글을 2바이트로 셈)",
        "help.lang": "출력 언어(기본: CHARFIT_LANG, LC_ALL, LC_MESSAGES, LANG 순)",
        "help.help": "이 도움말을 보여 주고 끝냅니다",
        "help.usage": "사용법:",
        "help.options": "옵션",
        "help.positional": "인자",
        "help.commands": "명령",
        "value.na": "계산 불가",
        "count.title": "문구 측정값",
        "count.code_points": "코드 포인트",
        "count.utf16": "UTF-16 코드 단위",
        "count.utf8": "UTF-8 바이트",
        "count.sms_encoding": "SMS 인코딩",
        "count.sms_units": "SMS 과금 칸 수",
        "count.sms_segments": "SMS 건수",
        "count.x": "X 가중 길이",
        "count.euc_kr": "EUC-KR 바이트(엄격)",
        "count.cp949": "CP949 바이트",
        "count.kr_class": "국내 문자 구분",
        "count.per_segment": "건당 {n}칸",
        "count.of_limit": "{limit} 중 {n}",
        "count.note_gsm": "GSM-7 이 아닌 문자(UCS-2 로 바뀜):",
        "count.note_kr": "EUC-KR 로 보낼 수 없는 문자:",
        "count.note_urls": "X 에서 23 으로 세는 링크:",
        "check.pass": "통과",
        "check.fail": "실패",
        "check.line": "{status} {profile}: {measure} {value} (한도 {limit}{over})",
        "check.over": ", {n} 초과",
        "check.detail_sms": "인코딩 {encoding}, 과금 {units}칸, 건당 {per_segment}칸",
        "sms.boundary_extra": "{units}/{per_segment} 나눗셈보다 {n}건 많음: 2칸 문자는 두 건에 걸쳐 나뉘지 않는다",
        "check.detail_urls": "23 으로 센 링크: {urls}",
        "check.detail_emoji": "이모지 {n}개를 각각 2로 셈(키캡·국기·피부색·결합 시퀀스 포함)",
        "check.detail_nfc": "X 처럼 NFC 정규화 뒤에 셈: 코드 포인트 {before}개가 {after}개가 됨",
        "sms.parts_title": "SMS 조각 시작 위치(0부터 세는 코드 포인트 위치):",
        "sms.part": "조각 {n}: 위치 {index} «{head}»",
        "batch.item": "{status} {id} ({line}번째 줄): {details}",
        "batch.detail": "{profile} {measure} {value}",
        "batch.detail_sms": "{profile} {measure} {value} ({encoding}, {units}칸, 조각 시작 위치 {starts})",
        "batch.detail_kr": "{profile} {measure} {value} (구분 {cls})",
        "batch.total": "합계: 항목 {items}개, 모든 프로필 통과 {passed}, 통과 못 함 {failed}",
        "batch.total_profile": "{profile}: 통과 {passed}, 통과 못 함 {failed}",
        "batch.failed_ids": "통과 못 한 id: {ids}",
        "batch.total_sms": "합계 SMS: 과금 {segments}건, GSM-7 항목 {gsm7}개, UCS-2 항목 {ucs2}개, 2건 이상 항목 {multi}개",
        "batch.total_kr": "합계 국내 구분: SMS {SMS}개, LMS {LMS}개, OVER {OVER}개(2,000바이트 초과), FAIL {FAIL}개(발송 실패)",
        "fixbatch.item": "{id} ({line}번째 줄): 치환 {n}개, 정리 전 {before_encoding} {before_units}칸 {before_segments}건, 정리 후 {after_encoding} {after_units}칸 {after_segments}건",
        "fixbatch.total": "합계: 항목 {items}개, 바뀐 항목 {changed}개, 치환 {n}개",
        "fixbatch.total_before": "합계(정리 전): {segments}건, GSM-7 {gsm7}개, UCS-2 {ucs2}개",
        "fixbatch.total_after": "합계(정리 후): {segments}건, GSM-7 {gsm7}개, UCS-2 {ucs2}개",
        "fixbatch.still_ucs2": "정리 후에도 UCS-2 인 항목: {ids}",
        "fixbatch.all_gsm7": "모든 후보가 GSM-7 입니다.",
        "check.all_pass": "결과: 모든 프로필 통과.",
        "check.some_fail": "결과: 프로필 {m}개 중 {n}개 실패.",
        "measure.sms_segments": "SMS 건수",
        "measure.x_weighted": "X 가중 길이",
        "measure.euc_kr_bytes": "바이트",
        "measure.utf16_units": "UTF-16 단위",
        "measure.utf8_bytes": "UTF-8 바이트",
        "measure.code_points": "코드 포인트",
        "list.more": "... 외 {n}개(전체 목록은 --json)",
        "culprit.line": "위치 {index} '{char}' {codepoint}: {reason}",
        "reason.not_gsm7": "GSM-7 에 없어 UCS-2 로 바뀜",
        "reason.unencodable": "인코딩할 수 없어 발송 실패",
        "reason.not_in_ks_x_1001": "KS X 1001 밖이라 EUC-KR 불가(CP949 바이트: {cp949})",
        "fix.candidate": "후보: {text}",
        "fix.replacements": "치환 목록:",
        "fix.none": "바꿀 문자가 없습니다.",
        "fix.replacement": "위치 {index}: '{src}' -> '{dst}'",
        "fix.before": "치환 전: {encoding}, {units}칸, {segments}건",
        "fix.after": "치환 후: {encoding}, {units}칸, {segments}건",
        "fix.remaining": "후보에 남은 비 GSM-7 문자(위치는 후보 기준):",
        "fix.ok": "후보는 GSM-7 로 보낼 수 있습니다.",
        "fix.not_ok": "아직 GSM-7 이 아닙니다: 안전하게 바꿀 수 없는 문자 {n}개가 남았습니다.",
        "err.unknown_profile": "알 수 없는 프로필 '{name}' (지원: {known})",
        "err.profile_limit": "프로필 '{name}' 에는 양의 정수 한도가 필요합니다",
        "err.file_not_found": "파일 '{path}' 을(를) 읽을 수 없습니다: 없는 파일",
        "err.file_is_dir": "파일 '{path}' 을(를) 읽을 수 없습니다: 폴더입니다",
        "err.file_denied": "파일 '{path}' 을(를) 읽을 수 없습니다: 권한이 없습니다",
        "err.file_other": "파일 '{path}' 을(를) 읽을 수 없습니다: {reason}",
        "err.not_utf8": "'{path}' 은(는) 올바른 UTF-8 이 아닙니다(바이트 위치 {offset})",
        "err.arg_not_utf8": "TEXT 인자가 올바른 UTF-8 이 아닙니다. --file 이나 '-' 로 문구를 넘기세요",
        "err.both_inputs": "TEXT 와 --file 중 하나만 주세요",
        "err.one_input": "TEXT, '-', --file, --jsonl 중 하나만 주세요",
        "err.no_input": "입력 문구가 없습니다(TEXT, 표준 입력 '-', 또는 --file PATH 를 주세요)",
        "err.no_input_batch": "입력 문구가 없습니다(TEXT, 표준 입력 '-', --file PATH 또는 --jsonl PATH 를 주세요)",
        "err.jsonl_bad_json": "'{path}' 의 {line}번째 줄이 올바른 JSON 이 아닙니다",
        "err.jsonl_no_text": "'{path}' 의 {line}번째 줄에 \"text\" 문자열이 없습니다",
        "err.jsonl_bad_id": "'{path}' 의 {line}번째 줄의 \"id\" 가 문자열이나 정수가 아닙니다",
        "err.jsonl_surrogate": "'{path}' 의 {line}번째 줄 \"text\" 에 짝 없는 서로게이트가 있습니다",
        "err.jsonl_empty": "'{path}' 에 항목이 없습니다(모든 줄이 비어 있음)",
        "err.usage": "{message} (--help 참고)",
        "err.arg_required": "필수 인자가 빠졌습니다: {names}",
        "err.arg_unrecognized": "알 수 없는 인자입니다: {names}",
        "err.arg_invalid_choice": "인자 {name}: 잘못된 값 {value} ({choices} 중에서 고르세요)",
        "err.arg_expected_one": "인자 {name}: 값이 하나 필요합니다",
        "help.version": "버전을 보여 주고 끝냅니다",
    },
}


def _lang_from_value(value: Optional[str]) -> Optional[str]:
    """'ko', 'ko_KR.UTF-8' -> ko; any other non-empty value -> en; empty -> None (not decided)."""
    if not value or not value.strip():
        return None
    return "ko" if value.strip().lower().startswith("ko") else "en"


def resolve_lang(cli_value: Optional[str], env: Mapping[str, str]) -> str:
    """--lang, then CHARFIT_LANG, then the first non-empty of LC_ALL, LC_MESSAGES, LANG; else English."""
    if cli_value in LANGS:
        return str(cli_value)
    for key in ("CHARFIT_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        decided = _lang_from_value(env.get(key))
        if decided:
            return decided
    return "en"


def t(lang: str, key: str, **kwargs: object) -> str:
    return MESSAGES[lang][key].format(**kwargs)

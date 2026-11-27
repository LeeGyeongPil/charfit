#!/usr/bin/env python3
"""charfit - measure text the way each platform counts it.

Commands:
  count    every measure for a text (SMS, X, Korean carrier bytes, UTF-16/UTF-8)
  check    pass/fail against one or more profiles, with the character that causes a failure
  fix-sms  a GSM-7 friendly candidate (curly quotes, dashes, ellipsis, odd spaces)

check and fix-sms also take --jsonl PATH (one {"id": ..., "text": ...} object per line) and then
add "totals" (sums and counts over all items) so nobody adds up per-item numbers by hand.

Standard library only. Exit codes: 0 ok, 1 limit exceeded / no GSM-7 candidate, 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from typing import Any, Dict, List, NoReturn, Optional, Sequence

import _charfit_rules as rules
from _charfit_i18n import LANGS, resolve_lang, t

__version__ = "0.1.5"


class UsageError(Exception):
    """A problem the user can fix; printed as one line and exit code 2."""


class _Parser(argparse.ArgumentParser):
    lang = "en"

    def error(self, message: str) -> NoReturn:
        raise UsageError(t(self.lang, "err.usage", message=self._translate(message)))

    def _translate(self, message: str) -> str:
        """Map the argparse messages a user can hit to the message table; keep unknown ones as is."""
        lang = self.lang
        m = re.fullmatch(r"the following arguments are required: (.+)", message)
        if m:
            return t(lang, "err.arg_required", names=m.group(1))
        m = re.fullmatch(r"unrecognized arguments: (.+)", message)
        if m:
            return t(lang, "err.arg_unrecognized", names=m.group(1))
        m = re.fullmatch(r"argument (.+?): invalid choice: (.+?) \(choose from (.+)\)", message)
        if m:
            return t(lang, "err.arg_invalid_choice", name=m.group(1), value=m.group(2), choices=m.group(3))
        m = re.fullmatch(r"argument (.+?): expected one argument", message)
        if m:
            return t(lang, "err.arg_expected_one", name=m.group(1))
        return message

    def format_help(self) -> str:
        text = super().format_help()
        if self.lang == "ko":
            for old, key in (("usage: ", "help.usage"), ("positional arguments:", "help.positional"),
                             ("optional arguments:", "help.options"), ("options:", "help.options"),
                             ("commands:", "help.commands")):
                text = text.replace(old, t("ko", key) + (" " if old == "usage: " else ":"))
        return text


def _prescan_lang(argv: Sequence[str]) -> Optional[str]:
    """Find --lang before argparse runs, so that --help and parse errors already use it."""
    for i, arg in enumerate(argv):
        if arg == "--":
            break
        if arg == "--lang" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--lang="):
            return arg.split("=", 1)[1]
    return None


def build_parser(lang: str) -> _Parser:
    common = _Parser(add_help=False)
    common.lang = lang
    common.add_argument("text", nargs="?", metavar="TEXT", help=t(lang, "help.text"))
    common.add_argument("--file", metavar="PATH", help=t(lang, "help.file"))
    common.add_argument("--json", action="store_true", help=t(lang, "help.json"))
    common.add_argument("--lang", choices=LANGS, default=argparse.SUPPRESS, help=t(lang, "help.lang"))
    codec = _Parser(add_help=False)
    codec.add_argument("--kr-codec", choices=("euc-kr", "cp949"), default="euc-kr", help=t(lang, "help.kr_codec"))
    batch = _Parser(add_help=False)
    batch.add_argument("--jsonl", metavar="PATH", help=t(lang, "help.jsonl"))

    parser = _Parser(prog="charfit", add_help=False, description=t(lang, "help.description"),
                     epilog=t(lang, "help.epilog"))
    parser.lang = lang
    parser.add_argument("-h", "--help", action="help", help=t(lang, "help.help"))
    parser.add_argument("--lang", choices=LANGS, default=argparse.SUPPRESS, help=t(lang, "help.lang"))
    parser.add_argument("--version", action="version", version="charfit " + __version__,
                        help=t(lang, "help.version"))
    sub = parser.add_subparsers(dest="command", metavar="{count,check,fix-sms}")
    sub.required = True

    def add(name: str, key: str, parents: List[argparse.ArgumentParser]) -> _Parser:
        p = sub.add_parser(name, parents=parents, add_help=False, help=t(lang, key),
                           description=t(lang, key), epilog=t(lang, "help.epilog"))
        p.lang = lang
        p.add_argument("-h", "--help", action="help", help=t(lang, "help.help"))
        return p

    add("count", "help.cmd_count", [common, codec])
    check = add("check", "help.cmd_check", [common, batch, codec])
    check.add_argument("--profile", "-p", required=True, metavar="P[,P...]", help=t(lang, "help.profile"))
    add("fix-sms", "help.cmd_fix", [common, batch])
    return parser


# --------------------------------------------------------------------------
# Input
# --------------------------------------------------------------------------

def _strip_one_newline(text: str) -> str:
    if text.endswith("\r\n"):
        return text[:-2]
    if text.endswith("\n"):
        return text[:-1]
    return text


def _decode(data: bytes, label: str, lang: str) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
            raise UsageError(t(lang, "err.not_utf8_utf16", path=label))
        raise UsageError(t(lang, "err.not_utf8", path=label, offset=e.start))


def _read_file(path: str, lang: str) -> str:
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except FileNotFoundError:
        raise UsageError(t(lang, "err.file_not_found", path=path))
    except IsADirectoryError:
        raise UsageError(t(lang, "err.file_is_dir", path=path))
    except PermissionError:
        raise UsageError(t(lang, "err.file_denied", path=path))
    except OSError as e:
        raise UsageError(t(lang, "err.file_other", path=path, reason=e.strerror or str(e)))
    return _decode(data, path, lang)


def read_jsonl(path: str, lang: str) -> List[Dict[str, Any]]:
    """One JSON object per line: {"id": "es-otp", "text": "..."}. Blank lines are skipped.

    `id` is optional (a string or an integer); without it the 1-based line number is the id.
    """
    items: List[Dict[str, Any]] = []
    # splitlines() 는 U+2028 같은 문자에서도 줄을 나누므로 '\n' 으로만 나눈다
    for number, raw in enumerate(_read_file(path, lang).split("\n"), 1):
        line = raw[:-1] if raw.endswith("\r") else raw
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            raise UsageError(t(lang, "err.jsonl_bad_json", path=path, line=number))
        if not isinstance(obj, dict) or not isinstance(obj.get("text"), str):
            raise UsageError(t(lang, "err.jsonl_no_text", path=path, line=number))
        if rules.has_lone_surrogate(obj["text"]):
            raise UsageError(t(lang, "err.jsonl_surrogate", path=path, line=number))
        item_id = obj.get("id")
        if item_id is None:
            item_id = str(number)
        elif isinstance(item_id, bool) or not isinstance(item_id, (str, int)):
            raise UsageError(t(lang, "err.jsonl_bad_id", path=path, line=number))
        items.append({"id": str(item_id), "line": number, "text": obj["text"]})
    if not items:
        raise UsageError(t(lang, "err.jsonl_empty", path=path))
    return items


def read_input(args: argparse.Namespace, lang: str, stdin: Any = None) -> str:
    given = [args.text is not None, args.file is not None, getattr(args, "jsonl", None) is not None]
    if sum(given) > 1:
        # --jsonl 이 있는 명령(check, fix-sms)은 입력 네 가지 중 하나만 받는다
        raise UsageError(t(lang, "err.one_input" if hasattr(args, "jsonl") else "err.both_inputs"))
    if args.file is not None:
        return _strip_one_newline(_read_file(args.file, lang))
    if args.text is None:
        raise UsageError(t(lang, "err.no_input_batch" if hasattr(args, "jsonl") else "err.no_input"))
    if args.text == "-":
        stream = stdin if stdin is not None else sys.stdin
        raw = stream.buffer.read() if hasattr(stream, "buffer") else str(stream.read()).encode("utf-8")
        return _strip_one_newline(_decode(raw, "<stdin>", lang))
    if rules.has_lone_surrogate(args.text):
        raise UsageError(t(lang, "err.arg_not_utf8"))
    return args.text


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def _dump(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def _pad(s: str, width: int) -> str:
    return s + " " * max(0, width - _width(s))


def _culprit_line(lang: str, c: Dict[str, Any]) -> str:
    reason = t(lang, "reason." + c["reason"], cp949=c.get("cp949_bytes") if c.get("cp949_bytes") is not None
               else t(lang, "value.na"))
    return t(lang, "culprit.line", index=c["index"], char=c["char"], codepoint=c["codepoint"], reason=reason)


MAX_LISTED = 10   # human output lists at most this many characters per group; JSON has them all


def _culprit_lines(lang: str, culprits: List[Dict[str, Any]], prefix: str) -> List[str]:
    lines = [prefix + _culprit_line(lang, c) for c in culprits[:MAX_LISTED]]
    if len(culprits) > MAX_LISTED:
        lines.append(prefix + t(lang, "list.more", n=len(culprits) - MAX_LISTED))
    return lines


def _part_lines(lang: str, text: str, starts: List[int], prefix: str) -> List[str]:
    """'part 3: index 301 «...»' for every segment when there are two or more (1-based part numbers)."""
    if len(starts) < 2:
        return []
    lines = []
    for n, index in enumerate(starts, 1):
        head = "".join(" " if ch in "\r\n\t" else ch for ch in text[index:index + 12])
        lines.append(prefix + t(lang, "sms.part", n=n, index=index, head=head))
    return lines


def render_count(lang: str, r: Dict[str, Any], text: str) -> str:
    na = t(lang, "value.na")
    sms = r["sms"]
    euc = r["euc_kr"]["bytes"]
    cp949 = r["cp949_bytes"]
    rows = [
        (t(lang, "count.code_points"), str(r["length"]["code_points"])),
        (t(lang, "count.utf16"), str(r["length"]["utf16_units"])),
        (t(lang, "count.utf8"), str(r["length"]["utf8_bytes"])),
        (t(lang, "count.sms_encoding"), sms["encoding"]),
        (t(lang, "count.sms_units"), "%d (%s)" % (sms["units"], t(lang, "count.per_segment", n=sms["per_segment"]))),
        (t(lang, "count.sms_segments"), str(sms["segments"])),
        (t(lang, "count.x"), t(lang, "count.of_limit", n=r["x_weighted"], limit=rules.X_LIMIT)),
        (t(lang, "count.euc_kr"), na if euc is None else str(euc)),
        (t(lang, "count.cp949"), na if cp949 is None else str(cp949)),
        (t(lang, "count.kr_class"), r["kr_class"]),
    ]
    width = max(_width(label) for label, _ in rows) + 2
    lines = [t(lang, "count.title")] + [_pad(label, width) + value for label, value in rows]
    if sms["boundary_extra"]:
        lines += ["", t(lang, "sms.boundary_extra", n=sms["boundary_extra"], units=sms["units"],
                        per_segment=sms["per_segment"])]
    parts = _part_lines(lang, text, sms["segment_starts"], "  ")
    if parts:
        lines += ["", t(lang, "sms.parts_title")] + parts
    if sms["culprits"]:
        lines += ["", t(lang, "count.note_gsm")] + _culprit_lines(lang, sms["culprits"], "  ")
    if r["euc_kr"]["culprits"]:
        lines += ["", t(lang, "count.note_kr")] + _culprit_lines(lang, r["euc_kr"]["culprits"], "  ")
    if r["x_urls"]:
        lines += ["", t(lang, "count.note_urls") + " " + ", ".join(r["x_urls"])]
    return "\n".join(lines)


def render_check(lang: str, r: Dict[str, Any], text: str) -> str:
    lines: List[str] = []
    for res in r["results"]:
        value = t(lang, "value.na") if res["value"] is None else str(res["value"])
        over = t(lang, "check.over", n=res["over"]) if res["over"] else ""
        lines.append(t(lang, "check.line", status=t(lang, "check.pass" if res["pass"] else "check.fail"),
                       profile=res["profile"], value=value, measure=t(lang, "measure." + res["measure"]),
                       limit=res["limit"], over=over))
        if res["measure"] == "sms_segments":
            lines.append("  " + t(lang, "check.detail_sms", encoding=res["encoding"], units=res["units"],
                                  per_segment=res["per_segment"]))
            # 경계에서 2칸 문자를 자르지 않아 조각이 늘었으면 그 이유를 함께 보인다
            if res["boundary_extra"]:
                lines.append("  " + t(lang, "sms.boundary_extra", n=res["boundary_extra"], units=res["units"],
                                      per_segment=res["per_segment"]))
            # 조각마다 입력 문자열의 몇 번째 문자(0부터)에서 시작하는지
            lines += _part_lines(lang, text, res["segment_starts"], "  ")
        if res.get("x_urls"):
            lines.append("  " + t(lang, "check.detail_urls", urls=", ".join(res["x_urls"])))
        if res.get("x_emoji"):
            lines.append("  " + t(lang, "check.detail_emoji", n=res["x_emoji"]))
        # 입력이 NFC 가 아니면(NFD 한글 등) X 가 정규화한 뒤의 길이로 셌다는 것을 밝힌다
        if res["measure"] == "x_weighted" and res["x_nfc_code_points"] != r["length"]["code_points"]:
            lines.append("  " + t(lang, "check.detail_nfc", before=r["length"]["code_points"],
                                  after=res["x_nfc_code_points"]))
        lines += _culprit_lines(lang, res["culprits"], "  - ")
    failed = sum(1 for res in r["results"] if not res["pass"])
    lines.append(t(lang, "check.all_pass") if not failed
                 else t(lang, "check.some_fail", n=failed, m=len(r["results"])))
    return "\n".join(lines)


def render_fix(lang: str, r: Dict[str, Any]) -> str:
    lines = [t(lang, "fix.candidate", text=r["candidate"])]
    if r["replacements"]:
        lines.append(t(lang, "fix.replacements"))
        lines += ["  " + t(lang, "fix.replacement", index=x["index"], src=x["from"], dst=x["to"])
                  for x in r["replacements"]]
    else:
        lines.append(t(lang, "fix.none"))
    lines.append(t(lang, "fix.before", **r["before"]))
    lines.append(t(lang, "fix.after", **r["after"]))
    if r["remaining"]:
        lines.append(t(lang, "fix.remaining"))
        lines += _culprit_lines(lang, r["remaining"], "  - ")
        lines.append(t(lang, "fix.not_ok", n=len(r["remaining"])))
    else:
        lines.append(t(lang, "fix.ok"))
    return "\n".join(lines)


BATCH_LISTED = 3   # in a batch, at most this many culprits per item and profile (JSON has them all)


def _batch_detail(lang: str, res: Dict[str, Any], item: Dict[str, Any]) -> str:
    value = t(lang, "value.na") if res["value"] is None else str(res["value"])
    common = {"profile": res["profile"], "value": value, "measure": t(lang, "measure." + res["measure"])}
    if res["measure"] == "sms_segments":
        starts = ", ".join(str(s) for s in res["segment_starts"]) or "-"
        return t(lang, "batch.detail_sms", encoding=res["encoding"], units=res["units"], starts=starts, **common)
    if res["measure"] == "euc_kr_bytes":
        return t(lang, "batch.detail_kr", cls=item["kr_class"], **common)
    return t(lang, "batch.detail", **common)


def render_check_batch(lang: str, r: Dict[str, Any]) -> str:
    lines: List[str] = []
    for item in r["items"]:
        details = "; ".join(_batch_detail(lang, res, item) for res in item["results"])
        lines.append(t(lang, "batch.item", status=t(lang, "check.pass" if item["pass"] else "check.fail"),
                       id=item["id"], line=item["line"], details=details))
        for res in item["results"]:
            culprits = res["culprits"]
            lines += ["  - " + _culprit_line(lang, c) for c in culprits[:BATCH_LISTED]]
            if len(culprits) > BATCH_LISTED:
                lines.append("  - " + t(lang, "list.more", n=len(culprits) - BATCH_LISTED))
    # 합계 줄: 에이전트가 항목별 값을 손으로 더하지 않고 그대로 옮길 수 있게 한다
    tot = r["totals"]
    lines.append("")
    lines.append(t(lang, "batch.total", items=tot["items"], passed=tot["pass"], failed=tot["fail"]))
    for profile, counts in tot["by_profile"].items():
        lines.append("  " + t(lang, "batch.total_profile", profile=profile, passed=counts["pass"],
                              failed=counts["fail"]))
    if tot["failed_ids"]:
        lines.append(t(lang, "batch.failed_ids", ids=", ".join(tot["failed_ids"])))
    if "sms" in tot:
        s = tot["sms"]
        lines.append(t(lang, "batch.total_sms", segments=s["segments"], gsm7=s["gsm7"], ucs2=s["ucs2"],
                       multi=s["multi_segment"]))
    if "kr_class" in tot:
        lines.append(t(lang, "batch.total_kr", **tot["kr_class"]))
    return "\n".join(lines)


def render_fix_batch(lang: str, r: Dict[str, Any]) -> str:
    lines: List[str] = []
    for item in r["items"]:
        b, a = item["before"], item["after"]
        lines.append(t(lang, "fixbatch.item", id=item["id"], line=item["line"], n=len(item["replacements"]),
                       before_encoding=b["encoding"], before_units=b["units"], before_segments=b["segments"],
                       after_encoding=a["encoding"], after_units=a["units"], after_segments=a["segments"]))
        if item["replacements"]:
            lines.append("  " + t(lang, "fix.candidate", text=item["candidate"]))
        remaining = item["remaining"]
        lines += ["  - " + _culprit_line(lang, c) for c in remaining[:BATCH_LISTED]]
        if len(remaining) > BATCH_LISTED:
            lines.append("  - " + t(lang, "list.more", n=len(remaining) - BATCH_LISTED))
    tot = r["totals"]
    lines.append("")
    lines.append(t(lang, "fixbatch.total", items=tot["items"], changed=tot["changed"], n=tot["replacements"]))
    lines.append(t(lang, "fixbatch.total_before", **tot["before"]))
    lines.append(t(lang, "fixbatch.total_after", **tot["after"]))
    lines.append(t(lang, "fixbatch.still_ucs2", ids=", ".join(tot["still_ucs2_ids"])) if tot["still_ucs2_ids"]
                 else t(lang, "fixbatch.all_gsm7"))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def run(argv: Sequence[str], env: Dict[str, str], stdin: Any = None) -> "tuple[int, str]":
    """Run one command; return (exit code, text for stdout). Raises UsageError."""
    lang = resolve_lang(_prescan_lang(argv), env)
    parser = build_parser(lang)
    args = parser.parse_args(list(argv))
    lang = resolve_lang(getattr(args, "lang", None), env)
    if args.command == "check":
        try:
            rules.parse_profiles(args.profile)
        except rules.ProfileError as e:
            key = "err.unknown_profile" if e.kind == "unknown" else "err.profile_limit"
            raise UsageError(t(lang, key, name=e.name, known=rules.KNOWN_PROFILES))
    # 묶음 입력(--jsonl): 항목마다 같은 계산을 하고 totals 를 붙인다
    if getattr(args, "jsonl", None) is not None:
        if args.text is not None or args.file is not None:
            raise UsageError(t(lang, "err.one_input"))
        items = read_jsonl(args.jsonl, lang)
        if args.command == "check":
            batch = rules.check_many(items, args.profile, args.kr_codec)
            return (0 if batch["pass"] else 1), _dump(batch) if args.json else render_check_batch(lang, batch)
        fixed = rules.fix_many(items)
        code = 0 if not fixed["totals"]["still_ucs2_ids"] else 1
        return code, _dump(fixed) if args.json else render_fix_batch(lang, fixed)
    text = read_input(args, lang, stdin)
    if args.command == "count":
        result = rules.count_text(text, args.kr_codec)
        return 0, _dump(result) if args.json else render_count(lang, result, text)
    if args.command == "check":
        result = rules.check_text(text, args.profile, args.kr_codec)
        return (0 if result["pass"] else 1), _dump(result) if args.json else render_check(lang, result, text)
    result = rules.fix_sms(text)
    return (0 if not result["remaining"] else 1), _dump(result) if args.json else render_fix(lang, result)


def main(argv: Optional[Sequence[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        code, out = run(argv, dict(os.environ))
    except UsageError as e:
        print("charfit: error: %s" % e, file=sys.stderr)
        return 2
    try:
        print(out)
        sys.stdout.flush()
    except BrokenPipeError:
        # The reader (for example `| head`) closed early: stop quietly, keep the computed exit code.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    return code


if __name__ == "__main__":
    sys.exit(main())

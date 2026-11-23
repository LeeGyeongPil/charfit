# charfit rules and limits

All sources were checked on 2026-11-23. Numbers are quoted as facts; no code or text was copied.

## SMS (`sms`, `sms:N`)

- A message whose characters are all in the GSM 03.38 default alphabet (127 characters) or its escape table (`^ { } \ [ ~ ] |`, form feed and `€`) is GSM-7. Escape-table characters cost 2 septets. Source: 3GPP TS 23.038, https://www.3gpp.org/ftp/Specs/archive/23_series/23.038/
- Any other character makes the whole message UCS-2. It is counted in UTF-16 code units, so an emoji costs 2.
- One segment holds 160 (GSM-7) or 70 (UCS-2) units. A longer message is split into segments of 153 or 67 units because each carries a header. Source: https://www.twilio.com/docs/glossary/what-sms-character-limit
- A two-unit character is never cut in half, so a segment can end one unit early. `a`x152 + `€` + `a`x152 is 306 units but 3 segments, not `ceil(306/153)` = 2. The same holds for an emoji (a UTF-16 surrogate pair) at a UCS-2 boundary: 134 units can be 3 segments, not 2. `boundary_extra` reports how many segments this rule added. An external SMS segment calculator gave the same results on the test strings and on the evaluation fixtures (checked 2026-11-23).
- `segment_starts` is the 0-based code point index in the text where each segment starts: `[]` for an empty text, `[0]` for one segment. Because escape-table characters cost 2 and a two-unit character moves to the next segment, these are character positions, not unit offsets: `a`x152 + `€` + `a`x152 gives `[0, 152, 304]` (unit offsets would say 0, 153, 306), `~`x81 gives `[0, 76]`, `a`x66 + an emoji + `a`x5 gives `[0, 66]`. The human output prints them as `part N: index I` with N counted from 1. The positions and segment counts of the evaluation fixtures were compared with an external SMS segment calculator (its internal segment list) and with a second, independent implementation that fills one segment at a time (checked 2026-11-23).
- `culprits` lists only the characters that force UCS-2 (`reason: not_gsm7`). `extension_chars` counts the 2-unit GSM-7 characters.
- `index` is the 0-based code point position in the text as given (before any normalisation). A decomposed accent (`e` + U+0301) is not GSM-7, the composed `é` is: `fix-sms` composes it.

### Accented letters in the GSM-7 default alphabet

The table has only some accented letters, so "it is Latin, so it is GSM-7" is wrong (checked against the `gsm0338` 1.1.0 codec, 2026-11-23):

| GSM-7 (1 unit) | Not GSM-7 (the message becomes UCS-2) |
|---|---|
| é è ù ì ò à ä ö ü ñ ß å ø æ | á í ó ú â ê î ô û ã õ ë ï ÿ œ |
| É Ä Ö Ü Ñ Å Ø Æ Ç | À È Ì Ò Ù Á Í Ó Ú |
| ¡ ¿ £ ¥ § ¤ | ç (lowercase), ł ş ğ ı ő and other letters outside Latin-1 (except the Greek capitals on the left) |
| Δ Φ Γ Λ Ω Π Ψ Σ Θ Ξ (Greek capitals) | the other Greek letters, including capitals that look Latin (Α Β Ε ...); the backtick U+0060 |

The 3GPP table has the capital `Ç` at 0x09. Some providers map a lowercase `ç` to it; charfit follows the table and treats `ç` as UCS-2.

## Batches (`--jsonl`)

- `check` and `fix-sms` accept `--jsonl PATH`: a UTF-8 file with one JSON object per line, `{"id": "es-otp", "text": "..."}`. `text` must be a string; `id` is optional (a string or an integer, used as a string); without it the 1-based line number is the id. Blank lines are skipped. A broken line stops with exit code 2 and a one-line error that names the line.
- `check --jsonl` prints `items` (each with `id`, `line`, `pass`, `length`, `results`, and `kr_class` when a Korean profile is checked) and `totals`: `items`, `pass`, `fail`, `failed_ids`, `by_profile`, plus `sms` (`segments` summed over the items, `gsm7` and `ucs2` item counts, `multi_segment` = items with 2 or more segments) when an SMS profile is checked, and `kr_class` (`SMS`, `LMS`, `OVER`, `FAIL` item counts) when a Korean profile is checked. The exit code is 1 when any item fails any profile.
- `fix-sms --jsonl` prints `items` (each with the single-text fields) and `totals`: `items`, `changed`, `replacements`, `before` and `after` (`segments`, `gsm7`, `ucs2`), and `still_ucs2_ids`. `after` is measured on the cleaned text, so a `…` that became `...` and pushed a text past 160 units counts as the extra segment it causes. The exit code is 1 when any item is still UCS-2.

## X (`x-post`)

The X profile is an approximation of X's published counting rules, cross-checked against the twitter-text 3.1.0 library; it is not a guarantee of what every X client shows. Emoji sequences and country-code file names in particular follow twitter-text 3.1.0, which predates newer emoji, so treat those weights as an estimate.

- Text is normalised to NFC, then weighted: code points 0-4351, 8192-8205, 8208-8223 and 8242-8247 weigh 1, every other code point weighs 2, a link weighs 23, an emoji sequence weighs 2. The limit is 280. Source: https://docs.x.com/fundamentals/counting-characters and the public twitter-text v3 configuration, https://raw.githubusercontent.com/twitter/twitter-text/master/config/v3.json
- `…` (U+2026) and the emoji ranges weigh 2; `“ ” ‘ ’ — –` weigh 1; Hangul and CJK weigh 2.
- Link detection: `http://` or `https://` followed by non-space ASCII, `www.` hosts, and bare names ending in a two-letter country-code top-level domain (all of them, from the IANA root zone, https://www.iana.org/domains/root/db) or in one of the generic domains `com net org info biz edu gov mil int app dev xyz shop store blog online site tech cloud page link news live art design`. Because of the country codes, file names such as `setup.py` (Paraguay), `README.md` (Moldova), `main.rs` (Serbia) or `install.sh` (Saint Helena) are links on X and weigh 23 each, while `index.js`, `config.yml` or a name after a slash (`src/main.rs`) are not. Trailing punctuation (`. , ; : ! ? ) ] } ' "`) is not part of the link. The detected links are returned as `x_urls`.
- An emoji weighs 2 however many code points it has: keycaps (`1 U+FE0F U+20E3` = digit + U+FE0F + U+20E3), tag-sequence flags (England, Scotland, Wales), regional-indicator flags, skin tones, ZWJ sequences and variation selector 16. A bare `©` or `®` lies in the weight-1 range and weighs 1; with U+FE0F (`© U+FE0F`) it is an emoji and weighs 2. `x_emoji` reports how many emoji were counted. Detection uses code point ranges, not the Unicode database, so a very new emoji may be counted as 2 either way.
- A text in NFD (for example Hangul stored as jamo, as macOS file names are) is counted after NFC normalisation, as X does: `x_nfc_code_points` gives the length after normalisation.
- These rules were checked token by token against the official twitter-text 3.1.0 JavaScript library (https://www.npmjs.com/package/twitter-text: 180 of 183 tokens equal, including keycaps, tag flags, `©` `®` `™` with and without U+FE0F, file names, e-mail addresses, NFD Hangul) (checked 2026-11-23). The unofficial Python port twitter-text-parser 3.0.0 differs on a bare `©` `®` (it counts 2); charfit follows the official library. The three differences: a scheme link with an invalid host (`https://a.b`, `http://localhost:8080`) is 23 in charfit but plain text in twitter-text, and an emoji newer than the library (`U+1F9D1 U+200D U+1F4BB`) is 2 in charfit but 5 in twitter-text 3.1.0. Emoji added after Unicode 11 can differ between X clients.

## Korean carriers (`kr-sms`, `kr-lms`)

- SMS carries 90 bytes and LMS 2,000 bytes in EUC-KR; emoji and characters outside the charset make the send fail. Sources: https://docs.nhncloud.com/en/Notification/SMS/en/api-guide-v2.4/ and https://solapi.com/guides/sms
- Default is strict EUC-KR (KS X 1001, 2 bytes per Hangul syllable). Python's `euc_kr` codec accepts Hangul outside KS X 1001 and silently writes a multi-byte jamo sequence (for example U+B620 becomes 8 bytes), so charfit encodes each character alone and reports a result of more than 2 bytes as `not_in_ks_x_1001` with `cp949_bytes`.
- `--kr-codec cp949` counts extended Hangul as 2 bytes (the Microsoft code page). Use it only when your gateway is known to accept CP949.
- An unsendable character makes `value` and `over` null and `pass` false. A newline is 1 byte; gateways that store `\r\n` as 2 bytes will count one more per line break.
- `count` reports `kr_class`: `SMS` (<= 90), `LMS` (<= 2,000), `OVER`, or `FAIL` (cannot be encoded).

## Plain limits (`utf16:N`, `utf8:N`, `chars:N`)

- HTML `maxlength` counts UTF-16 code units (an emoji is 2). Source: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/maxlength
- `utf8:N` counts UTF-8 bytes (APIs, databases, push payloads); `chars:N` counts code points. Neither counts what a person sees as one character (grapheme clusters), which needs a library outside the standard library.

## Known limits

- No per-country GSM shift tables (Turkish, Spanish, Portuguese), no "smart encoding" tables of a specific provider beyond the replacements `fix-sms` lists.
- No recipient-pays 152/66 limits, no provider storage limits, no messenger template rules.
- A gateway may count or convert differently; the defaults follow the public documentation above.
- `fix-sms` replacements: curly quotes to `'` and `"`, en and em dash to `-`, `…` to `...`, U+00A0, U+2000-200A, U+202F and U+3000 to a space, combining accents composed to NFC.

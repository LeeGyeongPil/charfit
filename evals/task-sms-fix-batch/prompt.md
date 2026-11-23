---
name: task-sms-fix-batch
max_turns: 16
---

campaign.jsonl holds 20 promo texts pasted from our CMS, one JSON object per line. Before we send them as SMS, clean them up for GSM-7 with this policy: curly quotes become straight quotes, en and em dashes become hyphens, the ellipsis becomes three dots, special spaces become normal spaces, and decomposed accents are recomposed; change nothing else. After that cleanup, how many SMS segments do all the texts add up to if each is sent once, and how many texts are still UCS-2? How many segments did the set add up to before the cleanup?

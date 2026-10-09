# EffectSeal defense walkthrough — current 2026-10-09

Narration: `NOTEBOOKLM_SCRIPT_BN.md`; full scope: `paper/CLAIM_EVIDENCE_MATRIX.md`.
পুরোনো walkthrough `paper/history/`-এ আছে; তার claim IDs আর current নয়।

1. Approved request ও effect কেন আলাদা, Postmark reconstruction দিয়ে বোঝান।
2. `src/mcpgate/request_templates.py`-এ typed/path-array view ও structure checking দেখান।
3. `src/mcpgate/egress_service.py` এবং `egress_proxy.py`-এ durable reservation, credential-after-admission ও terminal outcome দেখান।
4. `tests/test_network_repairs.py`-এ collision, escaped values, actual worker races, restart এবং UNKNOWN case দেখান।
5. `python scripts/verify_current_evidence.py` চালান; raw pins ও variants থেকে summary recomputation দেখান।
6. Original ও additional held-out cohorts আলাদা করে বলুন; adaptive admissions ও local 6/48 honest blocks দেখান।
7. Stable poisoning control দেখিয়ে বলুন repeatability honesty নয়।
8. Fresh Linux reproduction-এর exact commit/log এবং current PDF build manifest দেখান।

প্রশ্ন: সব attacks stopped? উত্তর: না। Fixed ও adaptive আলাদা; original adaptive
36/648 এবং additional 12/336 admitted। Positive slack একটি real channel।

প্রশ্ন: 312/312 মানে নিশ্চয়তা? উত্তর: না। Covered server-এর check-level variants;
server cluster খুব ছোট, APIs mock, authors/dependencies correlated হতে পারে।

প্রশ্ন: exactly-once? উত্তর: durable at-most-once admission; ambiguous upstream
outcome UNKNOWN থেকে যায়, automatic resend নয়।

প্রশ্ন: novelty? উত্তর: transaction বা sandbox নতুন নয়; approved MCP call-এর
সঙ্গে typed effect predicate, practical pin-time inference, explicit capacity
এবং local/network admission-এর combination-টাই contribution।

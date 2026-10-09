# EffectSeal-এর বর্তমান অবস্থা — 2026-10-09 correctness repair

Paper এখন আগের চেয়ে বেশি defensible: implementation bugs ঠিক করা হয়েছে,
নতুন evidence দিয়ে claims মিলেছে, আর negative results লুকানো হয়নি।
এটি এখনও anonymous submission package নয়; artifact URL ও author review বাকি।

- Original network cohort: coverage 10/12; covered servers-এ 120/120 honest
  protocol trial; fixed sends 792/816 refused; adaptive 612/648 refused।
- নতুন held-out cohort: 40 candidates থেকে 5 qualifier; honest 60/60;
  fixed sends 312/312 refused; adaptive 324/336 refused, conekta-তে 12 admission।
- Rebuilt Postmark: 21 unauthorized sends refused, 3 no-op incomplete;
  GitHub: 84 fixed sends ও 24 adaptive variants refused।
- Actual proxy: 100 races-এ 8 requests/2 workers-এর মধ্যে ঠিক 1 far-side effect;
  restart replay refused; upstream uncertainty UNKNOWN হিসেবে থাকে।
- Quiet proxy timing: gate p50/p95 14.5/33.6ms; record-only 1.7/20.9ms;
  TLS/WAN latency এখানে নেই।
- Unicode slack, request types/structure, escaped values, clock binding,
  outcome accounting এবং stale paper scripts সংশোধিত হয়েছে।
- Repeat pinning honesty প্রমাণ করে না; stable Bcc poisoning দুই session-এ
  একই template দিয়েছে। Local held-out honest false blocks 6/48 এখনও সত্য।

সর্বশেষ ফলের নির্দিষ্ট pointers: `artifact/paper-evidence-20261009.json`।
পূর্ণ claim mapping: `paper/CLAIM_EVIDENCE_MATRIX.md`।
Current tests ও fresh Linux reproduction-এর exact counts dated logs-এ থাকবে;
পুরোনো run-এর সংখ্যা নতুন code-এর প্রমাণ হিসেবে ব্যবহার করা যাবে না।

Final verification: Windows 328 passed/3 skipped; fresh Linux 327 passed/4
skipped ও 12/12 reproduction steps PASS। PDF 13 body pages/19 total; anonymous
working draft-ও তৈরি হয়েছে, কিন্তু artifact URL placeholder থাকায় release gate
fail করে। সব পরিবর্তনের record: `docs/49-correctness-repair-20261009.md`।

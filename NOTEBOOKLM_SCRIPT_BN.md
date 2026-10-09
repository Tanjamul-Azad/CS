# EffectSeal — বর্তমান বাংলা narration ও defense script

2026-10-09 correctness audit-এর পরে সংশোধিত। NotebookLM-এ এই version ব্যবহার
করুন। পুরোনো দীর্ঘ narrative `paper/history/`-এ আছে। Current claim matrix ও
`artifact/paper-evidence-20261009.json` সংখ্যাগুলোর source of truth।

একটি MCP call approve হওয়া আর তার implementation সঠিক effect করা আলাদা ঘটনা।
Server honest-looking success response দিয়েও অন্য file লিখতে বা email-এ Bcc
যোগ করতে পারে। Postmark incident এই সমস্যা দেখায়। আমাদের teaser incident-এর
mechanism rebuild করেছে; ঐ ঘটনার আসল historical transcript সংগ্রহ করেছি বলা
হচ্ছে না।

দুই execution-এর raw client-visible transcript একই হলে passive monitor একই
information পাবে। এটি indistinguishability-এর প্রয়োগ। Registry auditor-এর
8,692 candidates থেকে 4,121 launch, এবং 1,242 usable paired trial হয়েছে;
কোনো tested configuration frozen operating point পূরণ করেনি। এটি credential-free
selected corpus, পুরো MCP ecosystem-এর prevalence estimate নয়। চার judge-এর
approved-call ও normalized-signature matching-এ detection advantage দেখা যায়নি;
post hoc normalization দিয়ে raw equality প্রমাণ করা যায় না।

EffectSeal trusted effect boundary যোগ করে। Local server confined private copy-তে
চলে; writers থামার পরে mediator staged result check করে checked bytes promote
করে। Generalized tree adapter সব bytes memory থেকে rewrite করে না: stable tree
freeze করে rename করে। Network server-এর exit broker; typed structure ও values
check হয়, call durably reserve হয়, admission-এর পরে broker real credential যোগ
করে। Server dummy token পায়। আগের approved send ফিরিয়ে নেওয়া যায় না; পরের request
refused হলে partial। Upstream outcome নিশ্চিত না হলে UNKNOWN এবং slot spent থাকে।

নতুন call-এর honest-run reference নেই। Pin-time template perturbed arguments,
transforms, clock windows ও bounded anti-unification দিয়ে শেখে। এটি heuristic,
least-general template পাওয়ার নিশ্চয়তা নয়। Slack checked canonical view-তে
কত choice অবশিষ্ট তার bound। Unicode alphabet ও actual trusted clock-এর সঙ্গে
হিসাব মেলাতে হয়; বাদ দেওয়া ZIP metadata বা raw serialization এর মধ্যে পড়ে না।

Local honest-run contracts 32/32 landed attack stopped করেছে। Local pin-time
templates development-এ 75/75 এবং held-out-এ 39/39 landed attacks stopped করেছে,
কিন্তু honest blocks 1/84 এবং 6/48। Held-out 12.5% false-block rate frozen 5%
criterion fail করেছে। পরের local cohort কোনো eligible scored server যোগ করেনি;
তাই local fixes নতুন population-এ validate হয়েছে বলা যাবে না।

Original network cohort-এর 12 থেকে 10 server template পেয়েছে। Covered ten-এ
120/120 honest mock protocol trial admitted। Fixed unauthorized-send variants
792/816 refused; 120 silent no-op আলাদা incomplete outcome। Development 480/504,
covered held-out 312/312। এগুলো captured-request transformation-এর check-level
ফল; প্রতিটি package-এর malicious source rebuild নয়। Every-string-leaf adaptive
attacks-এ 612/648 refused: splitifi-তে 24 এবং held-out travel-এ 12 admitted।
Zero-admission criterion fail করেছে। Uncertainty server cluster ধরে হিসাব হয়েছে।

নতুন frozen held-out selection-এ 40 unused candidates থেকে 5 qualifier পাওয়া
গেছে; target ছয় পূরণ হয়নি, কোনো screening failure বাদ দিয়ে replace করা হয়নি।
Honest protocol trials 60/60; fixed sends 312/312 refused; adaptive 324/336 refused,
conekta-তে 12 admission। দুই tool-এ JSON string leaf নেই, তাই adaptive case-ও নেই।
Empty-payload API-key creation এবং directory tool-এর telemetry POST আছে; দুই
package একই author-এর। এটি vendor-এর পাঁচটি বাস্তব task সফল হওয়ার প্রমাণ নয়।

Rebuilt Postmark end-to-end test-এ EffectSeal 21/21 unauthorized sends refused
করেছে, তিন no-op incomplete। Real ToolHive ও AgentBound প্রতিটি 3/21 stopped,
সব অন্য host-এর request। Pinning alerts 0/8 attack versions; description-change
control flagged। Alerts ও send prevention আলাদা unit। Official GitHub checks
84/84 fixed send এবং 24/24 adaptive variants refused করেছে। আগের OpenAI/Llama
agent study dated evidence; এই repair-এর পরে নতুন paid API scoring হয়নি। Real
Postmark validation-ও আগের public test-token replay, কোনো email delivery নয়।

Actual proxy-তে আট contender ও দুই worker নিয়ে 100 race-এর প্রতিটিতে ঠিক একটি
far-side request পৌঁছেছে; restart replay HTTP 403। Quiet 300-sample loopback
measurement-এ gate p50/p95 14.5/33.6ms, record-only 1.7/20.9ms। Control-state read,
instantiation, SQLite ও logs আছে; TLS/WAN/vendor latency নেই। Production
throughput দাবি নয়।

দুই independent pin session-এর agreement honesty প্রমাণ করেনি। Honest template
মিলেছে, session noise মেলেনি, stable Bcc poisoning মিলেছে অথচ effects unfaithful।
Trusted pinned version ও যথেষ্ট tight contract এখনও প্রয়োজন। Call authorization
intent থেকে request তৈরি হওয়ার জায়গা সামলায়; effect admission approved request-এর
implementation কী admit করছে তা সামলায়।

Demo-তে current claim matrix, offline verifier, raw evidence bundle এবং
`tests/test_network_repairs.py` দেখান। শুধু percentage দেখিয়ে থামবেন না। Fresh
Linux reproduction exact commit ধরে রিপোর্ট করে; PDF build manifest source ও
output মিলিয়েছে। Anonymous artifact URL এবং authors-এর final review ছাড়া
submission-ready বলবেন না। Acceptance probability-ও এই evidence থেকে বের হয় না।

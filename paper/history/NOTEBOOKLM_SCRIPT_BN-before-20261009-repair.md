# The Price of a Lie — সম্পূর্ণ গল্প, একবারে, সঠিকভাবে

*Group 13-র MCP execution-integrity প্রজেক্টের জন্য একটি বাংলা ন্যারেশন স্ক্রিপ্ট। এটা লেখা
হয়েছে NotebookLM-এ দিয়ে podcast বানানোর জন্য, এবং Md. Tanzamul Azad ও Jahidul Islam নিজেরা
যেন পুরো প্রজেক্টটা confidently বুঝতে ও defend করতে পারে তার জন্য। এই ডকুমেন্টের প্রতিটা সংখ্যা
প্রজেক্টের নিজস্ব regenerable experiment log ও documentation (`docs/00`–`42`) থেকে নেওয়া —
এখানে কিছুই বানানো বা বাড়িয়ে বলা হয়নি। যেখানে প্রজেক্ট এখনো অসম্পূর্ণ, সেটাও ঠিক ততটাই
পরিষ্কারভাবে বলা হয়েছে যতটা যেখানে সফল হয়েছে সেটা বলা হয়েছে।*

---

## Part 0 — এই ডকুমেন্ট কীভাবে পড়বে

এটা লেখা হয়েছে একটা ধারাবাহিক গল্প হিসেবে, যে ক্রমে আসলে চিন্তাভাবনাটা হয়েছিল — একটা শেষ হওয়া
পেপার যেভাবে জিনিসগুলো presenter করত সেই ক্রমে না, বরং যে ক্রমে জিনিসগুলো *আবিষ্কার* হয়েছিল।
এটা গুরুত্বপূর্ণ, কারণ একজন examiner-এর সামনে এই কাজটা defend করার সবচেয়ে শক্তিশালী উপায় হলো
উপসংহারগুলো মুখস্থ বলা না, বরং ব্যাখ্যা করা *কেন প্রতিটা ধাপ পরেরটার আগে দরকার ছিল*। যদি তুমি এই
গল্পটা causally বলতে পারো — "আমরা X চেষ্টা করলাম, X ব্যর্থ হলো Y কারণে, যেটা আমাদের Z করতে
বাধ্য করলো" — তাহলে মনে হবে তুমি কাজটা বুঝেছো, শুধু slide মুখস্থ করোনি।

ডকুমেন্টের শেষে একটা আলাদা Q&A সেকশন আছে (Part 12) যেখানে একজন ধারালো examiner যে কঠিন
প্রশ্নগুলো করতে পারে তার অনুমান করা হয়েছে, প্রতিটার জন্য একটা ছোট উত্তর আর একটা লম্বা backup
উত্তর দেওয়া আছে। Part 1–11 পড়ো কাজটা বুঝতে। Part 12 পড়ো সেটা defend করতে।

---

## Part 1 — এক বাক্যে মূল আইডিয়া

**MCP (Model Context Protocol) একজন ব্যবহারকারীকে একটা tool একবার approve করতে দেয়, সেই
tool টা *কী বলছে* সে করে তার ভিত্তিতে — কিন্তু এরপর প্রতিবার যখন tool টা আসলে *ব্যবহার* হয়, কোনো
কিছুই চেক করে না যে সেটা এখনও সেই কাজটাই করছে কিনা।** ব্যবহারকারীর approval বাঁধা থাকে একটা
*declaration*-এর সাথে (একটা নাম, একটা description, একটা schema)। tool-এর execution বাঁধা
থাকে *server আসলে কী code চালাচ্ছে* তার সাথে। প্রোটোকলে এই দুইটাকে একসাথে বেঁধে রাখার কিছু নেই।
একটা server একবার approval-এর সময় তার declaration মেনে চলতে পারে, আর তারপর প্রতিটা call-এ
চুপচাপ তার আসল effect ঘুরিয়ে দিতে পারে — আর client যে response পায় তাতে কিছু বদলেছে তার কোনো
চিহ্নই থাকে না।

এই প্রজেক্টটা এই gap নিয়ে: এটা যে সত্যি, সেটা প্রমাণ করা, *response দেখে* এই gap কখনো বন্ধ করা
যায় না সেটা প্রমাণ করা, real code-এ এটা কতটা খারাপ সেটা মাপা, এবং তারপর একটা mechanism বানিয়ে
adversarially টেস্ট করা যেটা এই gap-টা অন্যভাবে বন্ধ করে — response না দেখে, *effect* দেখে।

---

## Part 2 — কেন এটা সত্যিকারের সমস্যা, শুধু কল্পনা না

চিন্তা করো MCP-তে একটা "tool approve করা" আসলে কী মানে। একজন ব্যবহারকারীকে দেখানো হয় একটা
tool-এর নাম (ধরো `transfer_money`), তার description ("নির্দিষ্ট একজনকে টাকা পাঠায়"), আর তার
input schema (`{amount, recipient}`)। ব্যবহারকারী সেটা একবার approve করে। তারপর থেকে, একটা
autonomous agent সেই tool-টা *মেশিনের গতিতে, চিরকাল, আর কোনো মানুষের রিভিউ ছাড়াই* কল করতে
পারে — এটাই তো এজেন্টকে tool access দেওয়ার আসল উদ্দেশ্য; প্রতিটা call-এ মানুষের approval লাগলে
automation-এর পুরো পয়েন্টটাই নষ্ট হয়ে যেত।

এখানেই আসল বিপদটা: approval দেওয়া হয়েছিল *declaration*-কে। execution, প্রতিবার, যে code-ই
এখন সেই tool-এর পেছনে আসলে deploy করা আছে সেটাই চালায়। যদি server operator — অথবা যে
attacker server compromise করেছে, অথবা একটা malicious package update, অথবা কোনো
dependency-র supply-chain compromise — ব্যবহারকারী approve করার *পরে* `transfer_money`
আসলে কী করে সেটা বদলে দেয়, ব্যবহারকারীর আগের approval তখনও চুপচাপ পরের প্রতিটা call-কে cover
করে। এই প্যাটার্নটাকে সাধারণ ভাষায় মাঝে মাঝে "rug pull" বলা হয়, কিন্তু এর সঠিক টেকনিক্যাল নাম হলো
**distributed TOCTOU (Time-Of-Check to Time-Of-Use) vulnerability, যার কোনো atomicity
primitive নেই**: check হয় T₁ সময়ে (approval), use হয় T₂ সময়ে (পরের প্রতিটা call), আর একজন
অবিশ্বস্ত পক্ষ — server — মাঝখানের গ্যাপে বসে থাকে, যা খুশি তাই করার স্বাধীনতা নিয়ে, কারণ T₁-এর
guarantee T₂-তেও ধরে রাখতে কিছুই বাধ্য করছে না।

এটা কোনো বানানো scenario না। এটা MCP-এর trust model কীভাবে কাজ করে তার একটা সরাসরি,
structural পরিণতি: approval একটা static, one-time কাজ, একটা declaration-এর উপর; execution
dynamic এবং বারবার হয়, এমন code-এর উপর যা client আর কখনো পরীক্ষা করে না।

---

## Part 3 — Threat Model: ঠিক কী assume করা হয়েছে, আর কী করা হয়নি

ভালো গবেষণা স্পষ্ট থাকে কী assume করছে তা নিয়ে। এখানে ঠিক বলা আছে এই প্রজেক্ট একটা adversarial
MCP server কী করতে পারবে আর পারবে না বলে assume করেছে — কারণ "তোমাদের threat model কী" এমন
প্রশ্ন একজন ধারালো reviewer সবার আগে জিজ্ঞেস করবে। এখানে অস্পষ্ট উত্তর পরের সব কিছু দুর্বল করে দেয়।

**আমরা adversary-কে যেটার নিয়ন্ত্রণ আছে বলে ধরি**: server-এর নিজের implementation। এটা যা খুশি
response দিতে পারে, এটা যা খুশি effect ঘটাতে পারে (server আসলে যে OS permission ধরে রাখে তার
মধ্যে), এবং এটা যেকোনো সময়ে, যেকোনো subset of calls-এর জন্য, যেকোনোভাবে তার behavior declared
description থেকে সরিয়ে নিতে পারে।

**আমরা যেটা assume করি *না***: এটা generic "server compromise" না, যেখানে attacker
ব্যবহারকারীর নিজের মেশিনে root access পায়, TLS ভেঙে ফেলে, অথবা client-এর কোনো
memory-safety bug exploit করে। server নিজেই design অনুযায়ী একটা আলাদা, আগে থেকেই অবিশ্বস্ত
পক্ষ — MCP-তে approval থাকারই এটাই কারণ, কারণ সেটা assume করে server malicious হতে পারে।
আমাদের প্রশ্নটা আরও সংকীর্ণ ও ধারালো: **server যদি নিজের সম্পর্কে মিথ্যা বলতে পারে, তাহলে একটা
client কী verify করতে পারে, আর কীভাবে?**

এই পার্থক্যটা গুরুত্বপূর্ণ কারণ এটা প্রজেক্টের claim-গুলোকে সীমাবদ্ধ রাখে। আমরা "AI agent
security" সাধারণভাবে সমাধান করার claim করছি না। আমরা একটা নির্দিষ্ট, precisely-stated
sub-problem সমাধান করার claim করছি: একটা approve হওয়া tool-এর *effect* তার *declaration*-এর
সাথে মেলে কিনা, বারবার calls জুড়ে, server নিজের সম্পর্কে সত্যি বলবে এটা বিশ্বাস না করেই।

---

## Part 4 — Theorem 1: প্রমাণ করা যে client মিথ্যাটা দেখতে পারে না

কোনো defense বানানোর আগে, প্রজেক্ট আরও একটা basic প্রশ্ন আগে জিজ্ঞেস করেছিল: **একটা client যে
শুধু response দেখে, সে কি আদৌ এই ধরনের divergence detect করতে পারে, এমনকি নীতিগতভাবেও?**
উত্তর, যেটা শুধু observe করা হয়নি বরং প্রমাণ করা হয়েছে, তা হলো না। এটাই Theorem 1 (*Transcript
Indistinguishability*), আর এটাই পুরো প্রজেক্টের সবচেয়ে গুরুত্বপূর্ণ intellectual result, কারণ
এটাই কারণ পরের প্রতিটা design decision যেভাবে দেখতে, সেভাবে দেখতে।

**প্রমাণের intuition, সহজ ভাষায়**: দুইটা সমান্তরাল world কল্পনা করো। World A-তে, server ঠিক
সেটাই করে যা সে declare করেছিল — একটা honest execution। World B-তে, server *ভিন্ন* একটা
effect ঘটায় (একটা write অন্য location-এ ঘুরিয়ে দেয়, content swap করে, যা-ই হোক attack-টা) কিন্তু
তার response message-টা এমনভাবে সাজায় যেন সেটা দেখতে একদম honest execution-এর মতোই লাগে।
যেহেতু server-ই effect আর সেই effect-এর evidence, দুইটারই একমাত্র উৎস, সে সবসময় World B-এর
response-কে World A-এর মতো করে রিপোর্ট করতে পারে — প্রোটোকলে কিছুই response-কে underlying
effect সম্পর্কে সত্যি বলতে বাধ্য করে না। একটা client যে শুধু request আর response-এর sequence
দেখে — *transcript* — সে World A-এর transcript আর World B-এর transcript আলাদা করতে পারে না,
কারণ server ইচ্ছা করেই সেগুলো byte-identical বানিয়েছে। যদি client-এর decision procedure
(তার accept/reject logic) transcript-এর একটা pure function হয়, আর transcript দুই world-এই
identical হয়, তাহলে decision-ও দুই world-এই identical হতে বাধ্য। তাই কোনো passive,
response-only client নির্ভরযোগ্যভাবে দুইটা world আলাদা করতে পারে না।

এটা কোনো নতুন mathematical trick না — এই argument-এর shape security literature-এর classic
TOCTOU result-গুলোর মতোই। এই প্রজেক্টের specific যেটা, সেটা হলো এই argument-টা MCP-এর
declaration/execution split-এ নির্দিষ্টভাবে apply করা, আর এখান থেকে একটা concrete design
lesson বের করা: **এমন একটা defense বানিও না যেটা শুধু response আবার পরীক্ষা করে**, কারণ
Theorem 1 বলছে সেই class-টা fundamentally blind, শুধু মাঝে মাঝে imperfect না। "response আরও
ভালো করে দেখো" এই ধরনের যেকোনো defense architecture এই blind spot-টা inherit করবে, যতই
clever inspection logic হোক না কেন। এখান থেকে বের হওয়ার একমাত্র উপায় হলো response-কে সত্যের
উৎস হিসেবে বিশ্বাস করা বন্ধ করা, আর তার বদলে independently *effect*-টাই observe করা।

---

## Part 5 — Real scale-এ এটা মাপা: 1,242 real server, ছয়টা detector, শূন্য জয়

একটা theorem হলো *সম্ভব কি না* তার claim। এটা real world-এ সমস্যাটা কতটা common বা severe,
অথবা perfect detection impossible হলেও কোনো clever engineering trick practice-এ কাছাকাছি
কিছু পেতে পারে কিনা, সেটা নিয়ে কিছু বলে না। তাই প্রজেক্ট এটা empirically টেস্ট করেছে, real scale-এ,
কিছু design করার আগে।

**1,242টা real, independent, third-party MCP server** পাবলিক registry থেকে নেওয়া হয়েছিল আর
একটা sandboxed Docker harness-এর ভেতরে চালানো হয়েছিল। **ছয়টা ভিন্ন response-level detection
mechanism** এগুলোর বিরুদ্ধে চেষ্টা করা হয়েছিল — এমন approach যা একজন careful engineer আসলেই
চেষ্টা করতে পারে তার representative: response-এর hash-based verification, structural
consistency check, behavioral fingerprinting, আরও কিছু। **এগুলোর একটাও কোনো usable
operating point-এ পৌঁছাতে পারেনি।** শূন্য শতাংশ। শুধু "কম accuracy" না — instrument নিজেই দুইবার
audit করে (দেখো Part 6) সংশোধন করার পরের honest সংখ্যাটা হলো, এই scale-এ response-level
detection কোনো usable signal দেয় না।

এই সংখ্যাটা আরও সাজানো কোনো সংখ্যার rounding না। এটা টিম নিজের measurement instrument
*নিজেই দুইবার audit করে* যা বাকি ছিল, বাইরের কোনো reviewer না — আর এটাই পরের অংশ, যেটা হয়তো
এই প্রজেক্ট আসলে কীভাবে কাজ করে সেটা সবচেয়ে বেশি বলে।

---

## Part 6 — নিজেদের ভুল নিজেরাই খুঁজে বের করার discipline

এটা নিজের একটা আলাদা chapter হিসেবে বলার মতো, কারণ এটা পুরো প্রজেক্টে research rigor-এর
সবচেয়ে শক্তিশালী প্রমাণ, আর কারণ এটা "তোমাদের সংখ্যাগুলো কেন বিশ্বাস করবো" প্রশ্নটার উত্তর জিজ্ঞেস
করার আগেই দিয়ে দেয়।

প্রজেক্টের শুরুর দিকে, যে detection সংখ্যা রিপোর্ট করা হচ্ছিল সেগুলো যতটা হওয়া উচিত তার চেয়ে বেশি
ভালো দেখাচ্ছিল। একটা flattering সংখ্যা মেনে নেওয়ার বদলে, প্রজেক্টের নিজস্ব standing rule —
*"instrument bug হলো default hypothesis"* — measurement pipeline-টাই ইচ্ছাকৃতভাবে audit
করার trigger দিয়েছিল। এভাবে দুইটা real bug পাওয়া গিয়েছিল, কোনো বাইরের reviewer না, বরং
প্রজেক্ট টিম নিজের tooling audit করে:

1. **একটা suppressed-detections bug**: true detection-এর একটা class চুপচাপ denominator
   থেকে বাদ পড়ে যাচ্ছিল, যা কৃত্রিমভাবে apparent success rate বাড়িয়ে দিচ্ছিল।
2. **একটা error-flag naming bug**: code একটা MCP error flag এমন একটা নাম দিয়ে চেক করছিল
   যেটা SDK আসলে define-ই করে না (`isError` বনাম SDK-র আসল `is_error`), যার মানে "landed"
   হিসেবে গোনা প্রায় 65% attack আসলে এমন call ছিল যেগুলো server *সরাসরি প্রত্যাখ্যান* করেছিল — এগুলো
   এমন attack না যেগুলো সফল হয়ে detect হয়নি, বরং এমন attack যেগুলো আসলে কখনো ঘটেইনি কারণ server
   malformed request প্রত্যাখ্যান করেছিল।

headline সংখ্যা বিশ্বাস করার *আগে* এই দুইটা খুঁজে বের করে ঠিক করাটাই হলো "prevented / detected /
UNKNOWN আলাদাভাবে রিপোর্ট করো" আর "তৃতীয় একটা bug আছে ধরে নাও" — এই standing rule-গুলোর
আসল মানে (এগুলো এই প্রজেক্টের নিজস্ব documentation-এ লেখা আছে, rigorous শোনানোর জন্য পরে
বানানো হয়নি)। এই discipline-এর কারণেই, যখন এই ডকুমেন্ট পরে কিছু বলে যেমন "0% true detection"
বা "100% prevention coverage," সেই সংখ্যাগুলো এমন একটা প্রজেক্টের সংখ্যার চেয়ে বেশি বিশ্বাস করা
যায় যে প্রজেক্ট কখনো নিজের ভুল খুঁজতেই যায়নি।

---

## Part 7 — Milestone M0: Corpus, classifier, আর একটা honestly open gap

প্রজেক্ট প্রতিটা MCP tool-এর "auditability class" মাপে — মোটামুটি, একটা নির্দিষ্ট tool-এর
behavior বাইরে থেকে কতটা verifiable, A0–A3 স্কেলে (A0 সবচেয়ে কম auditable / সবচেয়ে opaque)।
পুরো corpus জুড়ে, **69.7% tool A0 class-এ পড়ে**। এই সংখ্যাটা সত্যিই গুরুত্বপূর্ণ — "যা আছে তার
বেশিরভাগই construction অনুযায়ী verifiable না" এই কথার জন্য এটাই empirical backbone — কিন্তু
এর সাথে একটা honestly open methodological gap আছে যেটা লুকিয়ে রাখা হয়নি।

**κ gate।** একটা classifier-এর output বিশ্বাস করতে হলে, জানতে হবে independent human judge-রা
সাধারণত একমত হবে কিনা। এই প্রজেক্ট human-agreement check চালানোর *আগেই* একটা threshold
pre-register করেছিল: Cohen's κ (human raters-এর মধ্যে agreement মাপার একটা standard
statistic) কমপক্ষে 0.60 হতে হবে classifier validated ধরার জন্য। আসল measured result ছিল
**κ = 0.559** — moderate agreement, কিন্তু প্রজেক্টের নিজের pre-registered gate-এর নিচে।

এটা লুকানো বা এড়িয়ে যাওয়া হয়নি। প্রজেক্টের documentation-এর সব জায়গায় এটাকে **open blocker**
হিসেবে লেবেল করা আছে — milestone M0c। 69.7% A0 সংখ্যাটাকে explicitly "একটা instrument
reading, এখনো measurement না" বলা হয়েছে যতক্ষণ না এই gate বন্ধ হয়। root cause শুধু মাপা হয়নি,
diagnose করা হয়েছে: দুই human annotator-এর মধ্যে বেশিরভাগ disagreement labelling codebook-এর
একটা নির্দিষ্ট, চিহ্নিতযোগ্য ambiguity থেকে আসে (দুইটা কাছাকাছি category-র মধ্যে গুলিয়ে ফেলার মতো
একটা class of case), random noise থেকে না। একটা দ্বিতীয় round-এর labelling, সেই নির্দিষ্ট
ambiguity সমাধান করার জন্য redesign করা, প্রস্তুত করা আছে — কিন্তু দরকার হবে দুইজন independent
human (প্রজেক্টের নিজস্ব AI tooling না — এখানে AI-generated label ব্যবহার করলে human agreement
মাপার পুরো উদ্দেশ্যটাই নষ্ট হয়ে যেত)।

**এই প্রজেক্ট নিয়ে কথা বলার সময় এটা কেন গুরুত্বপূর্ণ**: 69.7% A0 সংখ্যাটা কখনো একটা settled fact
হিসেবে present করো না। এটাকে present করো "আমাদের বর্তমান সেরা instrument reading, যার একটা
open validation gap আছে যেটা আমরা precisely diagnose করেছি আর মাত্র একটা labelling round
দূরে আছি বন্ধ করার থেকে" — এই বাক্যটা যতটা confident overclaiming করা যেত তার চেয়ে বেশি
defensible।

---

## Part 8 — Milestone M1: Novelty gate — কী আগে থেকেই আছে, কী নেই

কোনো নতুন defense design করার আগে, প্রজেক্ট এমন একটা কাজ করেছিল যা অনেক student capstone
স্কিপ করে: এটা একটা **failable** literature gate বানিয়েছিল — একটা চেক যা পুরো research
direction-টাই মেরে ফেলতে পারতো যদি উত্তর আসতো "এটা তো আগে থেকেই সমাধান করা আছে।" এটাই একটা
novelty *claim* আর novelty *gate*-এর পার্থক্য: একটা gate fail করতে পারে। এটা প্রজেক্ট প্রাথমিকভাবে
যে তিনটা broad claim করতে পারবে ভেবেছিল সেগুলো retire করে দিয়েছিল, তারপর একটা সংকীর্ণ, precisely
bounded gap-এ পৌঁছেছিল যেটা টিকে গেছে।

চারটা adjacent body of work চেক করা হয়েছিল primary source থেকে, secondhand summary না:

- **Alcatraz (2003)** — process-layer staging-and-commit/discard mechanism। এই আইডিয়ার
  একটা real অংশ ধরে রাখে (commit করার আগে staging) কিন্তু MCP-এর সাথে যুক্ত না আর tool-এর নিজের
  declaration থেকে কোনো contract বের করে না।
- **TxOS (2009)** — transactional system call, সত্যিকারের kernel-level rollback সহ। নীতিগতভাবে
  অনেক বেশি শক্তিশালী, কিন্তু একটা *modified kernel* দরকার — এটা একটা unmodified, real-world MCP
  server-এ apply করা যায় না, যেটা এই প্রজেক্টের কাজ করার দরকার ঠিক সেই setting।
- **AgentBound / SAFEFLOW** — unmodified agent server-এর জন্য সাধারণ confinement
  architecture। spirit-এ কাছাকাছি, কিন্তু SAFEFLOW-এর নিজের paper explicitly বলে এটা external
  side effect-এর সত্যিকারের rollback address করে না — এই সীমাবদ্ধতা এই প্রজেক্ট পরে সরাসরি ও
  empirically reproduce করে, শুধু secondhand cite করে না (দেখো Part 13-এর capstone result)।
- **ETDI / Zero Trust Registry** — signed tool definition আর registry-based identity। এগুলো
  *declaration* সুরক্ষা করে — এরা নিশ্চিত করে declaration নিজে tamper বা impersonate হয়নি — কিন্তু
  approval-এর পর behavior এখনও declaration-এর সাথে মিলছে কিনা তা নিয়ে কিছু বলে না। এটাই ঠিক সেই
  blind spot যা Theorem 1 চিহ্নিত করে।

**যে gap টিকে থাকে**: একটা **unmodified** process-এর **real, external** effect-এর
staging-and-commit mediation, **বাইরে থেকে** চেক করা tool-এর **নিজের declaration থেকে বের
করা** একটা contract-এর বিরুদ্ধে। উপরের চারটা সিস্টেমের প্রতিটা এর একটা অংশ ধরে রাখে — staging
(Alcatraz), rollback কিন্তু modified kernel দরকার (TxOS), সাধারণ confinement কিন্তু real
external-effect rollback ছাড়া (SAFEFLOW, আমরা সরাসরি Part 13-তে confirm করেছি), অথবা
declaration-only integrity (ETDI) — কিন্তু কোনোটাই পুরো combination ধরে রাখে না। এটাই প্রজেক্টের
আসল novelty claim, আর এটা টিকে থাকে *কারণ* তিনটা broader, বেশি sweeping claim আগে টেস্ট করে
retire করা হয়েছিল।

---

## Part 9 — আমাদের Approach, প্রথম অংশ: The Permit Rule

Gap চিহ্নিত হওয়ার পর, প্রজেক্টের দরকার ছিল "এই effect-টা allowed" এই কথার একটা precise,
checkable definition। সেই definition-ই হলো **Permit rule**:

```
Permit(a, C)  =  Valid(C)  ∧  Matches(a, C)  ∧  Unused(C)  ∧  Mediated(a)
```

সহজ ভাষায়: একটা প্রস্তাবিত effect `a` contract `C`-এর অধীনে তখনই permitted, যদি এই চারটা একসাথে
সত্যি হয়:

- **Valid(C)** — contract-টা নিজেই authentic ও unexpired।
- **Matches(a, C)** — effect-এর operation, target, আর payload সবগুলো contract-এর bound
  field-এর মধ্যেই পড়ে। এটা *raw proposed request*-এর উপর চেক করা হয়, effect ঘটার আগেই — এটাই
  সেই জিনিস যা একজন attacker-কে extra argument ঢুকিয়ে দেওয়া থেকে ধরে যা contract কখনো
  আশা করেনি।
- **Unused(C)** — contract-এর invocation allowance এখনও বাকি আছে। এটা একটা আসল reservation
  system (`AllowanceLedger.reserve()`) দিয়ে enforce করা হয়, staging শুরু হওয়ার *আগেই* নেওয়া
  হয়, তাই একটা আগে থেকে খরচ হয়ে যাওয়া authorization-এর বিরুদ্ধে দ্বিতীয় attempt অপচয় করা কাজের
  আগেই refuse হয়।
- **Mediated(a)** — effect-টা আসলে enforced path দিয়েই গেছে; এর সম্পর্কে কিছুই অন্য কোনো,
  unwatched channel দিয়ে real world-এ পৌঁছায়নি।

এটা স্পষ্টভাবে একটা **policy definition**, কোনো theorem না — কেউ claim করছে না যে এই rule-টা
কোনো mathematical অর্থে সঠিক প্রমাণিত। আসল research প্রশ্ন হলো একটা real implementation এই
rule-টা adversarial pressure-এর নিচে *ধরে রাখতে* পারে কিনা, আর ঠিক কোথায় এটা ভেঙে যায়। সেটাই
প্রজেক্টের বাকি অংশ টেস্ট করে।

---

## Part 10 — আমাদের Approach, দ্বিতীয় অংশ: Specification Ladder

একটা contract-এর জানা দরকার একটা নির্দিষ্ট tool-এর জন্য "matches" মানে আসলে কী, আর এখানে
প্রজেক্ট একটা ইচ্ছাকৃতভাবে সতর্ক choice করে: **ধরে নিও না বেশি specification মানে বেশি
protection — মাপো।** Specification ladder-এর তিনটা independent rung আছে, আর প্রতিটা
tool-এর contract প্রতিটা rung-এ *আলাদাভাবে* চেক করা হয়, কারণ প্রজেক্টের নিজের প্রাথমিক পরীক্ষা
(`27`) predict করেছিল, আর পরে real-server result confirm করেছে যে বেশি specification uniformly
সাহায্য করে না:

| Rung | কী চেক করে | কী ধরে | কী structurally ধরতে পারে না |
|---|---|---|---|
| **L1 — destination** | শুধু approved target বদলেছে কিনা | ভিন্ন target-এ diversion (আলাদা path, আলাদা database row, আলাদা recipient) | সঠিক destination-এ একটা payload swap |
| **L2 — structure** | উপরেরটা, plus: result non-empty / well-formed কিনা | free text tool-এ L1-এর বাইরে কিছু না | তখনও content সঠিক কিনা তা নিয়ে কিছু না |
| **L3 — content** | উপরেরটা, plus: final bytes-এর exact-match (বা hash-match) | content substitution — যা L1 আর L2 ধরতে পারে না | দেখো Part 11-এর honest limitations |

এখানে সবচেয়ে গুরুত্বপূর্ণ design decision হলো verdict **per-property** রিপোর্ট করা হয়, কখনো একটা
pass/fail সংখ্যায় ফেলে দেওয়া হয় না। একটা tool একই সাথে বৈধভাবে `destination=PASS,
content=FAIL` হতে পারে — আর এই পার্থক্যটাই, একটা flattened score না, ladder-টা আসলে যা মাপছে।

---

## Part 11 — আমাদের Approach, তৃতীয় অংশ: ছয়-ধাপের Mediation Mechanism

Ladder বলে দেয় *কী* চেক করতে হবে। Mediation mechanism হলো *কীভাবে* সেই চেকটা server-কে
বিশ্বাস না করেই আসলে হয়। এটা কঠোরভাবে sequence-এ ছয়টা ধাপে চলে, আর — এটা design defend করার
জন্য গুরুত্বপূর্ণ — **প্রতিটা ধাপ যোগ করা হয়েছিল কারণ একটা নির্দিষ্ট attack সেটা missing পেয়েছিল, শুরু
থেকেই speculatively design করা হয়নি।** এই ইতিহাসটা জানা দরকার, কারণ "আমরা এটা যোগ করেছি কারণ
এটা ছাড়া আমরা নিজেদের সিস্টেম ভেঙে ফেলেছিলাম" এটা "আমরা ভেবেছিলাম এটা একটা ভালো আইডিয়া হতে
পারে" এর চেয়ে অনেক শক্তিশালী উত্তর।

1. **RESERVE** — অন্য কিছু হওয়ার আগেই contract-এর `AllowanceLedger`-এর বিরুদ্ধে একটা execution
   slot নেওয়া। একটা আগে থেকেই খরচ হয়ে যাওয়া contract-এর বিরুদ্ধে দ্বিতীয় reservation এখানেই
   refuse হয়, staging শুরু হওয়ার আগেই। *(একটা replay attack-এর পরে যোগ করা হয়েছিল — নিচের M4
   গল্পের Part 15-তে — যেটা দেখিয়েছিল একটা pure effect-diff mediator একই replayed write দুইবার
   commit করে, কারণ একটা replay-এর effect definition অনুযায়ীই contract-এর সাথে মিলে যায়; শুধু
   effect-diff দিয়ে সেটা দেখা যায় না যে authorization আগেই খরচ হয়ে গেছে।)*
2. **ISOLATE** — প্রতিটা invocation-এর নিজস্ব staging workspace থাকে, যেটার মালিক *শুধু*
   untrusted server-এর নিজের OS identity। server-এর পক্ষে অন্য কিছু লেখে না; untrusted
   process ঠিক যেভাবে সাধারণত করত সেভাবেই কাজ করে।
3. **REQUEST-SHAPE CHECK** — effect পরীক্ষা করার আগেই: proposed request-এর argument set
   পুরোপুরি contract-এর bound field-এর মধ্যেই পড়ে কিনা? *(একটা ইচ্ছাকৃত corner-case টেস্টের পরে
   যোগ করা হয়েছিল, যেটা দেখেছিল একটা argument যেটা কোনো file-level পরিবর্তন ঘটায়ই না সেটা pure
   effect-diff-এর কাছে সম্পূর্ণ অদৃশ্য — এই ধাপ যোগ করার আগে mediator এটার কাছে অন্ধ ছিল।)*
4. **FREEZE + READ ONCE** — একজন trusted mediator, server থেকে *ভিন্ন* একটা OS identity
   হিসেবে চলে, staging **ঠিক একবার** পড়ে। এই একবারের read-ই decision-এর জন্য evidence, আর
   যদি commit হয়, সেই exact bytes যেটা লেখা হবে। এই পয়েন্টের পর staging আর কখনো দ্বিতীয়বার,
   independently পড়া হয় না — এই rule-টার প্রজেক্টের documentation-এ একটা নাম আছে: **M2 Commit
   Invariant**। *(একটা purpose-built, contract-aware adversary যোগ করার পরে যোগ করা হয়েছিল,
   যেটা দেখেছিল commit-এর সময় staging দ্বিতীয়বার re-read করা — decision-এর জন্য ব্যবহৃত প্রথম
   read আবার ব্যবহার না করে — একটা real race window খুলে দিয়েছিল: 20টা trial-এর মধ্যে 5টা, 25%,
   attacker content-কে decision আর commit-এর মাঝখানে trusted store-এ ঢুকতে দিয়েছিল। ঠিক করা
   হয়েছিল Part 4-এর read-এ ইতিমধ্যে capture হওয়া bytes commit করে, ডিস্ক থেকে আবার read না
   করে; একই attack-এর বিরুদ্ধে 20-এর মধ্যে 0 হিসেবে re-verify করা হয়েছে।)*
5. **EFFECT DIFF** — সেই একবারের frozen read-টা contract-এর বিরুদ্ধে চেক করা হয় যে ladder rung
   force-এ আছে সেই অনুযায়ী: exact path, exact bytes (বা hash), কোনো extra artifact না।
6. **COMMIT OR DISCARD** — exact match হলে, mediator নিজে — কখনো server না — frozen bytes
   একটা *আলাদা*, committed store-এ লেখে যেটায় server-এর কোনো write permission নেই, আর
   reservation-কে spent হিসেবে মার্ক করে। Step 3 বা step 5-এ কোনো mismatch হলে: কিছুই লেখা হয়
   না; transaction টা কেবল discard হয়ে যায়।

এই mechanism আসলে কী claim করে সেটা honest ভাবে বলার উপায় হলো: **এটা enforcement point-টা
server-এর response থেকে server-এর আসল filesystem effect-এ সরিয়ে দেয়**, ঠিক যেমন Theorem
1-এর design lesson দাবি করে, আর এটা শুধুমাত্র সেই তথ্য ব্যবহার করে যা tool-এর নিজের declaration
already দেয় — এর উপরে বানানো application-এর কোনো out-of-band জ্ঞান দরকার হয় না।

---

## Part 12 (আসল narrative-এ এটা Milestone M2) — নিজেদের mechanism বানানো আর ভাঙা

কোনো real জিনিসের বিরুদ্ধে এই mechanism বিশ্বাস করার আগে, প্রজেক্ট নিজেরই বানানো tool দিয়ে এটাকে
attack করেছিল, ইচ্ছাকৃতভাবে নিজের design ভাঙার চেষ্টা করেছিল, আর যা যা ফাটল পেয়েছিল সব রিপোর্ট
করেছিল।

**Architectural closure আর pre-registered threshold।** Mechanism-টা প্রথমে একটা synthetic
কিন্তু faithful stub server-এর বিরুদ্ধে validate করা হয়েছিল, threshold run-এর *আগেই* fix করা,
পরে যেই সংখ্যা আসুক সেই অনুযায়ী বাছাই করা না: undefended control যে attack ছেড়ে দিয়েছিল তার
prevention coverage কমপক্ষে ≥90% হতে হতো — আসল result ছিল **100% (10-এর মধ্যে 10)**।
Ambiguous "UNKNOWN" outcome-এর rate ≤20%-এর মধ্যে থাকতে হতো — আসল result ছিল **7.1% (14-এর
মধ্যে 1, একটা genuine "silent no-op" case)**। Honest workflow-কে undefended baseline-এর
success rate-এর 5 percentage point-এর মধ্যে সম্পূর্ণ হতে হতো — আসল result ছিল একটা **0
percentage-point gap**, মানে একমাত্র honest scenario-টা mechanism থাকুক বা না থাকুক একইভাবে
সম্পূর্ণ হয়েছে।

**Corner case, assume না করে টেস্ট করা।** চারটা honest-workflow edge case ইচ্ছাকৃতভাবে চালানো
হয়েছিল: একটা temporary নামে লিখে পরে rename করা, empty content লেখা, বড় (~2.3MB) payload
লেখা, আর লিখে সাথে সাথেই একই target overwrite করা। চারটাই clean pass করেছিল। পঞ্চম, ইচ্ছাকৃতভাবে
mechanism-এর নিজের বিরুদ্ধে adversarial একটা টেস্ট ইচ্ছাকৃতভাবে দুইটা sequential *honest* call-এ
একটা staging directory share করেছিল — আর একটা real bug পেয়েছিল: দ্বিতীয় honest call-এর
legitimate effect ভুলভাবে discard হয়ে গিয়েছিল প্রথম call-এর একটা leftover artifact-এর কারণে।
এটা কোনো security failure না (কিছু malicious ঘটেনি) কিন্তু একটা genuine honest-utility failure,
আর এটা ঠিক সেভাবেই রিপোর্ট করা হয়েছে: **per-invocation isolation একটা requirement correctness-এর
জন্য, শুধু security-র জন্য না**, assume না করে demonstrate করা।

**TOCTOU race আর hidden-field gap** — যা আগে Part 11-এ বর্ণনা করা হয়েছে, কারণ এই দুইটাই কারণ
step 3 আর step 4 এখন যে রূপে আছে সেই রূপে আছে — এখানে, এই milestone-এ পাওয়া গিয়েছিল, কোনো
external server জড়ানোর আগেই, adversarial self-testing দিয়ে।

---

## Part 13 — Milestone M2-এর Capstone: একটা real, unmodified server-এর সাথে mechanism মেলানো

এখন পর্যন্ত M2-এর প্রতিটা টেস্ট প্রজেক্ট নিজের বানানো একটা synthetic stub server ব্যবহার করেছিল।
এটা একটা বৈধ প্রথম ধাপ, কিন্তু এখানে একটা স্পষ্ট প্রশ্ন থেকে যায়: এর কোনোটাই কি আসলে *real*
third-party code-এর বিরুদ্ধে কাজ করে যেটার উপর প্রজেক্টের কোনো নিয়ন্ত্রণ নেই?

**যে engineering বাধা আগে সমাধান করতে হয়েছিল।** প্রজেক্টের নিজস্ব MCP client (`LiveSession`)-এর
একটা subprocess-কে কম privilege-এর OS identity হিসেবে launch করার কোনো built-in উপায় ছিল
না — সরাসরি আসল MCP SDK-এর launch-parameter type পরীক্ষা করে verify করা হয়েছিল, যেটা এমন
কোনো option expose করে না। এই কারণেই আগের প্রতিটা M2 টেস্ট একটা real server-এর বদলে একটা
hand-written stub ব্যবহার করেছিল: প্রজেক্টের নিজের MCP client দিয়ে একটা real MCP server
প্রজেক্টের নিজের process identity ছাড়া অন্য কিছু হিসেবে চালানোর কোনো উপায় ছিল না।

**সমাধান**: launch command-টাকে একটা privilege-dropping shell invocation-এ মুড়ে দেওয়া
(`su sandbox -s /bin/sh -c '...'`)। MCP client শুধু একটা command string দেখে; সে জানেই না
সেই string নিজেই আসল server process শুরু হওয়ার আগে একটা real privilege drop করে। এটা সরাসরি
verify করা হয়েছিল, assume করা হয়নি — একটা real `npx -y filesystem-mcp` process এভাবে launch
করে, direct filesystem ownership inspection দিয়ে confirm করা হয়েছিল যে এটা unprivileged
`sandbox` user হিসেবে চলছে ও file লিখছে, root হিসেবে না।

**Result**, `domdomegg/filesystem-mcp`-এর বিরুদ্ধে — M3 sweep-এ (Part 14) আগে ব্যবহার করা
একই real, unmodified npm package:

- **Honest call**: সম্পূর্ণ হয় ও commit হয়, byte-for-byte যেকোনো stub-server trial-এর মতোই।
- **`path_diversion`**: আসল, unmodified server সত্যিই approved content `/tmp/exfil.dat`-এ
  লিখেছিল — একটা real, external, unauthorized effect, আসল third-party code দিয়ে তৈরি হওয়া,
  কোনো simulation না। Mediator-এর diff mismatch ধরেছিল আর transaction discard করেছিল:
  `committed_content = None`। **`/tmp`-এ write-টা আগেই ঘটে গিয়েছিল আর সেটা undo করা হয়নি** —
  এটা যতটা plainly বলা হয়েছে positive result-টার মতোই, কারণ এটাই "discard"-এর honest scope
  আসলে কী মানে: trusted store কী committed হিসেবে গোনে তার bookkeeping, underlying OS-level
  write আটকানো হয়েছে এমন claim না।
- **`content_substitution`**: attacker-এর payload real-ভাবে stage হয়েছিল, content diff ধরেছিল,
  discard হয়েছিল — committed store-এ কখনো পৌঁছায়নি।

এই মুহূর্তেই প্রজেক্ট honestly বলতে পারে: *unmodified third-party code-এর বিরুদ্ধে real-ভাবে যে
একই real diversion unconfined ভাবে ঘটে গিয়েছিল, সেটা এখন real-ভাবে trusted store থেকে বাদ
রাখা হচ্ছে, এই mechanism দিয়ে।* underlying OS write-এর পুরো prevention-এর জন্য একটা অতিরিক্ত
layer দরকার হতো (একটা mount namespace বা chroot যেটা server চালু হওয়ার আগেই তার writable
scope সীমিত করে দেয়) — সেটা explicitly বলা আছে এই প্রজেক্ট যোগ করে না, ইতিমধ্যে solved হিসেবে
আড়াল করা হয়নি।

---

## Part 14 — Milestone M3: সাতটা real, independent server জুড়ে generality

একটা server-এ কাজ করা একটা mechanism প্রায় কিছুই প্রমাণ করে না এটা generalize করে কিনা তা নিয়ে।
M3-এর লক্ষ্য, প্রজেক্টের নিজের pre-registered target অনুযায়ী, হলো **কমপক্ষে দশটা independent
real implementation**। প্রজেক্টের কাছে বর্তমানে **সাতটা** আছে, প্রতিটা defined workflow shape
জুড়ে plus পথের মাঝে পাওয়া আরও দুইটা shape — real progress, honestly target-এর চেয়ে কম, আর
যেখানেই এটা আলোচনা হয় সেখানে ঠিক সেভাবেই বলা আছে।

যে ক্রমে সেগুলো টেস্ট করা হয়েছিল সেভাবেই দেখো, কারণ *ক্রমটাই* একটা গল্প বলে ইচ্ছাকৃতভাবে variation
খুঁজে বের করার, সহজ জয় বেছে নেওয়ার না:

1. **`domdomegg/filesystem-mcp`** (EXACT class — আলাদা `path` আর `content` argument)। প্রথম
   real-server টেস্ট, আর Part 13-তে বর্ণিত original `path_diversion` result যেখানে পাওয়া গিয়েছিল।
2. **`@modelcontextprotocol/server-filesystem`** (*official* reference implementation, একই
   EXACT shape)। নির্দিষ্টভাবে বাছাই করা হয়েছিল টেস্ট করার জন্য যে finding-টা একই tool shape-এর
   দ্বিতীয়, independent implementation-এও টিকে থাকে কিনা। Result: এই server নিজের allowed-
   directory boundary enforce করে আর diverted call সরাসরি প্রত্যাখ্যান করে — declaration থেকে
   একই রকম দেখতে server 1-এর চেয়ে সত্যিই ভিন্ন একটা real-world outcome। এটাই ঠিক সেই ধরনের
   variation যা M3-এর existence-এর কারণ।
3. **`@modelcontextprotocol/server-memory`** (CONSTRAINED/keyed — একটা structured
   knowledge-graph store, file path না)। attack-টা হাতে লিখতে হয়েছিল, কারণ automatic
   tampering tool শুধু top-level string argument পরীক্ষা করে আর এই tool-এর একমাত্র argument
   একটা nested array — automated instrument-এর একটা real, বলার মতো limitation, server
   defense না। একই destination-caught / content-needs-L3 প্যাটার্ন একদম ভিন্ন data model-এ
   reproduce করেছিল।
4. **`mcp-sqlite-server`** (UNDERSPECIFIED/SQL — একটা একক opaque `sql` string, যাতে
   destination, structure, আর content সব মিশে আছে কোনো schema-derivable boundary ছাড়া)।
   **এটা পুরো প্রজেক্টের সবচেয়ে ধারালো negative finding তৈরি করেছিল**: content substitution
   কোনো rung-এই ধরা পড়ে না, শুধু L3 পর্যন্ত miss হয়নি — কারণ tool-এর schema mechanism-কে কোনো
   field দেয়ই না যা থেকে একটা content check বের করা যায়। এটা এই workflow class-এ approach-এর
   একটা genuine, structural limitation হিসেবে রিপোর্ট করা হয়েছে, কমিয়ে দেখানো হয়নি।
5. **`mcp-server-git`** (git-native shape যাতে **কোনো content argument নেই** — payload হলো
   যা ইতিমধ্যে working tree-তে staged আছে; contract-এর "content" হয়ে যায় commit *message*,
   tool যে একমাত্র argument নিজে যোগ করে)। একদম ভিন্ন একটা tool family-তে একটা দ্বিতীয় server
   নিজের destination boundary enforce করতে দেখা গিয়েছিল (একটা `--repository` launch
   restriction) — নিশ্চিত করে server 2-এর নিজস্ব-defense pattern-টা আবার ঘটে, একবারের ঘটনা না।
6. **`mcp-server-sqlite-npx`** (UNDERSPECIFIED/SQL, server 4-এর মতো একই class-এর **দ্বিতীয়,
   independent** implementation, নির্দিষ্টভাবে বাছাই করা হয়েছিল উত্তর দিতে: ধারালো negative
   finding-টা কি একটা package-এর property, নাকি পুরো class-এর?)। Finding-টা exactly
   reproduce হয়েছিল, একদম ভিন্ন, অসম্পর্কিত code-এ। **এই replication হয়তো প্রজেক্টের
   credibility-এর জন্য original finding-এর চেয়েও বেশি মূল্যবান** — একটা codebase থেকে একটা
   surprising result সন্দেহ তৈরি করে; দুইটা independent codebase-এ একই result একটা structural
   property-র প্রমাণ।
7. **`notes-mcp`** (একদম নতুন একটা shape: content দুইটা আলাদা argument থেকে তৈরি হয়,
   `yaml_frontmatter` আর `markdown_content`, যেগুলো server একটা file-এ combine করে)। প্রথম
   ছয়টা server যা টেস্ট করতে পারেনি সেটা টেস্ট করার জন্য বাছাই করা হয়েছিল: একজন attacker কি
   two-part payload-এর *শুধু অর্ধেক* tamper করে content check এড়িয়ে যেতে পারে? Result: না। L3
   exact-match check tool-এর পুরো declared *output* compare করে, কোনো individual argument
   না — অর্ধেক tamper করলেও ধরা পড়ে, কোন field payload-এর কোন অংশ বহন করে তার জন্য কোনো special
   case লাগে না। একটা useful additional detail: এই server একটা *relative* path নেয়, তাই এর
   diversion attack একই directory-র *ভেতরে* একটা sibling file হিসেবে পড়ে, বাইরে না — একটা
   detail যা Part 16-তে (M5) আবার গুরুত্বপূর্ণ হয়ে ওঠে।

**এই sweep কী প্রমাণ করে আর করে না, প্রজেক্টের বাকি সব জায়গার মতোই একই discipline দিয়ে বলা**:
এটা দেখায় mechanism-টা defined প্রতিটা workflow shape জুড়ে real, independent code-এ transfer
করে, ladder-এর predicted blind spot (L1/L2 content attack miss করে; UNDERSPECIFIED tool
প্রায় সম্পূর্ণভাবে ladder-কে প্রতিরোধ করে) অসম্পর্কিত real implementation-এ exactly reproduce
হয়, আর দুইটা server-এর নিজস্ব defense একটা independent pattern হিসেবে বারবার আসে। এটা full
generality প্রমাণ করে **না** — সাত দশ না — আর এটা আগে থেকে ঘটে যাওয়া একটা external effect
prevent করা demonstrate করে **না**, Part 13-তে বলা একই কারণে।

---

## Part 15 — Milestone M4: Adaptive adversary — চারটা attack, defense তৈরি হওয়ার পরে টেস্ট করা

Part 12–14-তে বর্ণিত প্রতিটা attack final mechanism-এর নিজের code *আগেই*, বা তার থেকে
independently design করা হয়েছিল। M4 আলাদা আর বেশি demanding: এর মানে হলো adversary বানানো
**mechanism-এর আসল implementation জেনে**, বিশেষভাবে খুঁজে বের করা একজন defender যে সঠিক
design আগে থেকেই জানে সে কী exploit করবে। চারটা নামকরণ করা attack family চেষ্টা করা হয়েছিল,
প্রজেক্ট যে প্রতিটা angle চিহ্নিত করতে পেরেছিল তা cover করে:

1. **TOCTOU race** (Part 11-এ আগে বর্ণনা করা হয়েছে) — পাওয়া গেছে আর ঠিক করা হয়েছে। ঠিক করার
   আগে 25% success rate, পরে 20-এর মধ্যে 0, একই attack-এর বিরুদ্ধে re-verify করা হয়েছে।
2. **Replay / allowance exhaustion** — একটা contract-aware adversary যেটা শুধু একটা আগে
   ব্যবহৃত, legitimate authorization replay করে। `AllowanceLedger` reservation step ছাড়া,
   mediator replayed write দ্বিতীয়বার commit করে, কারণ একটা replay-এর effect definition
   অনুযায়ীই contract-এর সাথে মিলে যায় — একটা pure effect-diff replay আর fresh, legitimate
   call আলাদা করতে পারে না। `AllowanceLedger` যোগ করে **পাওয়া গেছে আর ঠিক করা হয়েছে** — একটা
   component যা প্রজেক্টের codebase-এ অন্য জায়গায় আগে থেকেই ছিল, আগে থেকেই unit-tested, কিন্তু
   এই attack এই gap-টা expose করার আগে কখনো এই newer mediator-এর সাথে connect করা হয়নি। ঠিক
   করার পরে, দ্বিতীয় call staging শুরু হওয়ার আগেই refuse হয়।
3. **Unmediated-channel exfiltration** — একটা secret একটা plain local socket দিয়ে পাঠানো,
   একটা approved, honest file write-এর *একই* invocation-এ। Mediator honest write-টা এমনভাবে
   commit করে যেন কিছুই না ঘটেছে, কারণ socket channel-টা কখনো এর observation surface-এর অংশই
   ছিল না। **এটা একটা genuine, honest scope boundary হিসেবে demonstrate করা হয়েছে, কোনো fix
   সহ bug হিসেবে রিপোর্ট করা হয়নি** — প্রজেক্ট explicitly বলে একটা filesystem-only mechanism-এর
   *মধ্যে* কোনো fix নেই; এটা বন্ধ করতে একদম আলাদা একটা layer দরকার (network namespace
   isolation, একটা egress allowlist), যেটা দরকারি future work হিসেবে নাম দেওয়া আছে, ইতিমধ্যে
   cover করা হয়েছে বলে claim করা হয়নি।
4. **Utility-degradation / fixed-timing-window tradeoff** — একটা সম্পূর্ণ honest write যেটা
   ধীরে সম্পূর্ণ হয় (0.2s, 0.6s, আর 2.0s delay-তে টেস্ট করা হয়েছে একটা 0.8-সেকেন্ড grace
   window-এর mediator-এর বিরুদ্ধে)। 2.0-সেকেন্ড honest write — যেটা শেষমেশ সফল হয় — ঠিক একটা
   malicious `background_write` attack-এর মতোই discard হয় যেটা ইচ্ছাকৃতভাবে window-এর পরে
   পড়ার জন্য timed করা। **একটা genuine structural tradeoff হিসেবে রিপোর্ট করা হয়েছে, bug না**:
   একটা fixed delay-তে mediator-এর একবারের read definition অনুযায়ীই "ধীরে কিন্তু honest" আর
   "malicious ও patient" আলাদা করতে পারে না। Window বড় করলে একটা failure mode অন্যটার সাথে
   trade হয়; কোনোটাই দূর হয় না। একটা real fix fixed timeout-এর বদলে একটা explicit completion
   signal বা process-tree freezing ব্যবহার করত — আবারও, future work হিসেবে নাম দেওয়া আছে,
   solved বলে claim করা হয়নি।

**এই milestone ব্যাখ্যা করার সময় যেটা জোর দিয়ে বলার মতো**: দুইটা attack real fix-এ নিয়ে গিয়েছিল, যে
exploit সেগুলো খুঁজে পেয়েছিল ঠিক সেটার বিরুদ্ধে re-verify করা হয়েছে। দুইটা attack একটা
filesystem-only, single-read mediator চিরকাল কী promise করতে পারে তার genuine, স্থায়ী
সীমানা প্রকাশ করেছে — আর প্রজেক্ট সেই সীমানাগুলো explicitly নাম দেওয়া বেছে নিয়েছে, না বলে সেগুলো
চাপা দেওয়া বা claim না জানিয়ে quietly সংকুচিত করার বদলে।

---

## Part 16 — Milestone M5: "Demanding baseline"-এর বিরুদ্ধে held-out evaluation

একটা mechanism তখনই impressive যখন একজন careful engineer আসলে deploy করত সেই বিকল্পের
তুলনায়। M5-এর পুরো উদ্দেশ্যই সেই তুলনা: এই প্রজেক্টের mechanism বনাম **কোনো defense না** বনাম
**static least-privilege** — plain Unix directory/file permission, কোনো software logic
ছাড়াই, যা প্রজেক্টের নিজের research plan "demanding baseline" নাম দিয়েছে ঠিক এই কারণে যে এটাই একজন
competent engineer, এই প্রজেক্টের research ছাড়া, সম্ভবত প্রথমে বানাতো।

**প্রথম server — `domdomegg/filesystem-mcp`।** Static least-privilege standard পদ্ধতিতে বানানো
হয়েছিল: staging directory root ownership-এ লক করা, কোনো write bit ছাড়াই, একমাত্র approved
target file আগে থেকে তৈরি করা ও untrusted identity-র মালিকানায় (তাই server *সেই নির্দিষ্ট existing
file-এ* লিখতে *পারে*, কারণ file permission — directory permission না — একটা process ইতিমধ্যে
open access আছে এমন file-এ write নিয়ন্ত্রণ করে)। Result: static least-privilege দুইটা
attack-এর **কোনোটাই** ধরতে পারেনি। Path diversion একটা *absolute* path টার্গেট করে
(`/tmp/exfil.dat`) locked directory-র সম্পূর্ণ বাইরে — একটা folder-এ সীমাবদ্ধ কোনো
directory-permission scheme কখনো সেই folder-এর ভেতরে না ঢোকা একটা escape ধরতে পারে না।
Content substitution সঠিক destination-এ ভুল content-এর bytes লেখে — কোনো permission system
*কী* লেখা হচ্ছে তা চেক করে না, শুধু *কে* *কোথায়* লিখতে পারবে। এই প্রজেক্টের mechanism দুইটাই ধরেছিল।

**দ্বিতীয় server — `notes-mcp`, নির্দিষ্টভাবে যোগ করা হয়েছিল টেস্ট করতে প্রথম result-টা general
ছিল নাকি একটা server-এর path handling-এর একটা artifact ছিল।** এই server (Part 14-তে আগে
পরিচয় করানো হয়েছে) diverted write-কে একই staging directory-র *ভেতরে* একটা relative sibling
file হিসেবে resolve করে, বাইরের একটা absolute escape না — একমাত্র condition যার অধীনে
directory permission plausibly গুরুত্বপূর্ণ হতে পারে। Result, assume না করে empirically verify
করা: static least-privilege-এর path-diversion attempt operating system নিজেই একটা real
`PermissionError` দিয়ে **প্রত্যাখ্যান করে**, কারণ missing directory write-bit server-কে সেখানে
*যেকোনো* নতুন entry তৈরি করা থেকে আটকায়, diverted sibling file সহ। Content substitution, তবে,
**অপরিবর্তিতভাবে commit হয়** — ঠিক প্রথম server-এর মতোই — কারণ এতে নতুন file তৈরি করা জড়িতই না;
এটা সঠিক, আগে থেকে থাকা, permitted target overwrite করে।

**এই refinement যা তৈরি করে — আর এই refinement-টাই প্রজেক্টের আরও সফিস্টিকেটেড result-গুলোর একটা,
examiner-কে সাবধানে ব্যাখ্যা করার মতো**: static least-privilege টেস্ট করা প্রতিটা server-এ content
substitution-এর কাছে **structurally blind** — এটা permission system কী express করতে পারে
সেটার একটা property, কোনো একটা server-এর property না। কিন্তু path diversion-এর বিরুদ্ধে এর
apparent সাফল্য defender নিয়ন্ত্রণ করে এমন কোনো property **না** — এটা এর উপর নির্ভর করে *target
tool নিজের path-resolution behavior* কীভাবে diversion-টাকে locked boundary-র ভেতরে রাখে নাকি
বাইরে পাঠিয়ে দেয়। Static permission deploy করা একজন defender-এর আগে থেকে জানার কোনো উপায় নেই
সে কোন case-এ আছে, কারণ সেটা এমন code-এর উপর নির্ভর করে যা সে নিয়ন্ত্রণ করে না। এই প্রজেক্টের
mechanism দুইটা server-এই দুইটা attack ধরেছিল, এমন কোনো নির্ভরতা ছাড়াই — কারণ এটা আসল resulting
*content* চেক করে, শুধু একটা write কোথায় পড়েছে সেটা না।

---

## Part 17 — এই প্রজেক্ট কী claim করছে না: পূর্ণ, honest limitations list

এই সেকশনটা আছে নির্দিষ্টভাবে যাতে কোনো examiner এই প্রজেক্টকে এমন কিছু overclaim করতে ধরতে না
পারে যা এটা নিজেই, অন্য কোথাও, plainly বলে দিয়েছে। এই list মুখস্থ করো — এটাই তোমার সবচেয়ে
শক্তিশালী defense, কারণ জিজ্ঞেস করার আগেই নিজের limitation স্বেচ্ছায় বলে দেওয়া কোনো limitation
জানো না ধরা পড়ার চেয়ে অনেক বেশি convincing।

1. **κ = 0.559, প্রজেক্টের নিজের 0.60 pre-registered gate-এর নিচে।** 69.7% A0 সংখ্যাটা Round-2
   labelling এই gate বন্ধ না করা পর্যন্ত একটা unvalidated instrument reading থেকে যায়। এটাই
   প্রজেক্টের সবচেয়ে পুরনো open blocker (milestone M0c)।
2. **M3 সাতটা server, দশটা না।** এখনও কোনো full generality claim support করা যায় না। Network
   domain সম্পূর্ণ untouched — যা কিছু টেস্ট করা হয়েছে সবই একটা filesystem বা সমতুল্য একটা local
   store-এ লেখে; কোনোটাই HTTP-effect tool, message queue, বা remote API call টেস্ট করে না।
3. **আগে থেকে ঘটে যাওয়া একটা external effect-এর কোনো real rollback নেই।** "Discard" মানে trusted,
   committed store diverted effect-কে কখনো authorized হিসেবে গণনা করে না — এর মানে underlying
   OS-level write, record creation, বা commit undo করা হয়েছে এমন না। এটাই একই limitation
   SAFEFLOW-এর নিজের paper generally বর্ণনা করে; এই প্রজেক্ট real code-এ সরাসরি, empirically
   এটা confirm করে, শুধু cite করে না।
4. **Unmediated channel সম্পূর্ণ অদৃশ্য।** filesystem-এর বাইরে কিছু যা mechanism watch করে না —
   একটা network socket, একটা environment variable, একটা ভিন্ন IPC channel — এর observation
   surface-এর সম্পূর্ণ বাইরে। সরাসরি demonstrate করা হয়েছে (Part 15, attack 3), শুধু একটা
   theoretical gap হিসেবে argue করা হয়নি।
5. **Fixed timing window একটা genuine, unresolved tradeoff, কোনো pending fix সহ bug না।**
   কোনো একটা timeout value একই সাথে প্রতিটা honestly ধীর write সহ্য করতে আর প্রতিটা patient,
   deliberately-timed malicious write ধরতে পারে না।
6. **UNDERSPECIFIED/SQL class content attack-এর জন্য প্রায় সম্পূর্ণ blind spot**, দুইটা
   independent implementation-এ replicate করা হয়েছে। এটা tool-এর নিজের schema কী expose
   করে তার একটা structural property, এই design-এর মধ্যে বেশি engineering effort দিয়ে fix করা
   যায় এমন কিছু না — একটা genuinely ভিন্ন mechanism (SQL semantics parse করা, বা একটা
   application-level adapter দরকার) লাগবে, আর সেটা একটা open question হিসেবে নাম দেওয়া আছে,
   solved না।
7. **Per-invocation isolation একটা কঠিন requirement, কোনো optimization না।** Call-গুলোর মধ্যে
   একটা staging area share করা সম্পূর্ণ honest কাজ ভুলভাবে discard করায়, M2-এর corner-case
   টেস্টিং-এ সরাসরি demonstrate করা হয়েছে।
8. **Corpus শুধু credential-free server।** API key বা credential দরকার এমন server — mail,
   payments, code-hosting platform, সবচেয়ে বেশি ঝুঁকিপূর্ণ category — construction অনুযায়ী এই
   প্রজেক্টের প্রতিটা empirical measurement থেকে বাদ। মাপা হওয়া harm-গুলোকে এই প্রজেক্ট টেস্ট
   করেনি এমন deployment-এ কী সম্ভব তার একটা lower bound হিসেবে পড়া উচিত।
9. **এই mechanism confidentiality নিয়ে কিছু বলে না।** এর পুরো claim হলো trusted, committed
   store-এ যা পৌঁছায় তার integrity নিয়ে — একটা untrusted process ইতিমধ্যে access করার অনুমতি
   আছে এমন channel দিয়ে কী পড়তে বা exfiltrate করতে পারে তা নিয়ে না।

---

## Part 18 — কঠিন প্রশ্ন, দ্বিধা ছাড়া উত্তর

এই সেকশনটাই আসলে জোরে জোরে rehearse করার মতো। প্রতিটা প্রশ্নের একটা ছোট, এক-শ্বাসের উত্তর আছে যা
তুমি সাথে সাথেই বলতে পারো, তারপর একটা লম্বা, data-backed version যদি প্রশ্নকর্তা আরও push করে।
নিচের কোনো উত্তরের জন্য কিছু বানানোর দরকার নেই — প্রতিটা সংখ্যা আর claim Part 1–17-এ ইতিমধ্যে
প্রতিষ্ঠিত।

---

**প্র: "এটা কি শুধু sandboxing না? এখানে আসলে নতুন কী আছে?"**

*ছোট উত্তর:* না — শুধু sandboxing (Part 16) আমরা টেস্ট করা কোনো attack-ই ধরতে পারেনি; novelty
হলো একটা contract-derived content diff, process isolation না।

*লম্বা উত্তর:* আমরা এই ঠিক objection-টাই সরাসরি, empirically টেস্ট করেছি M5-এ। Static
least-privilege — real Unix permission, কোনো software layer ছাড়া — আমরা চেষ্টা করা প্রতিটা
server-এ content substitution-এর কাছে structurally blind, কারণ permission system *কে* *কোথায়*
লিখছে তা চেক করে, কখনো *কী* লেখা হচ্ছে তা না। Sandboxing একা আসল কাজটা করা mechanism না; আমাদের
specification-ladder content diff-ই করে। আমরা একটা failable novelty gate (Part 8) চারটা
adjacent system-এর বিরুদ্ধেও চালিয়েছি — Alcatraz, TxOS, AgentBound/SAFEFLOW, ETDI — আর
দেখেছি প্রতিটা আমাদের claim করা পুরো combination-এর শুধু একটা অংশ ধরে রাখে: staging
(Alcatraz), সত্যিকারের rollback কিন্তু modified kernel দরকার (TxOS), সাধারণ confinement
কিন্তু real external-effect rollback ছাড়া (SAFEFLOW, Part 13-তে আমরা সরাসরি confirm করেছি),
বা declaration-only integrity (ETDI)। কোনোটাই এইগুলোর সব একসাথে combine করে না: unmodified
process, real external effect, বাইরে থেকে চেক করা, tool-এর নিজের declaration থেকে বের করা একটা
contract-এর বিরুদ্ধে।

---

**প্র: "তোমাদের নিজেদের κ তোমাদের নিজেদের threshold-এর নিচে — তাহলে এই প্রজেক্টের কোনো সংখ্যা কেন
বিশ্বাস করবো?"**

*ছোট উত্তর:* কারণ আমরাই সেই threshold-টা নিজেরা set করেছিলাম, টেস্ট চালানোর আগে, আর আমরা লুকানোর
বদলে তোমাকে বলছি এটা fail করেছে।

*লম্বা উত্তর:* Pre-registered 0.60 gate-টা নির্দিষ্টভাবে এই কারণেই আছে যাতে আমরা পরে একটা দুর্বল
agreement সংখ্যাকে rationalize করতে না পারি। আমরা 0.559 মেপেছি, root cause precisely diagnose
করেছি (91% disagreement একটা নির্দিষ্ট codebook ambiguity থেকে আসে, random noise না), আর
downstream 69.7% A0 সংখ্যাটাকে "একটা instrument reading, এখনো measurement না" বলে লেবেল
করেছি এটা যেখানেই আসে আমাদের documentation-এ, তুমি জিজ্ঞেস করার আগেই। এটা এমন একটা সংখ্যার
চেয়ে বেশি শক্তিশালী trust signal যেটা কোনো pre-commitment ছাড়াই একটা arbitrary bar clear করে
ফেলেছিল।

---

**প্র: "তোমরা মাত্র সাতটা server টেস্ট করেছো। বাকি হাজার হাজার MCP server-এও এটা generalize করে
কীভাবে জানো?"**

*ছোট উত্তর:* আমরা এখনও দাবি করি না যে করে — M3 explicitly "in progress," complete না —
কিন্তু pattern-টা ইতিমধ্যে independent code-এ দুইবার replicate করেছে, যা সাতটা অসম্পর্কিত
single data point-এর চেয়ে শক্তিশালী প্রমাণ।

*লম্বা উত্তর:* আমাদের নিজস্ব pre-registered target দশটা independent implementation; আমাদের
কাছে সাতটা আছে, আর আমরা সেটা সব জায়গায় বলি, শুধু জিজ্ঞেস করলে না। কিন্তু সেই সাতটার মধ্যে দুইটা
হলো একই finding-এর *ইচ্ছাকৃত replication* independent code-এ — UNDERSPECIFIED/SQL
content-blindness result দুইটা অসম্পর্কিত SQL server package-এ exactly reproduce হয়েছে —
যেটা সাতটা অসম্পর্কিত single finding-এর চেয়ে একটা structural property-র বেশি শক্তিশালী প্রমাণ।
আমরা ইচ্ছাকৃতভাবে variation খুঁজেছি, সহজ জয় না: দুইটা server নিজেদের destination defense
enforce করে দেখা গিয়েছে (যেখানে আমাদের mechanism-এর marginal contribution কম), আর একটা server
(`notes-mcp`)-এর genuinely ভিন্ন একটা attack surface আছে (two-argument content, relative-path
resolution) যেটা আমরা নির্দিষ্টভাবে খুঁজে বের করেছি, একই EXACT-class server সাতবার repeat করার
বদলে।

---

**প্র: "`/tmp/exfil.dat`-এ malicious write টা তো আসলেই disk-এ ঘটে গেছে। এটা কি তোমাদের defense-এর
একটা failure না?"**

*ছোট উত্তর:* আমরা এটাকে "detection, না prevention of an already-landed effect" বলি, আর
প্রতিবার এই result রিপোর্ট করার সময় এটাই বলি — এটা একটা সংকীর্ণ, বেশি honest claim, কোনো লুকানো
দুর্বলতা না।

*লম্বা উত্তর:* Theorem 1 আমাদের ইতিমধ্যে বলে দেয় একটা passive client real OS write authority
ধরে রাখা একটা untrusted process-কে একটা real write করা থেকে আটকাতে পারে না — সেটা এমন কিছু
না যা effect-এর *পরে* বসা একটা contract-checking layer undo করতে পারে। আমাদের mechanism
আসলে যা guarantee করে, আর আমরা সাবধানে precisely বলি, সেটা হলো diverted effect কখনো *trusted,
committed store*-এ পৌঁছায় না যার উপর বাকি সিস্টেম নির্ভর করে। underlying OS-level write-এর পুরো
prevention-এর জন্য একটা অতিরিক্ত layer দরকার হবে — একটা mount namespace বা chroot যা server
প্রথমে কী লিখতে পারে তা সীমিত করে — আর আমরা explicitly নাম দিই আমরা এটা যোগ করি না, চুপচাপ solved
হিসেবে claim করি না।

---

**প্র: "তোমাদের TOCTOU fix আসলেই কাজ করে সেটা তোমরা কীভাবে জানো, নাকি এটা শুধু race-টা এমন কোথাও
সরিয়ে দিয়েছে যা তোমরা এখনো খুঁজে পাওনি?"**

*ছোট উত্তর:* আমরা নির্দিষ্টভাবে সেই race attack করার জন্য একটা adversary বানিয়েছি, fix-এর আগে
একটা real 25% success rate মেপেছি, আর fix-এর পরে একই attack 20-এর মধ্যে 0 হিসেবে আবার চালিয়েছি।

*লম্বা উত্তর:* আমরা শুধু fix কাজ করে বলে দাবি করি না — যে exploit bug-টা প্রথমে খুঁজে পেয়েছিল ঠিক
সেটার বিরুদ্ধে আবার verify করি। fix-এর আগে, mediator commit-এ staging দ্বিতীয়বার, independently
read করতো — diff decision-এর জন্য ব্যবহৃত read থেকে আলাদা — যা একটা real window তৈরি করতো যা
একটা adaptive adversary 20-এর মধ্যে 5 বার জিততে পারতো। Fix-টা mediator-কে decision-এর জন্য
ব্যবহৃত একবারের read-এ ইতিমধ্যে capture করা একই bytes commit করায় ("M2 Commit Invariant"),
দ্বিতীয় read-টা দ্রুত বা ভালোভাবে synchronize করার চেষ্টা না করে সম্পূর্ণভাবে সরিয়ে দিয়ে। তারপর আমরা
একই 20-trial attack আবার চালিয়ে 0টা success মেপেছি। আমরা claim করতে পারি না সিস্টেমের অন্য কোথাও
কোনো race নেই — কোনো টিমই honestly সেটা claim করতে পারে না — কিন্তু আমরা evidence সহ দেখাতে
পারি এই নির্দিষ্ট, আগে real ছিল এমন vulnerability এখন বন্ধ।

---

**প্র: "Static least-privilege তো একটা strawman-এর মতো শোনাচ্ছে। একজন real engineer permission-কে
অন্য tool-এর সাথে combine করত।"**

*ছোট উত্তর:* আমরাও একমত — আর এটাই ঠিক M5-এর কারণ যে পরিমাপ করে permission একা কী cover করে আর
করে না, permission useless এমন কোনো claim না।

*লম্বা উত্তর:* M5-এর পুরো পয়েন্টই precision, demolition না। আমরা দেখাই permission structurally
blind content substitution-এর কাছে (permission system কী express করতে পারে তার একটা property,
এর সাথে অন্য কী combine করা হচ্ছে তা নির্বিশেষে সত্যি), আর path diversion-এর বিরুদ্ধে এর apparent
সাফল্য একটা tool-এর নিজের path-resolution behavior-এর উপর নির্ভর করে, defender নিয়ন্ত্রণ করে
এমন কোনো property না। এটা "permission খারাপ" এর চেয়ে বেশি useful ও honest একটা finding — এটা
একজন real engineer-কে ঠিক বলে দেয় একটা permission-based defense-এর কোথায় একটা দ্বিতীয় layer
দরকার, আর ঠিক কী সেই দ্বিতীয় layer চেক করতে হবে (content, শুধু destination না)।

---

**প্র: "Network-এর মাধ্যমে attack হলে কী হয়, filesystem না?"**

*ছোট উত্তর:* পুরোপুরি scope-এর বাইরে, আর আমরা নিজেরাই এই gap-টা demonstrate করেছি, অন্য কেউ
খুঁজে পাওয়ার অপেক্ষায় না থেকে।

*লম্বা উত্তর:* M4-এর তৃতীয় attack (Part 15) একটা plain local socket দিয়ে একই call-এ একটা secret
পাঠিয়েছিল একটা honest file write-এর সাথে, আর আমাদের mediator honest write-টা এমনভাবে commit
করেছিল যেন কিছুই না ঘটেছে — socket channel-টা কখনো এটা watch করে এমন কিছুর অংশই ছিল না। আমরা
plainly বলি একটা filesystem-only design-এর *মধ্যে* এর কোনো fix নেই; এটা বন্ধ করতে একদম আলাদা
একটা layer দরকার, যেমন network namespace isolation বা একটা egress allowlist, আর আমরা সেটাকে
দরকারি future work হিসেবে নাম দিই, এই প্রজেক্ট ইতিমধ্যে cover করে এমন কিছু হিসেবে না।

---

**প্র: "এটা কেন একটা research contribution, শুধু একটা implementation project না কেন?"**

*ছোট উত্তর:* কারণ এটা প্রথমে একটা impossibility result প্রমাণ করে, real scale-এ এটা ground করে,
এমন একটা gate pass করে যা এটাকে মেরে ফেলতে পারতো, আর তারপর একটা concrete mechanism-কে নিজের
বলা failure mode-এর বিরুদ্ধে adversarially self-test করে — এটাই একটা research contribution-এর
shape, শুধু build না।

*লম্বা উত্তর:* পাঁচটা আলাদা জিনিস প্রতিটাই সত্যি হতে হয়েছিল এটাকে engineering-এর বদলে research
হিসেবে গোনার জন্য: (1) Theorem 1 একটা প্রমাণিত claim, empirical observation না; (2) এটা এমন
একটা scale-এ (1,242 real server) ground করা, যেটা এই space-এ তুলনীয় বেশিরভাগ defense রিপোর্ট
করে না, measurement instrument নিজেকে documented self-audit সহ; (3) novelty claim একটা
*failable* gate পার করেছে যা প্রথমে তিনটা broader claim retire করেছে, assert করা হয়নি; (4)
mechanism-টা adversarially self-test করা হয়েছিল একটা টিম দিয়ে যারা নিজেদের code সম্পূর্ণ জেনে
attack বানিয়েছিল, শুধু happy path টেস্ট না করে দুইটা real defect খুঁজে পেয়ে ঠিক করেছিল; (5) এটা
independent, real, unmodified third-party code-এ বারবার validate করা হয়েছিল — দুইটা ইচ্ছাকৃত
replication সহ — শুধু mechanism-এর জন্য tune করা synthetic benchmark-এ না।

---

## Part 19 — Contribution, এক প্যারাগ্রাফে যেটা তোমার মুখস্থ বলতে পারা উচিত

*"MCP একজন ব্যবহারকারীর একবারের approval একটা tool-এর declaration-এর সাথে বাঁধে, কিন্তু প্রতিটা
আসল execution server-এর আসল implementation যা করে তার সাথে বাঁধে — আর আমরা প্রমাণ করেছি, শুধু
observe না, যে শুধু response দেখা একটা client কখনো এই gap বন্ধ করতে পারে না, তারপর এটা
empirically 1,242টা real server জুড়ে শূন্য শতাংশ true detection-এ confirm করেছি, আমাদের নিজেদের
measurement tool audit করে আর তাতে দুইটা real bug আগে ঠিক করে। কিছু claim করার আগে closest
prior work-এর বিরুদ্ধে সেই finding চেক করেছি, তিনটা broad claim retire করেছি, আর একটা সংকীর্ণ,
precisely bounded gap টিকে থাকতে দেখেছি: একটা unmodified process-এর real external effect-এর
staging-and-commit mediation, বাইরে থেকে চেক করা tool-এর নিজের declaration থেকে বের করা একটা
contract-এর বিরুদ্ধে। আমরা সেই mechanism বানিয়েছি, adversary দিয়ে নিজেরাই এটা ভেঙেছি যারা এর
নিজের code জানতো, আমরা যে দুইটা real bug পেয়েছি সেগুলো ঠিক করেছি, যে দুইটা genuine structural
limit ঠিক করতে পারিনি সেগুলো নাম দিয়েছি, আর তারপর সাতটা independent real third-party server-এ
এটা validate করেছি — আমাদের ধারালো negative finding-এর দুইটা ইচ্ছাকৃত replication সহ — আর
আমাদের নিজেদের research plan যাকে 'demanding one' বলে সেই নির্দিষ্ট baseline-এর বিরুদ্ধে, ঠিক
যেখানে permission-only defense structurally blind সেখানে এটাকে হারিয়ে, দুইটা server-এ, একটা
না।"*

---

## Part 20 — Glossary, দ্রুত reference-এর জন্য

- **MCP** — Model Context Protocol; যে protocol দিয়ে একটা AI agent একটা client-server
  architecture-এর মাধ্যমে external tool খুঁজে পায় ও কল করে।
- **Declaration** — একটা tool-এর নাম, description, ও input schema, approval-এর সময় একবার
  পরীক্ষা করা।
- **Effect** — একটা tool কল হলে world-এ আসলে কী করে (একটা file write, একটা database record,
  একটা committed change)।
- **Transcript** — একটা session জুড়ে একটা client যে request আর response-এর সম্পূর্ণ sequence
  observe করে; একটা passive, response-only client-এর যা access আছে।
- **TOCTOU** — Time-Of-Check to Time-Of-Use; এক ধরনের vulnerability যেখানে একটা security
  decision এক মুহূর্তে নেওয়া হয় কিন্তু পরে যখন conditions বদলে যেতে পারে সেই মুহূর্তে সেটার উপর
  নির্ভর করা হয়।
- **Contract (C)** — একটা নির্দিষ্ট approved call যে bound field-এর set (destination,
  structure, content) touch করতে পারে, tool-এর নিজের declared schema থেকে বের করা।
- **Ladder rung (L1/L2/L3)** — destination-only / plus-structure / plus-content, একটা
  contract যে তিনটা independent level-এ চেক করা যায়।
- **Staging** — একটা isolated, per-invocation workspace যার মালিক untrusted server-এর নিজের
  OS identity, যেখানে এর real effect চেক হওয়ার আগে ঘটে।
- **Mediator** — trusted, আলাদা-OS-identity process যেটা staging ঠিক একবার পড়ে আর commit না
  discard সিদ্ধান্ত নেয়।
- **AllowanceLedger** — component যেটা enforce করে একটা contract শুধু যতবার authorized ততবারই
  খরচ করা যায়, replay attack আটকায়।
- **M0–M6** — প্রজেক্টের নিজস্ব milestone structure: M0 (measurement/classifier validation),
  M1 (novelty gate), M2 (mechanism, single domain), M3 (real server জুড়ে generality), M4
  (adaptive adversary), M5 (held-out evaluation), M6 (write-up)।
- **A0–A3** — প্রজেক্টের নিজস্ব auditability taxonomy, একটা tool-এর real-world behavior বাইরে
  থেকে কতটা verifiable তার জন্য, A0 সবচেয়ে কম auditable।
- **κ (Cohen's kappa)** — independent human rater-দের মধ্যে agreement মাপার একটা standard
  statistic, এখানে A0–A3 classifier-কে real human judgment-এর বিরুদ্ধে validate করতে ব্যবহার
  করা হয়েছে।

---

## Part 21 — সামনে কী করবে, আর publish করার আসল পথ

এই অংশটা ইচ্ছাকৃতভাবে গল্প না, practical — "এখন কী করবো" প্রশ্নের উত্তর, বাস্তবে কী achievable
আর কোন ক্রমে সেটা নিয়ে honest থেকে, শুধু একটা wish list না।

### 21.1 — এখনই যা করতে হবে, priority অনুযায়ী

1. **Round-2 labelling শেষ করে M0c বন্ধ করো।** পুরো প্রজেক্টে এটাই সবচেয়ে বেশি leverage-এর কাজ।
   Material আগে থেকেই তৈরি আছে (একটা instruction sheet আর দুইটা annotator sheet)। এটা বন্ধ না
   হওয়া পর্যন্ত, 69.7% A0 সংখ্যাটা — পুরো opening argument-এর empirical backbone — একটা
   unvalidated instrument reading হয়েই থাকে। প্রজেক্টের বাকি কোনো কাজ এটার বদলি হতে পারে না;
   এর জন্য সত্যিকারের দুইজন independent মানুষের labelling-টা আসলে করা দরকার।
2. **M3 সাত থেকে দশটা real server-এ নিয়ে যাও।** report deadline-এর জন্য urgent না, কিন্তু এটা
   প্রজেক্টের নিজের pre-registered generality target সরাসরি বন্ধ করে। unverified registry
   entry-র চেয়ে well-known, actively maintained MCP server-কে priority দাও — 1,242-server
   scale run-এর জন্য ব্যবহৃত corpus-এর long tail-এ অনেক বেশি low-quality বা broken package আছে,
   তাই নতুন M3 candidate reputable source থেকে বাছাই করা (official `modelcontextprotocol`
   organization, well-known community package) অন্ধভাবে খোঁজার চেয়ে অনেক বেশি time-efficient।
3. **আসল manuscript-টা লেখো।** "results আছে" আর "একটা paper আছে" এর মধ্যে এটাই সবচেয়ে বড় বাকি
   থাকা gap। `docs/` folder চমৎকার raw material, কোনো paper না — এটাকে Abstract →
   Introduction → Related Work → Threat Model → Design → Evaluation → Limitations →
   Conclusion-এ কম্প্রেস করতে হবে, একটা paper আসলে যে register ব্যবহার করে সেটায়, `docs/`
   file-গুলোর exploratory research-log voice-এ না।
4. **Consolidated figure বানাও।** তিনটা roll-up table (M3, M4, M5-র প্রতিটার জন্য একটা) আর
   দুই-তিনটা real diagram (threat model / declaration-vs-implementation split, mediation
   pipeline) এখনও standalone artifact হিসেবে নেই — এগুলো per-milestone document জুড়ে ছড়িয়ে
   আছে আর paper-এর জন্য একবার, পরিষ্কারভাবে বানাতে হবে।
5. **Manuscript তৈরি হয়ে গেলে একটা final internal consistency pass** — paper-এ quote করা
   প্রতিটা সংখ্যা content freeze করার আগে তার source table বা notebook-এর বিরুদ্ধে আরেকবার চেক
   করো — প্রজেক্ট এখন পর্যন্ত যে discipline ব্যবহার করেছে ঠিক সেটাই।

### 21.2 — Optional, কম-priority extension (শুধু যদি সত্যিই সময় থাকে)

- একটা network-domain test (এখনও সম্পূর্ণ untouched — এখন পর্যন্ত টেস্ট করা সব কিছু একটা
  filesystem বা সমতুল্য local store-এ লেখে)।
- UNDERSPECIFIED/SQL blind spot-এর জন্য একটা concrete চেষ্টা — যেমন একটা prototype adapter যা
  SQL যথেষ্ট ভালোভাবে parse করে একটা content check বের করতে পারে, এমনকি শুধু statement-এর একটা
  সংকীর্ণ subset-এর জন্য হলেও। এটা সরাসরি সেই open question-এর উত্তর দিত যা প্রজেক্ট নিজেই `29`-এর
  "next step" সেকশনে তোলে।
- M2-এর জন্য genuine concurrency testing (দুইটা call সত্যিই সময়ে overlap করছে, sequential না) —
  `30`-এর নিজের milestone table-এ untested হিসেবে নাম দেওয়া আছে।

শুধু বেশি thorough দেখানোর জন্য এই list-এর বাইরে নতুন experiment category বানিও না — প্রজেক্টের
এখন পর্যন্ত credibility একটা সীমাবদ্ধ সংখ্যক জিনিস rigorously করা থেকে এসেছে, অনেক জিনিস shallow
ভাবে করা থেকে না।

### 21.3 — Publish করার আসল পথ

একটা capstone report শেষ করা আর একটা paper সত্যিকারের publish করা — এই দুইটা আলাদা প্রক্রিয়া,
আলাদা timeline-এ। এই পার্থক্যটা নিয়ে স্পষ্ট থাকো যাতে একটা goal-এর জন্য তাড়াহুড়া করে অন্যটার ক্ষতি
না হয়।

1. **Manuscript-টাই আসল bottleneck — সেটা তৈরি হওয়ার আগে publication নিয়ে কিছুই গুরুত্বপূর্ণ না।**
   কোনো venue, কোনো formatting choice, কোনো submission strategy নিয়ে ভাবা useful না যতক্ষণ না
   21.1-এর 3 নম্বর item আসলে করা হয়েছে।
2. **কোথাও submit করার আগে citation quarantine বন্ধ করো।** প্রজেক্টের নিজস্ব standing rule বলে
   `paper/references.bib`-এর প্রতিটা entry এখনও `[U]` unverified হিসেবে মার্ক করা। একটা submit
   করা paper unverified citation বহন করতে পারে না — bibliography final ধরার আগে প্রতিটার primary
   source আসলে খুলে confirm করতে হবে।
3. **শুরুতেই একটা manuscript format ঠিক করো**, ভালো হয় supervisor-এর input নিয়ে — একটা standard
   two-column conference template (IEEE বা ACM `sigconf` style এই ধরনের systems/security-flavored
   paper-এর জন্য common default) কোনো নির্দিষ্ট venue-এর নিজস্ব requirement না থাকলে নিরাপদ default
   choice।
4. **দুইটা parallel, একে অপরকে বাদ না দেওয়া publishing path বিবেচনা করো, মোটামুটি এই ক্রমে:**
   - **একটা arXiv preprint** manuscript solid হলে: দ্রুত, peer-reviewed না, কিন্তু একটা public
     timestamp establish করে আর কাজটা সাথে সাথেই cite করতে দেয়। প্রথম ধাপ হিসেবে low risk, high
     value, আর পরে venue submission-কে বাধা দেয় না (বেশিরভাগ venue explicitly arXiv preprint
     allow করে)।
   - **একটা peer-reviewed venue।** এই stage-এর একটা প্রজেক্টের জন্য — real empirical result সহ
     একটা শক্তিশালী undergraduate capstone কিন্তু এখনও পুরোপুরি matured, দশ-plus-server dataset
     না — realistic target-এর মধ্যে আছে একটা national বা regional CS conference (Bangladesh-based
     student work সাধারণত ICCIT-র মতো venue টার্গেট করে), agent/tool-integrity কাজের জন্য
     উপযুক্ত একটা security-focused workshop, অথবা university-র নিজস্ব research symposium বা
     journal থাকলে সেটা। **সঠিক target venue আর তার বর্তমান call-for-papers deadline সরাসরি
     supervisor-এর সাথে confirm করো** — একটা আন্দাজ করা date-এর উপর নির্ভর করো না, কারণ CFP
     deadline বছর বছর বদলায় আর এখানে একটা আন্দাজ করলে ভুল date-এর চারপাশে পরিকল্পনা করার ঝুঁকি
     থাকে।
5. **বাছাই করা venue-এর requirement অনুযায়ী precisely format ও trim করো** (page limit,
   double-blind review দরকার হলে anonymization, exact template) শুধুমাত্র একটা venue আসলে বাছাই
   হওয়ার পরে — একটা generic draft থেকে একটা নির্দিষ্ট venue-এর template-এ reformat করা normal ও
   expected, নষ্ট হওয়া কাজ না।
6. **কোনো external submission-এর আগে explicit supervisor sign-off নাও।** Mr. Azizur Rahman
   Anik-এর নাম ও supervisor হিসেবে জড়িত থাকা authorship আর submission approval-এর জন্য paper-টা
   প্রজেক্টের নিজের repository থেকে বের হওয়ার আগেই confirm করা উচিত।
7. **Submission-এর পরে, reviewer feedback-কে ঠিক সেভাবেই treat করো যেভাবে এই প্রজেক্ট এখন
   পর্যন্ত নিজের limitation treat করেছে** — honestly action নেওয়ার মতো data হিসেবে, argue করে
   এড়িয়ে যাওয়ার মতো কিছু না। নিজের দুর্বল পয়েন্ট নাম দেওয়ার ক্ষেত্রে এতটা disciplined একটা প্রজেক্ট
   peer review-কে defensively না, constructively handle করার জন্য অস্বাভাবিকভাবে ভালোভাবে
   অবস্থানে আছে।

---

*স্ক্রিপ্ট শেষ। এই ডকুমেন্টটা প্রজেক্ট বোঝা ও defend করার জন্য source material — এটা final পেপার
না, আর এটাকে সেভাবে ভুল বোঝা উচিত না। Paper manuscript-টা (Abstract → Introduction → Related
Work → Design → Evaluation → Limitations → Conclusion) এখনও প্রজেক্টের `docs/` folder থেকে
আলাদাভাবে লেখা দরকার, যেখান থেকে এই script-টা তার content নিয়েছে।*

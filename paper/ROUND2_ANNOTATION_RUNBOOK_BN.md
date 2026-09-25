# Round-2 Human Annotation Runbook (Bangla)

এই runbook-টি `data/processed/labels_annotator_A.tsv` এবং
`labels_annotator_B.tsv`-এর 265টি frozen row-এর জন্য। এই কাজটি automation,
LLM, বা একজন মানুষের label copy করে শেষ করা যাবে না। Paper-এ human agreement
claim করার জন্য দুইজনের judgment সত্যিই independent হতে হবে।

দুইজনকে আলাদা, hash-manifested package বানাতে repository root থেকে চালান:

```bash
python scripts/build_annotator_packages.py
```

এরপর `artifact/annotator-packages/round2-annotator-A.zip` শুধু A-কে এবং
`round2-annotator-B.zip` শুধু B-কে দিন। কোনো package-এ অন্য annotator-এর sheet
থাকে না।

## 1. কারা annotation করবেন

- Annotator A এবং Annotator B আলাদা দুইজন মানুষ।
- দুজনই শুরু করার আগে `docs/14-labeling-codebook.md` সম্পূর্ণ পড়বেন।
- Label শেষ হওয়ার আগে তারা row, interpretation, বা tentative answer নিয়ে
  একে অন্যের সঙ্গে আলোচনা করবেন না।
- একই ব্যক্তি দুইটি file পূরণ করবেন না; এক file থেকে অন্য file-এ label copy
  করা যাবে না।
- সম্পর্ক ও compensation থাকলে paper-এর Ethics appendix-এ aggregate আকারে
  disclosure দিতে হবে।

## 2. File safety

1. কাজ শুরুর blank-sheet, sample, split, corpus archive, এবং codebook hash
   `artifact/round2-annotation-freeze.json`-এ ইতিমধ্যে সংরক্ষিত। কাজ শুরুর
   আগে fileগুলো ওই freeze-এর সঙ্গে মিলছে কি না যাচাই করুন।
2. Annotator A শুধু `labels_annotator_A.tsv` edit করবেন।
3. Annotator B শুধু `labels_annotator_B.tsv` edit করবেন।
4. প্রথম পাঁচটি given column (`server_id`, `tool`, `description`,
   `input_fields`, `siblings`) পরিবর্তন করা যাবে না।
5. শুধু `label`, `check`, `hint_conflict` পূরণ করতে হবে।

Allowed values:

| Column | Allowed value |
|---|---|
| `label` | `A0`, `A1`, `A2`, অথবা `A3` |
| `check` | concrete check; A0 হলে `-` বা সংক্ষিপ্ত কারণ |
| `hint_conflict` | conflict থাকলে `y`; না থাকলে `n` |

Excel ব্যবহার করলে TSV হিসেবেই save করতে হবে। Comma-separated CSV বা `.xlsx`
করলে scorer input নষ্ট হবে।

## 3. প্রতি row-তে decision

প্রথমে tool state mutate করে কি না ঠিক করুন। তারপর codebook-এর ordered
decision procedure অনুসরণ করুন এবং প্রথম applicable class নিন। A2 দেওয়ার
আগে sibling-এর নিজের description-এ read-back relation আছে কি না দেখুন। শুধু
sibling name plausible শোনালে A2 নয়। Evidence অপর্যাপ্ত হলে guess না করে A0
দিন এবং `check`-এ কারণ লিখুন।

প্রতি 25 row শেষে annotator নিজে তিনটি quality check করবেন:

- কোনো label blank কি না;
- A2/A3 row-তে concrete sibling/check লেখা আছে কি না;
- given columns accidental edit হয়েছে কি না।

## 4. Independence freeze

দুজন শেষ করলে file দুইটি read-only copy হিসেবে freeze করুন এবং SHA-256
সংরক্ষণ করুন। এই hash নেওয়ার আগে disagreement দেখা বা edit করা যাবে না। Raw
agreement অবশ্যই pre-adjudication files থেকে বের হবে।

## 5. Scoring

Repository root থেকে চালান:

```bash
python experiments/score_labels.py \
  --a data/processed/labels_annotator_A.tsv \
  --b data/processed/labels_annotator_B.tsv
```

Output-এ অন্তত রাখতে হবে:

- shared row count (লক্ষ্য 265);
- raw agreement;
- Cohen's kappa;
- agreed-row gold-standard size;
- tune বনাম held-out classifier precision/recall;
- A0 bias; এবং
- server count/cluster warning।

Kappa 0.60-এর নিচে হলে ফল লুকানো বা disagreement edit করে threshold পার করা
যাবে না। Codebook ambiguity document করে revise করতে হবে, তারপর নতুন round
আলাদা version/hash-এ চালাতে হবে। 0.60--0.69 হলে paper-এ limitation হিসেবে
বলতে হবে; 0.70 বা বেশি হলে substantial-agreement target পূরণ হয়েছে বলা যাবে।

## 6. Adjudication

Agreement score freeze হওয়ার পরেই disagreement list খুলুন। প্রতিটি disputed
row-এর জন্য:

1. A এবং B তাদের original rationale লিখবেন;
2. codebook-এর exact rule cite করবেন;
3. consensus হলে adjudicated label আলাদা file-এ লিখবেন;
4. consensus না হলে third adjudicator বা explicit UNKNOWN policy ব্যবহার
   করবেন; এবং
5. original A/B files কখনও overwrite করবেন না।

Paper-এ pre-adjudication kappa এবং final adjudicated dataset দুইটিই আলাদা করে
report করতে হবে।

## 7. Done criteria

Round 2 তখনই complete যখন:

- দুইটি file-তেই 265/265 valid labels এবং nonblank rationale আছে;
- frozen pre-adjudication hashes সংরক্ষিত;
- scorer complete report দিয়েছে;
- disagreement/adjudication log সংরক্ষিত;
- claim matrix এবং manuscript-এ actual result বসানো হয়েছে; এবং
- result খারাপ হলেও একইভাবে report করা হয়েছে।

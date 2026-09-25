# GitHub Actions Linux Evidence Runbook

এই runbook-এর উদ্দেশ্য: ছোট presentation laptop-এ Docker install না করেও
clean Ubuntu/Docker evidence run করা। Workflow file:
`.github/workflows/release-evidence.yml`।

## Safety properties

- Workflow শুধু manual `workflow_dispatch`; push/PR-তে নিজে থেকে চলে না।
- Job permission `contents: read`; repository লিখতে বা release publish করতে
  পারে না।
- Checkout-এর credential step শেষ হলে retained থাকে না।
- কোনো repository secret workflow-এ reference করা হয়নি।
- Third-party MCP server disposable Docker container-এ non-root execution path
  ব্যবহার করে; runtime network `none`, read-only root filesystem, memory/CPU/PID
  bounds এবং dropped capabilities থাকে।
- Package download কেবল image build-এর সময় exact version/integrity check-সহ
  হয়। Runtime-এ floating `latest` resolve হয় না।
- Result repository-তে নিজে commit হয় না; SHA-256 manifest-সহ Actions artifact
  হিসেবে download করতে হয়।

## First run: integrated real server

1. Current work commit এবং push করুন।
2. GitHub repository খুলে **Actions** → **MCPGate release evidence** →
   **Run workflow** যান।
3. `integrated-real-server` নির্বাচন করুন।
4. Run complete হলে `mcpgate-integrated-real-server-<commit>` artifact download
   করুন।
5. Artifact-এর `git-commit.txt`, `git-status.txt`, `docker-version.txt`,
   `uname.txt`, `m2_real_server.json`, এবং `MANIFEST.sha256` সংরক্ষণ করুন।
6. `m2_real_server.json`-এ honest row COMMITTED এবং path/content attack rows
   trusted store-এ refused কি না verify করুন। External `/tmp` observationকে
   trusted-store success হিসেবে relabel করবেন না।

এই run C8-এর integrated pinned-server evidence দিতে পারে। এটি 10-server
held-out gate বা human annotation gate বন্ধ করে না।

## Final run: full release

`full-release` mode কেবল তখনই চালাবেন যখন:

- Annotator A/B-এর 265টি করে valid row complete;
- pre-adjudication hash frozen;
- held-out manifest `FROZEN` এবং 10+ eligible independent server আছে;
- Linux transitive requirements file exact hash-locked;
- manuscript-এর evidence numbers frozen; এবং
- pushed Git tree clean।

Full runner incomplete conditionে fail করে—এটাই intended। Failure bypass করে
partial outputকে submission evidence বলা যাবে না।

## Current access blocker

Local `gh` client-এর saved GitHub token invalid। তাই এই machine থেকে workflow
dispatch/push করা এখন সম্ভব নয়। GitHub website দিয়ে login করে run করা যাবে, বা
`gh auth login -h github.com` দিয়ে নতুন authorization দিতে হবে। Authentication
হওয়ার আগে automated remote run হয়েছে বলা যাবে না।


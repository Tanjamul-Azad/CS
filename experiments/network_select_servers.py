"""Select network MCP servers from the registry by the frozen rule (RQ-N).

Rule: paper/NETWORK_PREREG_V2.md, "Server selection rule", amendment 2026-10-09.
Candidates are local npm/PyPI stdio servers in the 2026-10-08 registry harvest
that declare a secret (API key) environment variable and carry an open-source
license. Order: seeded shuffle (seed 20261008). Each candidate is installed in
a container and run behind the broker (record mode, generic recording mock, no
internet); it qualifies if one write-like tool, called with schema-derived
arguments, returns without error and sends at least one write request
(POST/PUT/PATCH) to exactly one host. The first 6 qualifiers form the
development set, the next 6 the held-out set. Every decision is logged.

    python experiments/network_select_servers.py [--max-candidates 200]
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import random
import re
import shutil
import sys
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

import network_postmark_pilot as P  # noqa: E402
from mcpmut.live import LiveSession  # noqa: E402

RAW = ROOT / "data" / "raw" / "registry_latest_2026-10-08.jsonl.gz"
SEED = 20261008
STAMP = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
OUT = ROOT / "artifact" / "results" / f"network_selection_{STAMP}"
WANTED = 12
SCREEN_TIMEOUT = 120
OPEN_LICENSES = ("MIT", "APACHE", "BSD", "ISC", "MPL", "GPL", "LGPL", "AGPL", "UNLICENSE",
                 "0BSD", "CC0", "ARTISTIC", "EPL", "ZLIB", "PYTHON SOFTWARE")
WRITE_VERBS = re.compile(r"(create|send|post|add|update|write|set|insert|publish|upload|"
                         r"comment|reply|submit|schedule|book|save|store|edit|append|log|"
                         r"remember|notify|message|invite|assign|label|tag|star|track)",
                         re.I)
EXCLUDE = ("postmark",)


# -- candidates ---------------------------------------------------------------

def candidates() -> list[dict]:
    out = []
    with gzip.open(RAW, "rt", encoding="utf-8") as fh:
        for line in fh:
            item = json.loads(line)
            server = item.get("server", {})
            meta = item.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {})
            if meta.get("status", "active") != "active" or not meta.get("isLatest", True):
                continue
            for pkg in server.get("packages") or []:
                if pkg.get("registryType") not in ("npm", "pypi"):
                    continue
                if (pkg.get("transport") or {}).get("type") != "stdio":
                    continue
                env = pkg.get("environmentVariables") or []
                if not any(e.get("isSecret") for e in env):
                    continue
                if any(x in (pkg.get("identifier") or "").lower() for x in EXCLUDE):
                    continue
                out.append({"name": server.get("name"), "registry": pkg["registryType"],
                            "identifier": pkg.get("identifier"), "version": pkg.get("version"),
                            "env": env, "arguments": pkg.get("packageArguments") or [],
                            "runtime_args": pkg.get("runtimeArguments") or []})
                break
    unique = {c["name"]: c for c in out}
    ordered = sorted(unique.values(), key=lambda c: c["name"])
    random.Random(SEED).shuffle(ordered)
    return ordered


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "effectseal-selection/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def license_of(c: dict) -> str:
    try:
        if c["registry"] == "npm":
            data = fetch_json(f"https://registry.npmjs.org/{c['identifier']}/{c['version']}")
            lic = data.get("license") or ""
            return lic if isinstance(lic, str) else json.dumps(lic)
        data = fetch_json(f"https://pypi.org/pypi/{c['identifier']}/{c['version']}/json")["info"]
        classifiers = " ".join(x for x in data.get("classifiers") or [] if "License" in x)
        return (data.get("license_expression") or data.get("license") or "")[:200] + " " + classifiers
    except Exception as error:  # noqa: BLE001
        return f"ERROR {error}"


def open_source(lic: str) -> bool:
    upper = lic.upper()
    return any(token in upper for token in OPEN_LICENSES)


# -- image --------------------------------------------------------------------

def build_image(c: dict, work: Path) -> str:
    ctx = work / f"ctx-{uuid.uuid4().hex[:8]}"
    ctx.mkdir(parents=True)
    ident, version = c["identifier"], c["version"]
    if c["registry"] == "npm":
        resolve = (
            "const p=require('/app/node_modules/" + ident + "/package.json');"
            "let b=p.bin;if(b&&typeof b==='object')b=Object.values(b)[0];"
            "if(!b)b=p.main||'index.js';"
            "require('fs').writeFileSync('/entry','#!/bin/sh\\nexec node /app/node_modules/"
            + ident + "/'+b+' \"$@\"\\n');")
        steps = (f"RUN mkdir /app && cd /app && npm init -y >/dev/null && "
                 f"npm install --omit=dev {ident}@{version} && node -e \"{resolve}\" && chmod 755 /entry\n")
    else:
        steps = (f"ENV UV_TOOL_DIR=/opt/tools UV_TOOL_BIN_DIR=/opt/bin\n"
                 f"RUN uv tool install '{ident}=={version}' && "
                 f"B=$(ls /opt/bin | grep -x '{ident}' || ls /opt/bin | head -1) && "
                 "printf '#!/bin/sh\\nexec /opt/bin/%s \"$@\"\\n' \"$B\" > /entry && chmod 755 /entry "
                 "&& chmod -R a+rX /opt/tools /opt/bin\n")
    (ctx / "Dockerfile").write_text(
        "FROM effectseal-netbase:1\n" + steps + "USER node\nENTRYPOINT [\"/entry\"]\n", encoding="utf-8")
    slug = re.sub(r'[^a-z0-9]+', '-', ident.lower()).strip('-')[:60]
    ver = re.sub(r'[^a-z0-9.]+', '-', version.lower()).strip('-.')
    tag = f"effectseal-net:{slug}-{ver}"  # a tag must not start with '-' or '.'
    P.sh("docker", "build", "-q", "-t", tag, str(ctx), timeout=900)
    shutil.rmtree(ctx, ignore_errors=True)
    return tag


def server_env(c: dict) -> dict:
    env = {}
    for e in c["env"]:
        name = e.get("name")
        if not name:
            continue
        if e.get("isSecret"):
            env[name] = "DUMMYKEY" + __import__("hashlib").sha256(name.encode()).hexdigest()[:12]
        elif e.get("isRequired"):
            if re.search(r"URL|HOST|ENDPOINT|BASE", name, re.I):
                env[name] = "https://api.vendor-mock.test"
            elif e.get("default"):
                env[name] = str(e["default"])
            else:
                env[name] = "mock-value"
    return env


class GenericBroker(P.Broker):
    def command_for(self, image: str, env: dict) -> str:
        base = {"HTTPS_PROXY": "http://127.0.0.1:8080", "HTTP_PROXY": "http://127.0.0.1:8080",
                "https_proxy": "http://127.0.0.1:8080", "http_proxy": "http://127.0.0.1:8080",
                "NODE_USE_ENV_PROXY": "1", "NODE_EXTRA_CA_CERTS": "/ca/ca.pem",
                "SSL_CERT_FILE": "/ca/ca.pem", "REQUESTS_CA_BUNDLE": "/ca/ca.pem",
                "HOME": "/tmp", "NO_UPDATE_NOTIFIER": "1", "npm_config_update_notifier": "false"}
        base.update(env)
        parts = ["docker", "run", "-i", "--rm", "--name", self.new_server_name(),
                 "--network", f"container:{self.name}",
                 "--read-only", "--tmpfs", "/tmp:rw,size=256m", "--cap-drop", "ALL",
                 "--security-opt", "no-new-privileges", "--memory", "768m", "--pids-limit", "256",
                 "-v", f"{self.ca / 'ca.pem'}:/ca/ca.pem:ro"]
        for key, value in base.items():
            parts += ["-e", f"{key}={value}"]
        return " ".join(parts + [image])


# -- arguments from a JSON schema ----------------------------------------------

TODAY = dt.date.today().isoformat()


def value_for(name: str, schema: dict, depth: int = 0):
    if depth > 3:
        return None
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    for key in ("anyOf", "oneOf"):
        if key in schema:
            options = [s for s in schema[key] if s.get("type") != "null"]
            if options:
                return value_for(name, options[0], depth + 1)
    kind = schema.get("type")
    if isinstance(kind, list):
        kind = next((k for k in kind if k != "null"), "string")
    n = name.lower()
    if kind == "integer":
        return max(1, int(schema.get("minimum", 1)))
    if kind == "number":
        return max(1.0, float(schema.get("minimum", 1)))
    if kind == "boolean":
        return False
    if kind == "array":
        item = value_for(name.rstrip("s"), schema.get("items") or {"type": "string"}, depth + 1)
        return [] if item is None else [item]
    if kind == "object":
        return args_for(schema, depth + 1)
    fmt = schema.get("format", "")
    if fmt == "email" or "email" in n:
        return "alice@example.org"
    if fmt in ("uri", "url") or n.endswith("url") or "link" in n:
        return "https://example.org/report"
    if fmt == "date" or n.endswith("date"):
        return TODAY
    if fmt == "date-time" or "time" in n:
        return f"{TODAY}T10:00:00Z"
    if n.endswith("id") or n.endswith("_id") or n.endswith("ids"):
        return "12345"
    if any(k in n for k in ("title", "name", "subject", "summary", "label")):
        return "Quarterly totals"
    if any(k in n for k in ("body", "content", "text", "message", "description", "note", "comment",
                            "query", "prompt")):
        return "Hello team, the Q3 totals are below."
    if any(k in n for k in ("phone", "number")):
        return "+15550100"
    pattern = schema.get("pattern")
    if pattern and re.fullmatch(pattern, "example"):
        return "example"
    return "example value"


def args_for(schema: dict, depth: int = 0) -> dict:
    props = schema.get("properties") or {}
    required = schema.get("required") or []
    out = {}
    for name in required:
        value = value_for(name, props.get(name, {}), depth)
        if value is not None:
            out[name] = value
    return out


def write_tools(tools: list[dict]) -> list[dict]:
    picked = []
    for tool in tools:
        ann = tool.get("annotations") or {}
        if ann.get("readOnlyHint") is True or ann.get("destructiveHint") is True:
            continue
        if re.search(r"delete|remove|destroy|drop|purge|cancel", tool["name"], re.I):
            continue
        if WRITE_VERBS.search(tool["name"]):
            picked.append(tool)
    return picked[:3]


# -- screening -----------------------------------------------------------------

def screen(broker: GenericBroker, c: dict, image: str) -> dict:
    env = server_env(c)
    record: dict = {"tools_tried": []}
    call_id = uuid.uuid4().hex[:10]
    broker.write_state({"mode": "record", "call_id": f"{call_id}/startup"})
    # A hung tool call must not stall selection: after the deadline the
    # watchdog removes the server container, the session fails, and the
    # candidate is recorded as not qualified.
    import threading
    name = None
    timer = threading.Timer(SCREEN_TIMEOUT, lambda: P.sh("docker", "rm", "-f", name, check=False)
                            if name else None)
    try:
        command = broker.command_for(image, env)
        name = broker.last_server
        timer.start()
        return _screen_session(broker, command, record, call_id)
    except Exception as error:  # noqa: BLE001
        record.update(qualified=False, reason=f"session failed or timed out "
                                              f"({SCREEN_TIMEOUT}s): {type(error).__name__}")
        return record
    finally:
        timer.cancel()
        broker.remove_server()


def _screen_session(broker, command, record, call_id) -> dict:
    with LiveSession(command) as session:
        tools = session.list_tools()
        record["tool_count"] = len(tools)
        for tool in write_tools(tools):
            args = args_for(tool.get("inputSchema") or {})
            sub = f"{call_id}/{tool['name']}"
            broker.write_state({"mode": "record", "call_id": sub})
            time.sleep(0.2)
            try:
                response = session.call(tool["name"], args)
                error = session.last_was_error
            except Exception as exc:  # noqa: BLE001
                response, error = f"{type(exc).__name__}: {exc}", True
            time.sleep(0.4)
            sent = [r for r in broker.lines("records.jsonl") if r["call_id"] == sub]
            writes = [r for r in sent if r["method"] in ("POST", "PUT", "PATCH")]
            hosts = sorted({urlsplit(r["url"]).hostname for r in sent})
            attempt = {"tool": tool["name"], "args": args, "error": error,
                       "response": str(response)[:300], "requests": len(sent),
                       "writes": len(writes), "hosts": hosts}
            record["tools_tried"].append(attempt)
            if not error and writes and len({urlsplit(r["url"]).hostname for r in writes}) == 1:
                record.update(qualified=True, tool=tool["name"], args=args, env_names=sorted(env),
                              input_schema=tool.get("inputSchema"))
                return record
    record["qualified"] = False
    record["reason"] = ("no write-like tool" if not record["tools_tried"]
                        else "no error-free call with writes to one host")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-candidates", type=int, default=200)
    parser.add_argument("--resume", help="existing selection directory to continue")
    a = parser.parse_args()
    out = Path(a.resume) if a.resume else OUT
    out.mkdir(parents=True, exist_ok=bool(a.resume))
    done = {}
    if a.resume and (out / "screening.jsonl").exists():
        for line in (out / "screening.jsonl").read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            done[entry["rank"]] = entry
    cands = candidates()
    (out / "candidates.json").write_text(json.dumps(
        {"seed": SEED, "raw": str(RAW.relative_to(ROOT)), "count": len(cands),
         "order": [c["name"] for c in cands]}, indent=1), encoding="utf-8")
    print(f"{len(cands)} candidates", flush=True)
    log = (out / "screening.jsonl").open("a", encoding="utf-8")
    qualified: list[dict] = [e for _, e in sorted(done.items()) if e.get("qualified")]
    work = Path(tempfile.mkdtemp(prefix="es-sel-"))
    with GenericBroker(work) as broker:
        for index, c in enumerate(cands[:a.max_candidates]):
            if index in done:
                continue
            entry = {"rank": index, "name": c["name"], "registry": c["registry"],
                     "identifier": c["identifier"], "version": c["version"]}
            if any(arg.get("isRequired") for arg in c["arguments"]):
                entry.update(qualified=False, reason="requires package arguments")
            else:
                entry["license"] = license_of(c)
                if not open_source(entry["license"]):
                    entry.update(qualified=False, reason="license not open source or unknown")
                else:
                    try:
                        image = build_image(c, work)
                        entry["image"] = image
                        entry.update(screen(broker, c, image))
                    except Exception as error:  # noqa: BLE001
                        entry.update(qualified=False, reason=f"install or launch failed: "
                                                             f"{type(error).__name__}: {str(error)[:300]}")
                    if not entry.get("qualified") and entry.get("image"):
                        P.sh("docker", "rmi", "-f", entry["image"], check=False)
            log.write(json.dumps(entry) + "\n")
            log.flush()
            print(f"[{index}] {c['name']}: {'QUALIFIED' if entry.get('qualified') else entry.get('reason')}",
                  flush=True)
            if entry.get("qualified"):
                qualified.append(entry)
                if len(qualified) == WANTED:
                    break
    sets = {"development": [q["name"] for q in qualified[:6]],
            "held_out": [q["name"] for q in qualified[6:12]],
            "screened": index + 1, "finished": dt.datetime.now(dt.timezone.utc).isoformat()}
    (out / "sets.json").write_text(json.dumps(sets, indent=2), encoding="utf-8")
    print(json.dumps(sets, indent=2))


if __name__ == "__main__":
    main()

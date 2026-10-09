#!/bin/sh
# Clean-clone reproduction on a fresh Linux machine or container.
#
# Run from the root of a fresh clone. Installs the hash-locked dependencies,
# then reruns the offline parts of the artifact and writes one log per step,
# plus a summary, to $OUT (default ./reproduction-out). No Docker, network
# service, or API key is needed after the install.
#
#   docker run --rm -v "$PWD:/src-repo:ro" -v "$PWD/out:/out" python:3.12-slim sh -c \
#     'apt-get update -qq && apt-get install -y -qq git >/dev/null &&
#      git config --global --add safe.directory "*" &&
#      git clone -q /src-repo /work && cd /work && OUT=/out sh scripts/reproduce_clean_linux.sh'
set -u
OUT=${OUT:-./reproduction-out}
mkdir -p "$OUT"
git log -1 --format='%H %s' > "$OUT/commit.txt"
python --version > "$OUT/python.txt" 2>&1
uname -a >> "$OUT/python.txt"

echo "installing hash-locked dependencies"
if [ "${SKIP_INSTALL:-0}" != "1" ]; then
python -m pip install -q --no-cache-dir --timeout 120 --retries 10 --require-hashes \
  -r artifact/requirements-full-linux.txt > "$OUT/pip-install.log" 2>&1 \
  || { echo "FAIL pip-install"; exit 1; }
fi
python -m pip freeze > "$OUT/pip-freeze.txt"

: > "$OUT/summary.txt"
failures=0
run() {
  name=$1; shift
  if "$@" > "$OUT/$name.log" 2>&1; then
    echo "PASS $name" | tee -a "$OUT/summary.txt"
  else
    echo "FAIL $name (exit $?)" | tee -a "$OUT/summary.txt"
    failures=$((failures + 1))
  fi
}

run tests             python -m pytest -q
run tla_local_model   python formal/check_model.py
run tla_network_model python formal/check_net_model.py
run theorem1_demo     python experiments/demo_theorem1.py
run mediator_ablation python experiments/run_mediator_ablations.py
run concurrency_100   python experiments/run_concurrency_100.py
run network_overhead  python experiments/measure_network_overhead.py --iters 500 --trials 100
run integrated_proxy  python experiments/measure_integrated_network.py --iters 300 --trials 100
run current_evidence  python scripts/verify_current_evidence.py
run file_baselines    python experiments/make_file_baselines.py
run figures_paper     python scripts/make_strengthening_figures.py
run figures_network   python scripts/make_network_figures.py
echo "done; see $OUT/summary.txt"
[ "$failures" -eq 0 ] || exit 1

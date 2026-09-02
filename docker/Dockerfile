# Sandbox for auditing real, unvetted third-party MCP servers.
#
# Carries both Node (for npx-published servers) and Python/uv (for
# py-published/py-module servers) plus our own defense code, so one image
# launches any of the 32 runnable-standalone servers from the triage.
#
# This image alone is not the isolation boundary -- `docker run` flags in
# experiments/run_scale.py (--cap-drop=ALL, --pids-limit, --memory, no
# host mounts beyond a scratch dir, non-root user) are what make running
# an unvetted package here safer than running it on the host directly.
# See docs/20 Phase 1 for why a container was required before this ran.

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

# Non-root: an unvetted package should not run as root even inside a
# throwaway container.
RUN useradd -m -u 10001 sandbox
WORKDIR /app

COPY requirements-runner.txt .
RUN pip install --no-cache-dir -r requirements-runner.txt

COPY src/ /app/src/
COPY docker/run_one.py /app/run_one.py

RUN mkdir -p /sandbox /out && chown -R sandbox:sandbox /app /sandbox /out
USER sandbox
ENV HOME=/sandbox
ENV PYTHONPATH=/app/src

ENTRYPOINT ["python3", "/app/run_one.py"]

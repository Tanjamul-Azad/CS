FROM effectseal-postmark:honest-f50d93080494
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates && rm -rf /var/lib/apt/lists/* && python3 -m venv /opt/scan && /opt/scan/bin/pip install --no-cache-dir 'mcp-scan==0.3.39'
COPY index_v*.js /app/
COPY config_*.json /cfg/
ENV PATH=/opt/scan/bin:$PATH
ENTRYPOINT []

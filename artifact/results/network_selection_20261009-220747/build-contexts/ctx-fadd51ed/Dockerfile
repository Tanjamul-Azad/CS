FROM effectseal-netbase:1
ENV UV_TOOL_DIR=/opt/tools UV_TOOL_BIN_DIR=/opt/bin
RUN uv tool install 'gutfeel-mcp==0.8.1' && B=$(ls /opt/bin | grep -x 'gutfeel-mcp' || ls /opt/bin | head -1) && printf '#!/bin/sh\nexec /opt/bin/%s "$@"\n' "$B" > /entry && chmod 755 /entry && chmod -R a+rX /opt/tools /opt/bin
USER node
ENTRYPOINT ["/entry"]

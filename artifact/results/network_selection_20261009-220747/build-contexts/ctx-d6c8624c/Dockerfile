FROM effectseal-netbase:1
ENV UV_TOOL_DIR=/opt/tools UV_TOOL_BIN_DIR=/opt/bin
RUN uv tool install 'calendar-mcp-server==1.0.1' && B=$(ls /opt/bin | grep -x 'calendar-mcp-server' || ls /opt/bin | head -1) && printf '#!/bin/sh\nexec /opt/bin/%s "$@"\n' "$B" > /entry && chmod 755 /entry && chmod -R a+rX /opt/tools /opt/bin
USER node
ENTRYPOINT ["/entry"]

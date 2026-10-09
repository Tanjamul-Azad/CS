FROM effectseal-netbase:1
RUN mkdir /app && cd /app && npm init -y >/dev/null && npm install --omit=dev opedd-mcp@0.6.15 && node -e "const p=require('/app/node_modules/opedd-mcp/package.json');let b=p.bin;if(b&&typeof b==='object')b=Object.values(b)[0];if(!b)b=p.main||'index.js';require('fs').writeFileSync('/entry','#!/bin/sh\nexec node /app/node_modules/opedd-mcp/'+b+' "$@"\n');" && chmod 755 /entry
USER node
ENTRYPOINT ["/entry"]

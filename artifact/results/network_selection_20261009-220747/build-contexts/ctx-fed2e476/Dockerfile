FROM effectseal-netbase:1
RUN mkdir /app && cd /app && npm init -y >/dev/null && npm install --omit=dev @codespar/mcp-conekta@0.2.2 && node -e "const p=require('/app/node_modules/@codespar/mcp-conekta/package.json');let b=p.bin;if(b&&typeof b==='object')b=Object.values(b)[0];if(!b)b=p.main||'index.js';require('fs').writeFileSync('/entry','#!/bin/sh\nexec node /app/node_modules/@codespar/mcp-conekta/'+b+' "$@"\n');" && chmod 755 /entry
USER node
ENTRYPOINT ["/entry"]

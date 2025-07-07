#!/bin/sh

# Sostituisce $BACKEND_URL nel file env.js
envsubst < /usr/share/nginx/html/env.js > /usr/share/nginx/html/env.runtime.js

# Sovrascrivi il vecchio file
mv /usr/share/nginx/html/env.runtime.js /usr/share/nginx/html/env.js

# Avvia nginx
exec nginx -g "daemon off;"
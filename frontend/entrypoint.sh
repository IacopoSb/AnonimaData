# WARNING: Check under Windows that this file has been saved with LF line endings.

#!/bin/sh
set -e
if [ -n "$BACKEND_URL" ]; then
  sed -i "s|API_BASE_URL_PLACEHOLDER|$BACKEND_URL|g" /usr/share/nginx/html/env.js
fi
exec "$@"
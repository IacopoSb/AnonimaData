

FROM nginx:alpine

# Copia i file dell'app
COPY dist/ /usr/share/nginx/html/

# Copia il template JS
COPY public/env.template.js /usr/share/nginx/html/env.js

# Aggiungi uno script per sostituire variabili ENV a runtime
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80

CMD ["/entrypoint.sh"]

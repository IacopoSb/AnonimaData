FROM nginx:alpine

COPY dist/ /usr/share/nginx/html/
COPY public/env.template.js /usr/share/nginx/html/env.js

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 8080

CMD ["/entrypoint.sh"]
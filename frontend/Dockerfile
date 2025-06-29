FROM nginx:alpine

# Copia il file HTML statico nella cartella servita da nginx
COPY index.html /usr/share/nginx/html/index.html

# Configurazione nginx opzionale: puoi aggiungere una tua nginx.conf se vuoi SPA routing
# COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

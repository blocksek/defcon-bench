# 2bird2can client — official handout WebGL client + the bot patch exposing
# window.unityInstance (client-side convenience for programmatic join; disclosed).
FROM nginx:alpine@sha256:feb6f75a08aa55b44576f98c15b8859819ecf54f3e4d2157f42c2d01cb58a3d2
COPY challenges/2bird2can/handout/2bird2can/client-docker/webgl-build /usr/share/nginx/html
COPY challenges/2bird2can/client_index.html /usr/share/nginx/html/index.html
COPY challenges/2bird2can/handout/2bird2can/client-docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY challenges/2bird2can/handout/2bird2can/client-docker/entrypoint.sh /docker-entrypoint.d/35-entrypoint.sh
RUN chmod +x /docker-entrypoint.d/35-entrypoint.sh

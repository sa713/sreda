FROM node:24-alpine AS metrics
WORKDIR /app
COPY metrics.mjs ./
COPY data/catalog.json ./data/
RUN mkdir /data && chown node:node /data
ENV SREDA_DB=/data/metrics.sqlite3
USER node
CMD ["node", "metrics.mjs"]

FROM pandoc/minimal:3.11-alpine AS build
RUN apk add --no-cache python3
WORKDIR /src
COPY build.py ./
COPY data/ data/
COPY content/ content/
COPY static/ static/
RUN python3 build.py

FROM nginx:stable-alpine AS site
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist/ /srv/sreda/

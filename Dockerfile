FROM node:24.15.0-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/api/package.json apps/api/package.json
COPY apps/web/package.json apps/web/package.json
RUN npm ci
COPY apps/web/index.html apps/web/vite.config.js apps/web/
COPY apps/web/src apps/web/src
RUN npm run build

FROM node:24.15.0-bookworm-slim AS dependencies
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/api/package.json apps/api/package.json
COPY apps/web/package.json apps/web/package.json
RUN npm ci --omit=dev && npm cache clean --force

FROM node:24.15.0-bookworm-slim AS runtime
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3001 DATABASE_PATH=/data/todos.sqlite
WORKDIR /app
COPY --from=dependencies /app/ ./
COPY apps/api/src apps/api/src
COPY database/migrations database/migrations
COPY --from=build /app/apps/web/dist apps/web/dist
RUN mkdir /data && chown node:node /data
USER node
EXPOSE 3001
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 CMD node -e "fetch('http://127.0.0.1:3001/api/todos').then(r=>{if(!r.ok)throw Error(r.status);return r.json()}).then(v=>{if(!Array.isArray(v))throw Error('Invalid response')}).catch(()=>process.exit(1))"
CMD ["node", "apps/api/src/server.js", "--serve-web"]

# Node gateway — build context = REPO ROOT (not this dir), because server.js
# serves the widget from ../../widget/. Deploy from the repo root:
#   fly deploy --config backend/gateway-node/fly.toml --dockerfile backend/gateway-node/Dockerfile .
FROM node:20-slim

# Mirror the repo layout inside the image so __dirname/../../widget resolves.
WORKDIR /app/backend/gateway-node

# Install prod deps first for layer caching.
COPY backend/gateway-node/package.json backend/gateway-node/package-lock.json ./
RUN npm ci --omit=dev

# Gateway source, then the widget it serves at /widget.js
COPY backend/gateway-node/ ./
COPY widget/ /app/widget/

ENV PORT=8080
EXPOSE 8080
CMD ["node", "server.js"]

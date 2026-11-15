FROM dhi.io/node:22-alpine3.24-dev AS dependencies

WORKDIR /tmp/build
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --cache /tmp/npm-cache

FROM dhi.io/node:22-alpine3.24

WORKDIR /app
ENV HOST=0.0.0.0 \
    PORT=8787
COPY --from=dependencies --chown=65532:65532 /tmp/build/node_modules ./node_modules
COPY --chown=65532:65532 package.json ./package.json
COPY --chown=65532:65532 src ./src

EXPOSE 8787
CMD ["node", "--experimental-strip-types", "src/local/server.ts"]

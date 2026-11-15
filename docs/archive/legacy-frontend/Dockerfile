FROM dhi.io/bun:1.4.4-debian13-dev AS dependencies
WORKDIR /tmp/app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

FROM dhi.io/bun:1.4.4-debian13-dev AS builder
WORKDIR /tmp/app
ARG NEXT_PUBLIC_API_URL=/api
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=dependencies /tmp/app/node_modules ./node_modules
COPY . .
RUN bun run build

FROM dhi.io/bun:1.4.4-debian13 AS runtime
WORKDIR /app/frontend
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=builder --chown=65532:65532 /tmp/app ./
EXPOSE 3000
CMD ["bun", "run", "start", "--hostname", "0.0.0.0", "--port", "3000"]

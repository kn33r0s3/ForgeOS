FROM oven/bun:1.3.11-slim AS dependencies
WORKDIR /app/frontend
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

FROM oven/bun:1.3.11-slim AS builder
WORKDIR /app/frontend
ARG NEXT_PUBLIC_API_URL=/api
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=dependencies /app/frontend/node_modules ./node_modules
COPY . .
RUN bun run build

FROM oven/bun:1.3.11-slim AS runtime
WORKDIR /app/frontend
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/frontend ./
EXPOSE 3000
CMD ["bun", "run", "start", "--hostname", "0.0.0.0", "--port", "3000"]

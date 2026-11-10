# Build stage
FROM node:22-alpine AS builder

WORKDIR /app

# Enable pnpm via corepack
RUN corepack enable && corepack prepare pnpm@latest --activate

# Copy root workspace configs and web app manifests
COPY pnpm-workspace.yaml .npmrc ./
COPY apps/web/package.json ./apps/web/

RUN pnpm install --filter @changescope/web

COPY apps/web ./apps/web

RUN pnpm --filter @changescope/web build

# Runtime stage
FROM nginx:alpine

COPY --from=builder /app/apps/web/dist /usr/share/nginx/html
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

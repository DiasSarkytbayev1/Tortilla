# Dev image. Production build path is deferred — see TODOS.md::prod-frontend-build.
FROM node:22-alpine

# pnpm via corepack — bundled with node 22, no extra install.
RUN corepack enable && corepack prepare pnpm@10.33.0 --activate

WORKDIR /app

# Copy manifest first so the dep layer caches.
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

EXPOSE 5173
CMD ["pnpm", "run", "dev"]

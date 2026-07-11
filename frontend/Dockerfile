FROM node:20-slim AS build

WORKDIR /app

ARG NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:5001
ENV NEXT_PUBLIC_BACKEND_URL=${NEXT_PUBLIC_BACKEND_URL}

COPY frontend/package*.json ./frontend/

WORKDIR /app/frontend

RUN npm ci

COPY frontend/ ./

RUN npm run build

FROM node:20-slim AS runtime

WORKDIR /app/frontend

ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000

ARG NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:5001
ENV NEXT_PUBLIC_BACKEND_URL=${NEXT_PUBLIC_BACKEND_URL}

COPY --from=build /app/frontend/package*.json ./
COPY --from=build /app/frontend/node_modules ./node_modules
COPY --from=build /app/frontend/.next ./.next
COPY --from=build /app/frontend/next.config.mjs ./next.config.mjs
COPY --from=build /app/frontend/jsconfig.json ./jsconfig.json

RUN mkdir -p public

EXPOSE 3000

CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
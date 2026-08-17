# 2bird2can reference runner — chromium + puppeteer-core driving the real WebGL client.
FROM node:20-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      chromium fonts-liberation ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ENV CHROME_BIN=/usr/bin/chromium PUPPETEER_SKIP_DOWNLOAD=1
WORKDIR /solver
RUN npm init -y >/dev/null 2>&1 && npm install --no-fund --no-audit puppeteer-core@23 >/dev/null 2>&1
COPY solvers/2bird2can/bot/ /solver/
ENTRYPOINT ["node", "solver.js"]

FROM mcr.microsoft.com/playwright:v1.64.1-noble

ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
WORKDIR /opt/argus-repro
COPY package.json sample.mjs probe-net.mjs probe-app.mjs entrypoint.sh ./
RUN npm install --omit=dev \
    && sed -i 's/\r$//' entrypoint.sh \
    && chmod +x entrypoint.sh

# Run this image on an internal Docker network: the app is reachable, the internet is not.
ENTRYPOINT ["/opt/argus-repro/entrypoint.sh"]

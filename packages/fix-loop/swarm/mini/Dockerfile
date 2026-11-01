# Sandbox for variant E (mini-swe-agent). Same base as docker/Dockerfile plus bash, which mini's ["bash", "-lc"] interpreter needs.
# The only network use is this build step (apk add); runs use --network none.
FROM alpine@sha256:294b683cb724975bec92580e1e685676bd4b50bda910ddb8c51d4cabeaec77e6
RUN apk add --no-cache bash
WORKDIR /work

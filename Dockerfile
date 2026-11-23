FROM python:3.15.2-slim-bookworm@sha256:96599df822d0e1c6bb700014a05c7f3c8cabc6e0f7ff3c4f9f69cee033b4b5d9 AS build

WORKDIR /src
COPY . /src
RUN pip install --no-cache-dir --prefix=/install ".[service]"

FROM python:3.15.2-slim-bookworm@sha256:96599df822d0e1c6bb700014a05c7f3c8cabc6e0f7ff3c4f9f69cee033b4b5d9

RUN apt-get update \
    && apt-get install -y --no-install-recommends firejail \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 agentshield

COPY --from=build /install /usr/local

USER agentshield
WORKDIR /home/agentshield

ENTRYPOINT ["agentshield"]
CMD ["--version"]

FROM python:3.12-slim-bookworm AS build

WORKDIR /src
COPY . /src
RUN pip install --no-cache-dir --prefix=/install ".[service]"

FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends firejail \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 agentshield

COPY --from=build /install /usr/local

USER agentshield
WORKDIR /home/agentshield

ENTRYPOINT ["agentshield"]
CMD ["--version"]

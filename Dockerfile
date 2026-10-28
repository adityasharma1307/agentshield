FROM python:3.12.16-slim-bookworm@sha256:62ed8e07e544e8555c5d93748d5275015136b7f5c52b5e8679b4de339c3779d3 AS build

WORKDIR /src
COPY . /src
RUN pip install --no-cache-dir --prefix=/install ".[service]"

FROM python:3.12.16-slim-bookworm@sha256:62ed8e07e544e8555c5d93748d5275015136b7f5c52b5e8679b4de339c3779d3

RUN apt-get update \
    && apt-get install -y --no-install-recommends firejail \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 agentshield

COPY --from=build /install /usr/local

USER agentshield
WORKDIR /home/agentshield

ENTRYPOINT ["agentshield"]
CMD ["--version"]

FROM python:3.15.0-slim-bookworm@sha256:0e019bbdfb5d9874cb2389f1c2884b64aa2ac97c99960b5bc521cef978c0617d AS build

WORKDIR /src
COPY . /src
RUN pip install --no-cache-dir --prefix=/install ".[service]"

FROM python:3.15.0-slim-bookworm@sha256:0e019bbdfb5d9874cb2389f1c2884b64aa2ac97c99960b5bc521cef978c0617d

RUN apt-get update \
    && apt-get install -y --no-install-recommends firejail \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 agentshield

COPY --from=build /install /usr/local

USER agentshield
WORKDIR /home/agentshield

ENTRYPOINT ["agentshield"]
CMD ["--version"]

FROM ubuntu:24.04
USER root

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV UV_PYTHON_DOWNLOADS=automatic

RUN apt-get update -y
RUN apt install python3 openssh-client curl git -y

COPY --from=ghcr.io/astral-sh/uv:0.8.14 /uv /uvx /bin/

RUN uv venv /venv
ENV PATH="/venv/bin:$PATH"
ENV VIRTUAL_ENV="/venv"

# # create pip and pip3 command wrappers in /bin
RUN echo '#!/bin/sh\nuv pip "$@"' > /bin/pip && \
    echo '#!/bin/sh\nuv pip "$@"' > /bin/pip3 && \
    chmod +x /bin/pip /bin/pip3

ADD dockerfiles/processor/requirements.txt /miranda/processor_requirements.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install -r /miranda/processor_requirements.txt

RUN mkdir /miranda/dist
ADD dist/mirmod-*.whl /miranda/dist
RUN uv pip install /miranda/dist/*.whl

ARG CACHEBUST=1
ARG LOGZOD_ARCH=x86_64
RUN curl -L https://github.com/mainly-ai/logzod/releases/latest/download/logzod-linux-${LOGZOD_ARCH} -o /usr/local/bin/logzod
RUN chmod +x /usr/local/bin/logzod

# # Create a non-root user
# RUN useradd -m -u 1000 processor
# RUN chown -R processor:processor /app
# USER processor

ENTRYPOINT ["/usr/local/bin/logzod", "/venv/bin/python3", "-m", "mirmod.processor"]
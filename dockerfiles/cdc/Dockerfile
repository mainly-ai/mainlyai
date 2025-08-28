FROM python:3.12-slim-trixie
USER root

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN uv venv /venv
ENV PATH="/venv/bin:$PATH"

ENV PYTHONUNBUFFERED=1

RUN mkdir -p /miranda/dist
ADD dist/cdc-*.whl /miranda/dist
ADD dist/mirmod-*.whl /miranda/dist
RUN uv pip install /miranda/dist/*.whl

ENTRYPOINT ["uv", "run", "-m", "cdc"]
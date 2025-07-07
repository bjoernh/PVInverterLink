FROM python:3.12.11-alpine@sha256:c610e4a94a0e8b888b4b225bfc0e6b59dee607b1e61fb63ff3926083ff617216

RUN apk add --update --no-cache --virtual .tmp-build-deps \
    gcc libc-dev linux-headers \
    && apk add libffi-dev

# Setup pipx to be accessible by all users
ENV PIPX_HOME=/app/.local/pipx \
    PIPX_BIN_DIR=/app/.local/bin \
    PATH=/app/.local/bin:$PATH

RUN python3 -m pip install pipx && \
    pipx install poetry

WORKDIR /app/

RUN poetry config virtualenvs.in-project true

COPY pyproject.toml poetry.lock /app/

RUN poetry install

ENV VENV_PATH="/app/.venv"
ENV PATH="$VENV_PATH/bin:${PATH}"

ENV PYTHONPATH /app/
EXPOSE 80

WORKDIR /app/solar_backend/

CMD ["uvicorn", "app:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "80"]

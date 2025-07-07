FROM python:3.13.5-alpine@sha256:9b4929a72599b6c6389ece4ecbf415fd1355129f22bb92bb137eea098f05e975

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

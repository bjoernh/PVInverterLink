FROM python:3.11.11-alpine@sha256:bc84eb94541f34a0e98535b130ea556ae85f6a431fdb3095762772eeb260ffc3
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apk add --update --no-cache --virtual .tmp-build-deps \
    gcc libc-dev linux-headers \
    && apk add libffi-dev

# Setup pipx to be accessible by all users
ENV PIPX_HOME=/app/.local/pipx \
    PIPX_BIN_DIR=/app/.local/bin \
    PATH=/app/.local/bin:$PATH

RUN python3 -m pip install pipx && \
    pipx install poetry==1.8.3

WORKDIR /app/

RUN poetry config virtualenvs.in-project true

COPY pyproject.toml poetry.lock /app/

RUN poetry install --without dev

ENV VENV_PATH="/app/.venv"
ENV PATH="$VENV_PATH/bin:${PATH}"

ENV PYTHONPATH /app/
EXPOSE 80

COPY ./solar_backend/ /app/solar_backend/
COPY ./alembic/ /app/alembic/
COPY ./alembic.ini /app/

WORKDIR /app/solar_backend/

CMD ["uvicorn", "app:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "80"]


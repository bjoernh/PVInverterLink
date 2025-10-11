FROM python:3.13-alpine
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apk add --update --no-cache --virtual .tmp-build-deps \
    gcc libc-dev linux-headers \
    && apk add libffi-dev

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app/

# Copy dependency files
COPY pyproject.toml uv.lock /app/
COPY README.md /app/

# Install dependencies
RUN uv sync --frozen --no-dev

# Set up PATH to use uv-managed environment
ENV PATH="/app/.venv/bin:${PATH}"

ENV PYTHONPATH /app/
EXPOSE 80

COPY ./solar_backend/ /app/solar_backend/
COPY ./alembic/ /app/alembic/
COPY ./alembic.ini /app/

WORKDIR /app/solar_backend/

CMD ["uvicorn", "app:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "80"]


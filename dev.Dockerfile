FROM python:3.13-alpine

RUN apk add --update --no-cache --virtual .tmp-build-deps \
    gcc libc-dev linux-headers \
    && apk add libffi-dev

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app/

# Copy dependency files
COPY pyproject.toml uv.lock /app/

# Install dependencies including dev dependencies
RUN uv sync --frozen

# Set up PATH to use uv-managed environment
ENV PATH="/app/.venv/bin:${PATH}"

ENV PYTHONPATH /app/
EXPOSE 80

WORKDIR /app/solar_backend/

CMD ["uvicorn", "app:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "80"]

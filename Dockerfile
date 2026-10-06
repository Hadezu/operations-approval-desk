FROM python:3.14-slim
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.23
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev
COPY manage.py ./
COPY config ./config
COPY desk ./desk
COPY scripts ./scripts
RUN useradd --create-home desk && chown -R desk:desk /app
USER desk
ENV BIND_HOST=0.0.0.0
EXPOSE 8187
CMD ["sh", "-c", "uv run --no-dev manage.py migrate --noinput && uv run --no-dev manage.py cleanup_demo && uv run --no-dev manage.py collectstatic --noinput && uv run --no-dev python -m scripts.serve"]

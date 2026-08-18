FROM python:3.13-slim

WORKDIR /srv

COPY pyproject.toml ./
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./

RUN pip install --no-cache-dir .

ENV PYTHONPATH=/srv/src

EXPOSE 8000

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

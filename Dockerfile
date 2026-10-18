FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LIBMYSQL_ENABLE_CLEARTEXT_PLUGIN=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential default-libmysqlclient-dev pkg-config ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY manage.py .
COPY hairdresser_django/ hairdresser_django/
COPY appointments/ appointments/

EXPOSE 8080

ENTRYPOINT ["python3"]
CMD ["manage.py", "runserver", "0.0.0.0:8080", "--noreload"]

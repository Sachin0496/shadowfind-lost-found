FROM python:3.12-slim

WORKDIR /srv/shadowfind

# OpenCV needs a couple of shared libraries even in the headless build
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt gunicorn

COPY app/ app/
RUN mkdir -p instance/uploads

WORKDIR /srv/shadowfind/app
ENV PORT=8000
EXPOSE 8000
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60"]

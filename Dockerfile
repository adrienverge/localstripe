FROM python:3

COPY . /app
WORKDIR /app
RUN pip install . && \
  rm -rf ./* && \
  chmod -R 0777 /tmp && \
  chown -R www-data:www-data /app

USER www-data

EXPOSE 8420

# Apparently the suggested number of workers is (2*CPU)+1. Our current CPU is 3 to 12, so at least 7
CMD ["gunicorn", "--workers", "7", "--bind", "0.0.0.0:8420", "--worker-class", "aiohttp.GunicornWebWorker", "localstripe.server:app"]

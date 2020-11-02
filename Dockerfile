FROM python:3

COPY . /app
WORKDIR /app
RUN pip install . && \
  rm -rf ./* && \
  chmod -R 0777 /tmp && \
  chown -R www-data:www-data /app

USER www-data

EXPOSE 8420

# "Gunicorn relies on the operating system to provide all of the load balancing when handling requests.
# Generally we recommend (2 x $num_cores) + 1 as the number of workers to start off with.
# While not overly scientific, the formula is based on the assumption that for a given core, ...
# ... one worker will be reading or writing from the socket while the other worker is processing a request."
# https://docs.gunicorn.org/en/latest/design.html#how-many-workers
CMD ["gunicorn", "--workers", "12", "--bind", "0.0.0.0:8420", "--worker-class", "aiohttp.GunicornWebWorker", "localstripe.server:app"]

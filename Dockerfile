FROM python:3.10-bullseye

COPY . /app
WORKDIR /app

RUN pip install . && \
  rm -rf ./* && \
  chmod -R 0777 /tmp
COPY localstripe/gunicorn.conf.py /app
RUN chown -R www-data:www-data /app

USER www-data

ENV DD_TRACE_ENABLED="true"
ENV DD_PROFILING_ENABLED="true"
ENV DD_PROFILING_HEAP_ENABLED="true"
ENV GUNICORN_WORKERS="1"

EXPOSE 8420

# "Gunicorn relies on the operating system to provide all of the load balancing when handling requests.
# Generally we recommend (2 x $num_cores) + 1 as the number of workers to start off with.
# While not overly scientific, the formula is based on the assumption that for a given core, ...
# ... one worker will be reading or writing from the socket while the other worker is processing a request."
# https://docs.gunicorn.org/en/latest/design.html#how-many-workers
CMD ["ddtrace-run", "gunicorn", "-c", "/app/gunicorn.conf.py", "--worker-class", "aiohttp.GunicornWebWorker", "localstripe.server:app", "--access-logfile", "-", "--error-logfile", "-", "--log-file", "-"]

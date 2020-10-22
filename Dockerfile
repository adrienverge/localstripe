FROM python:3

COPY . /app
WORKDIR /app
RUN pip install . && \
  rm -rf ./* && \
  chmod -R 0777 /tmp && \
  chown -R www-data:www-data /app

USER www-data

EXPOSE 8420

CMD ["gunicorn --workers 4 localstripe.server:app"]
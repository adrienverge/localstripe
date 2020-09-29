FROM python:3

COPY . /app
WORKDIR /app
RUN pip install . && \
  rm -rf ./*

USER www-data

EXPOSE 8420

CMD ["localstripe"]
FROM python:3.8-slim

RUN mkdir /app
WORKDIR /app

COPY setup.py .
COPY setup.cfg .
COPY localstripe/ ./localstripe/

RUN pip install -e .

EXPOSE 8420

CMD ["localstripe"]

FROM python:3-alpine
RUN mkdir /app
COPY localstripe /app/localstripe
COPY requirements.txt /app/requirements.txt
COPY LICENSE /app/LICENSE
COPY README.rst /app/README.rst
WORKDIR /app
RUN pip install -r requirements.txt
EXPOSE 8420
CMD ["python", "-m", "localstripe"]
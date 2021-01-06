FROM python:3

COPY . /app
WORKDIR /app

RUN python3 ./setup.py sdist

RUN pip3 install --upgrade dist/localstripe-*.tar.gz

CMD ["localstripe"]

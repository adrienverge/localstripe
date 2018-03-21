FROM python:alpine

ADD . /src

WORKDIR /src

RUN python setup.py install

EXPOSE 8420

ENTRYPOINT ["localstripe"]
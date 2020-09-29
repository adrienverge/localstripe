FROM python:3

RUN pip install localstripe

EXPOSE 8420

CMD ["localstripe"]
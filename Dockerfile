FROM python:3
COPY setup.py setup.cfg ./
ADD localstripe ./localstripe
RUN python3 setup.py sdist
RUN pip3 install --upgrade dist/localstripe-*.tar.gz
CMD ["localstripe"]

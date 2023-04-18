FROM python:3.10.11-bullseye

# Install dependancies
RUN pip install aiohttp>=2.3.2 python-dateutil>=2.6.1

# Install localstripe directly
COPY setup.cfg setup.py /tmp/
COPY localstripe /tmp/localstripe
RUN cd /tmp && PYTHONPATH=. python setup.py install

# Make stdout logging work better
ENV PYTHONUNBUFFERED 1

CMD ["localstripe"]

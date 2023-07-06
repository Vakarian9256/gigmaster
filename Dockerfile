FROM python:3.8-slim

RUN pip3 install -U pip && pip3 install -U wheel && pip3 install -U setuptools
COPY ./requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt && rm -r /tmp/requirements.txt
COPY . /code
WORKDIR /code
CMD ["bash"]

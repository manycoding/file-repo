FROM debian:9

RUN echo 'deb http://mirror.yandex.ru/debian jessie main contrib non-free >> /etc/apt/sources.list' && \
    apt-get update && \
    apt-get install -y imagemagick python3 python3-pip libffi-dev && \
    apt-get clean

RUN pip3 install --upgrade pip setuptools tornado wand bcrypt

ADD /src /pdf-repo

VOLUME /pdf-repo/storage/
EXPOSE 8888
WORKDIR /pdf-repo/
ENTRYPOINT python3 server.py

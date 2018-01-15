FROM debian:9

RUN echo 'deb http://mirror.yandex.ru/debian jessie main contrib non-free >> /etc/apt/sources.list' && \ 
    apt-get update && \
    apt-get install -y imagemagick python3 python3-pip git libffi-dev && \
    apt-get clean

RUN pip3 install --upgrade pip setuptools tornado PyPDF2 wand bcrypt

RUN git clone https://github.com/manycoding/pdf-repo

VOLUME /pdf-repo/media/
EXPOSE 8888
WORKDIR /pdf-repo/
ENTRYPOINT python3 server.py

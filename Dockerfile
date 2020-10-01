FROM alpine:3.10

MAINTAINER Karim Boumedhel <karimboumedhel@gmail.com>

LABEL name="karmab/autolabeller" \
      maintainer="karimboumedhel@gmail.com" \
      vendor="Karmalabs" \
      version="latest" \
      release="0" \
      summary="Node labeller based on rules" \
      description="Node labeller based on rules stored in a config map"

RUN apk add python3
RUN pip3 install kubernetes
ADD controller.py /

CMD [ "python3", "/controller.py" ]
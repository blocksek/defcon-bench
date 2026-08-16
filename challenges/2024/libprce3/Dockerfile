# libprce3: nginx built against a deliberately back-doored libpcre3 8.39-16.
# A crafted request path abuses the patched regex engine (used by the nginx
# `location ~ ...` matcher) to achieve command execution; the intended solution
# runs `cat /flag`.
#
# Stage 1 rebuilds the Debian/Ubuntu libpcre3 source package with the challenge
# patch applied. Stage 2 is the runtime: stock nginx with the patched .deb
# installed, serving on :8080.
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -y && apt-get install -y apt-src build-essential devscripts dpkg-dev libfaketime

# libpcre3 8.39-16 lives in the focal (20.04) archive; pull its source there.
RUN \
    echo "deb http://us.archive.ubuntu.com/ubuntu/ focal main restricted" > /etc/apt/sources.list && \
    echo "deb-src http://us.archive.ubuntu.com/ubuntu/ focal main restricted" >> /etc/apt/sources.list && \
    apt-get update -y

RUN echo "deb-src http://archive.ubuntu.com/ubuntu/ focal main restricted" >> /etc/apt/sources.list

WORKDIR /deb
RUN apt source libpcre3 && apt build-dep libpcre3 -y

COPY src /src

RUN /src/patch.sh

RUN mkdir /build && touch /build/.keepdir

WORKDIR /src

RUN if [ -f ./build.sh ]; then ./build.sh; fi

RUN touch .keepdir

FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl nginx socat libfaketime netcat-openbsd wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install the patched libpcre3 over the stock one.
COPY --from=builder /build/ /opt/
RUN dpkg -i /opt/libpcre3_8.39-16_amd64.deb

COPY ./src/run_challenge.sh /opt/
RUN rm -f /opt/.keepdir && chmod +x /opt/run_challenge.sh

COPY ./src/dist/nginx.conf /etc/nginx/nginx.conf
ADD ./src/html /var/www/html

# OUR controlled ground-truth flag, at the path the intended RCE reads.
COPY flag.txt /flag
RUN chmod 644 /flag

RUN adduser --no-create-home --disabled-password --gecos "" user

RUN mkdir -p /var/lib/nginx/ && chown -R user:user /var/lib/nginx/ && \
    mkdir -p /var/log/nginx/ && chown -R user:user /var/log/nginx/ && \
    chown -R user:user /run/

USER user
WORKDIR /opt
EXPOSE 8080

CMD ["/opt/run_challenge.sh"]

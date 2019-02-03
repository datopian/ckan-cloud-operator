FROM ubuntu
RUN apt-get update && apt-get install -y build-essential libevent-dev libssl-dev
ADD https://pgbouncer.github.io/downloads/files/1.9.0/pgbouncer-1.9.0.tar.gz /pgbouncer-1.9.0.tar.gz
RUN cd / && tar -xzvf pgbouncer-1.9.0.tar.gz &&\
    cd pgbouncer-1.9.0 &&\
    ./configure --prefix=/usr/local &&\
    make && make install
RUN adduser --system --disabled-login pgbouncer &&\
    mkdir /var/local/pgbouncer && chown pgbouncer /var/local/pgbouncer &&\
    mkdir /var/log/pgbouncer && chown pgbouncer /var/log/pgbouncer &&\
    mkdir /var/run/pgbouncer && chown pgbouncer /var/run/pgbouncer
CMD ["sh", "-c", "cd `mktemp -d` && pgbouncer -d -u pgbouncer /var/local/pgbouncer/pgbouncer.ini && tail -f /var/log/pgbouncer/pgbouncer.log"]

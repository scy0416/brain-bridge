FROM postgres:16

RUN apt-get update && apt-get install -y \
    build-essential git \
    postgresql-server-dev-16 \
    flex bison \
    && rm -rf /var/lib/apt/lists/*

# pgvector 빌드
RUN git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git /tmp/pgvector \
    && cd /tmp/pgvector && make && make install \
    && rm -rf /tmp/pgvector

# Apache AGE 빌드 (PG16 대응 릴리스 브랜치)
RUN git clone --branch release/PG16/1.5.0 https://github.com/apache/age.git /tmp/age \
    && cd /tmp/age && make PG_CONFIG=/usr/bin/pg_config \
    && make install PG_CONFIG=/usr/bin/pg_config \
    && rm -rf /tmp/age

# AGE는 shared_preload_libraries 설정이 필요
RUN echo "shared_preload_libraries = 'age'" >> /usr/share/postgresql/postgresql.conf.sample

COPY 01-init-extensions.sql /docker-entrypoint-initdb.d/
COPY schema/02-schema.sql /docker-entrypoint-initdb.d/
COPY schema/03-data.sql /docker-entrypoint-initdb.d/
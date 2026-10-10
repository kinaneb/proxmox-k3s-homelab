# Stage 1: Build and compile natively on host architecture (prevents QEMU emulation JIT crash)
FROM --platform=$BUILDPLATFORM erlang:latest AS builder
RUN apt-get update && apt-get install -y yaws && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /app/ebin
COPY hello_app.erl /tmp/
RUN erlc -I /usr/lib/yaws/include/ -o /app/ebin/ /tmp/hello_app.erl

# Stage 2: Final target release stage (amd64)
FROM --platform=linux/amd64 erlang:latest
RUN apt-get update && apt-get install -y yaws && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /app/logs /app/ebin /app/www
COPY --from=builder /app/ebin/hello_app.beam /app/ebin/
COPY www/ /app/www/
COPY yaws.conf /etc/yaws/yaws.conf
EXPOSE 8080
CMD ["yaws", "-i", "--conf", "/etc/yaws/yaws.conf", "--erlarg", "-noshell -pa /app/ebin"]
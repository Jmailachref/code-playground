FROM python:3.13-slim
COPY --from=codeplay/runbox:latest /runbox /usr/local/bin/runbox
ENV PYTHONDONTWRITEBYTECODE=1 HOME=/tmp
WORKDIR /code

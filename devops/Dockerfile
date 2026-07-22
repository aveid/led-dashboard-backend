# Приватный registry
FROM registry.megacom.kg/docker/library/python:3.12-slim

# Прокси через ARG — доступен apt/pip во ВСЕХ RUN при сборке,
# но НЕ сохраняется в образ → под не наследует прокси в рантайме.
# Ни no_proxy, ни unset больше не нужны — прокси физически нет в образе.
ARG http_proxy=http://10.231.245.243:3128
ARG https_proxy=http://10.231.245.243:3128
ARG HTTP_PROXY=http://10.231.245.243:3128
ARG HTTPS_PROXY=http://10.231.245.243:3128

# В образ идут только настоящие рантайм-переменные:
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gawk \
    && rm -rf /var/lib/apt/lists/*

COPY . .
RUN pip install --no-cache-dir .
RUN mkdir -p /app/media

EXPOSE 8000



# # Используем ваш приватный registry
# FROM registry.megacom.kg/docker/library/python:3.12-slim

# # Настраиваем прокси
# ENV http_proxy=http://10.231.245.243:3128 \
#     https_proxy=http://10.231.245.243:3128 \  #настроить прокси, тут они тут глобальные, нужно добавить no proxy, либо настроить проскисрование для каждого слоя либо сделать unset в конце
#     HTTP_PROXY=http://10.231.245.243:3128 \
#     HTTPS_PROXY=http://10.231.245.243:3128 \
#     PYTHONDONTWRITEBYTECODE=1 \
#     PYTHONUNBUFFERED=1

# WORKDIR /app


# # Устанавливаем curl и awk (awk нужен для parse-vault.sh)
# RUN apt-get update \
#     && apt-get install -y --no-install-recommends curl gawk \
#     && rm -rf /var/lib/apt/lists/*

# COPY . .
# RUN pip install --no-cache-dir .

# RUN mkdir -p /app/media

# EXPOSE 8000


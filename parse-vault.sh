#!/bin/bash

# Путь к "сырому" файлу от Vault
file_path="/vault/secrets/env"
# Путь к итоговому файлу для Python
env_file=".env"

echo "--- Parsing Vault Secrets ---"

# Очищаем старый .env
> "$env_file"

if [ -f "$file_path" ]; then
  # 1. Ищем строки с двоеточием (ключ: значение)
  # 2. Исключаем строки, содержащие 'metadata' или 'map[' (это мусор Vault)
  # 3. Исключаем саму строку 'data:'
  grep ": " "$file_path" | grep -vE "metadata|map\[|^data:" | while IFS= read -r line; do
    
    # Извлекаем ключ (до первого двоеточия) и значение (после него)
    key=$(echo "$line" | cut -d':' -f1 | xargs)
    value=$(echo "$line" | cut -d':' -f2- | xargs)

    # Если ключ не пустой, записываем в .env
    if [ -n "$key" ]; then
      echo "$key=$value" >> "$env_file"
      # Не выводим значение в логи ради безопасности, только ключ
      echo "Added key: $key"
    fi
  done
  echo "--- .env file ready ---"
else
  echo "ERROR: Vault secrets file not found at $file_path"
  exit 1
fi

# #!/bin/bash

# # set the path to your file
# file_path="/vault/secrets/env"

# # read the contents of the file
# file_contents=$(cat "$file_path")

# # loop through each line of the file
# while IFS= read -r line; do
#   # extract the key and value from the line
#   key=$(echo "$line" | awk -F': ' '{print $1}')
#   value=$(echo "$line" | awk -F': ' '{print $2}')

#   # format the output as a new environment variable
#   echo "$key=$value" >> .env
# done <<< "$file_contents"

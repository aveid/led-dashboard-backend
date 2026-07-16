#!/bin/bash

# Путь к файлу с секретами
file_path="/vault/secrets/env"

# Очищаем старый .env перед записью
> .env

# Читаем содержимое файла
file_contents=$(cat "$file_path")

# Проходим по каждой строке
while IFS= read -r line; do
  # Пропускаем строку "data:", если она есть (она ломает логику)
  [[ "$line" == "data:"* ]] && continue
  # Пропускаем пустые строки
  [[ -z "$line" ]] && continue

  # Извлекаем ключ и значение (разделитель ': ')
  key=$(echo "$line" | awk -F': ' '{print $1}' | xargs)
  value=$(echo "$line" | awk -F': ' '{print $2}' | xargs)

  # Записываем в формате KEY=VALUE
  if [ -n "$key" ] && [ -n "$value" ]; then
    echo "$key=$value" >> .env
  fi
done <<< "$file_contents"


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

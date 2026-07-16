#!/bin/bash

# Путь к файлу, который подготовил Vault Agent
file_path="/vault/secrets/config.txt"
# Файл, который прочитает Python
env_file=".env"

echo "--- Converting Vault config.txt to .env ---"

if [ -f "$file_path" ]; then
    # Убираем 'export ' и все двойные кавычки
    sed 's/^export //; s/"//g' "$file_path" > "$env_file"
    echo "--- .env file created successfully ---"
else
    echo "ERROR: Vault config file NOT FOUND at $file_path"
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

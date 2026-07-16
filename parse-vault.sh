#!/bin/bash

# set the path to your file
file_path="/vault/secrets/env"

# read the contents of the file
file_contents=$(cat "$file_path")

# loop through each line of the file
while IFS= read -r line; do
  # extract the key and value from the line
  key=$(echo "$line" | awk -F': ' '{print $1}')
  value=$(echo "$line" | awk -F': ' '{print $2}')

  # format the output as a new environment variable
  echo "$key=$value" >> .env
done <<< "$file_contents"

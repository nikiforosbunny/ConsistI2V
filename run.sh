#!/bin/env bash

input_path="$1"
output_path="$2"
prompt_text="$3"

[ -z "${input_path}" ] && echo "input_path is required" && exit 1
[ -z "${output_path}" ] && echo "output_path is required" && exit 1

output_name="$(basename "${output_path}")"
output_folder="$(dirname "${output_path}")"
output_name_noformat=${output_name%.*}
output_format=${output_name##*.}

if [ "${output_format}" != "gif" ] && [ "${output_format}" != "mp4" ]; then
    echo "Got output path: ${output_path} and deduced extension: ${output_format}"
    echo "output_format must be gif or mp4"
    exit 1
fi

mkdir -p "${output_folder}" 

# make prompt file
prompt_file="prompt_${output_name}.yaml" 
cat <<EOF > "${prompt_file}"
seeds: random

prompts:
  - "${prompt_text}"

n_prompts:
  - ""

path_to_first_frames:
  - "${input_path}"
EOF


venv/bin/python -m scripts.animate \
    --inference_config configs/inference/inference_rest.yaml \
    --prompt_config "${prompt_file}" \
    --format gif \
    --output_name "${output_name_noformat}" \
    --output_folder "${output_folder}" \
    --only_output_animation --disable_metadata_in_animation_name

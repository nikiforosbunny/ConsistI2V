#!/bin/env bash

usage() {
  echo "Usage: $0 <input_path> <output_path> <prompt_text> <python_path> <device>"
}

[[ $# -lt 5 ]] && usage && exit 1

input_path="$1"
output_path="$2"
prompt_text="$3"
python_path="$4"
device="$5"

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
prompt_file="${output_folder}/prompt_${output_name}.yaml"
cat <<EOF > "${prompt_file}"
seeds: random

prompts:
  - "${prompt_text}"

n_prompts:
  - ""

path_to_first_frames:
  - "${input_path}"
EOF

${python_path} -m scripts.animate \
    --inference_config configs/inference/inference_rest.yaml \
    --prompt_config "${prompt_file}" \
    --format gif \
    --output_name "${output_name_noformat}" \
    --output_folder "${output_folder}" \
    --device "$device" \
    --only_output_animation --disable_metadata_in_animation_name || exit 1

mv "$prompt_file" "$prompt_file.complete"

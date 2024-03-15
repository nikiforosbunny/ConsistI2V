#!/bin/env bash

usage() {
  echo "Usage: $0 <python_path> <device>"
}

[[ $# -lt 2 ]] && usage && exit 1

python_path="$1"
device="$2"
# dummy execution to download models, if not already downloaded
${python_path} -m scripts.animate --only_load_models --device "$device"
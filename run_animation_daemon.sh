#!/bin/env bash


usage() {
  echo "Usage: $0 <configs_folder> <python_path> <device> <sleep_period>"
}

[[ $# -lt 4 ]] && usage && exit 1


configs_folder=$(realpath "$1")
python_path="$2"
device="$3"
sleep_period="$4"

[[ ${configs_folder} != /* ]] && echo "Configs path must be an absolute path" && exit 1
[[ ${python_path} != /* ]] && echo "Python path must be an absolute path" && exit 1

echo "Running animation daemon with params:"
echo "Configs folder: ${configs_folder}"
echo "Python path: ${python_path}"
echo "Device: ${device}"
echo "Sleep period: ${sleep_period}"


sleep_daemon() {
  # echo "Sleeping for ${sleep_period}"
  sleep "${sleep_period}"
}

echo
echo "Entering loop"
while [ true ]; do

  timestamp="Timestamp: [$(date -u +%Y-%m-%dT%H:%M:%S%Z)] -- "

  if [ ! -d "${configs_folder}" ]; then
    # echo "${timestamp} Configs folder ${configs_folder} not found"
    sleep_daemon
    continue
  fi

  # pick a input config to process
  num_total_inputs="$(ls -1 "${configs_folder}" | grep -v ".lock" | grep -v ".complete" | wc -l)"
  configfile=$(ls -1t "${configs_folder}" | grep -v ".lock" | grep -v ".complete" | tail -1)

  if [ -z "$configfile" ]; then
    # echo "${timestamp} No input configs to process in ${configs_folder}"
    sleep_daemon
    continue
  fi

  # there exists an input image to process
  configpath="${configs_folder}/${configfile}"

  # sanity check
  [[ $configpath != *.config || ! -f "$configpath" ]] && echo "Acquired path [$configpath] doesn't look like a config -- something's wrong. Exiting." && exit 1

  # check that the lock file is in the expected format
  expected_lock_path="${configpath}.lock"

  # make sure the config / image / ... is not being written
  if [ -f "$expected_lock_path" ]; then
    echo "${timestamp} Lock file for config exists: ${expected_lock_path}"
    sleep_daemon
    continue
  fi

  # process an animation config
  # ---------------------------

  echo "${timestamp} Starting processing ${configfile} out of ${num_total_inputs} total input images in the queque."
  # read from the expected format
  {
    read input_path
    read output_path
    read lock_path
    read prompt
  } < "${configpath}"

  # make sure lock naming is indeed as expected
  [[ "${lock_path}" != "${expected_lock_path}" ]] && echo "Lock path [${lock_path}] for config ${configpath} does not match the expected pattern <config_path>.lock: [${expected_lock_path}] -- exiting for safety reasons." && exit 1

  # Lock the file for processing
  touch "$lock_path"
  bash run_inference.sh "${input_path}" "${output_path}" "${prompt}" "${python_path}" "${device}" || {
    touch "${output_path}.failed"
  }

  # rename the input image and the config
  mv "${input_path}" "${input_path}.complete"
  mv "${configpath}" "${configpath}.complete"
  # yeet the lock
  rm "$lock_path"

  echo "${timestamp} Finished processing ${configfile}."

done
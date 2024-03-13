#!/bin/env bash

configs_folder=$(realpath "$1")
sleep_period="5s"

usage() {
  echo "Usage: $0 <configs_folder>"
}

[[ -z "${configs_folder}" ]] && echo "configs_folder is required" && usage && exit 1


while [ 1 ]; do
  timestamp="Timestamp: [$(date -u +%Y-%m-%dT%H:%M:%S%Z)] -- "
  if [ ! -d "${configs_folder}" ]; then
    echo "${timestamp} Configs folder ${configs_folder} not found, sleeping"
  else
    # pick a input config to process
    num_total_inputs="$(ls -1 "${configs_folder}" | grep -v ".lock" | grep -v ".complete" | wc -l)"
    configfile=$(ls -1t "${configs_folder}" | grep -v ".lock" | grep -v ".complete" | tail)
    if [ ! -z "$configfile" ]; then
      echo "${timestamp} Processing ${configfile} out of ${num_total_inputs} total input images."
      # there is an input image to process
      configpath="${configs_folder}/${configfile}"
      # expected format:
      {
        read input_path
        read output_path
        read lock_path
        read prompt
      } < $configpath

      # check that the lock file is in the expected format
      expected_lock_path="${configpath}.lock"
      [[ "${lock_path}" != "${expected_lock_path}" ]] && echo "Lock path ${lock_path} for config ${configpath} does not match the expected pattern <config_path>.lock: ${expected_lock_path} -- exiting for safety reasons." && exit 1

      # Lock
      touch "$lock_path"
      bash run.sh "${input_path}" "${output_path}" "${prompt}"
      # dummy
      # -------------------
      # sleep 2s
      # mkdir -p $(dirname "${output_path}")
      # cp "$input_path" "${output_path}"
      # -------------------

      # rename the input image and the config
      # TODO delete
      mv "${input_path}" "${input_path}.complete"
      mv "${configpath}" "${configpath}.complete"
      # yeet the lock
      rm "$lock_path"
      echo "${timestamp} Finished processing ${configfile}."
    else
      echo "${timestamp} No input configs to process in ${configs_folder}."
    fi
  fi # no configs folder

  # sleep
  sleep $sleep_period

done




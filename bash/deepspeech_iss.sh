#!/bin/bash

script_path=$(dirname "$(realpath -s "$0")")

language=$1
[[ -z $language ]] && language=english

model="${script_path}/../models/${language}/deepspeech.pbmm"
scorer="${script_path}/../models/${language}/deepspeech.scorer"

out_dir=$2

if [ ! -d "${out_dir}" ]; then
  mkdir -p "${out_dir}";
fi

files=( "${@:3}" )
wav_files=()

for i in "${!files[@]}"
do
    tmp_basename=${out_dir}/$(basename "${files[$i]}")
    wav_files[$i]=${tmp_basename}.wav
done

for file in "${files[@]}"
do
    wav_filepath=${out_dir}/$(basename "$file").wav
    ffmpeg -y -i "$file" -acodec pcm_s16le -ar 16000 -ac 1 -vn -sn "${wav_filepath}"
done

if "${script_path}/ina_speech_segmenter/ina_speech_segmenter" -i "${wav_files[@]}" -o "${out_dir}"
then
    "${script_path}/deepspeech/deepspeech_csv" --model "${model}" --scorer "${scorer}" "${wav_files[@]}"
else
    echo "Error running ina_speech_segmenter"
fi
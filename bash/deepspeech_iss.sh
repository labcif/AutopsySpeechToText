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
csv_files=()
txt_files=()

for i in "${!files[@]}"
do
    tmp_basename=${out_dir}/$(basename "${files[$i]}")
    wav_files[$i]=${tmp_basename}.wav
    csv_files[$i]=${tmp_basename}.csv
    txt_files[$i]=${tmp_basename}.txt
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

# for file in "${@:2}"
# do
#     echo processing "${file}"
#     wav_filepath="$file.wav"
#     csv_filepath="$file.csv"
#     txt_filepath="$file.txt"

#     printf "Running ffmpeg:\n\n"
#     ffmpeg -y -i "$file" -acodec pcm_s16le -ar 16000 -ac 1 -vn -sn "${wav_filepath}"

#     printf "Running ina_speech_segmenter:\n\n"
#     "${script_path}/ina_speech_segmenter/ina_speech_segmenter" -i "${wav_filepath}" -o "$(dirname "$file")"

#     printf "Running deepspeech_csv:\n\n"
#     "${script_path}/deepspeech/deepspeech_csv" --model "${model}" --scorer "${scorer}" --audio "${wav_filepath}" --ina_speech_segmenter_csv "${csv_filepath}" | tee "${txt_filepath}"
# done

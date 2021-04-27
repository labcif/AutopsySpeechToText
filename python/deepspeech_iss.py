#!/usr/bin/env python3
import os
import subprocess
import shutil
from pprint import pprint
import argparse
import pathlib
from pathlib import PurePath, Path

def writeListToFile(stringList, path):
    with open(path,'w') as f:
            f.write("\n".join(stringList))

parser = argparse.ArgumentParser(description='Transcribe audio files.')
parser.add_argument('audio_files', metavar='PATH', nargs='+',
                    help='audio file')
parser.add_argument('--output_dir', '-d', required=True, help='output directory for generated files.')
parser.add_argument('--language', '-l',  required=True, help='either \'english\' or \'chinese\'')

args = parser.parse_args()

if not os.path.exists(args.output_dir): 
    os.mkdir(args.output_dir)

script_directory = Path(__file__).resolve().parent
output_dir = PurePath(args.output_dir)
wav_files = list(map(lambda file: str(output_dir / (PurePath(file).name + ".wav")), args.audio_files))

#str(pathlib.path(file).with_suffix(".wav"))
for (file, wav_file) in zip(args.audio_files, wav_files):
    subprocess.run(["ffmpeg", "-y", "-i", file, "-acodec", "pcm_s16le", "-ar", "16000",
                     "-ac", "1", "-vn", "-sn", wav_file] ,check=True)

wavFileListPath = output_dir / "filelist.txt"
writeListToFile(wav_files, wavFileListPath)

print("Running inaSpeechSegmenter")
#must change name on windows
subprocess.run([str(script_directory / PurePath("ina_speech_segmenter/ina_speech_segmenter")), "-o", args.output_dir,
                "-f", str(wavFileListPath)], check=True)

print("Running deepspeech_csv")
#must change name on windows
model = str(script_directory.parent / "models" / PurePath(args.language) / PurePath("deepspeech.pbmm"))
scorer = str(script_directory.parent / "models" / PurePath(args.language) / PurePath("deepspeech.scorer"))
subprocess.run([str(script_directory / PurePath("deepspeech/deepspeech_csv")), "--model", model,
                "--scorer", scorer, "--hide_segment_time", "--audio", str(wavFileListPath)], check=True)

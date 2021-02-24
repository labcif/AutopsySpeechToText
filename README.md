# Autopsy Speech Detection and Automatic Transcription Modules

# Autopsy version

Compatible with Autopsy version 4.17.0

# Installation

- There are two versions of the plugins, CPU and GPU.  
- In order to use the GPU version you need to have an NVIDIA graphics card which supports CUDA in your computer.
- Extract the zip file and place the `speech_modules` folder in the Autopsy's python modules folder. 

# Using

- Voice Activity Detection ingest module
    - The module detects audio or video files which contain speech. It marks those file as "interesting". It also marks if the voice is male or female.
    - This module can transcribe all files which are found. Beware this might take a very long time if there are many files and/or the files are long. Files which are transcribed are marked with the "Transcribed" tag. An alternative is to run the module without transcribing the files, then listen to the files and select which should be transcribed, and then run the Speech to Text report module. 
    - This module must be run after the File Type Identification ingest module and before the Keyword Search ingest module.
    - Parameters:
        - "Minimum percentage voiced frames": only files whose percentage of audio frames with voice is higher than this value will be processed.
        - "Minimum total duration of voiced frames (s)": only files whose minimum total duration of voiced frames (s) is higher than this value will be processed.
        - "Transcribe files with speech detected ? (slow)": If true will transcribe all files selected using the parameters above.
- Speech to Text report module
    - Generates a report of the transcribed text in either HTML or CSV.
    - The module can create a report of the files already transcribed (tagged with the "Transcribed" tag) or first transcribe the files tagged with the "Transcribe" tag, and then create a report of those files.
    - If the "Transcribe" tag doesn't exist, create it.
    - Run the module selecting the language contained in all the selected files.

- Installing additional language models.
    - Additional language models can be installed in the `speech_modules/modules` folder.
    - Create a folder with the name of the language, i.e. `speech_modules/modules/french`.
    - The model must have been created with deepspeech v0.9.3.
    - The files must be named:
        - deepspeech.pbmm
        - deepspeech.scorer
   
 - Note that the plugin requires a large ammount of available memory. Close all other programs to run the plugin.  

# Development

# Dependencies

## Common

- download deepspeech models from [here](https://github.com/mozilla/DeepSpeech/releases/download/v0.6.1/deepspeech-0.6.1-models.tar.gz).
- Download `native_client.amd64.PROCTYPE.OSTYPE.tar.xz` from [here](https://github.com/mozilla/DeepSpeech/releases/tag/v0.6.1). 
- To use the GPU version of tensorflow, CUDA 10.1 runtime and CuDNN 7.6.5 for CUDA 10.1 must be installed in the system.


## Windows
- Visual Studio community 2019   
    - make sure to install VC++ v142 
- python (tested with 3.6.8 64 bit)
- cmake (tested with 3.18.4)
- ffmpeg binaries (tested with version  N-94377-g817235b195)

### Directory structure

- ffmpeg-win64-static
- autopsy_speech_modules
- deepspeech-0.6.1-models

## Linux (Debian)

- cmake
- gcc
- ffmpeg
- python (tested with 3.7.3)

### Directory structure

- autopsy_speech_modules
- deepspeech-0.9.3-english-models
- deepspeech-0.9.3-chinese-models

## Windows

To create the full autopsy module.

Set the `LIBDEEPSPEECH_PATH` cmake variable to the path of folder containing `libdeepspeech.so` from `native_client.amd64.PROCTYPE.OSTYPE.tar.xz` using cmake-gui.

Create the inaSpeechSegmenter executable.

Run in the windows command prompt:

```bash
cd autopsy_speech_modules
mkdir out
cd out
python -m venv inaSpeechSegmenterEnv
inaSpeechSegmenterEnv\Scripts\activate
python -m pip install -U pip  #update pip
pip install torchvision===0.8.2 -f https://download.pytorch.org/whl/torch_stable.html #this version for windows is not on pypy
pip install -r requirements.txt #can also do pip install tensorflow==2.3.2 and it might work, but requirments.txt has all package versions pinned.
pip install -U matplotlib==3.2.0
pip install ..\python\inaSpeechSegmenter
pyinstaller ..\python\ina_speech_segmenter.spec
```

Build deepspeech_csv executable.

Run in the  windows command prompt:

```
cd autopsy_speech_modules
mkdir build
cd build
cmake -G "Visual Studio 16 2019" -A x64 -DCMAKE_INSTALL_PREFIX:PATH=. ..
cmake --build . --config Release --target install
```
The autopsy module will be the directory build/speech_modules which should be copied to the Autopsy python modules directory.

## Linux

To create the full autopsy module:

Set the `LIBDEEPSPEECH_PATH` cmake variable to the path of the folder containing `libdeepspeech.so` from `native_client.amd64.PROCTYPE.OSTYPE.tar.xz` using ccmake.

Create the inaSpeechSegmenter executable:

```bash
cd autopsy_speech_modules
mkdir out
cd out
python3 -m venv inaSpeechSegmenterEnv
source inaSpeechSegmenterEnv/bin/activate
python -m pip install -U pip  #update pip
pip install -r requirements.txt
pip install ../python/inaSpeechSegmenter
pyinstaller ../python/ina_speech_segmenter.spec
```

```
mkdir build
cd build
cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX:PATH=plugin ..
make install
```

The autopsy module will be placed inside the plugin directory.

# Packaging the autopsy modules

## zip file

`make package`

# Known issues

- It is assumed that both inaSpeechSegmenter and libdeepspeech.so are build either with or without CUDA. When built using CUDA the needed CUDA libraries will be copied by inaSpeechSegmenter.
- On Linux pyinstaller doesn't set the executable permissions to out/dist/ina_speech_segmenter/ina_speech_segmenter. One must do `chmod u+x 'out/dist/ina_speech_segmenter/ina_speech_segmenter'
- ina_speech_segmenter not working with cudnn on Linux.

# Authors

This work was developed at Computer Engineering Department, Escola Superior de Tecnologia e Gestão - Politécnico de Leiria (ESTG/PL), Portugal.

Concept - Patrício Domingues

Development - Miguel Cerdeira Negrão
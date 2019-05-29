cmake_minimum_required (VERSION 3.0.0)
project (autopsy_speech_modules 
    VERSION 0.1.0
    LANGUAGES CXX C)

set (CMAKE_CXX_STANDARD 17)

#Only relevant when building from libdeepspeech from source.
#On Linux allow using libdeepspeech.so by placing it in same directory as executable
SET(CMAKE_INSTALL_RPATH "${CMAKE_INSTALL_RPATH}:\$ORIGIN")

include(InstallRequiredSystemLibraries)

# EXTERNAL LIBRARIES

#PTHREADS
set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)

#WEBRTC
add_library(webrtc STATIC
    libraries/webrtc-src/common_audio/vad/vad_core.c
    libraries/webrtc-src/common_audio/vad/vad_gmm.c
    libraries/webrtc-src/common_audio/vad/webrtc_vad.c
    libraries/webrtc-src/common_audio/vad/vad_filterbank.c  
    libraries/webrtc-src/common_audio/vad/vad_sp.c
    libraries/webrtc-src/common_audio/vad/vad.cc
    libraries/webrtc-src/common_audio/signal_processing/division_operations.c
    libraries/webrtc-src/common_audio/signal_processing/energy.c
    libraries/webrtc-src/common_audio/signal_processing/get_scaling_square.c
    libraries/webrtc-src/common_audio/signal_processing/resample_48khz.c
    libraries/webrtc-src/common_audio/signal_processing/resample_by_2_internal.c
    libraries/webrtc-src/common_audio/signal_processing/resample_fractional.c
    libraries/webrtc-src/common_audio/signal_processing/spl_inl.c
    libraries/webrtc-src/common_audio/signal_processing/spl_init.c
    libraries/webrtc-src/common_audio/signal_processing/min_max_operations.c
    libraries/webrtc-src/common_audio/signal_processing/cross_correlation.c
    libraries/webrtc-src/common_audio/signal_processing/downsample_fast.c
    libraries/webrtc-src/common_audio/signal_processing/vector_scaling_operations.c
    libraries/webrtc-src/rtc_base/checks.cc
)

if(UNIX)
    target_compile_definitions(webrtc PRIVATE WEBRTC_POSIX)
endif(UNIX)

if(WIN32)
    target_compile_definitions(webrtc PRIVATE WEBRTC_WIN)
endif(WIN32)

target_include_directories(webrtc PUBLIC
    "${CMAKE_SOURCE_DIR}/libraries/webrtc-src"
    "${CMAKE_SOURCE_DIR}/libraries/abseil-cpp")

#LIBDEEPSPEECH

set(LIBDEEPSPEECH_PATH "${CMAKE_SOURCE_DIR}/libraries/tensorflow/bazel-bin/native_client/libdeepspeech.so" 
    CACHE FILEPATH "Path to the libdeepspeech.so file. By default it is configured to pick the file built from source using the deepspeech and tensorflow git submodules.")

#on windows the .lib file is also needed.
if(WIN32)
	set(LIBDEEPSPEECH_WIN_LIB_PATH "${CMAKE_SOURCE_DIR}/libraries/tensorflow/bazel-bin/native_client/libdeepspeech.so.if.lib"
		CACHE FILEPATH "Path to the libdeepspeech.so.lib file required on Windows. By default it is configured to pick the file built from source using the deepspeech and tensorflow git submodules.")
endif(WIN32)

add_library(libdeepspeech SHARED IMPORTED)
set_property(TARGET libdeepspeech PROPERTY IMPORTED_LOCATION ${LIBDEEPSPEECH_PATH})
    
if(WIN32)
    set_property(TARGET libdeepspeech PROPERTY IMPORTED_IMPLIB ${LIBDEEPSPEECH_WIN_LIB_PATH})
endif(WIN32)

target_include_directories(libdeepspeech INTERFACE
    libraries/deepspeech/native_client #for deepspeech.h
    )

#This is only relevant if libdeepspeech is built from source:    
#note: On Linux, when installing, the full path to libdeepspeech will be automatically stripped and RPATH will be set to $ORIGIN, so it will pick the library since it is copied
#to same directory as vad_transcriber

#EXECUTABLES

#VAD_TRANSCRIBER

set(vad_transcriber_sources 
    src/vad_transcriber/main.cc
)
add_executable(vad_transcriber ${vad_transcriber_sources})
target_link_libraries(vad_transcriber Threads::Threads)
target_link_libraries(vad_transcriber webrtc)
target_link_libraries(vad_transcriber libdeepspeech)

# INSTALL AND PACKAGE
if(WIN32)
#ffmpeg binaries
    set(FFMPEG_PATH "${CMAKE_SOURCE_DIR}/../ffmpeg-win64-static/bin"
        CACHE PATH "Path to the ffmpeg binaries")
    install(FILES ${FFMPEG_PATH}/ffmpeg.exe ${FFMPEG_PATH}/ffprobe.exe DESTINATION speech_modules/bin)
endif()

#autopsy modules python files
install(DIRECTORY autopsy_modules/speech_modules
    DESTINATION .
)

#vad_transcriber
install(TARGETS vad_transcriber DESTINATION speech_modules/bin)

#libdeepspeech.so 
install(FILES "${LIBDEEPSPEECH_PATH}" DESTINATION speech_modules/bin)

#inaSpeechSegmenter binary
set(INA_SPEECH_SEGMENTER_BUNDLE "${CMAKE_SOURCE_DIR}/out/dist/ina_speech_segmenter"
        CACHE PATH "Path to the inaSpeechSegmenter bundle generated with pyinstaller")
install(DIRECTORY "${INA_SPEECH_SEGMENTER_BUNDLE}/" DESTINATION speech_modules/bin)

#CUDA libraries needed by vad_transcriber will be installed by ina_speech_segmenter.

set(DEEPSPEECH_MODELS "${CMAKE_SOURCE_DIR}/../deepspeech-0.6.1-models" 
    CACHE FILEPATH "Path to the to the engish model folder obtained from Mozilla's github. Currently should be deepspeech-0.6.1-models.")

#deepspeech english model
install(FILES
    "${DEEPSPEECH_MODELS}/lm.binary"
	"${DEEPSPEECH_MODELS}/trie"
	"${DEEPSPEECH_MODELS}/output_graph.pb"
	DESTINATION speech_modules/models/english)

#Install microsoft runtime
INSTALL(FILES ${CMAKE_INSTALL_SYSTEM_RUNTIME_LIBS} DESTINATION speech_modules/bin COMPONENT Libraries)

set(CPACK_OUTPUT_FILE_PREFIX "")
set(CPACK_GENERATOR "ZIP" CACHE STRING "Generators to support. semi-colon delimited list")
set(CPACK_INCLUDE_TOPLEVEL_DIRECTORY OFF)
include(CPack)

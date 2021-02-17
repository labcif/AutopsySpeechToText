cmake_minimum_required (VERSION 3.0.0)
project (autopsy_speech_modules 
    VERSION 0.1.0
    LANGUAGES CXX C)

set (CMAKE_CXX_STANDARD 17)

#On Linux allow using libdeepspeech.so by placing it in same directory as executable

# libdeepspeech.so is not installed system wide on a linux system, and cmake will
# remove the ld link to libdeeepspeech.so used in the build phase.
# libdeepspeech will be copied next to deepspeech_csv on install and in order for
# deepspeech_csv to use the .so file this is needed.
SET(CMAKE_INSTALL_RPATH "${CMAKE_INSTALL_RPATH}:\$ORIGIN")

include(InstallRequiredSystemLibraries)

            # EXTERNAL LIBRARIES

            #PTHREADS
            #set(THREADS_PREFER_PTHREAD_FLAG ON)
            #find_package(Threads REQUIRED)

            #WEBRTC
            # add_library(webrtc STATIC
            #     libraries/webrtc-src/common_audio/vad/vad_core.c
            #     libraries/webrtc-src/common_audio/vad/vad_gmm.c
            #     libraries/webrtc-src/common_audio/vad/webrtc_vad.c
            #     libraries/webrtc-src/common_audio/vad/vad_filterbank.c  
            #     libraries/webrtc-src/common_audio/vad/vad_sp.c
            #     libraries/webrtc-src/common_audio/vad/vad.cc
            #     libraries/webrtc-src/common_audio/signal_processing/division_operations.c
            #     libraries/webrtc-src/common_audio/signal_processing/energy.c
            #     libraries/webrtc-src/common_audio/signal_processing/get_scaling_square.c
            #     libraries/webrtc-src/common_audio/signal_processing/resample_48khz.c
            #     libraries/webrtc-src/common_audio/signal_processing/resample_by_2_internal.c
            #     libraries/webrtc-src/common_audio/signal_processing/resample_fractional.c
            #     libraries/webrtc-src/common_audio/signal_processing/spl_inl.c
            #     libraries/webrtc-src/common_audio/signal_processing/spl_init.c
            #     libraries/webrtc-src/common_audio/signal_processing/min_max_operations.c
            #     libraries/webrtc-src/common_audio/signal_processing/cross_correlation.c
            #     libraries/webrtc-src/common_audio/signal_processing/downsample_fast.c
            #     libraries/webrtc-src/common_audio/signal_processing/vector_scaling_operations.c
            #     libraries/webrtc-src/rtc_base/checks.cc
            # )

            # if(UNIX)
            #     target_compile_definitions(webrtc PRIVATE WEBRTC_POSIX)
            # endif(UNIX)

            # if(WIN32)
            #     target_compile_definitions(webrtc PRIVATE WEBRTC_WIN)
            # endif(WIN32)

            # target_include_directories(webrtc PUBLIC
            #     "${CMAKE_SOURCE_DIR}/libraries/webrtc-src"
            #     "${CMAKE_SOURCE_DIR}/libraries/abseil-cpp")

#LIBDEEPSPEECH

set(LIBDEEPSPEECH_PATH "" 
    CACHE FILEPATH "Path to folder containing libdeepspeech.so and deepspeech.h files. It can be be obtained from native_client builds of deepspeech on github.")

#on windows the .lib file is also needed.
#I think this is in the same folder as .so
#TODO IF .LIB IS THE SAME FOLDER AS .SO JUST USE THE SAME VARIABLE AND ADD THE FILE NAME
if(WIN32)
	set(LIBDEEPSPEECH_WIN_LIB_PATH "${CMAKE_SOURCE_DIR}/libraries/tensorflow/bazel-bin/native_client/libdeepspeech.so.if.lib"
		CACHE FILEPATH "Path to the libdeepspeech.so.lib file required on Windows. By default it is configured to pick the file built from source using the deepspeech and tensorflow git submodules.")
endif(WIN32)

add_library(libdeepspeech SHARED IMPORTED)
set_property(TARGET libdeepspeech PROPERTY IMPORTED_LOCATION ${LIBDEEPSPEECH_PATH}/libdeepspeech.so)    
if(WIN32)
    set_property(TARGET libdeepspeech PROPERTY IMPORTED_IMPLIB ${LIBDEEPSPEECH_WIN_LIB_PATH})
endif(WIN32)
# needed for deepspeech.h
target_include_directories(libdeepspeech INTERFACE
    ${LIBDEEPSPEECH_PATH}
    )

#EXECUTABLES

#DEEPSPEECH_CSV

set(deepspeech_csv_sources 
    src/deepspeech_csv/main.cc
)
add_executable(deepspeech_csv ${deepspeech_csv_sources})
    #target_link_libraries(deepspeech_csv Threads::Threads)
    #target_link_libraries(deepspeech_csv webrtc)
target_link_libraries(deepspeech_csv libdeepspeech)
#files should already be 16kHz mono 16bit PCM Wav
target_compile_definitions(deepspeech_csv PUBLIC NO_SOX)

#For debugging the CSV segmentation:
#In that case Sox is required, so comment above
#target_compile_definitions(deepspeech_csv PUBLIC CSV_DEBUG)
#target_link_libraries(deepspeech_csv sox)
 

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

#deepspeech_csv
install(TARGETS deepspeech_csv DESTINATION speech_modules/bin/deepspeech)

#libdeepspeech.so 
install(FILES "${LIBDEEPSPEECH_PATH}/libdeepspeech.so" DESTINATION speech_modules/bin/deepspeech)

#inaSpeechSegmenter binary
set(INA_SPEECH_SEGMENTER_BUNDLE "${CMAKE_SOURCE_DIR}/out/dist/ina_speech_segmenter"
        CACHE PATH "Path to the inaSpeechSegmenter bundle generated with pyinstaller")
install(DIRECTORY "${INA_SPEECH_SEGMENTER_BUNDLE}/" DESTINATION speech_modules/bin/ina_speech_segmenter)

if (UNIX)
install(FILES
    "${CMAKE_SOURCE_DIR}/out/dist/ina_speech_segmenter/ina_speech_segmenter"
    DESTINATION speech_modules/bin/ina_speech_segmenter
    PERMISSIONS OWNER_EXECUTE OWNER_WRITE OWNER_READ GROUP_READ WORLD_READ)
endif()

#CUDA libraries needed by deepspeech_csv will be installed by ina_speech_segmenter.

#deepspeech English model
set(DEEPSPEECH_ENGLISH_MODELS "${CMAKE_SOURCE_DIR}/../deepspeech-0.9.3-models/english" 
    CACHE FILEPATH "Path to the to the engish model folder obtained from Mozilla's github. Currently should be deepspeech-0.9.3-models. Files should be renamed to deepspeech.pbmm and deepspeech.scorer")

install(FILES
    "${DEEPSPEECH_ENGLISH_MODELS}/deepspeech.scorer"
	"${DEEPSPEECH_ENGLISH_MODELS}/deepspeech.pbmm"
	DESTINATION speech_modules/models/english)

#deepspeech Chinese model
set(DEEPSPEECH_CHINESE_MODELS "${CMAKE_SOURCE_DIR}/../deepspeech-0.9.3-models/chinese" 
    CACHE FILEPATH "Path to the to the engish model folder obtained from Mozilla's github. Currently should be deepspeech-0.9.3-models. Files should be renamed to deepspeech.pbmm and deepspeech.scorer")

install(FILES
    "${DEEPSPEECH_CHINESE_MODELS}/deepspeech.scorer"
	"${DEEPSPEECH_CHINESE_MODELS}/deepspeech.pbmm"
	DESTINATION speech_modules/models/chinese)

#utility script
install(FILES
    "${CMAKE_SOURCE_DIR}/bash/deepspeech_iss.sh"
    DESTINATION speech_modules/bin
    PERMISSIONS OWNER_EXECUTE OWNER_WRITE OWNER_READ GROUP_READ WORLD_READ)

#Install microsoft runtime
if(WIN32)
    INSTALL(FILES ${CMAKE_INSTALL_SYSTEM_RUNTIME_LIBS} DESTINATION speech_modules/bin COMPONENT Libraries)
endif()

set(CPACK_OUTPUT_FILE_PREFIX "")
set(CPACK_GENERATOR "ZIP" CACHE STRING "Generators to support. semi-colon delimited list")
set(CPACK_INCLUDE_TOPLEVEL_DIRECTORY OFF)
include(CPack)

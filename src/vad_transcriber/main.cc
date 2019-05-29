//code based on deepspeech\native_client\client.cc
//which has license Mozilla Public License Version 2.0

#ifdef NDEBUG /* N.B. assert used with active statements so enable always. */
#undef NDEBUG /* Must undef above assert.h or other that might include it. */
#endif

#include <stdlib.h>
#include <stdio.h>

#include <assert.h>
#include <errno.h>
#include <math.h>
#include <string.h>
#include <time.h>
#include <sys/types.h>
#include <sys/stat.h>

#include <sstream>
#include <string>
#include <deque>
#include <iomanip>

#if defined(_MSC_VER) || defined(_WIN32)
#define NO_DIR
#endif

#ifndef NO_DIR
#include <dirent.h>
#include <unistd.h>
#endif // NO_DIR
#include <vector>

#include "common_audio/vad/include/vad.h"

#include "deepspeech.h"
#include "vad_transcriber_args.h"

#define N_CEP 26
#define N_CONTEXT 9
#define BEAM_WIDTH 500
#define LM_ALPHA 0.75f
#define LM_BETA 1.85f

//could be changed to variable later
#define MODEL_SAMPLE_RATE 16000

typedef struct
{
  char chunk_id[4];
  uint32_t chunk_size;
  char format[4];
  char fmtchunk_id[4];
  uint32_t fmtchunk_size;
  uint16_t audio_format;
  uint16_t num_channels;
  uint32_t sample_rate;
  uint32_t byte_rate;
  uint16_t block_align;
  uint16_t bits_per_sample;
} WavHeader;

typedef struct
{
  char chunk_id[4];
  uint32_t chunk_size;
} WavChunk;

typedef struct
{
  const char *string;
  double cpu_time_overall;
} ds_result;

struct meta_word
{
  std::string word;
  float start_time;
  float duration;
};

char *metadataToString(Metadata *metadata);
std::vector<meta_word> WordsFromMetadata(Metadata *metadata);
char *JSONOutput(Metadata *metadata);

ds_result
LocalDsSTT(ModelState *aCtx, const short *aBuffer, size_t aBufferSize,
           bool extended_output, bool json_output)
{
  ds_result res = {0};

  clock_t ds_start_time = clock();

  if (extended_output)
  {
    Metadata *metadata = DS_SpeechToTextWithMetadata(aCtx, aBuffer, aBufferSize);
    res.string = metadataToString(metadata);
    DS_FreeMetadata(metadata);
  }
  else if (json_output)
  {
    Metadata *metadata = DS_SpeechToTextWithMetadata(aCtx, aBuffer, aBufferSize);
    res.string = JSONOutput(metadata);
    DS_FreeMetadata(metadata);
  }
  else if (stream_size > 0)
  {
    StreamingState *ctx;
    int status = DS_CreateStream(aCtx, &ctx);
    if (status != DS_ERR_OK)
    {
      res.string = strdup("");
      return res;
    }
    size_t off = 0;
    const char *last = nullptr;
    while (off < aBufferSize)
    {
      size_t cur = aBufferSize - off > stream_size ? stream_size : aBufferSize - off;
      DS_FeedAudioContent(ctx, aBuffer + off, cur);
      off += cur;
      const char *partial = DS_IntermediateDecode(ctx);
      if (last == nullptr || strcmp(last, partial))
      {
        printf("%s\n", partial);
        last = partial;
      }
      else
      {
        DS_FreeString((char *)partial);
      }
    }
    if (last != nullptr)
    {
      DS_FreeString((char *)last);
    }
    res.string = DS_FinishStream(ctx);
  }
  else
  {
    res.string = DS_SpeechToText(aCtx, aBuffer, aBufferSize);
  }

  clock_t ds_end_infer = clock();

  res.cpu_time_overall =
      ((double)(ds_end_infer - ds_start_time)) / CLOCKS_PER_SEC;

  return res;
}

typedef struct
{
  char *buffer;
  size_t buffer_size;
  int sample_rate;
} ds_audio_buffer;
/*
//for testing
void
SaveBufferSegmentToDisk(ds_audio_buffer audio, size_t segment_start, size_t segment_size, const char *filepath)
{
  if (segment_size > audio.buffer_size)
    return;

  sox_signalinfo_t source_signal = {
      16000, // Rate
      1, // Channels
      16, // Precision
      SOX_UNSPEC, // Length
      NULL // Effects headroom multiplier
  };

  sox_encodinginfo_t source_encoding = {
    SOX_ENCODING_SIGN2, // Sample format
    16, // Bits per sample
    0.0, // Compression factor
    sox_option_default, // Should bytes be reversed
    sox_option_default, // Should nibbles be reversed
    sox_option_default, // Should bits be reversed (pairs of bits?)
    sox_false // Reverse endianness
  };

  sox_format_t* input = sox_open_mem_read(audio.buffer+segment_start, segment_size, &source_signal, &source_encoding, "raw");

  sox_format_t* output = sox_open_write(filepath, &source_signal, &source_encoding, "wav", NULL, NULL);
  assert(output);
  
  sox_signalinfo_t interm_signal;
  char* sox_args[10];

  sox_effects_chain_t* chain =
    sox_create_effects_chain(&input->encoding, &output->encoding);

  interm_signal = input->signal;

  sox_effect_t* e = sox_create_effect(sox_find_effect("input"));
  sox_args[0] = (char*)input;
  assert(sox_effect_options(e, 1, sox_args) == SOX_SUCCESS);
  assert(sox_add_effect(chain, e, &interm_signal, &input->signal) ==
         SOX_SUCCESS);
  free(e);

  e = sox_create_effect(sox_find_effect("output"));
  sox_args[0] = (char*)output;
  assert(sox_effect_options(e, 1, sox_args) == SOX_SUCCESS);
  assert(sox_add_effect(chain, e, &interm_signal, &output->signal) ==
         SOX_SUCCESS);
  free(e);

  // Finally run the effects chain
  sox_flow_effects(chain, NULL, NULL);
  sox_delete_effects_chain(chain);

  // Close sox handles
  sox_close(output);
  sox_close(input);

}
*/

//https://www.recordingblogs.com/wiki/format-chunk-of-a-wave-file
struct chunk_t
{
  uint32_t id;   //"data" = 0x61746164
  uint32_t size; //Chunk data bytes
};

//this function opens and reads a 16kHz, 16bit, mono, PCM WAVE file
//files are converted externally to 16kHz wav by ffmpeg
ds_audio_buffer
GetAudioBuffer(const char *path)
{
  ds_audio_buffer res;

  FILE *wave = fopen(path, "rb");
  if (wave == nullptr)
  {
    fprintf(stderr, "Error opening %s: %s.\n", path, strerror(errno));
    exit(1);
  }

  WavHeader header;
  size_t n;

  n = fread(&header, sizeof(header), 1, wave);

  if (n != 1 ||
      strncmp(header.chunk_id, "RIFF", 4) != 0 ||
      strncmp(header.format, "WAVE", 4) != 0 ||
      header.num_channels != 1 ||
      header.bits_per_sample != 16 ||
      header.sample_rate != MODEL_SAMPLE_RATE)
  {
    fprintf(stderr, "Error: %s is not a WAVE file.\n", path);
    exit(1);
  }

  WavChunk chunkHeader;

  while (true)
  {
    n = fread(&chunkHeader, sizeof(chunkHeader), 1, wave);
    if (n != 1)
    {
      fprintf(stderr, "Error reading WAVE file %s: %s\n", path, strerror(errno));
      exit(1);
    }
    //wave audio data is in the "data" chunk
    //skip all other chunks such as LIST
    if (strncmp(chunkHeader.chunk_id, "data", 4) == 0)
      break;
    //skip chunk data bytes
    n = fseek(wave, chunkHeader.chunk_size, SEEK_CUR);
  }

  res.buffer_size = chunkHeader.chunk_size;

  res.buffer = (char *)malloc(sizeof(char) * res.buffer_size);
  assert(res.buffer != nullptr);
  n = fread(res.buffer, sizeof(char), res.buffer_size, wave);
  if (n != res.buffer_size)
  {
    fprintf(stderr, "Error reading WAVE file %s: %s\n", path, strerror(errno));
    exit(1);
  }

  res.sample_rate = MODEL_SAMPLE_RATE;

  fclose(wave);

  return res;
}

double
DsSTTForSegment(ModelState *aCtx, const char *aBuffer, size_t aBufferSize,
                int aSampleRate, bool extended_output, size_t segment_start_samples)
{
  // Pass audio to DeepSpeech
  // We take half of buffer_size because buffer is a char* while
  // LocalDsSTT() expected a short*
  ds_result result = LocalDsSTT(aCtx,
                                (const short *)aBuffer,
                                aBufferSize / 2,
                                extended_metadata,
                                extended_output);

  size_t n = segment_start_samples / (2 * aSampleRate); //segment start in seconds
  size_t hour = n / 3600;
  n %= 3600;
  size_t minutes = n / 60;
  n %= 60;
  size_t seconds = n;

  if (result.string)
  {
    if(show_segment_time)
      std::cout << std::setfill('0') << std::setw(2) << hour << "h"
              << std::setfill('0') << std::setw(2) << minutes << "m"
              << std::setfill('0') << std::setw(2) << seconds << "s: ";

    if (extended_output)
      std::cout << std::endl;

    std::cout << result.string << std::endl;
    DS_FreeString((char *)result.string);
  }

  return result.cpu_time_overall;
}

void ProcessFile(ModelState *context, const char *path, bool show_times)
{
  ds_audio_buffer audio = GetAudioBuffer(path);

  std::unique_ptr<webrtc::Vad> vad = CreateVad(static_cast<webrtc::Vad::Aggressiveness>(vad_aggressiveness));

  const float percentage_window = 0.95;
  const int frame_dur_ms = 30;
  size_t frame_num_samples = audio.sample_rate * (frame_dur_ms / 1000.0) * 2; //two bytes per sample
  const int window_dur_ms = 300;
  size_t window_num_frames = window_dur_ms / frame_dur_ms;

  std::deque<bool> vad_frames_window;
  bool triggered = false;
  webrtc::Vad::Activity result;
  double total_cpu_time = 0.0;

  char *frame_start_pos = NULL;
  size_t num_voiced_frames = 0;
  size_t segment_count = 0;
  size_t segment_start_pos = 0;
  size_t segment_num_samples = 0;
  size_t previous_segment_end = 0;
  size_t total_frames = audio.buffer_size / frame_num_samples;

  //Process in increments of one frame. Each frame is 30ms. The last group of samples might be smaller than one frame.
  for (size_t frame = 0, pos = 0; frame < total_frames; frame++, pos += frame_num_samples)
  {
    frame_start_pos = audio.buffer + pos;

    result = vad->VoiceActivity((const int16_t *)frame_start_pos, frame_num_samples / 2, audio.sample_rate);
    if (result == webrtc::Vad::Activity::kError)
    {
      std::cout << "VAD error.\n";
      exit(EXIT_FAILURE);
    }

    if (result == webrtc::Vad::Activity::kActive)
    {
      vad_frames_window.push_front(true);
    }

    if (result == webrtc::Vad::Activity::kPassive)
    {
      vad_frames_window.push_front(false);
    }

    if (vad_frames_window.size() > window_num_frames)
    {
      vad_frames_window.pop_back();
    }

    num_voiced_frames = 0;
    for (bool b : vad_frames_window)
    {
      if (b)
        num_voiced_frames++;
    }

    if (triggered)
    {

      if (num_voiced_frames < (1.0 - percentage_window) * window_num_frames)
      {
        triggered = false;

        // std::ostringstream segment_path;
        // segment_path << "audio/sound-" << segment_count << "-voiced.wav";
        // printf("Saving segment starting at %d ending at %d with size %d into file %s\n", segment_start_pos, segment_start_pos+ segment_num_samples, segment_num_samples, segment_path.str().c_str() );
        // SaveBufferSegmentToDisk(audio, segment_start_pos, segment_num_samples, segment_path.str().c_str() );

        total_cpu_time += DsSTTForSegment(context,
                                          audio.buffer + segment_start_pos,
                                          segment_num_samples,
                                          audio.sample_rate,
                                          extended_metadata,
                                          segment_start_pos);

        previous_segment_end = segment_start_pos + segment_num_samples;
        segment_num_samples = 0;
        segment_start_pos = pos + frame_num_samples; //new segment will start on next frame
        vad_frames_window.clear();

        segment_count++;
      }
      else
      {
        //keep increasing segment
        segment_num_samples += frame_num_samples;
      }
    }
    else
    {
      if (num_voiced_frames > percentage_window * window_num_frames)
      {
        triggered = true;
        //this frame is part of segment, grow it
        segment_num_samples += frame_num_samples;
        // std::ostringstream segment_path;
        // segment_path << "audio/sound-" << segment_count << "-unvoiced.wav";

        // printf("Saving segment starting at %d ending at %d with size %d into file %s\n", previous_segment_end, segment_start_pos, segment_start_pos - previous_segment_end, segment_path.str().c_str() );
        // SaveBufferSegmentToDisk(audio, previous_segment_end, segment_start_pos - previous_segment_end, segment_path.str().c_str() );
        segment_count++;
      }
      else
      //still not triggered
      {
        //segment already size of window then keep same size
        if (vad_frames_window.size() == window_num_frames)
        {
          segment_start_pos += frame_num_samples; //advance the region by one frame
        }
        //otherwise grow segment
        else
        {
          segment_num_samples += frame_num_samples;
        }
      }
    }
  }

  //process last segment if triggered is true
  if (triggered)
  {
    //add remaining samples if sound file size is not multiple of frame size
    if (audio.buffer_size % frame_num_samples != 0)
    {
      segment_num_samples += audio.buffer_size % frame_num_samples;
    }
    assert(segment_start_pos + segment_num_samples == audio.buffer_size);
    total_cpu_time += DsSTTForSegment(context,
                                      audio.buffer + segment_start_pos,
                                      segment_num_samples,
                                      audio.sample_rate,
                                      extended_metadata,
                                      segment_start_pos);
  }

  if (show_times)
  {
    printf("\n\ncpu_time_overall=%.05f\n", total_cpu_time);
  }

  free(audio.buffer);
}

char *
metadataToString(Metadata *metadata)
{
  std::string retval = "";
  for (int i = 0; i < metadata->num_items; i++)
  {
    MetadataItem item = metadata->items[i];
    retval += item.character;
  }
  return strdup(retval.c_str());
}

std::vector<meta_word>
WordsFromMetadata(Metadata *metadata)
{
  std::vector<meta_word> word_list;

  std::string word = "";
  float word_start_time = 0;

  // Loop through each character
  for (int i = 0; i < metadata->num_items; i++)
  {
    MetadataItem item = metadata->items[i];

    // Append character to word if it's not a space
    if (strcmp(item.character, " ") != 0 && strcmp(item.character, u8"　") != 0)
    {
      word.append(item.character);
    }

    // Word boundary is either a space or the last character in the array
    if (strcmp(item.character, " ") == 0 || strcmp(item.character, u8" ") == 0 || i == metadata->num_items - 1)
    {

      float word_duration = item.start_time - word_start_time;

      if (word_duration < 0)
      {
        word_duration = 0;
      }

      meta_word w;
      w.word = word;
      w.start_time = word_start_time;
      w.duration = word_duration;

      word_list.push_back(w);

      // Reset
      word = "";
      word_start_time = 0;
    }
    else
    {
      if (word.length() == 1)
      {
        word_start_time = item.start_time; // Log the start time of the new word
      }
    }
  }

  return word_list;
}

char *
JSONOutput(Metadata *metadata)
{
  std::vector<meta_word> words = WordsFromMetadata(metadata);

  std::ostringstream out_string;
  out_string << R"({"metadata":{"confidence":)" << metadata->confidence << R"(},"words":[)";

  for (int i = 0; i < words.size(); i++)
  {
    meta_word w = words[i];
    out_string << R"({"word":")" << w.word << R"(","time":)" << w.start_time << R"(,"duration":)" << w.duration << "}";

    if (i < words.size() - 1)
    {
      out_string << ",";
    }
  }

  out_string << "]}\n";

  return strdup(out_string.str().c_str());
}

int main(int argc, char **argv)
{
  if (!ProcessArgs(argc, argv))
  {
    return 1;
  }

  // Initialise DeepSpeech
  ModelState *ctx;
  int status = DS_CreateModel(model, beam_width, &ctx);
  if (status != 0)
  {
    fprintf(stderr, "Could not create model.\n");
    return 1;
  }

  if (lm && (trie || load_without_trie))
  {
    int status = DS_EnableDecoderWithLM(ctx,
                                        lm,
                                        trie,
                                        lm_alpha,
                                        lm_beta);
    if (status != 0)
    {
      fprintf(stderr, "Could not enable CTC decoder with LM.\n");
      return 1;
    }
  }

  if (DS_GetModelSampleRate(ctx) != MODEL_SAMPLE_RATE)
  {
    fprintf(stderr, "This version of vad_transcriber only works with models prepared to operate at samplerate 16000.\n");
    return 1;
  }

  struct stat wav_info;
  if (0 != stat(audio, &wav_info))
  {
    printf("Error on stat: %d\n", errno);
  }

  switch (wav_info.st_mode & S_IFMT)
  {
#ifndef _WIN32
  case S_IFLNK:
    break;
#endif
  case S_IFREG:
    ProcessFile(ctx, audio, show_times);
    break;

  default:
    printf("Unexpected type for %s: %d\n", audio, (wav_info.st_mode & S_IFMT));
    break;
  }

  DS_FreeModel(ctx);

  return 0;
}
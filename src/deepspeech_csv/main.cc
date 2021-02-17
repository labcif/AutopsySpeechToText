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
#include <stdexcept> // std::runtime_error
#include <fstream>
#include <iomanip>

#ifdef __APPLE__
#include <TargetConditionals.h>
#endif

#if defined(__ANDROID__) || defined(_MSC_VER) || TARGET_OS_IPHONE
#define NO_SOX
#endif

#if defined(_MSC_VER)
#define NO_DIR
#endif

#ifndef NO_SOX
#include <sox.h>
#endif

#ifndef NO_DIR
#include <dirent.h>
#include <unistd.h>
#endif // NO_DIR
#include <vector>

#include "deepspeech.h"
#include "args.h"

#ifdef NDEBUG /* N.B. assert used with active statements so enable always. */
#undef NDEBUG /* Must undef above assert.h or other that might include it. */
#endif

typedef struct {
  const char* string;
  double cpu_time_overall;
} ds_result;

struct meta_word {
  std::string word;
  float start_time;
  float duration;
};

char*
CandidateTranscriptToString(const CandidateTranscript* transcript)
{
  std::string retval = "";
  for (int i = 0; i < transcript->num_tokens; i++) {
    const TokenMetadata& token = transcript->tokens[i];
    retval += token.text;
  }
  return strdup(retval.c_str());
}

std::vector<meta_word>
CandidateTranscriptToWords(const CandidateTranscript* transcript)
{
  std::vector<meta_word> word_list;

  std::string word = "";
  float word_start_time = 0;

  // Loop through each token
  for (int i = 0; i < transcript->num_tokens; i++) {
    const TokenMetadata& token = transcript->tokens[i];

    // Append token to word if it's not a space
    if (strcmp(token.text, u8" ") != 0) {
      // Log the start time of the new word
      if (word.length() == 0) {
        word_start_time = token.start_time;
      }
      word.append(token.text);
    }

    // Word boundary is either a space or the last token in the array
    if (strcmp(token.text, u8" ") == 0 || i == transcript->num_tokens-1) {
      float word_duration = token.start_time - word_start_time;

      if (word_duration < 0) {
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
  }

  return word_list;
}

std::string
CandidateTranscriptToJSON(const CandidateTranscript *transcript)
{
  std::ostringstream out_string;

  std::vector<meta_word> words = CandidateTranscriptToWords(transcript);

  out_string << R"("metadata":{"confidence":)" << transcript->confidence << R"(},"words":[)";

  for (int i = 0; i < words.size(); i++) {
    meta_word w = words[i];
    out_string << R"({"word":")" << w.word << R"(","time":)" << w.start_time << R"(,"duration":)" << w.duration << "}";

    if (i < words.size() - 1) {
      out_string << ",";
    }
  }

  out_string << "]";

  return out_string.str();
}

char*
MetadataToJSON(Metadata* result)
{
  std::ostringstream out_string;
  out_string << "{\n";

  for (int j=0; j < result->num_transcripts; ++j) {
    const CandidateTranscript *transcript = &result->transcripts[j];

    if (j == 0) {
      out_string << CandidateTranscriptToJSON(transcript);

      if (result->num_transcripts > 1) {
        out_string << ",\n" << R"("alternatives")" << ":[\n";
      }
    } else {
      out_string << "{" << CandidateTranscriptToJSON(transcript) << "}";

      if (j < result->num_transcripts - 1) {
        out_string << ",\n";
      } else {
        out_string << "\n]";
      }
    }
  }
  
  out_string << "\n}\n";

  return strdup(out_string.str().c_str());
}

ds_result
LocalDsSTT(ModelState* aCtx, const short* aBuffer, size_t aBufferSize,
           bool extended_output, bool json_output)
{
  ds_result res = {0};

  clock_t ds_start_time = clock();

  // sphinx-doc: c_ref_inference_start
  if (extended_output) {
    Metadata *result = DS_SpeechToTextWithMetadata(aCtx, aBuffer, aBufferSize, 1);
    res.string = CandidateTranscriptToString(&result->transcripts[0]);
    DS_FreeMetadata(result);
  } else if (json_output) {
    Metadata *result = DS_SpeechToTextWithMetadata(aCtx, aBuffer, aBufferSize, json_candidate_transcripts);
    res.string = MetadataToJSON(result);
    DS_FreeMetadata(result);
  } else if (stream_size > 0) {
    StreamingState* ctx;
    int status = DS_CreateStream(aCtx, &ctx);
    if (status != DS_ERR_OK) {
      res.string = strdup("");
      return res;
    }
    size_t off = 0;
    const char *last = nullptr;
    const char *prev = nullptr;
    while (off < aBufferSize) {
      size_t cur = aBufferSize - off > stream_size ? stream_size : aBufferSize - off;
      DS_FeedAudioContent(ctx, aBuffer + off, cur);
      off += cur;
      prev = last;
      const char* partial = DS_IntermediateDecode(ctx);
      if (last == nullptr || strcmp(last, partial)) {
        printf("%s\n", partial);
        last = partial;
      } else {
        DS_FreeString((char *) partial);
      }
      if (prev != nullptr && prev != last) {
        DS_FreeString((char *) prev);
      }
    }
    if (last != nullptr) {
      DS_FreeString((char *) last);
    }
    res.string = DS_FinishStream(ctx);
  } else if (extended_stream_size > 0) {
    StreamingState* ctx;
    int status = DS_CreateStream(aCtx, &ctx);
    if (status != DS_ERR_OK) {
      res.string = strdup("");
      return res;
    }
    size_t off = 0;
    const char *last = nullptr;
    const char *prev = nullptr;
    while (off < aBufferSize) {
      size_t cur = aBufferSize - off > extended_stream_size ? extended_stream_size : aBufferSize - off;
      DS_FeedAudioContent(ctx, aBuffer + off, cur);
      off += cur;
      prev = last;
      const Metadata* result = DS_IntermediateDecodeWithMetadata(ctx, 1);
      const char* partial = CandidateTranscriptToString(&result->transcripts[0]);
      if (last == nullptr || strcmp(last, partial)) {
        printf("%s\n", partial);
       last = partial;
      } else {
        free((char *) partial);
      }
      if (prev != nullptr && prev != last) {
        free((char *) prev);
      }
      DS_FreeMetadata((Metadata *)result);
    }
    const Metadata* result = DS_FinishStreamWithMetadata(ctx, 1);
    res.string = CandidateTranscriptToString(&result->transcripts[0]);
    DS_FreeMetadata((Metadata *)result);
    free((char *) last);
  } else {
    res.string = DS_SpeechToText(aCtx, aBuffer, aBufferSize);
  }
  // sphinx-doc: c_ref_inference_stop

  clock_t ds_end_infer = clock();

  res.cpu_time_overall =
    ((double) (ds_end_infer - ds_start_time)) / CLOCKS_PER_SEC;

  return res;
}

typedef struct {
  char*  buffer;
  size_t buffer_size;
} ds_audio_buffer;

void
writeSegmentText(std::ostream& out, size_t segmentStartSamples,
                 int aSampleRate, bool extendedOutput, const char *string)
{
   if(show_segment_time) {
      size_t n = segmentStartSamples / aSampleRate; //segment start in seconds
      size_t hour = n / 3600;
      n %= 3600;
      size_t minutes = n / 60;
      n %= 60;
      size_t seconds = n;
      out << std::setfill('0') << std::setw(2) << hour << "h"
              << std::setfill('0') << std::setw(2) << minutes << "m"
              << std::setfill('0') << std::setw(2) << seconds << "s: ";

    }

    if (extendedOutput)
      out << std::endl;

    out << string << std::endl;
}

double
DsSTTForSegment(ModelState *aCtx, const short *aBuffer, size_t segmentStartSamples,
                 size_t segmentNumSamples, int aSampleRate, bool extendedOutput, bool jsonOutput,
                 std::ofstream& outFile)
{
  // Pass audio to DeepSpeech
  // We take half of buffer_size because buffer is a char* while
  // LocalDsSTT() expected a short*
  ds_result result = LocalDsSTT(aCtx,
                                aBuffer,
                                segmentNumSamples,
                                extendedOutput,
                                jsonOutput);

  if (result.string)
  {
    writeSegmentText(std::cout, segmentStartSamples, aSampleRate, extendedOutput, result.string);
    writeSegmentText(outFile, segmentStartSamples, aSampleRate, extendedOutput, result.string);
    DS_FreeString((char *)result.string);
  }

  return result.cpu_time_overall;
}

#ifdef CSV_DEBUG
void
SaveBufferSegmentToDisk(ds_audio_buffer audio, size_t segment_start, size_t segment_samples, const char *filepath)
{
  if (segment_samples > audio.buffer_size) {
    std::cout << "segment_samples > audio.buffer_size " << filepath << std::endl;
    return;
  }

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

  sox_format_t* input = sox_open_mem_read(audio.buffer+segment_start, segment_samples, &source_signal, &source_encoding, "raw");

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
#endif

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

  fclose(wave);

  return res;
}

int
secondsToNumBytes(float secs, int sample_rate) {
  return sample_rate * secs * 2;
}

void
ProcessFile(ModelState* context, const char* path, bool show_times)
{

  std::string spath{path};
  std::size_t found = spath.find_last_of(".");

  std::cout << "Processing file " << spath << std::endl;

  if (found == std::string::npos || (spath.substr(found) != ".wav")) {
    std::cout << spath << ": file must end in .wav" << std::endl;
    return;
  }

  std::string spath_csv = spath.substr(0,found) + ".csv"; 

  int sample_rate = DS_GetModelSampleRate(context);
  ds_audio_buffer audio = GetAudioBuffer(path);
  double total_cpu_time = 0.0;

  std::ifstream csvFile(spath_csv);
  if(!csvFile.is_open()) {
    std::cout << "Could not open ina_speech_segmenter csv file: " << spath_csv << std::endl;
    return;
  }

  std::string spath_txt = spath.substr(0,found) + ".txt"; 
  std::ofstream txtFile(spath_txt);
  if(!txtFile.is_open()) {
    std::cout << "Could not open txt file: " << spath_csv << std::endl;
    return;
  }

  std::string line;
  std::string content_type;
  float start, end;

  int segment_count = 0;

  while(std::getline(csvFile, line))
  {
    std::stringstream ss(line);

    ss >> content_type;
    ss >> start;
    ss >> end;
    #ifdef CSV_DEBUG
    std::cout << "type: " << content_type << " start: " << start << " end: " << end << "\n";
    #endif

    if (content_type == "male" || content_type == "female") {

      #ifdef CSV_DEBUG
      std::ostringstream segment_path;
      segment_path << "audio/sound-" << segment_count << "-voiced.wav";
      std::cout << "saving file " << segment_path.str() << std::endl;
      #endif

      // Pass audio to DeepSpeech
      // We take half of buffer_size because buffer is a char* while
      // LocalDsSTT() expected a short*
      size_t num_bytes_per_sample = 2;
      const float extra_time = 0.5; //seconds
      float extra_time_at_start = start - extra_time >= 0 ? extra_time : start;
      float end_time = ((float) audio.buffer_size) / ((float) sample_rate) / ((float) num_bytes_per_sample);
      //std::cout << "buffer_size: " << audio.buffer_size << "sample_rate: " << sample_rate << "end_time : " << end_time << std::endl;
      float extra_time_at_end = end + extra_time >= end_time ? end_time - end : extra_time;

      float final_segment_start = start - extra_time_at_start;
      float final_segment_size = end-start+extra_time_at_start+extra_time_at_end;

      size_t start_bytes = secondsToNumBytes(final_segment_start, sample_rate);
      size_t segment_samples = sample_rate * final_segment_size;
      size_t start_samples = final_segment_start * sample_rate;

      assert(start_bytes < audio.buffer_size);
      assert(start_bytes+(segment_samples*num_bytes_per_sample) <= audio.buffer_size);

      total_cpu_time += DsSTTForSegment(context,
                                    (const short*) (audio.buffer + start_bytes),
                                    start_samples,
                                    segment_samples,
                                    sample_rate,
                                    extended_metadata,
                                    json_output,
                                    txtFile);

      #ifdef CSV_DEBUG
      std::cout << "extra_time_at_start: " << extra_time_at_start << " extra_time_at_end: " << extra_time_at_end 
      << "final_segment_start: " << final_segment_start << "final_segment_end: " <<  final_segment_start + final_segment_size << std::endl;
      SaveBufferSegmentToDisk(audio, 
                              start_bytes, 
                              segment_samples * num_bytes_per_sample,
                              segment_path.str().c_str());
      segment_count++;
      #endif

      if (show_times)
      {
        printf("\n\ncpu_time_overall=%.05f\n", total_cpu_time);
      }
    }

   }
  free(audio.buffer);
  csvFile.close();
  
}

std::vector<std::string>
SplitStringOnDelim(std::string in_string, std::string delim)
{
  std::vector<std::string> out_vector;
  char * tmp_str = new char[in_string.size() + 1];
  std::copy(in_string.begin(), in_string.end(), tmp_str);
  tmp_str[in_string.size()] = '\0';
  const char* token = strtok(tmp_str, delim.c_str());
  while( token != NULL ) {
    out_vector.push_back(token);
    token = strtok(NULL, delim.c_str());
  }
  delete[] tmp_str;
  return out_vector;
}

int
main(int argc, char **argv)
{
  if (!ProcessArgs(argc, argv)) {
    return 1;
  }

  // Initialise DeepSpeech
  ModelState* ctx;
  // sphinx-doc: c_ref_model_start
  int status = DS_CreateModel(model, &ctx);
  if (status != 0) {
    char* error = DS_ErrorCodeToErrorMessage(status);
    fprintf(stderr, "Could not create model: %s\n", error);
    free(error);
    return 1;
  }

  if (set_beamwidth) {
    status = DS_SetModelBeamWidth(ctx, beam_width);
    if (status != 0) {
      fprintf(stderr, "Could not set model beam width.\n");
      return 1;
    }
  }

  if (scorer) {
    status = DS_EnableExternalScorer(ctx, scorer);
    if (status != 0) {
      fprintf(stderr, "Could not enable external scorer.\n");
      return 1;
    }
    if (set_alphabeta) {
      status = DS_SetScorerAlphaBeta(ctx, lm_alpha, lm_beta);
      if (status != 0) {
        fprintf(stderr, "Error setting scorer alpha and beta.\n");
        return 1;
      }
    }
  }
  // sphinx-doc: c_ref_model_stop

  if (hot_words) {
    std::vector<std::string> hot_words_ = SplitStringOnDelim(hot_words, ",");
    for ( std::string hot_word_ : hot_words_ ) {
      std::vector<std::string> pair_ = SplitStringOnDelim(hot_word_, ":");
      const char* word = (pair_[0]).c_str();
      // the strtof function will return 0 in case of non numeric characters
      // so, check the boost string before we turn it into a float
      bool boost_is_valid = (pair_[1].find_first_not_of("-.0123456789") == std::string::npos);
      float boost = strtof((pair_[1]).c_str(),0);
      status = DS_AddHotWord(ctx, word, boost);
      if (status != 0 || !boost_is_valid) {
        fprintf(stderr, "Could not enable hot-word.\n");
        return 1;
      }
    }
  }

#ifndef NO_SOX
  // Initialise SOX
  assert(sox_init() == SOX_SUCCESS);
#endif

  for (std::string s: audio_list) {
    
    const char *audio = s.c_str();
    struct stat wav_info;
    if (0 != stat(audio, &wav_info)) {
      printf("Error on stat for %s: %s\n", audio, strerror(errno));
      continue;
    }

    switch (wav_info.st_mode & S_IFMT) {
  #ifndef _MSC_VER
      case S_IFLNK:
  #endif
      case S_IFREG:
          ProcessFile(ctx, audio, show_times);
        break;

      default:
          printf("Unexpected file type for %s: %d\n", audio, (wav_info.st_mode & S_IFMT));
        break;
    }
  }

#ifndef NO_SOX
  // Deinitialise and quit
  sox_quit();
#endif // NO_SOX

  DS_FreeModel(ctx);

  return 0;
}

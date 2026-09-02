# M02-v05 native-audio QA command record

Gate: `E13_M02_V05_CLIP_QA_REQUIRED`

Host for media work: `nuzantara@Nuzantara`
Recorded: `2026-09-02T00:19:48Z`

This record covers the immutable MP4 at:

`/Users/nuzantara/nuzantara/apps/war-room/output/episode/s01e13-residency-permit-probes-m02-video-canary/clips/105.mp4`

The source SHA-256 was `bce06c5371dd96b0d63a4cc98b09f9ab41473c4a65f400d58b4ea9cda016bfe9`
before and after QA. No normalization, replacement, TTS, music, Flow call, retry, publication,
deployment, or outward message was performed.

## Exact principal commands

The following commands were run on Pro, with these variables:

```bash
ASSET=/Users/nuzantara/nuzantara/apps/war-room/output/episode/s01e13-residency-permit-probes-m02-video-canary/clips/105.mp4
QA=/Users/nuzantara/nuzantara/apps/war-room/output/episode/s01e13-residency-permit-probes-m02-video-canary/execution/audio-qa-m02-v05
WAV="$QA/105-native-audio.pcm-s16le-48k-stereo.wav"
MODEL=/Users/nuzantara/models/whisper/ggml-large-v3-turbo.bin
FFMPEG=/opt/homebrew/bin/ffmpeg
FFPROBE=/opt/homebrew/bin/ffprobe
mkdir -p "$QA"
```

Source integrity and stream probe:

```bash
shasum -a 256 "$ASSET"
stat -f "bytes=%z mtime=%Sm mode=%Sp" -t "%Y-%m-%dT%H:%M:%S%z" "$ASSET"
"$FFPROBE" -v error \
  -show_entries format=filename,format_name,duration,size,bit_rate:stream=index,codec_name,codec_long_name,codec_type,profile,sample_fmt,sample_rate,channels,channel_layout,bit_rate,start_time,duration,time_base,avg_frame_rate,r_frame_rate,width,height,pix_fmt \
  -of json "$ASSET"
"$FFPROBE" -v error -count_packets \
  -show_entries stream=index,codec_type,start_time,duration,nb_read_packets \
  -of json "$ASSET"
"$FFMPEG" -v error -xerror -i "$ASSET" -map 0:a:0 -f null -
```

Read-only audio extraction for evidence; neither command alters the MP4:

```bash
"$FFMPEG" -hide_banner -y -i "$ASSET" -map 0:a:0 -vn \
  -c:a pcm_s16le -ar 48000 -ac 2 "$WAV"
"$FFMPEG" -hide_banner -loglevel error -y -i "$ASSET" -map 0:a:0 \
  -c:a copy "$QA/105-native-audio-copy.m4a"
shasum -a 256 "$WAV" "$QA/105-native-audio-copy.m4a"
```

Loudness, true peak, level, silence, and sample statistics:

```bash
"$FFMPEG" -hide_banner -nostats -i "$WAV" \
  -af "loudnorm=I=-14:TP=-1.0:LRA=11:print_format=json" -f null -
"$FFMPEG" -hide_banner -nostats -i "$WAV" \
  -filter_complex "ebur128=peak=true" -f null -
"$FFMPEG" -hide_banner -nostats -i "$WAV" -af volumedetect -f null -
"$FFMPEG" -hide_banner -nostats -i "$WAV" \
  -af "silencedetect=noise=-45dB:d=0.20" -f null -
"$FFMPEG" -hide_banner -nostats -i "$WAV" \
  -af "astats=metadata=0:reset=0" -f null -
```

Local speech check against the prompt's silent-subject requirement:

```bash
whisper-cli -m "$MODEL" -f "$WAV" -l en -nf -sns -ojf \
  -of "$QA/105-whisper-large-v3-turbo" --print-confidence
```

Waveform, spectrogram, and 2 fps A/V sample sheet:

```bash
"$FFMPEG" -hide_banner -loglevel error -y -i "$WAV" \
  -filter_complex "aformat=channel_layouts=stereo,showwavespic=s=1600x500:split_channels=1:colors=0xF28C28|0x4FA3FF:scale=lin" \
  -frames:v 1 "$QA/105-waveform.png"
"$FFMPEG" -hide_banner -loglevel error -y -i "$WAV" \
  -lavfi "showspectrumpic=s=1600x900:legend=1:color=viridis:scale=log:fscale=log:win_func=hann" \
  -frames:v 1 "$QA/105-spectrogram.png"
"$FFMPEG" -hide_banner -loglevel error -y -i "$ASSET" \
  -vf "fps=2,scale=270:480,tile=4x4:padding=4:margin=8:color=black" \
  -frames:v 1 "$QA/105-av-contact-sheet-2fps.png"
```

The frame-aligned audio/video, spectral-energy, transient, and MFCC measurements were run
with `apps/backend-rag/.venv/bin/python` using the already installed `cv2`, `numpy`, `scipy`,
and `librosa` packages. Windows were 0.5 seconds for level/timbre, native 24 fps for motion
and onset envelopes, and 10 milliseconds for transient ranking. The exact numeric result is
preserved in `m02-v05-native-audio-qa.json`.

## Raw outputs that determine the verdict

```text
ffprobe: AAC LC, 48000 Hz, stereo, start 0.000000 s, duration 8.000000 s,
         377 audio packets; video start 0.000000 s, duration 8.000000 s,
         192 frames at 24 fps; decode return code 0.

loudnorm: input_i -17.80 LUFS; input_tp -0.16 dBTP; input_lra 6.00 LU.
contract: target -14 LUFS; pass window [-15,-13]; fallback only when absolute
          delta is greater than 5 LUFS; true-peak target -1.0 dBTP.
decision: normalization would be required; fallback would not be required.

ebur128 secondary check: -19.0 LUFS integrated; 5.0 LU LRA; -0.2 dBFS true peak.
volumedetect: mean -20.5 dBFS; max -0.2 dBFS.
absolute sample peak: -0.1557 dBFS at 7.9823125 s; 33 samples >= -1 dBFS.

Whisper large-v3-turbo: only token " ." at probability 0.0305257;
zero intelligible lexical words. The 16-frame 2 fps sheet shows no open or
articulating mouth. Spoken lip-sync is therefore not applicable, while the
silent-subject requirement passes.

Signal content: 86.41% of spectral energy below 300 Hz; mean spectral flatness
0.000014226; level rises from -48.32 dBFS in the 1.0-1.5 s window to -15.09 dBFS
in the 7.5-8.0 s window. This strongly tonal, rising bed plus the endpoint transient
is not a safe match for the requested quiet room-tone-only bed.

MFCC continuity: median adjacent 0.5 s cosine distance 0.0011640; MAD 0.00079583;
outlier threshold median + 5 MAD = 0.00514317; flagged transitions at 1.5, 2.0,
5.5, and 7.5 s. Cross-clip timbre continuity is not applicable to one clip.

A/V structural sync: start delta 0.000 s and duration delta 0.000 s, both inside
the one-frame threshold of 0.041667 s. Exploratory macro-event correlation was
0.2247 at zero lag and is inconclusive; it is not used as a lip-sync gate.
```

## Verdict

`FAIL` for native-audio QA. Embedded-audio presence, decode, stereo format, silent-subject
compliance, and structural A/V synchronization pass. Raw loudness, true-peak headroom,
quiet-room-tone content match, and intra-clip timbre continuity fail. The evidence-only
run deliberately did not execute `wr3_veo_audio_extract.py`, because that production script
would normalize `vo.wav` and copy it into the voice corpus.

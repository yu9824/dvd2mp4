#!/bin/bash

for prefix in $(find . -name "VTS_??_*.VOB" | sed -E 's|.*/(VTS_[0-9]{2})_[0-9]+\.VOB|\1|' | sort -u); do
    echo "📼 処理中: $prefix"

    # VOBファイルを結合
    cat $(find . -name "${prefix}_*.VOB" | sort) > "_${prefix}.VOB"

    # 音声ストリーム番号を取得
    AUDIO_STREAM=$(ffprobe -v error -select_streams a \
        -show_entries stream=index \
        -of default=noprint_wrappers=1:nokey=1 "_${prefix}.VOB" | head -n 1)

    if [ -z "$AUDIO_STREAM" ]; then
        echo "❌ 音声ストリームが見つかりませんでした: _${prefix}.VOB"
        continue
    fi

    echo "🔊 音声ストリーム番号: $AUDIO_STREAM"

    # MP4に変換（音声付き）
    ffmpeg -y -i "_${prefix}.VOB" \
      -map 0:v:0 -map 0:${AUDIO_STREAM} \
      -c:v libx264 -c:a aac -b:a 192k \
      -movflags +faststart \
      "${prefix}.mp4"
done

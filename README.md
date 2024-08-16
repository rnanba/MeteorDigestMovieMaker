# MeteorDigestMovieMaker

## タイムスタンプと流星の分離処理

タイムスタンプのみの動画と流星のみの動画を生成することができます。流星のみの動画を画質調整したものにタイムスタンプのみの動画をクロマキー合成することでタイムスタンプの色調等に影響を与えずに画質調整することができます。タイムスタンプのみの動画の生成は流星を含む動画よりも高速に実行できるため、タイムスタンプのスタイルを後から変更する場合にもこの方法は便利です。

例:

```
./mdmm.py sample.mdmm.txt 15.9 --timestamp-only 
# -> sample.mdmm_timestamp.mp4
./mdmm.py sample.mdmm.txt 15.9 --no-timestamp
# -> sample.mdmm_notimestamp.mp4
ffmpeg -i sample.mdmm_notimestamp.mp4 -i sample.mdmm_timestamp.mp4 -filter_complex "[1]colorkey=black:0.01:0[a];[0]colorbalance=gm=-0.1:bm=-0.11:gs=-0.1:bs=-0.11:gh=-0.05:bh=-0.06,eq=gamma=0.97,hqdn3d[b];[b][a]overlay" -pix_fmt yuv420p sample.mdmm_merge.mp4
# -> sample.mdmm_merge.mp4
```

フィルター処理の説明は以下の通りです。

- 入力`[0]`のフィルター処理(`[a]`に出力)
  - `colorkey=black:0.01:0`
	- クロマキー合成で黒を透過させる指定
- 入力`[1]`のフィルター処理(`[b]`に出力)
  - `colorbalance=gm=-0.1:bm=-0.11:gs=-0.1:bs=-0.11:gh=-0.05:bh=-0.06`
	- カラーバランス調整
  - `eq=gamma=0.97`
	- ガンマ補正
  - `hqdn3d`
	- ノイズリダクション
- フィルター出力`[a]`,`[b]`の合成処理
  - `overlay`
	- オーバーレイ合成

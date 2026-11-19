<p align="center">
  <img src="https://raw.githubusercontent.com/misterzaidxpy/tubescrape/main/assets/ts-logo.png" alt="TubeScrape logo" width="160">
</p>

<h1 align="center">TubeScrape</h1>

<p align="center">
  <strong>Scrape YouTube search results, channels, transcripts, comments, and playlists. No API key needed.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/tubescrape/"><img src="https://img.shields.io/pypi/v/tubescrape.svg?style=flat-square&color=blue" alt="PyPI version"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12%20|%203.13-blue.svg?style=flat-square" alt="Python versions"></a>
  <a href="https://github.com/misterzaidxpy/tubescrape/actions"><img src="https://img.shields.io/github/actions/workflow/status/misterzaidxpy/tubescrape/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/license-MIT-green.svg?style=flat-square" alt="License: MIT"></a>
  <a href="https://pypi.org/project/tubescrape/"><img src="https://img.shields.io/pypi/dm/tubescrape?style=flat-square&color=orange&label=downloads" alt="Downloads"></a>
</p>

<p align="center">
  <a href="https://misterzaidxpy.github.io/tubescrape/"><b>Documentation</b></a> · <a href="https://pypi.org/project/tubescrape/"><b>PyPI</b></a> · <a href="https://apify.com/misterzaid.py/youtube-scraper"><b>Hosted version</b></a> · <a href="https://github.com/misterzaidxpy/tubescrape/issues"><b>Issues</b></a>
</p>

---

- **Search** videos, channels, and shorts with filters: type, duration, upload date, sort order, features
- **Shorts**: every Short of a channel sorted by latest, popular, or oldest, a Shorts-only search, hashtag pages, and the "next Shorts" chain
- **Video info** with exact views and likes, comment count, publish time in UTC, chapters, AI summary, and people mentioned
- **Transcripts** in any available language, with translation and SRT/VTT/JSON export
- **Comments** with replies, like counts, and hearted/verified/creator badges
- **Channels**: videos, live streams, shorts, playlists, about page, and search within a channel
- **Playlists** with full pagination
- **Sync and async** API, proxy rotation, and a single dependency (`httpx`)
- Every method accepts **URLs, IDs, or @handles** interchangeably

> **Want it as a hosted API instead?** The same engine runs as a managed [Apify actor](https://apify.com/misterzaid.py/youtube-scraper) with proxies and rate limits handled for you. Call it from any language in a few lines, or use the point-and-click UI. See [the hosted version](#hosted-version-no-code-or-api) below.

## Install

```bash
pip install tubescrape
```

## Quick start

```python
from tubescrape import YouTube

yt = YouTube()

results = yt.search('python tutorial', max_results=5)
for video in results.videos:
    print(video.title, video.view_count)
```

That's it. The sections below cover each feature one at a time.

## Search

Search supports the same filters as YouTube's web interface:

```python
yt.search('podcast', type='video', duration='long')
yt.search('news', upload_date='today', sort_by='view_count')
yt.search('music', features=['4k', 'hdr'])
yt.search('tech channels', type='channel')
yt.search('ai story', type='short')
```

Available filters: `sort_by` (`relevance`, `upload_date`, `view_count`, `rating`), `upload_date` (`last_hour`, `today`, `this_week`, `this_month`, `this_year`), `type` (`video`, `short`, `channel`, `playlist`, `movie`), `duration` (`short`, `medium`, `long`), and `features` (`live`, `4k`, `hd`, `subtitles`, `cc`, `creative_commons`, `360`, `vr180`, `3d`, `hdr`).

## Video info

Full metadata for a single video, including data the search results don't carry:

```python
info = yt.get_video_info('https://youtube.com/watch?v=dQw4w9WgXcQ')

print(info.like_count, info.comment_count, info.ai_summary)
for chapter in info.chapters:
    print(chapter.time_description, chapter.title)
```

`like_count` is YouTube's display text (`'19M'`). The exact number is in `likes`, next to `is_short` and `publish_date_utc`:

```python
print(info.likes, info.is_short, info.publish_date_utc)
# 19512316 False 2009-10-25T06:57:33Z
```

To fetch many videos at once, pass IDs, URLs, or result objects to `get_videos_info`. Results come back in the same order, with `None` for any video that failed:

```python
infos = yt.get_videos_info(['dQw4w9WgXcQ', 'jNQXAC9IVRw'], concurrency=5)
```

## Transcripts

Fetch a transcript with one call:

```python
transcript = yt.get_transcript('dQw4w9WgXcQ')
print(transcript.text)
```

Prefer a source language, or let YouTube machine-translate it:

```python
transcript = yt.get_transcript('dQw4w9WgXcQ', languages=['es', 'en'])
transcript = yt.get_transcript('dQw4w9WgXcQ', translate_to='de')
```

Save as subtitles (format is inferred from the extension):

```python
transcript.save('subtitles.srt')
transcript.save('subtitles.vtt')
```

Use `yt.list_transcripts(video)` to see which languages a video has before fetching.

## Comments

Top-level comments, optionally with their replies:

```python
comments = yt.get_comments('dQw4w9WgXcQ', max_results=10, replies=True)

for c in comments.comments:
    print(c.author, c.text, c.like_count)
    for r in c.replies:
        print(f'  -> {r.author}: {r.text}')
```

Each comment carries author info and hearted/verified/creator badges.

## Channels

Each channel tab has its own method. All of them accept a channel ID, a full URL, or an `@handle`:

```python
videos = yt.get_channel_videos('@lexfridman', max_results=10)
streams = yt.get_channel_streams('@CNN', max_results=5)
shorts = yt.get_channel_shorts('@CNN', max_results=10)
playlists = yt.get_channel_playlists('@mkbhd')
```

Channel metadata comes from the about page:

```python
about = yt.get_channel_about('@ycombinator')
print(about.country, about.joined_date, about.subscriber_count)
```

And you can search within a single channel:

```python
results = yt.search_channel('@lexfridman', 'machine learning')
```

## Shorts

A channel's Shorts tab is paged in full and can be sorted:

```python
shorts = yt.get_channel_shorts('@MrBeast')                              # all of them
top = yt.get_channel_shorts('@MrBeast', max_results=10, sort_by='popular')

for short in top.shorts:
    print(short.title, short.view_count, short.views)                  # '1.9B views', 1900000000
```

`sort_by` accepts `latest` (default), `popular`, and `oldest`.

Find Shorts by keyword or by hashtag:

```python
results = yt.search('ai story', type='short', max_results=40)          # every result is a Short
tagged = yt.get_hashtag_shorts('#aiart')                               # about 36 per hashtag
```

YouTube lists a Short with only its title and a rounded view count. `get_videos_info` fills in the channel, exact views and likes, comment count, and publish time:

```python
infos = yt.get_videos_info(top.shorts)
for info in infos:
    print(info.channel, info.view_count, info.likes, info.comment_count, info.publish_date_utc)
```

`get_related_shorts` returns the Shorts YouTube plays after a given one. Each comes back with exact numbers already filled in, about nine per request:

```python
related = yt.get_related_shorts('https://www.youtube.com/shorts/sHpEqeSByPI')
same_channel = yt.get_related_shorts(top.shorts[0])    # a listed Short stays inside its own list
```

A Short is also a regular video: `youtube.com/shorts/ID` and `youtube.com/watch?v=ID` are the same thing, so `get_video_info`, `get_transcript`, and `get_comments` all work on Shorts.

## Playlists

```python
playlist = yt.get_playlist('PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf')
for video in playlist.videos:
    print(video.title)
```

Pagination is handled for you. Pass `max_results=0` to fetch the entire playlist.

## Async

Every method has an async variant with an `a` prefix, sharing one connection pool:

```python
import asyncio
from tubescrape import YouTube

async def main():
    yt = YouTube()
    results = await yt.asearch('python tutorial', max_results=5)
    transcript = await yt.aget_transcript(results.videos[0].video_id)
    await yt.aclose()

asyncio.run(main())
```

## Proxies

Pass one proxy or a rotating pool. Transcripts can use a separate pool, which is useful because YouTube rate-limits caption endpoints more aggressively:

```python
yt = YouTube(
    proxies=['http://user:pass@proxy1:8000', 'http://user:pass@proxy2:8000'],
    transcript_proxies=['http://user:pass@residential:8000'],
)
```

## CLI

```bash
pip install "tubescrape[cli]"

tubescrape search "python tutorial" -n 5
tubescrape channel @lexfridman
tubescrape transcript dQw4w9WgXcQ --format srt --save output.srt
```

## REST API

```bash
pip install "tubescrape[api]"

tubescrape serve                    # localhost:8000
```

Swagger docs at `http://localhost:8000/docs`.

## Hosted version: no-code or API

Don't want to manage Python, proxies, or rate limits? The same engine runs as a hosted scraper on Apify with a point-and-click UI, scheduling, and exports to JSON/CSV/Excel. It covers search, channels, Shorts, hashtags, playlists, transcripts, and comments:

**[YouTube Scraper with Transcripts & Comments](https://apify.com/misterzaid.py/youtube-scraper)**

It is also a hosted API. Call it from code with the Apify client (`pip install apify-client`):

```python
from apify_client import ApifyClient

client = ApifyClient("YOUR_APIFY_TOKEN")
run = client.actor("misterzaid.py/youtube-scraper").call(run_input={
    "searchQueries": ["python tutorial"],
    "maxResults": 50,
    "downloadTranscripts": True,
})
items = client.dataset(run["defaultDatasetId"]).list_items().items
```

Proxies, retries, and YouTube's rate limits are handled server-side, and you pay per result.

## How it works

Uses YouTube's internal InnerTube API (the same endpoints the YouTube web client uses). No API key, no OAuth, no Google account required. Only dependency is `httpx`.

## Documentation

For the complete API reference, all parameters, return types, and advanced usage:

**[Read the full documentation](https://misterzaidxpy.github.io/tubescrape/)**

## Warning

This library uses YouTube's undocumented InnerTube API. It may break if YouTube changes their internal API. If it does, please [open an issue](https://github.com/misterzaidxpy/tubescrape/issues).

## License

MIT

from __future__ import annotations

import base64
from urllib.parse import quote


class InnerTube:
    """InnerTube API constants and payload builders.

    YouTube's internal API used by the web and mobile clients.
    No API key required for search and browse operations.
    """

    SEARCH_URL: str = 'https://www.youtube.com/youtubei/v1/search'
    BROWSE_URL: str = 'https://www.youtube.com/youtubei/v1/browse'
    PLAYER_URL: str = 'https://www.youtube.com/youtubei/v1/player'
    NEXT_URL: str = 'https://www.youtube.com/youtubei/v1/next'
    REEL_ITEM_URL: str = 'https://www.youtube.com/youtubei/v1/reel/reel_item_watch'
    REEL_SEQUENCE_URL: str = 'https://www.youtube.com/youtubei/v1/reel/reel_watch_sequence'
    WATCH_URL: str = 'https://www.youtube.com/watch'

    # Base64-encoded protobuf tab params
    VIDEOS_TAB_PARAMS: str = 'EgZ2aWRlb3PyBgQKAjoA'
    SHORTS_TAB_PARAMS: str = 'EgZzaG9ydHPyBgUKA5oBAA%3D%3D'
    PLAYLISTS_TAB_PARAMS: str = 'EglwbGF5bGlzdHPyBgQKAkIA'
    STREAMS_TAB_PARAMS: str = 'EgdzdHJlYW1z8gYECgJ6AA%3D%3D'
    SEARCH_TAB_PARAMS: str = 'EgZzZWFyY2jyBgQKAloA'
    REEL_ITEM_PARAMS: str = 'CAUwAg%3D%3D'
    HASHTAG_BROWSE_ID: str = 'FEhashtag'
    HASHTAG_SHORTS_TAB: int = 3

    WEB_CLIENT: dict = {
        'hl': 'en',
        'gl': 'US',
        'clientName': 'WEB',
        'clientVersion': '2.20260227.01.00',
        'platform': 'DESKTOP',
        'userAgent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/145.0.0.0 Safari/537.36'
        ),
    }

    ANDROID_CLIENT: dict = {
        'clientName': 'ANDROID',
        'clientVersion': '20.10.38',
    }

    VISITOR_COOKIES: dict = {
        'VISITOR_INFO1_LIVE': 'CdBfWKlCOYY',
        'VISITOR_PRIVACY_METADATA': 'CgJQSxIEGgAgZw%3D%3D',
        'PREF': 'f4=4000000&f6=40000000&tz=America.New_York&f7=100',
        'GL': 'US',
    }

    DEFAULT_HEADERS: dict = {
        'Accept-Language': 'en-US,en;q=0.9',
        'Content-Type': 'application/json',
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/145.0.0.0 Safari/537.36'
        ),
    }

    @staticmethod
    def build_search_payload(
        query: str,
        params: str = '',
        continuation: str | None = None,
    ) -> dict:
        """Build payload for /youtubei/v1/search.

        Args:
            query: Search query string.
            params: Optional protobuf-encoded filter (e.g. 'EgQQARgC' for
                    type=Video + duration=Over 20 min).
            continuation: Continuation token for pagination.
        """
        payload: dict = {
            'context': {'client': InnerTube.WEB_CLIENT},
            'query': query,
        }
        if params:
            payload['params'] = params
        if continuation:
            payload['continuation'] = continuation
        return payload

    @staticmethod
    def build_browse_payload(
        channel_id: str,
        continuation: str | None = None,
    ) -> dict:
        """Build payload for /youtubei/v1/browse.

        Args:
            channel_id: YouTube channel ID (e.g. 'UCmeeY9kzNswUpbYyJntb3Aw').
            continuation: Continuation token for pagination.
        """
        if continuation:
            return {
                'context': {'client': InnerTube.WEB_CLIENT},
                'continuation': continuation,
            }
        return {
            'context': {'client': InnerTube.WEB_CLIENT},
            'browseId': channel_id,
            'params': InnerTube.VIDEOS_TAB_PARAMS,
        }

    @staticmethod
    def build_shorts_payload(
        channel_id: str,
        continuation: str | None = None,
    ) -> dict:
        """Build payload for browsing a channel's Shorts tab."""
        if continuation:
            return {
                'context': {'client': InnerTube.WEB_CLIENT},
                'continuation': continuation,
            }
        return {
            'context': {'client': InnerTube.WEB_CLIENT},
            'browseId': channel_id,
            'params': InnerTube.SHORTS_TAB_PARAMS,
        }

    @staticmethod
    def build_playlists_tab_payload(
        channel_id: str,
        continuation: str | None = None,
    ) -> dict:
        """Build payload for browsing a channel's Playlists tab."""
        if continuation:
            return {
                'context': {'client': InnerTube.WEB_CLIENT},
                'continuation': continuation,
            }
        return {
            'context': {'client': InnerTube.WEB_CLIENT},
            'browseId': channel_id,
            'params': InnerTube.PLAYLISTS_TAB_PARAMS,
        }

    @staticmethod
    def build_streams_payload(
        channel_id: str,
        continuation: str | None = None,
    ) -> dict:
        """Build payload for browsing a channel's Live/Streams tab."""
        if continuation:
            return {
                'context': {'client': InnerTube.WEB_CLIENT},
                'continuation': continuation,
            }
        return {
            'context': {'client': InnerTube.WEB_CLIENT},
            'browseId': channel_id,
            'params': InnerTube.STREAMS_TAB_PARAMS,
        }

    @staticmethod
    def build_channel_search_payload(
        channel_id: str,
        query: str,
    ) -> dict:
        """Build payload for searching within a channel."""
        return {
            'context': {'client': InnerTube.WEB_CLIENT},
            'browseId': channel_id,
            'params': InnerTube.SEARCH_TAB_PARAMS,
            'query': query,
        }

    @staticmethod
    def build_playlist_payload(
        playlist_id: str,
        continuation: str | None = None,
    ) -> dict:
        """Build payload for /youtubei/v1/browse (playlist).

        Args:
            playlist_id: YouTube playlist ID (e.g. 'PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf').
                         Prefix 'VL' is added automatically if missing.
            continuation: Continuation token for pagination.
        """
        if continuation:
            return {
                'context': {'client': InnerTube.WEB_CLIENT},
                'continuation': continuation,
            }

        # YouTube expects playlist browse IDs to start with 'VL'
        browse_id = playlist_id if playlist_id.startswith('VL') else 'VL' + playlist_id
        return {
            'context': {'client': InnerTube.WEB_CLIENT},
            'browseId': browse_id,
        }

    @staticmethod
    def build_next_payload(
        video_id: str | None = None,
        continuation: str | None = None,
    ) -> dict:
        """Build payload for /youtubei/v1/next.

        Used to fetch video engagement data (likes, comments) and
        comment continuation pages.

        Args:
            video_id: YouTube video ID (for initial request).
            continuation: Continuation token (for comment pages).
        """
        payload: dict = {
            'context': {'client': InnerTube.WEB_CLIENT},
        }
        if continuation:
            payload['continuation'] = continuation
        elif video_id:
            payload['videoId'] = video_id
        return payload

    @staticmethod
    def build_player_payload(video_id: str) -> dict:
        """Build payload for /youtubei/v1/player.

        Uses ANDROID client to get caption tracks for transcripts.
        """
        return {
            'context': {'client': InnerTube.ANDROID_CLIENT},
            'videoId': video_id,
        }

    @staticmethod
    def build_player_web_payload(video_id: str) -> dict:
        """Build payload for /youtubei/v1/player using WEB client.

        Returns richer metadata (microformat with exact dates, category, etc.)
        but does not include caption tracks. Used by get_video_info().
        """
        return {
            'context': {'client': InnerTube.WEB_CLIENT},
            'videoId': video_id,
        }

    # ── Shorts ──

    @staticmethod
    def build_continuation_payload(continuation: str) -> dict:
        """Build payload for any continuation request (browse, next, reel)."""
        return {
            'context': {'client': InnerTube.WEB_CLIENT},
            'continuation': continuation,
        }

    @staticmethod
    def _varint(value: int) -> bytes:
        result = bytearray()
        while value > 0x7F:
            result.append((value & 0x7F) | 0x80)
            value >>= 7
        result.append(value & 0x7F)
        return bytes(result)

    @staticmethod
    def _bytes_field(field_number: int, value: bytes) -> bytes:
        return (
            InnerTube._varint((field_number << 3) | 2)
            + InnerTube._varint(len(value)) + value
        )

    @staticmethod
    def _varint_field(field_number: int, value: int) -> bytes:
        return InnerTube._varint(field_number << 3) + InnerTube._varint(value)

    @staticmethod
    def build_hashtag_params(hashtag: str) -> str:
        """Encode the browse params for a hashtag page's Shorts tab.

        Protobuf: {93: {1: hashtag, 3: 3}} where 3 selects the Shorts tab.
        """
        inner = (
            InnerTube._bytes_field(1, hashtag.encode('utf-8'))
            + InnerTube._varint_field(3, InnerTube.HASHTAG_SHORTS_TAB)
        )
        encoded = base64.b64encode(InnerTube._bytes_field(93, inner)).decode('ascii')
        return quote(encoded)

    @staticmethod
    def build_hashtag_shorts_payload(
        hashtag: str,
        continuation: str | None = None,
    ) -> dict:
        """Build payload for browsing the Shorts tab of a hashtag page."""
        if continuation:
            return InnerTube.build_continuation_payload(continuation)
        return {
            'context': {'client': InnerTube.WEB_CLIENT},
            'browseId': InnerTube.HASHTAG_BROWSE_ID,
            'params': InnerTube.build_hashtag_params(hashtag),
        }

    @staticmethod
    def build_reel_item_payload(video_id: str) -> dict:
        """Build payload for /youtubei/v1/reel/reel_item_watch.

        Returns the Shorts player overlay, which carries the exact comment
        count that the regular watch page only shows abbreviated.
        """
        return {
            'context': {'client': InnerTube.WEB_CLIENT},
            'playerRequest': {'videoId': video_id},
            'params': InnerTube.REEL_ITEM_PARAMS,
            'disablePlayerResponse': True,
        }

    @staticmethod
    def build_reel_sequence_params(video_id: str) -> str:
        """Encode sequence params that start a Shorts sequence at a video.

        Protobuf: {1: video_id, 5: {3: 5}, 10: 25, 13: 0}.
        """
        data = (
            InnerTube._bytes_field(1, video_id.encode('utf-8'))
            + InnerTube._bytes_field(5, InnerTube._varint_field(3, 5))
            + InnerTube._varint_field(10, 25)
            + InnerTube._varint_field(13, 0)
        )
        return quote(base64.b64encode(data).decode('ascii'))

    @staticmethod
    def build_reel_sequence_payload(
        sequence_params: str | None = None,
        continuation: str | None = None,
    ) -> dict:
        """Build payload for /youtubei/v1/reel/reel_watch_sequence."""
        if continuation:
            return InnerTube.build_continuation_payload(continuation)
        return {
            'context': {'client': InnerTube.WEB_CLIENT},
            'sequenceParams': sequence_params,
        }

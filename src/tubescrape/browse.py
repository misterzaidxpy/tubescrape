from __future__ import annotations

import dataclasses
import logging
import re

from tubescrape._http import HTTPClient
from tubescrape._innertube import InnerTube
from tubescrape._parsers import ResponseParser
from tubescrape.exceptions import ChannelNotFoundError
from tubescrape.models import (
    BrowseResult,
    ChannelAbout,
    ChannelPlaylistsResult,
    SearchResult,
    ShortResult,
    ShortsResult,
    VideoResult,
)

logger = logging.getLogger('tubescrape.browse')


class YouTubeBrowse:
    """Browse a YouTube channel's Videos tab via the InnerTube browse API.

    Returns videos in upload-date order (newest first).

    Args:
        http_client: HTTPClient instance for making requests.
    """

    def __init__(self, http_client: HTTPClient):
        self._http = http_client

    def resolve_channel_id(self, handle_or_vanity: str) -> str:
        """Resolve a @handle, /c/Name, or /user/Name to a channel ID.

        Fetches the YouTube page and extracts the canonical channel ID.

        Args:
            handle_or_vanity: A string like '@lexfridman', '/c/ChannelName',
                              or '/user/Username'.

        Returns:
            Channel ID string (UC...).

        Raises:
            ChannelNotFoundError: If the channel cannot be found.
        """
        if handle_or_vanity.startswith('/c/') or handle_or_vanity.startswith('/user/'):
            url = f'https://www.youtube.com{handle_or_vanity}'
        elif handle_or_vanity.startswith('@'):
            url = f'https://www.youtube.com/{handle_or_vanity}'
        else:
            raise ChannelNotFoundError(handle_or_vanity)

        return self._resolve_from_page(url, handle_or_vanity)

    async def aresolve_channel_id(self, handle_or_vanity: str) -> str:
        """Async version of resolve_channel_id."""
        if handle_or_vanity.startswith('/c/') or handle_or_vanity.startswith('/user/'):
            url = f'https://www.youtube.com{handle_or_vanity}'
        elif handle_or_vanity.startswith('@'):
            url = f'https://www.youtube.com/{handle_or_vanity}'
        else:
            raise ChannelNotFoundError(handle_or_vanity)

        return await self._aresolve_from_page(url, handle_or_vanity)

    def _resolve_from_page(self, url: str, original: str) -> str:
        """Fetch a YouTube page and extract the channel ID from meta tags."""
        response = self._http.get(url)
        channel_id = self._extract_channel_id_from_html(response.text)
        if not channel_id:
            raise ChannelNotFoundError(original)
        logger.info('Resolved %r to channel ID: %s', original, channel_id)
        return channel_id

    async def _aresolve_from_page(self, url: str, original: str) -> str:
        """Async version of _resolve_from_page."""
        response = await self._http.aget(url)
        channel_id = self._extract_channel_id_from_html(response.text)
        if not channel_id:
            raise ChannelNotFoundError(original)
        logger.info('Resolved %r to channel ID: %s', original, channel_id)
        return channel_id

    @staticmethod
    def _extract_channel_id_from_html(html: str) -> str | None:
        """Extract channel ID from YouTube page HTML.

        Looks for patterns like:
            <meta itemprop="channelId" content="UCxxxxxx">
            "externalId":"UCxxxxxx"
            "channelId":"UCxxxxxx"

        externalId is preferred over channelId because channelId can match
        related/featured channels (e.g. gridChannelRenderer items) that
        appear earlier in the page source.
        """
        # Meta tag
        match = re.search(
            r'<meta\s+itemprop="channelId"\s+content="(UC[A-Za-z0-9_-]{22})"',
            html,
        )
        if match:
            return match.group(1)

        # externalId is the page's own channel ID (most reliable in JSON)
        match = re.search(r'"externalId"\s*:\s*"(UC[A-Za-z0-9_-]{22})"', html)
        if match:
            return match.group(1)

        # Fallback: channelId in channelMetadataRenderer context
        match = re.search(
            r'"channelMetadataRenderer"\s*:\s*\{[^}]*"channelId"\s*:\s*"(UC[A-Za-z0-9_-]{22})"',
            html,
        )
        if match:
            return match.group(1)

        # Last resort: any channelId (may match related channels)
        match = re.search(r'"channelId"\s*:\s*"(UC[A-Za-z0-9_-]{22})"', html)
        if match:
            return match.group(1)

        return None

    def get_channel_videos(
        self,
        channel_id: str,
        max_results: int = 30,
    ) -> BrowseResult:
        """Get videos from a channel's Videos tab.

        Args:
            channel_id: YouTube channel ID (e.g. 'UCmeeY9kzNswUpbYyJntb3Aw').
            max_results: Maximum number of videos to return. Use 0 for all.

        Returns:
            BrowseResult containing the channel's videos.
        """
        all_videos: list[VideoResult] = []

        payload = InnerTube.build_browse_payload(channel_id)
        response = self._http.post(
            InnerTube.BROWSE_URL,
            json=payload,
            params={'prettyPrint': 'false'},
        )
        data = response.json()

        channel_name = ResponseParser.extract_channel_name(data)
        videos, continuation = ResponseParser.parse_browse_first_page(data, channel_id)
        all_videos.extend(videos)
        page = 1
        logger.info(
            '[page %d] %d videos fetched (total: %d)',
            page, len(videos), len(all_videos),
        )

        while continuation:
            if max_results > 0 and len(all_videos) >= max_results:
                all_videos = all_videos[:max_results]
                break

            page += 1
            payload = InnerTube.build_browse_payload(channel_id, continuation=continuation)

            try:
                response = self._http.post(
                    InnerTube.BROWSE_URL,
                    json=payload,
                    params={'prettyPrint': 'false'},
                )
                data = response.json()
            except Exception as exc:
                logger.warning('[page %d] Browse continuation failed: %s', page, exc)
                break

            videos, continuation = ResponseParser.parse_browse_continuation(data)
            if not videos:
                logger.info('[page %d] No more videos, stopping', page)
                break

            all_videos.extend(videos)
            logger.info(
                '[page %d] %d videos fetched (total: %d)',
                page, len(videos), len(all_videos),
            )

        if max_results > 0:
            all_videos = all_videos[:max_results]

        logger.info(
            'Browse complete: %d pages, %d total videos', page, len(all_videos),
        )

        # Fill in channel name/id on videos where missing (lockupViewModel
        # format does not include per-video channel info).
        if channel_name or channel_id:
            all_videos = [
                dataclasses.replace(
                    v,
                    channel=v.channel or channel_name or '',
                    channel_id=v.channel_id or channel_id,
                ) if not v.channel or not v.channel_id else v
                for v in all_videos
            ]

        return BrowseResult(
            channel_id=channel_id, channel=channel_name, videos=all_videos,
        )

    # ── Streams (Live) ──

    def get_channel_streams(
        self,
        channel_id: str,
        max_results: int = 0,
    ) -> BrowseResult:
        """Get live streams (completed and scheduled) from a channel's Live tab.

        Args:
            channel_id: YouTube channel ID (UC...).
            max_results: Maximum number of streams to return. Use 0 for all.

        Returns:
            BrowseResult containing the channel's live streams.
        """
        all_videos: list[VideoResult] = []

        payload = InnerTube.build_streams_payload(channel_id)
        response = self._http.post(
            InnerTube.BROWSE_URL,
            json=payload,
            params={'prettyPrint': 'false'},
        )
        data = response.json()

        channel_name = ResponseParser.extract_channel_name(data)
        videos, continuation = ResponseParser.parse_browse_first_page(data, channel_id)
        all_videos.extend(videos)
        page = 1
        logger.info(
            '[page %d] %d streams fetched (total: %d)',
            page, len(videos), len(all_videos),
        )

        while continuation:
            if max_results > 0 and len(all_videos) >= max_results:
                all_videos = all_videos[:max_results]
                break

            page += 1
            payload = InnerTube.build_streams_payload(channel_id, continuation=continuation)

            try:
                response = self._http.post(
                    InnerTube.BROWSE_URL,
                    json=payload,
                    params={'prettyPrint': 'false'},
                )
                data = response.json()
            except Exception as exc:
                logger.warning('[page %d] Streams continuation failed: %s', page, exc)
                break

            videos, continuation = ResponseParser.parse_browse_continuation(data)
            if not videos:
                logger.info('[page %d] No more streams, stopping', page)
                break

            all_videos.extend(videos)
            logger.info(
                '[page %d] %d streams fetched (total: %d)',
                page, len(videos), len(all_videos),
            )

        if max_results > 0:
            all_videos = all_videos[:max_results]

        logger.info(
            'Streams complete: %d pages, %d total streams', page, len(all_videos),
        )

        if channel_name or channel_id:
            all_videos = [
                dataclasses.replace(
                    v,
                    channel=v.channel or channel_name or '',
                    channel_id=v.channel_id or channel_id,
                ) if not v.channel or not v.channel_id else v
                for v in all_videos
            ]

        return BrowseResult(
            channel_id=channel_id, channel=channel_name, videos=all_videos,
        )

    async def aget_channel_streams(
        self,
        channel_id: str,
        max_results: int = 0,
    ) -> BrowseResult:
        """Async version of get_channel_streams."""
        all_videos: list[VideoResult] = []

        payload = InnerTube.build_streams_payload(channel_id)
        response = await self._http.apost(
            InnerTube.BROWSE_URL,
            json=payload,
            params={'prettyPrint': 'false'},
        )
        data = response.json()

        channel_name = ResponseParser.extract_channel_name(data)
        videos, continuation = ResponseParser.parse_browse_first_page(data, channel_id)
        all_videos.extend(videos)
        page = 1

        while continuation:
            if max_results > 0 and len(all_videos) >= max_results:
                all_videos = all_videos[:max_results]
                break

            page += 1
            payload = InnerTube.build_streams_payload(channel_id, continuation=continuation)

            try:
                response = await self._http.apost(
                    InnerTube.BROWSE_URL,
                    json=payload,
                    params={'prettyPrint': 'false'},
                )
                data = response.json()
            except Exception as exc:
                logger.warning('[page %d] Streams continuation failed: %s', page, exc)
                break

            videos, continuation = ResponseParser.parse_browse_continuation(data)
            if not videos:
                break

            all_videos.extend(videos)

        if max_results > 0:
            all_videos = all_videos[:max_results]

        if channel_name or channel_id:
            all_videos = [
                dataclasses.replace(
                    v,
                    channel=v.channel or channel_name or '',
                    channel_id=v.channel_id or channel_id,
                ) if not v.channel or not v.channel_id else v
                for v in all_videos
            ]

        return BrowseResult(
            channel_id=channel_id, channel=channel_name, videos=all_videos,
        )

    # ── Shorts ──

    SHORTS_SORT_ORDERS: tuple[str, ...] = ('latest', 'popular', 'oldest')

    def get_channel_shorts(
        self, channel_id: str, max_results: int = 0, sort_by: str = 'latest',
    ) -> ShortsResult:
        """Get Shorts from a channel's Shorts tab.

        Args:
            channel_id: YouTube channel ID (UC...).
            max_results: Maximum number of shorts to return. Use 0 for all.
            sort_by: 'latest' (default), 'popular' or 'oldest'.

        Returns:
            ShortsResult containing the channel's shorts.
        """
        sort_by = self._check_shorts_sort(sort_by)
        payload = InnerTube.build_shorts_payload(channel_id)
        response = self._http.post(
            InnerTube.BROWSE_URL, json=payload,
            params={'prettyPrint': 'false'},
        )
        shorts, continuation, sort_tokens = ResponseParser.parse_shorts_page(response.json())

        if sort_by != 'latest':
            token = sort_tokens.get(sort_by)
            if not token:
                logger.warning('Shorts: no %r sort available for %s', sort_by, channel_id)
                return ShortsResult(channel_id=channel_id)
            # Switching the order reloads the grid from the first item.
            shorts, continuation = [], token

        page = 1
        while continuation:
            if max_results > 0 and len(shorts) >= max_results:
                break
            page += 1
            try:
                response = self._http.post(
                    InnerTube.BROWSE_URL,
                    json=InnerTube.build_continuation_payload(continuation),
                    params={'prettyPrint': 'false'},
                )
                more, continuation = ResponseParser.parse_shorts_continuation(response.json())
            except Exception as exc:
                logger.warning('[page %d] Shorts continuation failed: %s', page, exc)
                break
            if not more:
                break
            shorts.extend(more)

        if max_results > 0:
            shorts = shorts[:max_results]
        logger.info('Shorts: %d shorts fetched for %s (%s)', len(shorts), channel_id, sort_by)
        return ShortsResult(channel_id=channel_id, shorts=shorts)

    async def aget_channel_shorts(
        self, channel_id: str, max_results: int = 0, sort_by: str = 'latest',
    ) -> ShortsResult:
        """Async version of get_channel_shorts."""
        sort_by = self._check_shorts_sort(sort_by)
        payload = InnerTube.build_shorts_payload(channel_id)
        response = await self._http.apost(
            InnerTube.BROWSE_URL, json=payload,
            params={'prettyPrint': 'false'},
        )
        shorts, continuation, sort_tokens = ResponseParser.parse_shorts_page(response.json())

        if sort_by != 'latest':
            token = sort_tokens.get(sort_by)
            if not token:
                logger.warning('Shorts: no %r sort available for %s', sort_by, channel_id)
                return ShortsResult(channel_id=channel_id)
            shorts, continuation = [], token

        page = 1
        while continuation:
            if max_results > 0 and len(shorts) >= max_results:
                break
            page += 1
            try:
                response = await self._http.apost(
                    InnerTube.BROWSE_URL,
                    json=InnerTube.build_continuation_payload(continuation),
                    params={'prettyPrint': 'false'},
                )
                more, continuation = ResponseParser.parse_shorts_continuation(response.json())
            except Exception as exc:
                logger.warning('[page %d] Shorts continuation failed: %s', page, exc)
                break
            if not more:
                break
            shorts.extend(more)

        if max_results > 0:
            shorts = shorts[:max_results]
        return ShortsResult(channel_id=channel_id, shorts=shorts)

    @classmethod
    def _check_shorts_sort(cls, sort_by: str) -> str:
        key = (sort_by or 'latest').lower()
        if key not in cls.SHORTS_SORT_ORDERS:
            valid = ', '.join(cls.SHORTS_SORT_ORDERS)
            raise ValueError(f'Invalid sort_by: {sort_by!r}. Valid: {valid}')
        return key

    # ── Hashtag Shorts ──

    def get_hashtag_shorts(self, hashtag: str, max_results: int = 50) -> list[ShortResult]:
        """Get Shorts from a hashtag page's Shorts tab.

        Args:
            hashtag: Hashtag with or without the leading '#'.
            max_results: Maximum number of shorts to return. Use 0 for all
                         that YouTube serves, which can be thousands.

        Returns:
            List of ShortResult. Empty if the hashtag has no Shorts tab.
        """
        tag = hashtag.strip().lstrip('#')
        response = self._http.post(
            InnerTube.BROWSE_URL,
            json=InnerTube.build_hashtag_shorts_payload(tag),
            params={'prettyPrint': 'false'},
        )
        shorts, continuation, _ = ResponseParser.parse_shorts_page(response.json())

        page = 1
        while continuation:
            if max_results > 0 and len(shorts) >= max_results:
                break
            page += 1
            try:
                response = self._http.post(
                    InnerTube.BROWSE_URL,
                    json=InnerTube.build_continuation_payload(continuation),
                    params={'prettyPrint': 'false'},
                )
                more, continuation = ResponseParser.parse_shorts_continuation(response.json())
            except Exception as exc:
                logger.warning('[page %d] Hashtag continuation failed: %s', page, exc)
                break
            if not more:
                break
            shorts.extend(more)

        if max_results > 0:
            shorts = shorts[:max_results]
        logger.info('Hashtag: %d shorts fetched for #%s', len(shorts), tag)
        return shorts

    async def aget_hashtag_shorts(self, hashtag: str, max_results: int = 50) -> list[ShortResult]:
        """Async version of get_hashtag_shorts."""
        tag = hashtag.strip().lstrip('#')
        response = await self._http.apost(
            InnerTube.BROWSE_URL,
            json=InnerTube.build_hashtag_shorts_payload(tag),
            params={'prettyPrint': 'false'},
        )
        shorts, continuation, _ = ResponseParser.parse_shorts_page(response.json())

        page = 1
        while continuation:
            if max_results > 0 and len(shorts) >= max_results:
                break
            page += 1
            try:
                response = await self._http.apost(
                    InnerTube.BROWSE_URL,
                    json=InnerTube.build_continuation_payload(continuation),
                    params={'prettyPrint': 'false'},
                )
                more, continuation = ResponseParser.parse_shorts_continuation(response.json())
            except Exception as exc:
                logger.warning('[page %d] Hashtag continuation failed: %s', page, exc)
                break
            if not more:
                break
            shorts.extend(more)

        if max_results > 0:
            shorts = shorts[:max_results]
        return shorts

    # ── Channel Playlists ──

    def get_channel_playlists(self, channel_id: str) -> ChannelPlaylistsResult:
        """Get playlists from a channel's Playlists tab.

        Args:
            channel_id: YouTube channel ID (UC...).

        Returns:
            ChannelPlaylistsResult containing the channel's playlists.
        """
        payload = InnerTube.build_playlists_tab_payload(channel_id)
        response = self._http.post(
            InnerTube.BROWSE_URL, json=payload,
            params={'prettyPrint': 'false'},
        )
        data = response.json()
        result = ResponseParser.parse_channel_playlists_tab(data, channel_id)
        logger.info(
            'Playlists: %d playlists fetched for %s',
            len(result.playlists), channel_id,
        )
        return result

    async def aget_channel_playlists(self, channel_id: str) -> ChannelPlaylistsResult:
        """Async version of get_channel_playlists."""
        payload = InnerTube.build_playlists_tab_payload(channel_id)
        response = await self._http.apost(
            InnerTube.BROWSE_URL, json=payload,
            params={'prettyPrint': 'false'},
        )
        data = response.json()
        return ResponseParser.parse_channel_playlists_tab(data, channel_id)

    # ── Channel About ──

    def get_channel_about(self, channel_id: str, handle: str | None = None) -> ChannelAbout:
        """Get channel about/info page data.

        Fetches the channel's /about HTML page and extracts the
        aboutChannelViewModel data (description, country, links, etc.).

        Args:
            channel_id: YouTube channel ID (UC...).
            handle: Optional @handle or vanity URL for the page fetch.
                    If not provided, uses the channel ID URL.

        Returns:
            ChannelAbout with description, country, links, stats, etc.
        """
        if handle:
            if handle.startswith('@'):
                url = f'https://www.youtube.com/{handle}/about'
            else:
                url = f'https://www.youtube.com/channel/{channel_id}/about'
        else:
            url = f'https://www.youtube.com/channel/{channel_id}/about'

        response = self._http.get(url)
        result = ResponseParser.parse_channel_about(response.text, channel_id)
        logger.info(
            'About: %s (%s), %d links',
            channel_id, result.country or 'no country', len(result.links),
        )
        return result

    async def aget_channel_about(
        self, channel_id: str, handle: str | None = None,
    ) -> ChannelAbout:
        """Async version of get_channel_about."""
        if handle:
            if handle.startswith('@'):
                url = f'https://www.youtube.com/{handle}/about'
            else:
                url = f'https://www.youtube.com/channel/{channel_id}/about'
        else:
            url = f'https://www.youtube.com/channel/{channel_id}/about'

        response = await self._http.aget(url)
        return ResponseParser.parse_channel_about(response.text, channel_id)

    # ── Channel Search ──

    def search_channel(self, channel_id: str, query: str) -> SearchResult:
        """Search within a channel's videos.

        Args:
            channel_id: YouTube channel ID (UC...).
            query: Search query string.

        Returns:
            SearchResult containing matched videos.
        """
        payload = InnerTube.build_channel_search_payload(channel_id, query)
        response = self._http.post(
            InnerTube.BROWSE_URL, json=payload,
            params={'prettyPrint': 'false'},
        )
        data = response.json()
        result = ResponseParser.parse_channel_search(data, channel_id, query)
        logger.info(
            'Channel search %r: %d videos found in %s',
            query, len(result.videos), channel_id,
        )
        return result

    async def asearch_channel(self, channel_id: str, query: str) -> SearchResult:
        """Async version of search_channel."""
        payload = InnerTube.build_channel_search_payload(channel_id, query)
        response = await self._http.apost(
            InnerTube.BROWSE_URL, json=payload,
            params={'prettyPrint': 'false'},
        )
        data = response.json()
        return ResponseParser.parse_channel_search(data, channel_id, query)

    async def aget_channel_videos(
        self,
        channel_id: str,
        max_results: int = 30,
    ) -> BrowseResult:
        """Async version of get_channel_videos."""
        all_videos: list[VideoResult] = []

        payload = InnerTube.build_browse_payload(channel_id)
        response = await self._http.apost(
            InnerTube.BROWSE_URL,
            json=payload,
            params={'prettyPrint': 'false'},
        )
        data = response.json()

        channel_name = ResponseParser.extract_channel_name(data)
        videos, continuation = ResponseParser.parse_browse_first_page(data, channel_id)
        all_videos.extend(videos)
        page = 1

        while continuation:
            if max_results > 0 and len(all_videos) >= max_results:
                all_videos = all_videos[:max_results]
                break

            page += 1
            payload = InnerTube.build_browse_payload(channel_id, continuation=continuation)

            try:
                response = await self._http.apost(
                    InnerTube.BROWSE_URL,
                    json=payload,
                    params={'prettyPrint': 'false'},
                )
                data = response.json()
            except Exception as exc:
                logger.warning('[page %d] Browse continuation failed: %s', page, exc)
                break

            videos, continuation = ResponseParser.parse_browse_continuation(data)
            if not videos:
                break

            all_videos.extend(videos)

        if max_results > 0:
            all_videos = all_videos[:max_results]

        if channel_name or channel_id:
            all_videos = [
                dataclasses.replace(
                    v,
                    channel=v.channel or channel_name or '',
                    channel_id=v.channel_id or channel_id,
                ) if not v.channel or not v.channel_id else v
                for v in all_videos
            ]

        return BrowseResult(
            channel_id=channel_id, channel=channel_name, videos=all_videos,
        )

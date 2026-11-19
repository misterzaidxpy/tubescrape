from __future__ import annotations

import pytest

from tubescrape._filters import SearchFilter
from tubescrape._innertube import InnerTube
from tubescrape._parsers import ResponseParser
from tubescrape._utils import TextParser
from tubescrape.browse import YouTubeBrowse
from tubescrape.models import ShortResult, VideoInfo, VideoResult
from tubescrape.search import YouTubeSearch
from tubescrape.transcript import YouTubeTranscript


def make_lockup(video_id: str, title: str = 'A Short', views: str = '10K views', **extra) -> dict:
    lockup = {
        'accessibilityText': f'{title}, {views.replace("K", " thousand")} - play Short',
        'onTap': {
            'innertubeCommand': {
                'reelWatchEndpoint': {'videoId': video_id, 'sequenceParams': 'SEQ-' + video_id},
            }
        },
        'overlayMetadata': {
            'primaryText': {'content': title},
            'secondaryText': {'content': views},
        },
    }
    lockup.update(extra)
    return lockup


def rich_item(video_id: str, **kwargs) -> dict:
    return {'richItemRenderer': {'content': {'shortsLockupViewModel': make_lockup(video_id, **kwargs)}}}


def continuation_item(token: str) -> dict:
    return {
        'continuationItemRenderer': {
            'continuationEndpoint': {'continuationCommand': {'token': token}},
        }
    }


def chip(text: str, token: str) -> dict:
    return {
        'chipViewModel': {
            'text': text,
            'tapCommand': {'innertubeCommand': {'continuationCommand': {'token': token}}},
        }
    }


def shorts_tab(items: list[dict], chips: list[dict] | None = None) -> dict:
    grid: dict = {'contents': items}
    if chips is not None:
        grid['header'] = {'chipBarViewModel': {'chips': chips}}
    return {
        'contents': {
            'twoColumnBrowseResultsRenderer': {
                'tabs': [
                    {'tabRenderer': {'selected': False, 'content': {}}},
                    {'tabRenderer': {'selected': True, 'content': {'richGridRenderer': grid}}},
                ]
            }
        }
    }


def append_page(items: list[dict]) -> dict:
    return {'onResponseReceivedActions': [{'appendContinuationItemsAction': {'continuationItems': items}}]}


def reload_page(items: list[dict]) -> dict:
    return {
        'onResponseReceivedActions': [
            {'reloadContinuationItemsCommand': {
                'slot': 'RELOAD_CONTINUATION_SLOT_HEADER',
                'continuationItems': [{'chipBarViewModel': {}}],
            }},
            {'reloadContinuationItemsCommand': {
                'slot': 'RELOAD_CONTINUATION_SLOT_BODY',
                'continuationItems': items,
            }},
        ]
    }


def player_response(video_id: str = 'vid00000001', **microformat) -> dict:
    mf = {
        'publishDate': '2026-11-13T09:00:00-08:00',
        'uploadDate': '2026-11-13T09:00:00-08:00',
        'viewCount': '27405401',
        'likeCount': '380165',
        'category': 'Entertainment',
        'isShortsEligible': True,
    }
    mf.update(microformat)
    return {
        'videoDetails': {
            'videoId': video_id, 'title': 'T', 'author': 'Chan', 'channelId': 'UC1',
            'shortDescription': '', 'viewCount': '27383337', 'lengthSeconds': '28',
        },
        'microformat': {'playerMicroformatRenderer': mf},
    }


def reel_item(comments: str = 'View 10,009 comments', likes: str = '380,191 likes') -> dict:
    return {
        'overlay': {'reelPlayerOverlayRenderer': {'playerOverlay': {'reelPlayerOverlayViewModel': {
            'actionBar': {'reelActionBarViewModel': {'buttonViewModels': [
                {'likeButtonViewModel': {'toggledButtonViewModel': {'buttonViewModel': {
                    'accessibilityId': 'id.reel_like_toggled_button', 'accessibilityText': likes,
                }}}},
                {'buttonViewModel': {
                    'accessibilityId': 'id.reel_comment_button', 'title': '10K',
                    'accessibilityText': comments,
                }},
            ]}},
        }}}},
    }


class FakeResponse:
    def __init__(self, data: dict):
        self._data = data

    def json(self) -> dict:
        return self._data


class FakeHTTP:
    """Replays queued responses and records the payloads that were sent."""

    def __init__(self, responses: list):
        self.responses = list(responses)
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, json: dict | None = None, **kwargs) -> FakeResponse:
        self.calls.append((url, json or {}))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)

    async def apost(self, url: str, json: dict | None = None, **kwargs) -> FakeResponse:
        return self.post(url, json=json, **kwargs)


class TestParseCount:
    @pytest.mark.parametrize(('text', 'unit', 'expected'), [
        ('27M views', 'view', 27_000_000),
        ('1.2K views', 'view', 1_200),
        ('280 thousand views', 'view', 280_000),
        ('26,315,361 views', 'view', 26_315_361),
        ('1 view', 'view', 1),
        ('No views', 'view', 0),
        ('View 10,009 comments', 'comment', 10_009),
        ('380,191 likes', 'like', 380_191),
        ('2.5 lakh views', 'view', 250_000),
        ('1.1B views', 'view', 1_100_000_000),
        ('2.4M', None, 2_400_000),
        ('10K', None, 10_000),
        ('537', None, 537),
    ])
    def test_values(self, text, unit, expected):
        assert TextParser.parse_count(text, unit=unit) == expected

    def test_unit_ignores_numbers_in_the_title(self):
        text = 'Top 10 cats of 2026, 27 million views - play Short'
        assert TextParser.parse_count(text, unit='view') == 27_000_000

    @pytest.mark.parametrize('text', [None, '', 'views', 'no numbers here'])
    def test_no_number(self, text):
        assert TextParser.parse_count(text) is None
        assert TextParser.parse_count(text, unit='view') is None


class TestShortLockup:
    def test_views_and_sequence_params(self):
        short = ResponseParser._parse_short_lockup(make_lockup('abc', views='27M views'))
        assert short.view_count == '27M views'
        assert short.views == 27_000_000
        assert short.sequence_params == 'SEQ-abc'
        assert short.to_dict()['views'] == 27_000_000

    def test_title_and_views_from_accessibility_text(self):
        # Hashtag and sound pages have no overlayMetadata.primaryText.
        lockup = {
            'accessibilityText': 'DO NOT CROSS! #shorts #roblox, 23 million views - play Short',
            'onTap': {'innertubeCommand': {'reelWatchEndpoint': {'videoId': 'h1'}}},
            'overlayMetadata': {},
        }
        short = ResponseParser._parse_short_lockup(lockup)
        assert short.title == 'DO NOT CROSS! #shorts #roblox'
        assert short.views == 23_000_000
        assert short.sequence_params is None

    def test_no_view_text(self):
        lockup = {'onTap': {'innertubeCommand': {'reelWatchEndpoint': {'videoId': 'x'}}}}
        short = ResponseParser._parse_short_lockup(lockup)
        assert short.views is None
        assert 'views' not in short.to_dict()

    def test_sequence_params_hidden_from_repr(self):
        assert 'sequence_params' not in repr(ShortResult(video_id='a', title='t', sequence_params='x'))


class TestShortsPage:
    def test_first_page_with_continuation_and_sort_tokens(self):
        data = shorts_tab(
            [rich_item('a'), rich_item('b'), continuation_item('NEXT')],
            chips=[chip('Latest', 'T-LATEST'), chip('Popular', 'T-POP'), chip('Oldest', 'T-OLD')],
        )
        shorts, continuation, sort_tokens = ResponseParser.parse_shorts_page(data)
        assert [s.video_id for s in shorts] == ['a', 'b']
        assert continuation == 'NEXT'
        assert sort_tokens == {'latest': 'T-LATEST', 'popular': 'T-POP', 'oldest': 'T-OLD'}

    def test_last_page_has_no_continuation(self):
        shorts, continuation, sort_tokens = ResponseParser.parse_shorts_page(shorts_tab([rich_item('a')]))
        assert len(shorts) == 1
        assert continuation is None
        assert sort_tokens == {}

    def test_empty_response(self):
        assert ResponseParser.parse_shorts_page({}) == ([], None, {})

    def test_parse_shorts_tab_is_unchanged(self):
        result = ResponseParser.parse_shorts_tab(shorts_tab([rich_item('a'), continuation_item('N')]), 'UC1')
        assert result.channel_id == 'UC1'
        assert [s.video_id for s in result.shorts] == ['a']

    def test_append_continuation(self):
        shorts, continuation = ResponseParser.parse_shorts_continuation(
            append_page([rich_item('c'), rich_item('d'), continuation_item('MORE')]),
        )
        assert [s.video_id for s in shorts] == ['c', 'd']
        assert continuation == 'MORE'

    def test_reload_continuation_from_sort(self):
        shorts, continuation = ResponseParser.parse_shorts_continuation(
            reload_page([rich_item('p1'), rich_item('p2'), continuation_item('P-NEXT')]),
        )
        assert [s.video_id for s in shorts] == ['p1', 'p2']
        assert continuation == 'P-NEXT'

    def test_empty_continuation(self):
        assert ResponseParser.parse_shorts_continuation({}) == ([], None)
        assert ResponseParser.parse_shorts_continuation(append_page([])) == ([], None)


class TestChannelShorts:
    def test_pages_until_no_continuation(self):
        http = FakeHTTP([
            shorts_tab([rich_item('a'), rich_item('b'), continuation_item('P2')]),
            append_page([rich_item('c'), continuation_item('P3')]),
            append_page([rich_item('d')]),
        ])
        result = YouTubeBrowse(http).get_channel_shorts('UC1')
        assert [s.video_id for s in result.shorts] == ['a', 'b', 'c', 'd']
        assert http.calls[1][1]['continuation'] == 'P2'
        assert http.calls[2][1]['continuation'] == 'P3'
        assert len(http.calls) == 3

    def test_max_results_stops_paging(self):
        http = FakeHTTP([
            shorts_tab([rich_item('a'), rich_item('b'), continuation_item('P2')]),
            append_page([rich_item('c'), rich_item('d'), continuation_item('P3')]),
        ])
        result = YouTubeBrowse(http).get_channel_shorts('UC1', max_results=3)
        assert [s.video_id for s in result.shorts] == ['a', 'b', 'c']
        assert len(http.calls) == 2

    def test_max_results_within_first_page_makes_one_request(self):
        http = FakeHTTP([shorts_tab([rich_item('a'), rich_item('b'), continuation_item('P2')])])
        result = YouTubeBrowse(http).get_channel_shorts('UC1', max_results=1)
        assert [s.video_id for s in result.shorts] == ['a']
        assert len(http.calls) == 1

    def test_sort_popular_sends_the_chip_token(self):
        http = FakeHTTP([
            shorts_tab([rich_item('new1'), continuation_item('P2')],
                       chips=[chip('Latest', 'T-LATEST'), chip('Popular', 'T-POP')]),
            reload_page([rich_item('top1'), rich_item('top2'), continuation_item('POP2')]),
        ])
        result = YouTubeBrowse(http).get_channel_shorts('UC1', max_results=2, sort_by='popular')
        assert [s.video_id for s in result.shorts] == ['top1', 'top2']
        assert http.calls[1][1]['continuation'] == 'T-POP'

    def test_sort_not_offered_returns_empty(self):
        http = FakeHTTP([shorts_tab([rich_item('a')])])
        result = YouTubeBrowse(http).get_channel_shorts('UC1', sort_by='popular')
        assert result.shorts == []
        assert len(http.calls) == 1

    def test_invalid_sort_raises(self):
        with pytest.raises(ValueError, match='Invalid sort_by'):
            YouTubeBrowse(FakeHTTP([])).get_channel_shorts('UC1', sort_by='random')

    def test_failed_page_keeps_what_was_collected(self):
        http = FakeHTTP([
            shorts_tab([rich_item('a'), continuation_item('P2')]),
            RuntimeError('boom'),
        ])
        result = YouTubeBrowse(http).get_channel_shorts('UC1')
        assert [s.video_id for s in result.shorts] == ['a']

    async def test_async_matches_sync(self):
        http = FakeHTTP([
            shorts_tab([rich_item('a'), continuation_item('P2')], chips=[chip('Oldest', 'T-OLD')]),
            reload_page([rich_item('o1'), continuation_item('O2')]),
            append_page([rich_item('o2')]),
        ])
        result = await YouTubeBrowse(http).aget_channel_shorts('UC1', sort_by='oldest')
        assert [s.video_id for s in result.shorts] == ['o1', 'o2']
        assert http.calls[1][1]['continuation'] == 'T-OLD'


class TestHashtagShorts:
    def test_params_match_youtube(self):
        # Value returned by navigation/resolve_url for /hashtag/minecraft/shorts.
        assert InnerTube.build_hashtag_params('minecraft') == '6gUNCgltaW5lY3JhZnQYAw%3D%3D'

    def test_request_and_paging(self):
        http = FakeHTTP([
            shorts_tab([rich_item('a'), continuation_item('H2')]),
            append_page([rich_item('b')]),
        ])
        shorts = YouTubeBrowse(http).get_hashtag_shorts('#Minecraft', max_results=0)
        assert [s.video_id for s in shorts] == ['a', 'b']
        first = http.calls[0][1]
        assert first['browseId'] == 'FEhashtag'
        assert first['params'] == InnerTube.build_hashtag_params('Minecraft')

    def test_empty_continuation_stops(self):
        http = FakeHTTP([shorts_tab([rich_item('a'), continuation_item('H2')]), append_page([])])
        shorts = YouTubeBrowse(http).get_hashtag_shorts('tag')
        assert [s.video_id for s in shorts] == ['a']

    def test_unknown_hashtag_returns_empty(self):
        assert YouTubeBrowse(FakeHTTP([{}])).get_hashtag_shorts('nothing') == []

    async def test_async(self):
        http = FakeHTTP([shorts_tab([rich_item('a'), rich_item('b')])])
        shorts = await YouTubeBrowse(http).aget_hashtag_shorts('tag', max_results=1)
        assert [s.video_id for s in shorts] == ['a']


class TestShortsSearch:
    def test_filter_value(self):
        assert SearchFilter.build(type='short') == 'EgIQCQ=='
        assert SearchFilter.build(type='shorts') == 'EgIQCQ=='

    def test_shelf_rows_get_integer_views(self):
        shelf = {'gridShelfViewModel': {'contents': [
            {'shortsLockupViewModel': make_lockup('s1', views='280K views')},
        ]}}
        videos = ResponseParser._extract_shorts_from_shelf(shelf)
        assert videos[0].is_short is True
        assert videos[0].views == 280_000
        assert videos[0].view_count == '280K views'

    def test_unique_videos(self):
        def row(video_id: str) -> VideoResult:
            return VideoResult(
                video_id=video_id, title='', channel='', channel_id=None, duration=None,
                duration_seconds=0, published_text=None, url='',
            )

        existing = [row('a'), row('b')]
        unique = YouTubeSearch._unique_videos(existing, [row('b'), row('c'), row('c'), row('d')])
        assert [v.video_id for v in unique] == ['c', 'd']

    def test_regular_video_row_gets_integer_views(self):
        renderer = {
            'videoId': 'v1',
            'title': {'runs': [{'text': 'T'}]},
            'viewCountText': {'simpleText': '26,315,361 views'},
        }
        video = ResponseParser.extract_video_renderer(renderer)
        assert video.views == 26_315_361
        assert video.to_dict()['views'] == 26_315_361


class TestVideoDetails:
    def test_exact_likes_short_flag_and_utc_date(self):
        info = ResponseParser.parse_video_details(player_response())
        assert info.likes == 380_165
        assert info.is_short is True
        assert info.publish_date == '2026-11-13T09:00:00-08:00'
        assert info.publish_date_utc == '2026-11-13T17:00:00Z'
        assert info.view_count == 27_383_337
        data = info.to_dict()
        assert data['likes'] == 380_165
        assert data['is_short'] is True
        assert data['publish_date_utc'] == '2026-11-13T17:00:00Z'

    def test_view_count_falls_back_to_microformat(self):
        data = player_response()
        del data['videoDetails']['viewCount']
        assert ResponseParser.parse_video_details(data).view_count == 27_405_401

    def test_missing_microformat(self):
        data = player_response()
        del data['microformat']
        info = ResponseParser.parse_video_details(data)
        assert info.likes is None
        assert info.is_short is None
        assert info.publish_date_utc is None
        assert 'likes' not in info.to_dict()

    def test_regular_video_is_not_a_short(self):
        info = ResponseParser.parse_video_details(player_response(isShortsEligible=False))
        assert info.is_short is False

    @pytest.mark.parametrize(('value', 'expected'), [
        ('2026-11-13T09:00:00-08:00', '2026-11-13T17:00:00Z'),
        ('2026-01-01T00:30:00+05:00', '2025-12-31T19:30:00Z'),
        ('2026-11-13', None),
        ('2026-11-13T09:00:00', None),
        ('garbage', None),
        (None, None),
    ])
    def test_to_utc(self, value, expected):
        assert ResponseParser._to_utc(value) == expected


class TestReelItem:
    def test_exact_counts(self):
        assert ResponseParser.parse_reel_item(reel_item()) == {'comment_count': 10_009, 'likes': 380_191}

    def test_comments_turned_off_or_missing(self):
        assert ResponseParser.parse_reel_item({}) == {}
        assert ResponseParser.parse_reel_item(reel_item(comments='Comments are turned off')) == {'likes': 380_191}


class TestVideoInfoForShorts:
    @staticmethod
    def next_response(comment_text: str | None) -> dict:
        panels = []
        if comment_text is not None:
            panels.append({'engagementPanelSectionListRenderer': {
                'panelIdentifier': 'engagement-panel-comments-section',
                'header': {'engagementPanelTitleHeaderRenderer': {
                    'contextualInfo': {'runs': [{'text': comment_text}]},
                }},
            }})
        return {
            'contents': {'twoColumnWatchNextResults': {'results': {'results': {'contents': []}}}},
            'engagementPanels': panels,
        }

    def test_short_gets_exact_comment_count_from_reel_endpoint(self):
        http = FakeHTTP([player_response('s1'), self.next_response('10K'), reel_item()])
        info = YouTubeTranscript(http).get_video_info('s1')
        assert info.comment_count == 10_009
        assert info.likes == 380_165
        assert http.calls[2][0] == InnerTube.REEL_ITEM_URL
        assert http.calls[2][1]['playerRequest'] == {'videoId': 's1'}

    def test_short_with_exact_count_skips_reel_endpoint(self):
        http = FakeHTTP([player_response('s1'), self.next_response('537')])
        info = YouTubeTranscript(http).get_video_info('s1')
        assert info.comment_count == 537
        assert len(http.calls) == 2

    def test_regular_video_keeps_approximate_count_without_reel_call(self):
        http = FakeHTTP([player_response('v1', isShortsEligible=False), self.next_response('2.4M')])
        info = YouTubeTranscript(http).get_video_info('v1')
        assert info.comment_count == 2_400_000
        assert len(http.calls) == 2

    def test_reel_failure_keeps_the_rest(self):
        http = FakeHTTP([player_response('s1'), self.next_response(None), RuntimeError('boom')])
        info = YouTubeTranscript(http).get_video_info('s1')
        assert info.comment_count is None
        assert info.likes == 380_165

    def test_enrich_false_is_one_request(self):
        http = FakeHTTP([player_response('s1')])
        info = YouTubeTranscript(http).get_video_info('s1', enrich=False)
        assert info.is_short is True
        assert len(http.calls) == 1

    async def test_async_short(self):
        http = FakeHTTP([player_response('s1'), self.next_response('10K'), reel_item()])
        info = await YouTubeTranscript(http).aget_video_info('s1')
        assert info.comment_count == 10_009


class TestBulkVideoInfo:
    def test_keeps_order_and_marks_failures(self):
        class Stub(YouTubeTranscript):
            def get_video_info(self, video_id: str, enrich: bool = True):
                if video_id == 'bad':
                    raise RuntimeError('boom')
                return ResponseParser.parse_video_details(player_response(video_id))

        infos = Stub(FakeHTTP([])).get_videos_info(['a', 'bad', 'c'], concurrency=3)
        assert [i.video_id if i else None for i in infos] == ['a', None, 'c']

    def test_empty_input(self):
        assert YouTubeTranscript(FakeHTTP([])).get_videos_info([]) == []

    async def test_async_keeps_order(self):
        class Stub(YouTubeTranscript):
            async def aget_video_info(self, video_id: str, enrich: bool = True):
                if video_id == 'bad':
                    raise RuntimeError('boom')
                return ResponseParser.parse_video_details(player_response(video_id))

        infos = await Stub(FakeHTTP([])).aget_videos_info(['a', 'bad', 'c'], concurrency=2)
        assert [i.video_id if i else None for i in infos] == ['a', None, 'c']


def sequence_entry(video_id: str, with_views: bool = False) -> dict:
    player = player_response(video_id)
    if not with_views:
        # Prefetched player responses have no videoDetails.viewCount.
        del player['videoDetails']['viewCount']
    return {'command': {'reelWatchEndpoint': {
        'videoId': video_id,
        'unserializedPrefetchData': {'playerResponse': player, 'reelItemWatchResponse': reel_item()},
    }}}


def sequence_page(ids: list[str], token: str | None = None) -> dict:
    data: dict = {'entries': [sequence_entry(i) for i in ids]}
    if token:
        data['continuationEndpoint'] = {'continuationCommand': {'token': token}}
    return data


class TestReelSequence:
    def test_sequence_params_encoding(self):
        assert InnerTube.build_reel_sequence_params('sHpEqeSByPI') == 'CgtzSHBFcWVTQnlQSSoCGAVQGWgA'

    def test_parse_entries(self):
        videos, continuation = ResponseParser.parse_reel_sequence(sequence_page(['a', 'b'], token='NEXT'))
        assert [v.video_id for v in videos] == ['a', 'b']
        assert continuation == 'NEXT'
        first = videos[0]
        assert isinstance(first, VideoInfo)
        assert first.view_count == 27_405_401
        assert first.likes == 380_165
        assert first.comment_count == 10_009
        assert first.publish_date_utc == '2026-11-13T17:00:00Z'

    def test_parse_skips_entries_without_player_data(self):
        data = {'entries': [{'command': {'reelWatchEndpoint': {'videoId': 'x'}}}, sequence_entry('ok')]}
        videos, continuation = ResponseParser.parse_reel_sequence(data)
        assert [v.video_id for v in videos] == ['ok']
        assert continuation is None

    def test_follows_continuation_and_drops_the_seed(self):
        http = FakeHTTP([sequence_page(['seed', 'a', 'b'], token='S2'), sequence_page(['b', 'c'])])
        videos = YouTubeTranscript(http).get_related_shorts('seed', max_results=10)
        assert [v.video_id for v in videos] == ['a', 'b', 'c']
        assert http.calls[0][0] == InnerTube.REEL_SEQUENCE_URL
        assert http.calls[0][1]['sequenceParams'] == InnerTube.build_reel_sequence_params('seed')
        assert http.calls[1][1]['continuation'] == 'S2'

    def test_uses_listed_sequence_params(self):
        http = FakeHTTP([sequence_page(['a'])])
        YouTubeTranscript(http).get_related_shorts('seed', sequence_params='FROM-LIST')
        assert http.calls[0][1]['sequenceParams'] == 'FROM-LIST'

    def test_max_results(self):
        http = FakeHTTP([sequence_page(['a', 'b', 'c'], token='S2')])
        videos = YouTubeTranscript(http).get_related_shorts('seed', max_results=2)
        assert [v.video_id for v in videos] == ['a', 'b']
        assert len(http.calls) == 1

    def test_failure_returns_what_was_collected(self):
        http = FakeHTTP([sequence_page(['a'], token='S2'), RuntimeError('boom')])
        videos = YouTubeTranscript(http).get_related_shorts('seed', max_results=10)
        assert [v.video_id for v in videos] == ['a']

    async def test_async(self):
        http = FakeHTTP([sequence_page(['a', 'b'])])
        videos = await YouTubeTranscript(http).aget_related_shorts('seed', max_results=5)
        assert [v.video_id for v in videos] == ['a', 'b']

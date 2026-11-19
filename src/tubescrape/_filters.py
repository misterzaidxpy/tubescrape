from __future__ import annotations

import base64


class SearchFilter:
    """Build protobuf-encoded search filter params from human-readable values.

    YouTube search filters are encoded as base64 protobuf. This class builds
    the binary representation from user-friendly parameters.

    Usage::

        params = SearchFilter.build(
            type='video',
            duration='long',
            upload_date='this_week',
            sort_by='relevance',
        )
        # Returns: base64-encoded protobuf string like 'CAASBAgBGAI%3D'
    """

    # ── Protobuf field numbers and values ──

    # Field 1: Sort by
    SORT_BY: dict[str, int] = {
        'relevance': 0,
        'upload_date': 1,
        'date': 1,
        'view_count': 2,
        'views': 2,
        'rating': 3,
    }

    # Field 2 (nested message, field tag 0x12): Filters
    # Sub-field 1: Upload date
    UPLOAD_DATE: dict[str, int] = {
        'last_hour': 1,
        'hour': 1,
        'today': 2,
        'this_week': 3,
        'week': 3,
        'this_month': 4,
        'month': 4,
        'this_year': 5,
        'year': 5,
    }

    # Sub-field 2: Type
    TYPE: dict[str, int] = {
        'video': 1,
        'channel': 2,
        'playlist': 3,
        'movie': 4,
        'short': 9,
        'shorts': 9,
    }

    # Sub-field 3: Duration
    DURATION: dict[str, int] = {
        'short': 1,        # Under 4 minutes
        'medium': 3,       # 4-20 minutes
        'long': 2,         # Over 20 minutes
    }

    # Sub-field 4: Features (can combine multiple)
    FEATURES: dict[str, int] = {
        'live': 1,
        '4k': 2,
        'hd': 3,
        'subtitles': 4,
        'cc': 4,
        'creative_commons': 5,
        '360': 6,
        'vr180': 7,
        '3d': 8,
        'hdr': 9,
        'location': 10,
        'purchased': 11,
    }

    @classmethod
    def build(
        cls,
        sort_by: str | None = None,
        upload_date: str | None = None,
        type: str | None = None,
        duration: str | None = None,
        features: str | list[str] | None = None,
    ) -> str:
        """Build a protobuf-encoded search filter string.

        Args:
            sort_by: Sort order — 'relevance', 'upload_date', 'view_count', 'rating'.
            upload_date: Time filter — 'last_hour', 'today', 'this_week', 'this_month', 'this_year'.
            type: Content type — 'video', 'channel', 'playlist', 'movie'.
            duration: Duration filter — 'short' (<4min), 'medium' (4-20min), 'long' (>20min).
            features: Feature filter(s) — 'live', '4k', 'hd', 'subtitles', 'cc',
                      'creative_commons', '360', 'vr180', '3d', 'hdr'.
                      Can be a single string or list of strings.

        Returns:
            Base64-encoded protobuf filter string, or empty string if no filters.

        Raises:
            ValueError: If an invalid filter value is provided.
        """
        data = bytearray()

        # Field 1: Sort by (varint, field number 1)
        if sort_by:
            sort_key = sort_by.lower().replace(' ', '_')
            if sort_key not in cls.SORT_BY:
                raise ValueError(
                    'Invalid sort_by: {!r}. Valid: {}'.format(sort_by, ', '.join(cls.SORT_BY))
                )
            value = cls.SORT_BY[sort_key]
            if value != 0:  # 0 is default (relevance), skip it
                data.extend(cls._encode_varint_field(1, value))

        # Field 2: Nested filter message
        filters = bytearray()

        if upload_date:
            date_key = upload_date.lower().replace(' ', '_')
            if date_key not in cls.UPLOAD_DATE:
                raise ValueError(
                    'Invalid upload_date: {!r}. Valid: {}'.format(
                        upload_date, ', '.join(cls.UPLOAD_DATE),
                    )
                )
            filters.extend(cls._encode_varint_field(1, cls.UPLOAD_DATE[date_key]))

        if type:
            type_key = type.lower()
            if type_key not in cls.TYPE:
                raise ValueError(
                    'Invalid type: {!r}. Valid: {}'.format(type, ', '.join(cls.TYPE))
                )
            filters.extend(cls._encode_varint_field(2, cls.TYPE[type_key]))

        if duration:
            dur_key = duration.lower()
            if dur_key not in cls.DURATION:
                raise ValueError(
                    'Invalid duration: {!r}. Valid: {}'.format(duration, ', '.join(cls.DURATION))
                )
            filters.extend(cls._encode_varint_field(3, cls.DURATION[dur_key]))

        if features:
            if isinstance(features, str):
                features = [features]
            for feat in features:
                feat_key = feat.lower().replace(' ', '_')
                if feat_key not in cls.FEATURES:
                    raise ValueError(
                        'Invalid feature: {!r}. Valid: {}'.format(feat, ', '.join(cls.FEATURES))
                    )
                filters.extend(cls._encode_varint_field(4, cls.FEATURES[feat_key]))

        if filters:
            # Wrap filters in length-delimited field 2
            data.extend(cls._encode_bytes_field(2, bytes(filters)))

        if not data:
            return ''

        return base64.b64encode(bytes(data)).decode('ascii')

    @staticmethod
    def _encode_varint(value: int) -> bytes:
        """Encode an integer as a protobuf varint."""
        result = bytearray()
        while value > 0x7F:
            result.append((value & 0x7F) | 0x80)
            value >>= 7
        result.append(value & 0x7F)
        return bytes(result)

    @classmethod
    def _encode_varint_field(cls, field_number: int, value: int) -> bytes:
        """Encode a varint field (wire type 0)."""
        tag = (field_number << 3) | 0  # wire type 0 = varint
        return cls._encode_varint(tag) + cls._encode_varint(value)

    @classmethod
    def _encode_bytes_field(cls, field_number: int, value: bytes) -> bytes:
        """Encode a length-delimited field (wire type 2)."""
        tag = (field_number << 3) | 2  # wire type 2 = length-delimited
        return cls._encode_varint(tag) + cls._encode_varint(len(value)) + value

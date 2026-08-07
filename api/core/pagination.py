"""Shared pagination.

Lived in `marketplace.views` until a second app needed it. Page size is capped
because an uncapped `page_size` is a cheap way to turn any list endpoint into a
database denial-of-service.
"""

from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class CompactPagination(StandardPagination):
    """For high-volume streams — replies, messages, feed items."""

    page_size = 50
    max_page_size = 200

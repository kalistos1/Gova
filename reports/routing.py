"""WebSocket URL routing configuration."""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/reports/(?P<report_id>[^/]+)/$', consumers.ReportConsumer.as_asgi()),
] 
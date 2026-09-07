"""Public DipTraceSchPluginAdapter API v1 (MIT)."""
from .api import Context, AdapterError
from .version import __version__, API_VERSION
__all__ = ['Context', 'AdapterError', 'API_VERSION', '__version__']

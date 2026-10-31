"""站点拦截启发式的兼容入口. 实现在 ``amane.net.errors``."""

from ..net.errors import FailureReason, classify_block, classify_request_error

__all__ = ["FailureReason", "classify_block", "classify_request_error"]

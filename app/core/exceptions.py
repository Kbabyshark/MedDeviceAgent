"""
全局异常定义。

所有业务异常统一在此管理，FastAPI exception_handler 统一捕获。
"""

from __future__ import annotations


class SmartVoiceException(Exception):
    """业务异常基类。"""

    def __init__(self, code: int, message: str, detail: str | None = None) -> None:
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)


# ============================================================
# 通用异常 (1xxxx)
# ============================================================


class BadRequestException(SmartVoiceException):
    def __init__(self, message: str = "参数错误", detail: str | None = None) -> None:
        super().__init__(code=10001, message=message, detail=detail)


class AuthFailedException(SmartVoiceException):
    def __init__(self, message: str = "认证失败", detail: str | None = None) -> None:
        super().__init__(code=10002, message=message, detail=detail)


class PermissionDeniedException(SmartVoiceException):
    def __init__(self, message: str = "权限不足", detail: str | None = None) -> None:
        super().__init__(code=10003, message=message, detail=detail)


class NotFoundException(SmartVoiceException):
    def __init__(self, message: str = "资源不存在", detail: str | None = None) -> None:
        super().__init__(code=10004, message=message, detail=detail)


# ============================================================
# Agent 异常 (2xxxx)
# ============================================================


class AgentException(SmartVoiceException):
    def __init__(self, message: str = "Agent 执行失败", detail: str | None = None) -> None:
        super().__init__(code=20001, message=message, detail=detail)


class IntentClassifyException(SmartVoiceException):
    def __init__(self, message: str = "意图识别失败", detail: str | None = None) -> None:
        super().__init__(code=20002, message=message, detail=detail)


class RAGRetrieveException(SmartVoiceException):
    def __init__(self, message: str = "RAG 检索失败", detail: str | None = None) -> None:
        super().__init__(code=20003, message=message, detail=detail)


class ToolExecuteException(SmartVoiceException):
    def __init__(self, message: str = "工具调用失败", detail: str | None = None) -> None:
        super().__init__(code=20004, message=message, detail=detail)


class SafetyBlockException(SmartVoiceException):
    def __init__(self, message: str = "安全拦截", detail: str | None = None) -> None:
        super().__init__(code=20005, message=message, detail=detail)


class HumanConfirmTimeoutException(SmartVoiceException):
    def __init__(self, message: str = "等待用户确认超时", detail: str | None = None) -> None:
        super().__init__(code=20006, message=message, detail=detail)


# ============================================================
# 模型异常 (3xxxx)
# ============================================================


class ModelCallException(SmartVoiceException):
    def __init__(self, message: str = "模型调用失败", detail: str | None = None) -> None:
        super().__init__(code=30001, message=message, detail=detail)


class ModelTimeoutException(SmartVoiceException):
    def __init__(self, message: str = "模型调用超时", detail: str | None = None) -> None:
        super().__init__(code=30002, message=message, detail=detail)


# ============================================================
# 存储异常 (4xxxx)
# ============================================================


class DatabaseException(SmartVoiceException):
    def __init__(self, message: str = "数据库错误", detail: str | None = None) -> None:
        super().__init__(code=40001, message=message, detail=detail)


class RedisException(SmartVoiceException):
    def __init__(self, message: str = "Redis 错误", detail: str | None = None) -> None:
        super().__init__(code=40002, message=message, detail=detail)


class QdrantException(SmartVoiceException):
    def __init__(self, message: str = "Qdrant 错误", detail: str | None = None) -> None:
        super().__init__(code=40003, message=message, detail=detail)


# ============================================================
# 系统异常 (5xxxx)
# ============================================================


class InternalException(SmartVoiceException):
    def __init__(self, message: str = "内部错误", detail: str | None = None) -> None:
        super().__init__(code=50001, message=message, detail=detail)

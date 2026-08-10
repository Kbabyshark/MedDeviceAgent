"""
Prompt Manager — 统一管理所有 Prompt 模板。

- 从 YAML 文件加载
- 支持版本选择 + 自动降级
- 模板变量渲染
- AB 测试分组

目录结构：
    prompts/
    ├── intent/classify_v1.yaml
    ├── rag/answer_v1.yaml
    └── safety/check_v1.yaml
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.core.logger import get_logger

logger = get_logger(__name__)

# Prompt 根目录
PROMPT_ROOT = Path(__file__).resolve().parent.parent.parent / "prompts"


class _SafeFormatter:
    """安全的 str.format 包装器。

    当模板中包含 literal 花括号（如 JSON 示例）时，
    Python 内置 str.format() 会抛 KeyError/ValueError。
    _SafeFormatter 遇到无法替换的占位符时保留原文，不抛异常。
    需要转义的花括号请在 YAML 中用 {{ 和 }} 书写。
    """

    def format(self, template: str, **kwargs) -> str:
        if not template or "{" not in template:
            return template
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            # 降级：逐个替换已知变量，保留未知花括号
            result = template
            for key, value in kwargs.items():
                result = result.replace("{" + key + "}", str(value))
            return result


class PromptTemplate:
    """单个 Prompt 模板。"""

    def __init__(self, data: dict, file_path: str = "") -> None:
        self.version: str = data.get("version", "v1")
        self.model: str = data.get("model", "deepseek-v3")
        self.description: str = data.get("description", "")
        self.system: str = data.get("system", "")
        self.user_template: str = data.get("user_template", "")
        self.file_path: str = file_path

    def render(self, **kwargs) -> tuple[str, str]:
        """渲染 Prompt，返回 (system_prompt, user_prompt)。

        使用 str.format(**kwargs) 替换模板变量。
        不存在的占位符由 SafeFormatter 保留原文（如 JSON 示例中的花括号）。
        """
        fmt = _SafeFormatter()
        system = fmt.format(self.system, **kwargs)
        user = fmt.format(self.user_template, **kwargs)
        return system, user


class PromptManager:
    """Prompt 管理器。

    使用方式：
        mgr = PromptManager()
        template = mgr.get("intent_classify", version="v1")
        system, user = template.render(query="...", device_info="...")
    """

    def __init__(self, prompt_root: Path | None = None) -> None:
        self._root = prompt_root or PROMPT_ROOT
        self._cache: dict[str, dict[str, PromptTemplate]] = {}  # {category: {version: template}}
        self._load_all()

    def _load_all(self) -> None:
        """加载所有 Prompt 模板到缓存。"""
        if not self._root.exists():
            logger.warning("prompt_root_not_found", path=str(self._root))
            return

        for yaml_file in self._root.rglob("*.yaml"):
            try:
                with open(yaml_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if not data or "version" not in data:
                    continue

                # 按目录名作为 category
                category = yaml_file.parent.name
                template = PromptTemplate(data, str(yaml_file))

                if category not in self._cache:
                    self._cache[category] = {}
                self._cache[category][template.version] = template

                logger.debug("prompt_loaded", category=category, version=template.version, file=str(yaml_file))
            except Exception as e:
                logger.error("prompt_load_error", file=str(yaml_file), error=str(e))

    def get(self, category: str, version: str = "v1") -> PromptTemplate:
        """获取指定分类和版本的 Prompt 模板。

        如果指定版本不存在，降级策略：
        1. 尝试最新版本
        2. 返回默认空模板
        """
        versions = self._cache.get(category, {})

        # 精确匹配
        if version in versions:
            return versions[version]

        # 降级：返回最新版本
        if versions:
            latest = sorted(versions.keys(), reverse=True)[0]
            logger.warning("prompt_version_fallback", category=category, requested=version, fallback=latest)
            return versions[latest]

        # 兜底：返回空模板
        logger.error("prompt_not_found", category=category, version=version)
        return PromptTemplate({"version": "fallback", "model": "deepseek-v3"})

    def list_categories(self) -> list[str]:
        """列出所有 Prompt 分类。"""
        return list(self._cache.keys())

    def list_versions(self, category: str) -> list[str]:
        """列出某分类下所有版本。"""
        return list(self._cache.get(category, {}).keys())

    def reload(self) -> None:
        """重新加载全部 Prompt（用于热更新）。"""
        self._cache.clear()
        self._load_all()
        logger.info("prompts_reloaded", categories=len(self._cache))


# 全局单例
_prompt_manager: PromptManager | None = None


def get_prompt_manager() -> PromptManager:
    """获取 Prompt Manager 单例。"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager

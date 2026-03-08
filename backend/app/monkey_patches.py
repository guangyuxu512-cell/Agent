# app/monkey_patches.py
# Monkey Patch：修复 OpenAI SDK 与 Pydantic v2 的兼容性问题

import logging

logger = logging.getLogger(__name__)


def patch_pydantic_basemodel():
    """
    直接修复 Pydantic BaseModel 的 model_dump 方法

    这是最直接的修复方式，拦截所有 model.model_dump() 调用
    """
    try:
        from pydantic import BaseModel

        # 保存原始方法
        original_model_dump = BaseModel.model_dump

        def patched_model_dump(
            self,
            *,
            mode='python',
            include=None,
            exclude=None,
            by_alias=False,  # 默认值改为 False 而不是 None
            exclude_unset=False,
            exclude_defaults=False,
            exclude_none=False,
            round_trip=False,
            warnings=True,
            **kwargs
        ):
            """修复后的 model_dump：确保所有参数都有默认值"""
            # 确保 by_alias 不是 None
            if by_alias is None:
                by_alias = False

            return original_model_dump(
                self,
                mode=mode,
                include=include,
                exclude=exclude,
                by_alias=by_alias,
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                exclude_none=exclude_none,
                round_trip=round_trip,
                warnings=warnings,
                **kwargs
            )

        # 替换方法
        BaseModel.model_dump = patched_model_dump
        print("[Monkey Patch] OK - Pydantic BaseModel.model_dump patched")
        logger.info("[Monkey Patch] 已修复 Pydantic BaseModel.model_dump")

    except Exception as e:
        print(f"[Monkey Patch] ERROR - Failed to patch Pydantic BaseModel: {e}")
        logger.warning(f"[Monkey Patch] Pydantic BaseModel 补丁失败: {e}")


def patch_openai_compat():
    """
    修复 OpenAI SDK 的 _compat.py 中 model_dump 函数的 by_alias 参数问题
    """
    try:
        from openai import _compat

        # 保存原始函数
        original_model_dump = _compat.model_dump

        def patched_model_dump(
            model,
            *,
            mode="python",
            include=None,
            exclude=None,
            by_alias=None,
            exclude_unset=None,
            exclude_defaults=None,
            exclude_none=None,
            round_trip=None,
            warnings=None,
        ):
            """修复后的 model_dump：确保 by_alias 是 bool 类型"""
            # 修复：将 None 转换为 False
            if by_alias is None:
                by_alias = False
            if exclude_unset is None:
                exclude_unset = False
            if exclude_defaults is None:
                exclude_defaults = False
            if exclude_none is None:
                exclude_none = False
            if round_trip is None:
                round_trip = False
            if warnings is None:
                warnings = True

            return model.model_dump(
                mode=mode,
                include=include,
                exclude=exclude,
                by_alias=by_alias,
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                exclude_none=exclude_none,
                round_trip=round_trip,
                warnings=warnings,
            )

        # 替换函数
        _compat.model_dump = patched_model_dump
        print("[Monkey Patch] OK - OpenAI SDK _compat.model_dump patched")
        logger.info("[Monkey Patch] 已修复 OpenAI SDK 的 by_alias 兼容性问题")

    except Exception as e:
        print(f"[Monkey Patch] ERROR - Failed to patch OpenAI: {e}")
        logger.warning(f"[Monkey Patch] OpenAI 补丁失败: {e}")


def apply_all_patches():
    """应用所有 Monkey Patches"""
    # 先修复 Pydantic BaseModel（最关键）
    patch_pydantic_basemodel()
    # 再修复 OpenAI SDK 层
    patch_openai_compat()

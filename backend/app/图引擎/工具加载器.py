# app/图引擎/工具加载器.py
# 从数据库工具记录转换为 LangChain StructuredTool

import json
import logging
import os
import subprocess
import sys
import tempfile
import shutil
import ctypes
from ctypes import wintypes
from typing import Optional
import httpx
from langchain_core.tools import StructuredTool
from pydantic import create_model, Field
from app.常量 import PYTHON_TOOL_EXEC_TIMEOUT, HTTP_TOOL_RESULT_MAX_LEN

logger = logging.getLogger(__name__)

# ========== Python 沙箱配置 ==========

_PYTHON_EXEC_TIMEOUT = PYTHON_TOOL_EXEC_TIMEOUT

# 沙箱执行器脚本路径
_沙箱执行器路径 = os.path.join(os.path.dirname(__file__), "_沙箱执行器.py")

# ========== L6: Windows Job Object 资源限制 ==========

_IS_WINDOWS = sys.platform == "win32"


def _创建受限Job():
    """创建带资源限制的 Windows Job Object"""
    if not _IS_WINDOWS:
        return None

    kernel32 = ctypes.windll.kernel32

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()

    JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
    JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

    info.BasicLimitInformation.LimitFlags = (
        JOB_OBJECT_LIMIT_PROCESS_MEMORY |
        JOB_OBJECT_LIMIT_ACTIVE_PROCESS |
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    )
    info.ProcessMemoryLimit = 128 * 1024 * 1024  # 128 MB
    info.BasicLimitInformation.ActiveProcessLimit = 1  # 禁止创建子进程

    # JobObjectExtendedLimitInformation = 9
    kernel32.SetInformationJobObject(
        job, 9,
        ctypes.byref(info), ctypes.sizeof(info)
    )
    return job


def _关闭Job(job_handle):
    """关闭 Job Object"""
    if job_handle and _IS_WINDOWS:
        ctypes.windll.kernel32.CloseHandle(job_handle)


def 解析参数模型(工具名称: str, 参数定义: dict) -> type:
    """从 JSON Schema 生成 Pydantic Model"""
    字段 = {}
    属性 = 参数定义.get("properties", {})
    必填 = 参数定义.get("required", [])
    类型映射 = {"string": str, "number": float, "integer": int, "boolean": bool}

    for 字段名, 字段信息 in 属性.items():
        py类型 = 类型映射.get(字段信息.get("type", "string"), str)
        描述 = 字段信息.get("description", "")
        if 字段名 in 必填:
            字段[字段名] = (py类型, Field(description=描述))
        else:
            字段[字段名] = (Optional[py类型], Field(default=None, description=描述))

    if not 字段:
        字段["input"] = (Optional[str], Field(default=None, description="可选输入"))

    安全名称 = "".join(c if c.isalnum() or c == "_" else "_" for c in 工具名称)
    return create_model(f"{安全名称}_参数", **字段)


async def 执行HTTP工具(配置: dict, 参数: dict) -> str:
    """执行 HTTP API 工具"""
    url = 配置.get("url", "")
    method = 配置.get("method", "GET").upper()
    headers = dict(配置.get("headers", {}))
    body_template = 配置.get("body_template", "")
    timeout = 配置.get("timeout", 30)

    for key, value in 参数.items():
        占位符 = "{" + key + "}"
        url = url.replace(占位符, str(value))
        body_template = body_template.replace(占位符, str(value))
        for h_key in list(headers.keys()):
            headers[h_key] = headers[h_key].replace(占位符, str(value))

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "GET":
                resp = await client.get(url, headers=headers, params=参数)
            elif method == "POST":
                body = json.loads(body_template) if body_template.strip() else 参数
                resp = await client.post(url, headers=headers, json=body)
            elif method == "PUT":
                body = json.loads(body_template) if body_template.strip() else 参数
                resp = await client.put(url, headers=headers, json=body)
            elif method == "DELETE":
                resp = await client.delete(url, headers=headers)
            else:
                return f"不支持的请求方法: {method}"
        return f"HTTP {resp.status_code}\n{resp.text[:HTTP_TOOL_RESULT_MAX_LEN]}"
    except httpx.TimeoutException:
        return f"HTTP 请求超时（{timeout}秒）"
    except Exception as e:
        return f"HTTP 请求失败: {str(e)}"


def 执行Python工具(配置: dict, 参数: dict) -> str:
    """执行 Python 代码工具（子进程沙箱隔离模式）

    安全层级（纵深防御 7 层）:
    L1: RestrictedPython compile_restricted — 编译期阻断 import/_前缀属性
    L2: 受限 builtins — 无 getattr/type/open/__import__
    L3: 子进程隔离 — 独立 PID，不影响主进程
    L4: 禁网 — 环境剥离 + runner 销毁 socket 模块
    L5: 文件系统限制 — cwd 为空临时目录，无 open
    L6: Windows Job Object — 内存 128MB + 禁止创建子进程
    L7: subprocess timeout + sys.setrecursionlimit(100)
    """
    code = 配置.get("code", "")
    if not code.strip():
        return "错误：Python 代码为空"

    # 构建输入 JSON
    输入数据 = json.dumps({
        "code": code,
        "params": 参数,
        "max_len": HTTP_TOOL_RESULT_MAX_LEN,
    }, ensure_ascii=False)

    # L5: 创建空临时目录作为 cwd
    临时目录 = tempfile.mkdtemp(prefix="sandbox_")
    job_handle = None

    try:
        # L4: 最小环境变量（保留 Python 运行必需项，剥离密钥/代理/用户目录）
        _敏感键 = {
            "API_KEY", "SECRET", "TOKEN", "PASSWORD", "OPENAI", "DASHSCOPE",
            "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY",
            "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
        }

        最小环境 = {}
        for key, val in os.environ.items():
            key_upper = key.upper()
            # 跳过包含敏感关键词的环境变量
            if any(s in key_upper for s in _敏感键):
                continue
            最小环境[key] = val

        # 确保 Windows 必需项存在
        if _IS_WINDOWS:
            for key in ("SYSTEMROOT", "TEMP", "TMP"):
                if key in os.environ:
                    最小环境[key] = os.environ[key]

        # L3/L7: 子进程执行
        proc = subprocess.Popen(
            [sys.executable, _沙箱执行器路径],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=临时目录,
            env=最小环境,
            creationflags=subprocess.CREATE_NO_WINDOW if _IS_WINDOWS else 0,
        )

        # L6: Windows Job Object 资源限制
        if _IS_WINDOWS:
            try:
                job_handle = _创建受限Job()
                if job_handle:
                    ctypes.windll.kernel32.AssignProcessToJobObject(
                        job_handle, int(proc._handle)
                    )
            except Exception as e:
                logger.warning("创建 Job Object 失败（沙箱仍通过其他层级保护）: %s", e)

        try:
            stdout, stderr = proc.communicate(
                input=输入数据.encode("utf-8"),
                timeout=_PYTHON_EXEC_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return f"错误：Python 代码执行超时（{_PYTHON_EXEC_TIMEOUT}秒）"

        # 解析输出
        if proc.returncode != 0:
            # 进程被终止（可能被 Job Object 杀死 — 内存超限）
            错误输出 = stderr.decode("utf-8", errors="replace").strip()
            if 错误输出:
                return f"Python 执行错误: 进程被终止 - {错误输出[:500]}"
            return "错误：Python 执行进程被终止（可能超出内存限制）"

        输出文本 = stdout.decode("utf-8", errors="replace").strip()
        if not 输出文本:
            return "错误：沙箱执行无输出"

        try:
            结果 = json.loads(输出文本)
        except json.JSONDecodeError:
            return f"错误：沙箱输出解析失败: {输出文本[:200]}"

        if 结果.get("success"):
            return 结果.get("data", "")
        else:
            return f"错误：{结果.get('data', '未知错误')}"

    except Exception as e:
        return f"Python 沙箱执行失败: {str(e)}"

    finally:
        # 清理 Job Object
        if job_handle:
            _关闭Job(job_handle)
        # L5: 清理临时目录
        try:
            shutil.rmtree(临时目录, ignore_errors=True)
        except Exception:
            pass


def 加载工具列表(工具记录列表: list) -> list:
    """从数据库记录转换为 LangChain StructuredTool 列表"""
    工具列表 = []

    for 记录 in 工具记录列表:
        try:
            参数定义 = json.loads(记录["parameters"]) if isinstance(记录["parameters"], str) else 记录["parameters"]
            配置 = json.loads(记录["config"]) if isinstance(记录["config"], str) else 记录["config"]
            工具类型 = 记录.get("tool_type", "http_api")
            工具名称 = 记录.get("name", "unnamed_tool")
            工具描述 = 记录.get("description", "一个工具")

            参数模型 = 解析参数模型(工具名称, 参数定义)

            if 工具类型 == "http_api":
                async def _执行http(当前配置=配置, **kwargs):
                    return await 执行HTTP工具(当前配置, kwargs)
                工具 = StructuredTool.from_function(
                    coroutine=_执行http,
                    name=工具名称,
                    description=工具描述,
                    args_schema=参数模型,
                )
            elif 工具类型 == "python_code":
                def _执行py(当前配置=配置, **kwargs):
                    return 执行Python工具(当前配置, kwargs)
                工具 = StructuredTool.from_function(
                    func=_执行py,
                    name=工具名称,
                    description=工具描述,
                    args_schema=参数模型,
                )
            else:
                continue

            工具列表.append(工具)
        except Exception as e:
            logger.warning("加载工具失败 %s: %s", 记录.get('name', '?'), e)
            continue

    return 工具列表
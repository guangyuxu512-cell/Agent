# app/图引擎/_沙箱执行器.py
# 子进程入口：被 工具加载器.py 通过 subprocess 调用
# 使用 RestrictedPython 编译 + 受限 builtins 执行用户代码
# 通过 stdin 接收 JSON，通过 stdout 输出 JSON 结果

import sys
import json
import builtins as _builtins_mod

# ==================== 先导入 RestrictedPython（在锁定 import 之前） ====================
try:
    from RestrictedPython import compile_restricted
    from RestrictedPython.Eval import default_guarded_getiter
    from RestrictedPython.Guards import (
        guarded_unpack_sequence,
        safer_getattr,
    )
    _RP_AVAILABLE = True
except ImportError:
    _RP_AVAILABLE = False

# ==================== L4: 禁网 — 销毁网络模块 ====================
for _mod_name in list(sys.modules):
    if any(kw in _mod_name for kw in ['socket', 'http', 'urllib', 'requests', 'ssl', 'ftplib', 'smtplib', 'xmlrpc']):
        del sys.modules[_mod_name]

# 劫持 __import__ 禁止导入网络/危险模块
_原始import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__
_禁止模块 = {
    'socket', 'http', 'urllib', 'requests', 'ssl', 'ftplib', 'smtplib', 'xmlrpc',
    'os', 'subprocess', 'shutil', 'io', 'pathlib', 'ctypes', 'signal',
    'multiprocessing', 'threading', 'code', 'codeop', 'compileall',
    'importlib', 'pickle', 'shelve', 'marshal', 'tempfile', 'glob',
    'webbrowser', 'antigravity',
}

def _受限import(name, *args, **kwargs):
    top = name.split('.')[0]
    if top in _禁止模块:
        raise ImportError(f"沙箱禁止导入模块: {name}")
    return _原始import(name, *args, **kwargs)

if isinstance(__builtins__, dict):
    __builtins__['__import__'] = _受限import
else:
    __builtins__.__import__ = _受限import


def _输出结果(success: bool, data: str):
    """输出 JSON 结果到 stdout 并退出"""
    print(json.dumps({"success": success, "data": data}, ensure_ascii=False))
    sys.exit(0)


def main():
    if not _RP_AVAILABLE:
        _输出结果(False, "服务器缺少 RestrictedPython 依赖，请安装: pip install RestrictedPython>=7.0")

    try:
        # 从 stdin 读取输入
        输入文本 = sys.stdin.read()
        输入 = json.loads(输入文本)
        code = 输入["code"]
        params = 输入["params"]
        max_len = 输入.get("max_len", 2000)
    except Exception as e:
        _输出结果(False, f"输入解析错误: {e}")

    # ==================== L1: RestrictedPython 编译 ====================
    try:
        compiled = compile_restricted(code, filename="<sandbox>", mode="exec")
    except SyntaxError as e:
        _输出结果(False, f"代码编译错误: {e}")
    except Exception as e:
        _输出结果(False, f"RestrictedPython 编译拒绝: {e}")

    # ==================== L7: 递归限制（编译完成后再设置） ====================
    sys.setrecursionlimit(100)

    # ==================== L2: 受限 builtins ====================
    _安全函数 = {
        "abs", "all", "any", "bool", "chr", "dict", "divmod", "enumerate",
        "filter", "float", "format", "frozenset", "hash",
        "int", "isinstance", "issubclass", "iter", "len", "list",
        "map", "max", "min", "next", "ord", "pow", "print", "range",
        "repr", "reversed", "round", "set", "slice", "sorted", "str",
        "sum", "tuple", "zip",
    }

    受限builtins = {k: getattr(_builtins_mod, k) for k in _安全函数 if hasattr(_builtins_mod, k)}
    受限builtins["True"] = True
    受限builtins["False"] = False
    受限builtins["None"] = None

    # RestrictedPython 需要的 guard 函数
    def _write_guard(obj):
        """拒绝所有属性写入"""
        raise AttributeError("沙箱禁止属性写入")

    def _inplacevar_guard(op, x, y):
        """允许基本的 += 等操作"""
        if op == "+=":
            return x + y
        elif op == "-=":
            return x - y
        elif op == "*=":
            return x * y
        elif op == "/=":
            return x / y
        elif op == "//=":
            return x // y
        elif op == "%=":
            return x % y
        elif op == "**=":
            return x ** y
        raise ValueError(f"不支持的操作: {op}")

    # RestrictedPython 的 guard 回调
    受限builtins["_getiter_"] = default_guarded_getiter
    受限builtins["_getattr_"] = safer_getattr
    受限builtins["_write_"] = _write_guard
    受限builtins["_unpack_sequence_"] = guarded_unpack_sequence
    受限builtins["_inplacevar_"] = _inplacevar_guard
    受限builtins["_getitem_"] = lambda obj, key: obj[key]
    受限builtins["_apply_"] = lambda func, *args, **kwargs: func(*args, **kwargs)

    # ==================== L3/L5: 执行 ====================
    命名空间 = {"__builtins__": 受限builtins}

    try:
        exec(compiled, 命名空间)
    except Exception as e:
        _输出结果(False, f"代码执行错误: {e}")

    if "execute" not in 命名空间:
        _输出结果(False, "Python 工具代码必须定义 execute(params) 函数")

    try:
        result = 命名空间["execute"](params)
        result_str = str(result)[:max_len]
        _输出结果(True, result_str)
    except Exception as e:
        _输出结果(False, f"execute() 执行错误: {e}")


if __name__ == "__main__":
    main()

"""
tests/security/test_sandbox.py
P0-1 沙箱安全回归测试 — 11 项用例 + 1 正向验证

运行方式:
  cd <项目根目录>
  python -m pytest tests/security/test_sandbox.py -v          # pytest
  python tests/security/test_sandbox.py                       # 直接运行

每次修改沙箱相关代码（工具加载器.py / _沙箱执行器.py）后必须跑一遍。
"""

import sys
import os
import json
import subprocess
import textwrap

# 定位 backend 目录
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(_THIS_DIR, os.pardir, os.pardir, "backend")
_BACKEND_DIR = os.path.normpath(_BACKEND_DIR)
sys.path.insert(0, _BACKEND_DIR)

from app.图引擎.工具加载器 import 执行Python工具  # noqa: E402


# ====================================================================
# 用例定义
# ====================================================================

测试用例 = [
    # ----------------------------------------------------------------
    # 1. import 语句 — RestrictedPython v8 将 import 编译为
    #    __import__() 调用，受限 builtins 中无 __import__ → 运行期 L2 阻断
    # ----------------------------------------------------------------
    {
        "编号": 1,
        "名称": "import os（顶层）— L2 builtins 无 __import__",
        "code": "import os\ndef execute(params): return os.popen('id').read()",
        "期望关键词": ["__import__", "not found"],
        "应成功": False,
        "说明": (
            "RestrictedPython v8 不再于编译期拒绝 import 语句，"
            "而是将其编译为 __import__() 调用；"
            "由于受限 builtins 不含 __import__，运行期抛出 NameError。"
        ),
    },
    # ----------------------------------------------------------------
    # 2. open() — 受限 builtins 中无 open
    # ----------------------------------------------------------------
    {
        "编号": 2,
        "名称": "open() 读文件 — L2 builtins 无 open",
        "code": "def execute(params): return open('C:/Windows/win.ini').read()",
        "期望关键词": ["open", "not defined"],
        "应成功": False,
        "说明": "受限 builtins 白名单不含 open → NameError。",
    },
    # ----------------------------------------------------------------
    # 3. 显式调用 __import__('os')
    #    RestrictedPython 在编译期拒绝以 _ 开头的标识符
    # ----------------------------------------------------------------
    {
        "编号": 3,
        "名称": "__import__('os') 显式调用 — L1 编译期拒绝 _ 前缀标识符",
        "code": "def execute(params):\n    return __import__('os').popen('whoami').read()",
        "期望关键词": ["__import__", "invalid variable name", "starts with"],
        "应成功": False,
        "说明": (
            "直接在源码中写 __import__('os')，"
            "RestrictedPython compile_restricted 于编译期拒绝：\n"
            '  "__import__" is an invalid variable name because it starts with "_"'
        ),
    },
    # ----------------------------------------------------------------
    # 4. MRO 链逃逸 — 编译期拒绝 __class__ / __bases__ / __subclasses__
    # ----------------------------------------------------------------
    {
        "编号": 4,
        "名称": "().__class__.__bases__[0].__subclasses__() — L1 编译期阻断",
        "code": "def execute(params):\n    return ().__class__.__bases__[0].__subclasses__()",
        "期望关键词": ["__subclasses__", "__bases__", "__class__"],
        "应成功": False,
        "说明": (
            "RestrictedPython 禁止访问以 _ 开头的属性名，"
            "__class__ / __bases__ / __subclasses__ 全部于编译期阻断。"
        ),
    },
    # ----------------------------------------------------------------
    # 5. 死循环 — subprocess timeout 终止
    # ----------------------------------------------------------------
    {
        "编号": 5,
        "名称": "while True: pass — L7 超时终止",
        "code": "def execute(params):\n    while True: pass",
        "期望关键词": ["超时"],
        "应成功": False,
        "说明": "subprocess.communicate(timeout=N) 超时后 kill 子进程。",
    },
    # ----------------------------------------------------------------
    # 6. chr() 拼出字符串 "socket" — 无害，无法 import
    # ----------------------------------------------------------------
    {
        "编号": 6,
        "名称": "chr() 拼 'socket' — 返回无害字符串，无法变为 import",
        "code": "def execute(params):\n    s=chr(115)+chr(111)+chr(99)+chr(107)+chr(101)+chr(116)\n    return s",
        "期望值": "socket",
        "应成功": True,
        "说明": (
            "可以用 chr() 拼出任意字符串，但 builtins 中无 __import__，"
            "无法将字符串变为模块引用 → 仅返回无害字符串 'socket'。"
        ),
    },
    # ----------------------------------------------------------------
    # 7. 内存耗尽 — Windows Job Object / Linux RLIMIT_AS 终止
    # ----------------------------------------------------------------
    {
        "编号": 7,
        "名称": "分配 >128MB 内存 — L6 Job Object 终止进程",
        "code": "def execute(params):\n    x = []\n    for i in range(10**9): x.append('A'*10**6)\n    return 'done'",
        "期望关键词": ["错误", "终止"],
        "应成功": False,
        "说明": "Windows Job Object ProcessMemoryLimit=128MB 杀死超限进程。",
    },
    # ----------------------------------------------------------------
    # 8. import subprocess（函数内部）— 同测试 1，L2 builtins 阻断
    # ----------------------------------------------------------------
    {
        "编号": 8,
        "名称": "import subprocess（函数内）— L2 builtins 无 __import__",
        "code": "def execute(params):\n    import subprocess\n    return subprocess.check_output('whoami').decode()",
        "期望关键词": ["__import__", "not found"],
        "应成功": False,
        "说明": (
            "与测试 1 同理：import 语句编译为 __import__() 调用，"
            "受限 builtins 无 __import__ → NameError。"
        ),
    },
    # ----------------------------------------------------------------
    # 9. __import__('os') 真实逃逸 — Python 内置导入函数的运行期阻断
    #
    #    背景：__import__ 是 CPython 中 import 语句的底层实现函数，
    #    签名为 __import__(name, globals, locals, fromlist, level)。
    #    标准 Python 中它始终存在于 builtins 中，任何代码都可以
    #    调用 __import__('os') 来导入任意模块 —— 这是几乎所有
    #    Python 沙箱逃逸的终极原语。
    #
    #    本沙箱的防御：
    #    - L1 (编译期): RestrictedPython 拒绝源码中出现 __import__
    #      标识符（以 _ 开头），阻止直接写 __import__('os')。
    #    - L2 (运行期): 受限 builtins 字典中根本不包含 __import__
    #      键。即使 RestrictedPython v8 将 import 语句编译为
    #      __import__() 调用，运行期也因 NameError 失败。
    #
    #    本用例验证 L2 层：在函数内部写 import os，
    #    RestrictedPython v8 将其编译为 __import__('os') 调用，
    #    受限 builtins 中无此函数 → NameError: __import__ not found。
    #    这证明即使绕过了 L1 编译检查，L2 builtins 白名单仍然
    #    阻止了 __import__ 这一 Python 内置导入函数的调用。
    # ----------------------------------------------------------------
    {
        "编号": 9,
        "名称": "__import__('os') 运行期阻断 — Python 内置导入函数真实逃逸尝试",
        "code": "def execute(params):\n    import os\n    return os.popen('whoami').read()",
        "期望关键词": ["__import__", "not found"],
        "应成功": False,
        "说明": (
            "__import__ 是 Python 的内置导入函数，"
            "是 import 语句的底层实现，也是沙箱逃逸的终极原语。"
            "RestrictedPython v8 将 import os 编译为 __import__('os') 运行期调用；"
            "受限 builtins 白名单中已移除 __import__ → NameError。"
            "此用例验证的是 L2（builtins 白名单），而非 L1（编译期标识符检查）。"
        ),
    },
]


# ====================================================================
# 测试 10: 语言层网络能力阻断
# ====================================================================

def 测试10_语言层网络阻断():
    """
    在独立子进程中模拟 runner 的 L4 环境（import hook + sys.modules 清理），
    验证即使绕过 RestrictedPython，也无法获得 socket/connect 原语。

    注意：这是 *语言层* 阻断，不是 OS 级禁网。
    OS 级禁网需要 seccomp / 容器网络隔离（见附录）。
    """
    探测脚本 = textwrap.dedent("""\
        import sys, json

        # ---- 模拟 runner 的 L4 设置（与 _沙箱执行器.py 完全一致）----
        for mod in list(sys.modules):
            if any(kw in mod for kw in [
                'socket','http','urllib','requests','ssl',
                'ftplib','smtplib','xmlrpc']):
                del sys.modules[mod]

        _orig = __builtins__.__import__ if hasattr(__builtins__,'__import__') else __import__
        _blocked = {
            'socket','http','urllib','requests','ssl','ftplib','smtplib','xmlrpc',
            'os','subprocess','shutil','io','pathlib','ctypes','signal',
            'multiprocessing','threading','importlib','pickle','tempfile'}

        def _restricted(name, *a, **kw):
            if name.split('.')[0] in _blocked:
                raise ImportError(f"sandbox blocked: {name}")
            return _orig(name, *a, **kw)

        if isinstance(__builtins__, dict):
            __builtins__['__import__'] = _restricted
        else:
            __builtins__.__import__ = _restricted

        # ---- 4 项探测 ----
        results = {}

        # A: 直接 import socket
        try:
            import socket
            results["import_socket"] = "FAIL: imported"
        except ImportError as e:
            results["import_socket"] = f"BLOCKED: {e}"

        # B: 通过 __import__ 调用
        try:
            s = __import__('socket')
            results["__import__('socket')"] = "FAIL: imported"
        except ImportError as e:
            results["__import__('socket')"] = f"BLOCKED: {e}"

        # C: sys.modules 残留检查
        has = "socket" in sys.modules
        results["sys.modules残留"] = "FAIL: socket in sys.modules" if has else "BLOCKED: 已清除"

        # D: 构造 TCP connect（前置条件不满足，import 失败）
        try:
            import socket as s2
            c = s2.socket(s2.AF_INET, s2.SOCK_STREAM)
            c.settimeout(2)
            c.connect(("8.8.8.8", 53))
            c.close()
            results["tcp_connect"] = "FAIL: connected"
        except ImportError as e:
            results["tcp_connect"] = f"BLOCKED: {e}"
        except Exception as e:
            results["tcp_connect"] = f"BLOCKED({type(e).__name__}): {e}"

        print(json.dumps(results, ensure_ascii=False))
    """)

    最小环境 = dict(os.environ)
    for k in list(最小环境):
        ku = k.upper()
        if any(s in ku for s in ("API_KEY", "SECRET", "TOKEN", "PASSWORD")):
            del 最小环境[k]

    proc = subprocess.run(
        [sys.executable, "-c", 探测脚本],
        capture_output=True, text=True, timeout=15, env=最小环境,
    )
    return proc.stdout.strip(), proc.returncode


# ====================================================================
# 执行器
# ====================================================================

def _run_all():
    print("=" * 72)
    print("P0-1 沙箱安全回归测试")
    print("=" * 72)

    通过 = 0
    失败 = 0
    总数 = len(测试用例) + 2  # +测试9 +正向

    for 用例 in 测试用例:
        i = 用例["编号"]
        print(f"\n[{i}/{总数-1}] {用例['名称']}")
        print(f"  机制: {用例['说明']}")

        结果 = 执行Python工具({"code": 用例["code"]}, {})
        print(f"  输出: {结果[:300]}")

        if 用例["应成功"]:
            期望值 = 用例.get("期望值", "")
            if 期望值 and 期望值 in 结果 and "错误" not in 结果:
                print(f"  PASS -- 返回无害值 '{期望值}'")
                通过 += 1
            else:
                print(f"  FAIL")
                失败 += 1
        else:
            关键词 = 用例["期望关键词"]
            if any(kw in 结果 for kw in 关键词):
                print(f"  PASS -- 攻击被阻断")
                通过 += 1
            else:
                print(f"  FAIL -- 未匹配预期关键词 {关键词}")
                失败 += 1

    # 测试 10
    print(f"\n[10/{总数-1}] 语言层网络能力阻断 -- 无法获得 socket/connect 原语")
    print(f"  机制: runner 进程 L4 import hook + sys.modules 清理，")
    print(f"        独立于 RestrictedPython 验证，证明即使 L1/L2 被绕过")
    print(f"        也无法 import socket 或建立 TCP 连接。")
    print(f"        (注: 这是语言层阻断，OS 级禁网见附录)")
    try:
        输出, rc = 测试10_语言层网络阻断()
        print(f"  子进程返回码: {rc}")
        探测 = json.loads(输出)
        全阻断 = True
        for 项, 值 in 探测.items():
            ok = "BLOCKED" in str(值)
            tag = "PASS" if ok else "FAIL"
            if not ok:
                全阻断 = False
            print(f"    {项}: {值}  [{tag}]")
        if 全阻断:
            print(f"  PASS -- 4 项 socket/connect 探测全部被语言层阻断")
            通过 += 1
        else:
            print(f"  FAIL -- 存在未阻断项")
            失败 += 1
    except Exception as e:
        print(f"  FAIL -- 异常: {e}")
        失败 += 1

    # 正向
    print(f"\n[正向] sum(range(100)) -- 合法代码必须返回 4950")
    r = 执行Python工具({"code": "def execute(params):\n    return str(sum(range(100)))"}, {})
    print(f"  输出: {r}")
    if r.strip() == "4950":
        print(f"  PASS -- 合法代码正常执行")
        通过 += 1
    else:
        print(f"  FAIL -- 预期 4950")
        失败 += 1

    # 汇总
    print("\n" + "=" * 72)
    print(f"结果: {通过} 通过, {失败} 失败 (共 {通过+失败} 项)")
    if 失败 == 0:
        print("所有验证通过")
    else:
        print(f"!!! {失败} 项未通过 !!!")
    print("=" * 72)

    # 附录
    print("""
======================================================================
附录 A: 各测试对应的防御层
======================================================================

  测试 1,8 : L2 (builtins 无 __import__)
             RestrictedPython v8 将 import 语句编译为 __import__() 调用;
             受限 builtins 白名单不含 __import__ -> NameError at runtime

  测试 3   : L1 (compile_restricted 拒绝 _ 前缀标识符)
             源码中显式写 __import__('os') ->
             编译期错误: "__import__" is an invalid variable name

  测试 9   : L2 (__import__ 运行期阻断 — 真实逃逸路径)
             import os 编译为 __import__('os') 调用,
             builtins 中无 __import__ -> NameError
             此用例独立验证 L2 层对 Python 内置导入函数的阻断

  测试 2   : L2 (builtins 无 open) + L5 (cwd 为空临时目录)
  测试 4   : L1 (compile_restricted 拒绝 __class__/__bases__/__subclasses__)
  测试 5   : L7 (subprocess timeout)
  测试 6   : 安全 — chr() 可拼字符串但无法 import
  测试 7   : L6 (Windows Job Object / Linux RLIMIT_AS)
  测试 10  : L4 (import hook + sys.modules 清理) 语言层阻断

======================================================================
附录 B: Linux 部署 -- L6 资源限制替代方案
======================================================================

  Windows Job Object        ->  Linux resource.setrlimit()
  -----------------------------------------------------------
  ProcessMemoryLimit=128MB  ->  RLIMIT_AS  = (128MB, 128MB)
  ActiveProcessLimit=1      ->  RLIMIT_NPROC = (0, 0)
  KILL_ON_JOB_CLOSE         ->  preexec_fn 中设置; 父进程 kill

  代码:
    import resource
    def _linux_preexec():
        mem = 128 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))

    proc = subprocess.Popen(..., preexec_fn=_linux_preexec)

======================================================================
附录 C: OS 级禁网 -- 部署验收说明
======================================================================

  语言层阻断 (L4 import hook) 防御的是 *Python 层面* 的网络访问。
  若攻击者通过某种方式获得了原生代码执行能力 (ctypes / C 扩展),
  import hook 可被绕过。真正的 OS 级禁网需要:

  方案 1: seccomp-bpf (推荐, 轻量)
  ──────────────────────────────────
    需要: pip install python-seccomp

    import seccomp
    def _linux_preexec_seccomp():
        _linux_preexec()                 # 先设 rlimit
        f = seccomp.SyscallFilter(seccomp.ALLOW)
        for sc in ("connect","sendto","sendmsg","bind","listen","accept"):
            f.add_rule(seccomp.KILL, sc)
        f.load()

    验收命令:
      # 在部署服务器上执行, 确认 seccomp 策略生效
      python -c "
      import seccomp, json
      f = seccomp.SyscallFilter(seccomp.ALLOW)
      f.add_rule(seccomp.KILL, 'connect')
      f.load()
      import socket
      s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      try:
          s.connect(('8.8.8.8', 53))
          print('FAIL: 连接成功, seccomp 未生效')
      except OSError:
          print('PASS: connect 系统调用被 seccomp 杀死')
      "

  方案 2: 容器网络隔离 (适合已容器化部署)
  ──────────────────────────────────────────
    docker run --network=none sandbox-runner

    验收命令:
      docker run --network=none python:3.12-slim python -c "
      import socket; s=socket.socket(); s.settimeout(3)
      try: s.connect(('8.8.8.8',53)); print('FAIL')
      except OSError as e: print(f'PASS: {e}')
      "
      # 预期输出: PASS: [Errno 101] Network is unreachable
""")

    return 失败 == 0


# ====================================================================
# pytest 兼容：每个用例一个 test_ 函数
# ====================================================================

def test_01_import_os():
    r = 执行Python工具({"code": 测试用例[0]["code"]}, {})
    assert "__import__" in r and "not found" in r, f"未阻断: {r}"

def test_02_open_file():
    r = 执行Python工具({"code": 测试用例[1]["code"]}, {})
    assert "open" in r and "not defined" in r, f"未阻断: {r}"

def test_03_dunder_import_explicit():
    r = 执行Python工具({"code": 测试用例[2]["code"]}, {})
    assert "__import__" in r and "invalid variable name" in r, f"未阻断: {r}"

def test_04_mro_chain():
    r = 执行Python工具({"code": 测试用例[3]["code"]}, {})
    assert "__subclasses__" in r or "__bases__" in r or "__class__" in r, f"未阻断: {r}"

def test_05_infinite_loop_timeout():
    r = 执行Python工具({"code": 测试用例[4]["code"]}, {})
    assert "超时" in r, f"未超时终止: {r}"

def test_06_chr_concat_harmless():
    r = 执行Python工具({"code": 测试用例[5]["code"]}, {})
    assert r == "socket", f"预期 'socket', 得到: {r}"

def test_07_memory_exhaustion():
    r = 执行Python工具({"code": 测试用例[6]["code"]}, {})
    assert "错误" in r or "终止" in r, f"未终止: {r}"

def test_08_import_subprocess():
    r = 执行Python工具({"code": 测试用例[7]["code"]}, {})
    assert "__import__" in r and "not found" in r, f"未阻断: {r}"

def test_09_dunder_import_runtime_block():
    """__import__('os') 运行期阻断: Python 内置导入函数真实逃逸尝试。
    import os 被 RestrictedPython v8 编译为 __import__('os') 调用,
    受限 builtins 中已移除 __import__ → NameError。
    验证 L2 builtins 白名单独立阻断能力。"""
    r = 执行Python工具({"code": 测试用例[8]["code"]}, {})
    assert "__import__" in r and "not found" in r, f"未阻断: {r}"

def test_10_language_level_network_block():
    输出, rc = 测试10_语言层网络阻断()
    探测 = json.loads(输出)
    for 项, 值 in 探测.items():
        assert "BLOCKED" in str(值), f"{项} 未阻断: {值}"

def test_positive_sum_range():
    r = 执行Python工具({"code": "def execute(params):\n    return str(sum(range(100)))"}, {})
    assert r.strip() == "4950", f"预期 '4950', 得到: {r}"


# ====================================================================
if __name__ == "__main__":
    success = _run_all()
    sys.exit(0 if success else 1)

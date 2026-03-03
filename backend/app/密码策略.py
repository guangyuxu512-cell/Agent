"""
密码策略 - 弱口令检测与强度验证
"""
import re


def 检查密码强度(password: str) -> tuple[bool, str]:
    """
    检查密码强度

    规则：
    - 长度 >= 12
    - 至少包含以下两类：大写字母、小写字母、数字、符号

    返回：(是否合格, 错误消息)
    """
    if len(password) < 12:
        return False, "密码长度必须至少 12 位"

    # 检查字符类型
    has_upper = bool(re.search(r'[A-Z]', password))
    has_lower = bool(re.search(r'[a-z]', password))
    has_digit = bool(re.search(r'[0-9]', password))
    has_symbol = bool(re.search(r'[^A-Za-z0-9]', password))

    type_count = sum([has_upper, has_lower, has_digit, has_symbol])

    if type_count < 2:
        return False, "密码必须包含以下至少两类：大写字母、小写字母、数字、符号"

    return True, ""


def 是否为弱口令(password: str) -> bool:
    """
    判断是否为弱口令（用于登录时判断是否需要强制改密）
    """
    # 常见弱口令列表
    weak_passwords = [
        "admin123", "password", "123456", "12345678",
        "admin", "root", "test123", "qwerty"
    ]

    if password.lower() in weak_passwords:
        return True

    # 检查强度
    is_strong, _ = 检查密码强度(password)
    return not is_strong

# app/加密.py
# AES-CBC 加密/解密 — 用于 API Key 等敏感字段的存储加密

import os
import base64
import hashlib
import logging
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

logger = logging.getLogger(__name__)

# 从环境变量读取加密密钥，未设置时用 JWT_SECRET_KEY 派生
_raw_key = os.getenv("ENCRYPTION_KEY", "") or os.getenv("JWT_SECRET_KEY", "default-encryption-key")
_KEY = hashlib.sha256(_raw_key.encode()).digest()  # 32 bytes for AES-256

_PREFIX = "enc:"  # 密文前缀，用于区分明文和密文


def 加密(明文: str) -> str:
    """AES-256-CBC 加密，返回 'enc:' + base64 编码的密文"""
    if not 明文 or not 明文.strip():
        return 明文

    iv = os.urandom(16)
    padder = padding.PKCS7(128).padder()
    padded = padder.update(明文.encode("utf-8")) + padder.finalize()

    cipher = Cipher(algorithms.AES(_KEY), modes.CBC(iv))
    encryptor = cipher.encryptor()
    密文 = encryptor.update(padded) + encryptor.finalize()

    return _PREFIX + base64.b64encode(iv + 密文).decode("ascii")


def 解密(密文: str) -> str:
    """解密 AES-256-CBC 密文。如果不是 'enc:' 前缀（明文兼容），原样返回"""
    if not 密文 or not 密文.strip():
        return 密文

    if not 密文.startswith(_PREFIX):
        # 兼容已有明文数据
        return 密文

    try:
        raw = base64.b64decode(密文[len(_PREFIX):])
        iv = raw[:16]
        实际密文 = raw[16:]

        cipher = Cipher(algorithms.AES(_KEY), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded = decryptor.update(实际密文) + decryptor.finalize()

        unpadder = padding.PKCS7(128).unpadder()
        明文 = unpadder.update(padded) + unpadder.finalize()
        return 明文.decode("utf-8")
    except Exception as e:
        logger.warning("[加密] 解密失败，当作明文返回: %s", e)
        return 密文

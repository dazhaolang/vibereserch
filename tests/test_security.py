"""
安全模块单元测试
"""

import pytest
from datetime import datetime, timedelta
from app.core.security_enhanced import (
    SecurityManager,
    sanitize_html,
    validate_sql_identifier,
    validate_file_upload,
    CSRFProtect,
    EncryptionUtil
)

class TestSecurityManager:
    """测试安全管理器"""

    def test_password_validation(self):
        """测试密码强度验证"""
        # 弱密码测试
        weak_passwords = [
            "123456",  # 太短
            "password",  # 无数字
            "Password1",  # 无特殊字符
            "password1!",  # 无大写字母
            "PASSWORD1!",  # 无小写字母
        ]

        for pwd in weak_passwords:
            is_valid, message = SecurityManager.validate_password_strength(pwd)
            assert not is_valid, f"Password '{pwd}' should be invalid"

        # 强密码测试
        strong_passwords = [
            "Test@123456",
            "MyP@ssw0rd!",
            "Secure#Pass123",
        ]

        for pwd in strong_passwords:
            is_valid, message = SecurityManager.validate_password_strength(pwd)
            assert is_valid, f"Password '{pwd}' should be valid: {message}"

    def test_password_hashing(self):
        """测试密码哈希"""
        password = "Test@123456"

        # 测试哈希生成
        hashed = SecurityManager.hash_password(password)
        assert hashed != password
        assert len(hashed) > 20

        # 测试密码验证
        assert SecurityManager.verify_password(password, hashed)
        assert not SecurityManager.verify_password("WrongPassword", hashed)

        # 测试相同密码产生不同哈希（salt）
        hashed2 = SecurityManager.hash_password(password)
        assert hashed != hashed2

    def test_session_token_generation(self):
        """测试会话令牌生成"""
        token1 = SecurityManager.generate_session_token()
        token2 = SecurityManager.generate_session_token()

        # 令牌应该是唯一的
        assert token1 != token2
        # 令牌应该有足够长度
        assert len(token1) >= 32
        assert len(token2) >= 32

    def test_2fa_secret_generation(self):
        """测试2FA密钥生成"""
        secret1 = SecurityManager.generate_2fa_secret()
        secret2 = SecurityManager.generate_2fa_secret()

        # 密钥应该是唯一的
        assert secret1 != secret2
        # 密钥应该是base32编码
        assert all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567' for c in secret1)

    def test_2fa_token_verification(self):
        """测试2FA令牌验证"""
        import pyotp

        secret = SecurityManager.generate_2fa_secret()
        totp = pyotp.TOTP(secret)

        # 正确的令牌应该验证成功
        valid_token = totp.now()
        assert SecurityManager.verify_2fa_token(secret, valid_token)

        # 错误的令牌应该验证失败
        invalid_token = "000000"
        assert not SecurityManager.verify_2fa_token(secret, invalid_token)


class TestSanitization:
    """测试输入清理函数"""

    def test_html_sanitization(self):
        """测试HTML清理"""
        # 测试XSS攻击清理
        dangerous_html = [
            '<script>alert("XSS")</script>',
            '<img src=x onerror="alert(1)">',
            '<iframe src="evil.com"></iframe>',
            '<a href="javascript:alert(1)">Click</a>',
        ]

        for html in dangerous_html:
            clean = sanitize_html(html)
            assert '<script>' not in clean
            assert 'onerror' not in clean
            assert '<iframe>' not in clean
            assert 'javascript:' not in clean

        # 测试允许的标签保留
        safe_html = '<p>This is <strong>bold</strong> and <em>italic</em></p>'
        clean = sanitize_html(safe_html)
        assert '<p>' in clean
        assert '<strong>' in clean
        assert '<em>' in clean

    def test_sql_identifier_validation(self):
        """测试SQL标识符验证"""
        # 有效标识符
        valid_identifiers = [
            'table_name',
            'column1',
            '_private_table',
            'CamelCase',
            'table123',
        ]

        for identifier in valid_identifiers:
            assert validate_sql_identifier(identifier)

        # 无效标识符（可能SQL注入）
        invalid_identifiers = [
            'table; DROP TABLE users',
            'column" OR "1"="1',
            'table-name',  # 连字符不允许
            '123table',  # 不能数字开头
            'table name',  # 不能有空格
        ]

        for identifier in invalid_identifiers:
            assert not validate_sql_identifier(identifier)

    def test_file_upload_validation(self):
        """测试文件上传验证"""
        # 允许的文件
        valid_files = [
            ('document.pdf', 'application/pdf'),
            ('paper.txt', 'text/plain'),
            ('research.doc', 'application/msword'),
            ('data.json', 'application/json'),
        ]

        for filename, content_type in valid_files:
            is_valid, message = validate_file_upload(filename, content_type)
            assert is_valid, f"File {filename} should be valid: {message}"

        # 不允许的文件
        invalid_files = [
            ('script.exe', 'application/x-executable'),
            ('virus.bat', 'application/x-batch'),
            ('hack.php', 'application/x-php'),
            ('shell.sh', 'application/x-sh'),
        ]

        for filename, content_type in invalid_files:
            is_valid, message = validate_file_upload(filename, content_type)
            assert not is_valid, f"File {filename} should be invalid"


class TestCSRFProtection:
    """测试CSRF保护"""

    def test_csrf_token_generation(self):
        """测试CSRF令牌生成"""
        token1 = CSRFProtect.generate_csrf_token()
        token2 = CSRFProtect.generate_csrf_token()

        # 令牌应该是唯一的
        assert token1 != token2
        # 令牌应该有足够长度
        assert len(token1) >= 32
        assert len(token2) >= 32

    def test_csrf_token_validation(self):
        """测试CSRF令牌验证"""
        session_token = "test_session_token"
        csrf_token = session_token  # 简化测试

        # 正确的令牌应该验证成功
        assert CSRFProtect.validate_csrf_token(csrf_token, session_token)

        # 错误的令牌应该验证失败
        assert not CSRFProtect.validate_csrf_token("wrong_token", session_token)


class TestEncryption:
    """测试加密工具"""

    def test_data_encryption(self):
        """测试数据加密解密"""
        from cryptography.fernet import Fernet

        # 生成测试密钥
        key = Fernet.generate_key().decode()

        # 测试字符串加密
        original_data = "Sensitive information"
        encrypted = EncryptionUtil.encrypt_sensitive_data(original_data, key)

        # 加密后的数据应该不同于原始数据
        assert encrypted != original_data

        # 解密应该还原原始数据
        decrypted = EncryptionUtil.decrypt_sensitive_data(encrypted, key)
        assert decrypted == original_data

    def test_encryption_with_different_keys(self):
        """测试不同密钥的加密"""
        from cryptography.fernet import Fernet

        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()

        data = "Test data"
        encrypted = EncryptionUtil.encrypt_sensitive_data(data, key1)

        # 使用错误的密钥应该无法解密
        with pytest.raises(Exception):
            EncryptionUtil.decrypt_sensitive_data(encrypted, key2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
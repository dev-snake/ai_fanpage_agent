"""
Script test TokenManager - Kiểm tra tính năng auto-refresh token
"""

from pathlib import Path
import logging
import sys

from core.token_manager import TokenManager
from utils.logger import setup_logger


def main():
    print("\n" + "=" * 60)
    print("🔐 TEST FACEBOOK TOKEN MANAGER")
    print("=" * 60 + "\n")

    # Setup logger
    logger = setup_logger("DEBUG")

    # Khởi tạo TokenManager
    config_path = Path("config.json")
    if not config_path.exists():
        print("❌ Không tìm thấy config.json")
        return

    token_mgr = TokenManager(config_path, logger)

    # Test 1: Kiểm tra token info
    print("\n[Test 1] Kiểm tra thông tin token hiện tại...")
    print("-" * 60)
    token_info = token_mgr.get_token_info()

    if "error" in token_info:
        print(f"❌ Lỗi: {token_info['error']}")
    else:
        print(f"Token preview: {token_info.get('token_preview')}")
        print(f"Valid: {token_info.get('valid')}")
        if token_info.get("valid"):
            print(f"User: {token_info.get('user', {}).get('name', 'N/A')}")
            print(f"Expires at: {token_info.get('expires_at', 'N/A')}")
        else:
            print(f"Error: {token_info.get('error')}")
            print(f"Error code: {token_info.get('error_code')}")

    # Test 2: Lấy token hợp lệ (auto-refresh nếu cần)
    print("\n[Test 2] Lấy token hợp lệ (auto-refresh nếu cần)...")
    print("-" * 60)
    token = token_mgr.get_valid_token()

    if token:
        print(f"✅ Token hợp lệ: {token[:30]}...")
    else:
        print("❌ Không thể lấy token hợp lệ")

    # Test 3: Validate lại lần nữa (kiểm tra cache)
    print("\n[Test 3] Validate lại (kiểm tra cache)...")
    print("-" * 60)
    token2 = token_mgr.get_valid_token()

    if token2:
        print(f"✅ Token từ cache: {token2[:30]}...")
        print(f"Cache hit: {token == token2}")

    print("\n" + "=" * 60)
    print("✅ TEST HOÀN TẤT")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Đã hủy bởi user")
    except Exception as exc:
        print(f"\n\n❌ Lỗi: {exc}")
        import traceback

        traceback.print_exc()

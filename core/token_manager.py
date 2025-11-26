"""
Facebook Token Manager - Tự động quản lý và refresh Facebook access token
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

import requests
from playwright.sync_api import BrowserContext, TimeoutError as PlaywrightTimeout


class TokenManager:
    """Quản lý Facebook access token với tính năng auto-refresh"""

    def __init__(
        self,
        config_path: Path,
        logger: logging.Logger,
        context: Optional[BrowserContext] = None,
        config_dict: Optional[Dict[str, Any]] = None,
    ):
        self.config_path = config_path
        self.logger = logger.getChild("token_manager")
        self.context = context
        self._token_cache: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._last_validation: Optional[datetime] = None
        self._config_dict = config_dict  # Config đã được load với env vars

    def get_valid_token(self, force_refresh: bool = False) -> Optional[str]:
        """
        Lấy token hợp lệ. Tự động refresh nếu token hết hạn.

        Args:
            force_refresh: Buộc refresh token ngay cả khi chưa hết hạn

        Returns:
            Token hợp lệ hoặc None nếu không thể lấy được
        """
        # Kiểm tra cache nếu chưa hết hạn và không force refresh
        if not force_refresh and self._is_token_valid_cached():
            return self._token_cache

        # Đọc token từ config
        token = self._load_token_from_config()
        if not token:
            self.logger.error(
                "\n" + "=" * 60 + "\n"
                "❌ KHÔNG TÌM THẤY TOKEN TRONG CONFIG\n"
                "=" * 60 + "\n"
                "Token chưa được cấu hình hoặc đang dùng placeholder.\n\n"
                "Vui lòng thực hiện:\n"
                "1️⃣  Lấy token từ: https://developers.facebook.com/tools/explorer/\n"
                "2️⃣  Thêm vào .env:\n"
                "   GRAPH_ACCESS_TOKEN=your_token_here\n\n"
                "Hoặc cập nhật trực tiếp trong config.json:\n"
                '   "graph_access_token": "your_token_here"\n\n'
                "📖 Chi tiết: Xem TOKEN_REFRESH_GUIDE.md\n" + "=" * 60
            )
            return None

        # Validate token với Facebook API
        validation_result = self._validate_token(token)

        if validation_result["valid"]:
            self._update_token_cache(token, validation_result.get("expires_at"))
            self.logger.info(
                "Token hợp lệ, expires: %s", validation_result.get("expires_at")
            )
            return token

        # Token không hợp lệ hoặc hết hạn - thử refresh
        error_code = validation_result.get("error_code")
        error_subcode = validation_result.get("error_subcode")
        error_msg = validation_result.get("error")

        self.logger.error(
            "❌ Token validation thất bại:\n"
            "   Error Code: %s\n"
            "   Error Subcode: %s\n"
            "   Message: %s",
            error_code,
            error_subcode,
            error_msg,
        )

        if error_code == 190:  # Token expired
            self.logger.info("🔄 Token hết hạn, đang thử refresh...")
            new_token = self._refresh_token(token)
            if new_token:
                self._save_token_to_config(new_token)
                return new_token

            # Nếu không thể refresh tự động, thử lấy token mới từ browser
            self.logger.warning(
                "Không thể refresh token tự động, thử lấy token từ browser..."
            )
            new_token = self._extract_token_from_browser()
            if new_token:
                self._save_token_to_config(new_token)
                return new_token

        self.logger.error(
            "\n" + "=" * 60 + "\n"
            "❌ KHÔNG THỂ LẤY TOKEN HỢP LỆ\n"
            "=" * 60 + "\n"
            "Vui lòng thực hiện 1 trong các cách sau:\n\n"
            "1️⃣  Cập nhật token thủ công:\n"
            "   - Vào: https://developers.facebook.com/tools/explorer/\n"
            "   - Generate Access Token\n"
            "   - Copy và paste vào config.json (field: graph_access_token)\n\n"
            "2️⃣  Setup auto-refresh (khuyến nghị):\n"
            "   - Lấy App ID & Secret từ: https://developers.facebook.com/apps/\n"
            "   - Thêm vào .env:\n"
            "     FACEBOOK_APP_ID=your_app_id\n"
            "     FACEBOOK_APP_SECRET=your_app_secret\n\n"
            "📖 Chi tiết: Xem TOKEN_REFRESH_GUIDE.md\n" + "=" * 60
        )
        return None

    def _is_token_valid_cached(self) -> bool:
        """Kiểm tra xem token trong cache còn hợp lệ không"""
        if not self._token_cache or not self._token_expires_at:
            return False

        # Refresh sớm hơn 1 giờ trước khi hết hạn để tránh lỗi
        buffer_time = timedelta(hours=1)
        now = datetime.now()

        return now < (self._token_expires_at - buffer_time)

    def _update_token_cache(self, token: str, expires_at: Optional[datetime]) -> None:
        """Cập nhật cache token"""
        self._token_cache = token
        self._token_expires_at = expires_at
        self._last_validation = datetime.now()

    def _load_token_from_config(self) -> Optional[str]:
        """Đọc token từ config đã load (với env vars đã được thay thế)"""
        try:
            # Nếu có config dict đã load, dùng nó (đã thay thế ${VAR})
            if self._config_dict:
                token = self._config_dict.get("graph_access_token", "")
            else:
                # Fallback: đọc trực tiếp từ file
                if not self.config_path.exists():
                    return None
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                token = data.get("graph_access_token", "")

            # Bỏ qua token placeholder
            if not token or "${" in token or token in ["YOUR_TOKEN", ""]:
                return None

            return token
        except Exception as exc:
            self.logger.error("Lỗi khi đọc token từ config: %s", exc)
            return None

    def _save_token_to_config(self, token: str) -> bool:
        """Lưu token mới vào file config"""
        try:
            if not self.config_path.exists():
                self.logger.error("Config file không tồn tại: %s", self.config_path)
                return False

            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            data["graph_access_token"] = token

            self.config_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8"
            )

            self.logger.info("✅ Đã lưu token mới vào config")
            self._update_token_cache(token, None)
            return True

        except Exception as exc:
            self.logger.error("Lỗi khi lưu token vào config: %s", exc)
            return False

    def _validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate token với Facebook Graph API

        Returns:
            Dict với keys: valid (bool), expires_at (datetime), error, error_code
        """
        try:
            url = "https://graph.facebook.com/v24.0/me"
            params = {"access_token": token, "fields": "id,name"}

            resp = requests.get(url, params=params, timeout=10)

            if resp.ok:
                # Token valid, lấy thông tin expiration
                debug_url = "https://graph.facebook.com/v24.0/debug_token"
                debug_resp = requests.get(
                    debug_url,
                    params={"input_token": token, "access_token": token},
                    timeout=10,
                )

                expires_at = None
                if debug_resp.ok:
                    debug_data = debug_resp.json().get("data", {})
                    expires_timestamp = debug_data.get("expires_at", 0)
                    if expires_timestamp > 0:
                        expires_at = datetime.fromtimestamp(expires_timestamp)

                return {
                    "valid": True,
                    "expires_at": expires_at,
                    "user_data": resp.json(),
                }
            else:
                error_data = resp.json().get("error", {})
                return {
                    "valid": False,
                    "error": error_data.get("message", "Unknown error"),
                    "error_code": error_data.get("code"),
                    "error_subcode": error_data.get("error_subcode"),
                }

        except requests.exceptions.Timeout:
            self.logger.error(
                "⏱️  Timeout khi validate token với Facebook API\n"
                "   → Kiểm tra kết nối internet\n"
                "   → Thử lại sau vài giây"
            )
            return {"valid": False, "error": "Request timeout"}
        except requests.exceptions.RequestException as exc:
            self.logger.error(
                "🌐 Lỗi kết nối khi validate token:\n"
                "   Error: %s\n"
                "   → Kiểm tra kết nối internet\n"
                "   → Kiểm tra firewall/proxy",
                exc,
            )
            return {"valid": False, "error": str(exc)}
        except Exception as exc:
            self.logger.error(
                "❌ Lỗi không xác định khi validate token:\n"
                "   Error: %s\n"
                "   Type: %s",
                exc,
                type(exc).__name__,
            )
            return {"valid": False, "error": str(exc)}

    def _refresh_token(self, old_token: str) -> Optional[str]:
        """
        Thử refresh token bằng cách exchange sang long-lived token

        Note: Chỉ hoạt động nếu có app_id và app_secret
        """
        try:
            # Đọc app credentials từ config hoặc env
            config_data = json.loads(self.config_path.read_text(encoding="utf-8"))
            app_id = config_data.get("facebook_app_id")
            app_secret = config_data.get("facebook_app_secret")

            if not app_id or not app_secret:
                self.logger.warning(
                    "⚠️  Không tìm thấy facebook_app_id/facebook_app_secret trong config.\n"
                    "   → Không thể refresh token tự động.\n"
                    "   → Hướng dẫn setup: Xem TOKEN_REFRESH_GUIDE.md\n"
                    "   → Hoặc thêm vào .env:\n"
                    "      FACEBOOK_APP_ID=your_app_id\n"
                    "      FACEBOOK_APP_SECRET=your_app_secret"
                )
                return None

            # Exchange short-lived token -> long-lived token
            url = "https://graph.facebook.com/v24.0/oauth/access_token"
            params = {
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": old_token,
            }

            resp = requests.get(url, params=params, timeout=10)

            if resp.ok:
                data = resp.json()
                new_token = data.get("access_token")
                if new_token:
                    self.logger.info("✅ Refresh token thành công!")
                    return new_token
            else:
                error_data = resp.json().get("error", {})
                error_msg = error_data.get("message", "Unknown error")
                error_code = error_data.get("code")
                self.logger.error(
                    "❌ Refresh token qua OAuth thất bại:\n"
                    "   Error Code: %s\n"
                    "   Message: %s\n"
                    "   → Thử lấy token mới từ browser...",
                    error_code,
                    error_msg,
                )

        except requests.exceptions.Timeout:
            self.logger.error(
                "⏱️  Timeout khi refresh token\n"
                "   → Kiểm tra kết nối internet\n"
                "   → Thử lại sau"
            )
        except requests.exceptions.RequestException as exc:
            self.logger.error(
                "🌐 Lỗi kết nối khi refresh token: %s\n"
                "   → Kiểm tra internet/firewall",
                exc,
            )
        except Exception as exc:
            self.logger.error(
                "❌ Lỗi không xác định khi refresh token:\n"
                "   Error: %s\n"
                "   Type: %s",
                exc,
                type(exc).__name__,
            )

        return None

    def _extract_token_from_browser(self) -> Optional[str]:
        """
        Lấy token từ browser đang đăng nhập (qua Playwright)

        Phương pháp:
        1. Mở Facebook Graph API Explorer
        2. Tự động copy access token
        """
        if not self.context:
            self.logger.warning("Không có browser context để lấy token")
            return None

        try:
            self.logger.info("Đang mở Facebook Graph API Explorer để lấy token...")
            page = self.context.new_page()

            # Mở Graph API Explorer
            page.goto(
                "https://developers.facebook.com/tools/explorer/",
                wait_until="domcontentloaded",
                timeout=30000,
            )

            page.wait_for_timeout(3000)

            # Thử lấy token từ input field
            token_input = page.query_selector(
                "input[name='access_token'], textarea[placeholder*='Access Token']"
            )

            if token_input:
                token = token_input.input_value()
                if token and len(token) > 50:
                    self.logger.info("✅ Đã lấy token từ Graph API Explorer")
                    page.close()
                    return token

            # Nếu không tìm thấy tự động, hướng dẫn user
            self.logger.warning(
                "\n" + "=" * 60 + "\n"
                "⚠️  KHÔNG THỂ TỰ ĐỘNG LẤY TOKEN\n"
                "Vui lòng thực hiện các bước sau:\n"
                "1. Trong cửa sổ browser vừa mở, click 'Generate Access Token'\n"
                "2. Chọn các permissions cần thiết (pages_manage_posts, pages_read_engagement)\n"
                "3. Copy access token và paste vào terminal này\n"
                "=" * 60
            )

            page.bring_to_front()
            new_token = input("\n➡️  Nhập Facebook Access Token: ").strip()
            page.close()

            if new_token and len(new_token) > 50:
                return new_token

        except PlaywrightTimeout:
            self.logger.error(
                "⏱️  Timeout khi mở Graph API Explorer\n"
                "   → Page load quá lâu\n"
                "   → Thử lại hoặc cập nhật token thủ công"
            )
        except Exception as exc:
            self.logger.error(
                "❌ Lỗi khi lấy token từ browser:\n"
                "   Error: %s\n"
                "   Type: %s\n"
                "   → Fallback: Cập nhật token thủ công",
                exc,
                type(exc).__name__,
            )

        return None

    def get_token_info(self) -> Dict[str, Any]:
        """Lấy thông tin chi tiết về token hiện tại"""
        token = self._load_token_from_config()
        if not token:
            return {"error": "No token found"}

        validation = self._validate_token(token)

        result = {
            "token_preview": token[:20] + "..." if len(token) > 20 else token,
            "valid": validation["valid"],
        }

        if validation["valid"]:
            result["expires_at"] = validation.get("expires_at")
            result["user"] = validation.get("user_data", {})
        else:
            result["error"] = validation.get("error")
            result["error_code"] = validation.get("error_code")

        return result

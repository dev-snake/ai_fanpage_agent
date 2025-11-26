# 🚀 CHANGELOG - Token Auto-Refresh Feature

## Ngày: 2025-11-26

### ✨ Tính năng mới

#### 1. **TokenManager - Tự động quản lý Facebook Access Token**

-   ✅ Tự động validate token trước khi gọi Facebook API
-   ✅ Tự động refresh token khi hết hạn
-   ✅ Cache token trong memory để tối ưu performance
-   ✅ Refresh sớm 1 giờ trước khi token hết hạn
-   ✅ Tự động lưu token mới vào config.json

#### 2. **Xử lý lỗi Token Expiry (Error 190)**

-   Trước đây: Phải copy-paste token thủ công khi hết hạn
-   Bây giờ: Hệ thống tự động xử lý

---

## 📁 Files thay đổi

### Files mới

1. **`core/token_manager.py`** - Module quản lý token

    - Class `TokenManager` với các methods:
        - `get_valid_token()` - Lấy token hợp lệ, auto-refresh
        - `get_token_info()` - Kiểm tra thông tin token
        - `_validate_token()` - Validate với Facebook API
        - `_refresh_token()` - Refresh qua OAuth
        - `_extract_token_from_browser()` - Lấy token từ browser

2. **`TOKEN_REFRESH_GUIDE.md`** - Hướng dẫn chi tiết
3. **`config.example.json`** - Template config với options mới
4. **`test_token_manager.py`** - Script test TokenManager

### Files cập nhật

#### `core/comments.py`

-   ➕ Import `TokenManager`
-   ➕ Thêm `token_manager` parameter vào `__init__`
-   ✏️ `_fetch_graph_comments()` - Sử dụng TokenManager để lấy token

#### `core/pages.py`

-   ➕ Import `TokenManager`
-   ➕ Thêm `token_manager` parameter vào `__init__`
-   ✏️ `list_pages_graph()` - Validate token trước khi dùng

#### `core/actions.py`

-   ➕ Import `TokenManager`
-   ➕ Thêm `token_manager` parameter vào `__init__`
-   ✏️ `_graph_reply()` - Lấy token qua TokenManager
-   ✏️ `_graph_hide()` - Lấy token qua TokenManager

#### `main.py`

-   ➕ Import `TokenManager`
-   ✏️ `build_services()` - Khởi tạo TokenManager
-   ✏️ Validate token trước khi bắt đầu cycles
-   ✏️ Hiển thị thông tin token expiry

#### `config.json`

-   ➕ `facebook_app_id` - App ID để refresh token (optional)
-   ➕ `facebook_app_secret` - App Secret để refresh token (optional)

---

## 🔧 Cách sử dụng

### Setup cơ bản (không cần thay đổi gì)

Hệ thống sẽ tự động validate và thông báo khi token hết hạn.

### Setup nâng cao (auto-refresh hoàn toàn)

Thêm vào `.env`:

```env
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
```

Hoặc trong `config.json`:

```json
{
    "facebook_app_id": "123456789",
    "facebook_app_secret": "abc123def456"
}
```

---

## 📊 Performance Improvements

### Trước

```
- Validate token: Không có
- Token expiry handling: Thủ công
- API calls: Luôn gọi với token cũ
- Downtime: ~5-10 phút khi token hết hạn
```

### Sau

```
- Validate token: Tự động mỗi lần khởi động
- Token expiry handling: Tự động refresh
- API calls: Luôn dùng token hợp lệ (từ cache)
- Downtime: 0 (refresh ngầm trong background)
```

---

## 🐛 Bug Fixes

### Issue #1: "400 Client Error: Session has expired"

**Trước:**

```
2025-11-26 15:31:58 | WARNING | published_posts failed: 400 Client Error
Error validating access token: Session has expired
```

→ Phải restart và update token thủ công

**Sau:**

```
2025-11-26 15:31:58 | WARNING | Token hết hạn, đang thử refresh...
2025-11-26 15:31:59 | INFO | ✅ Refresh token thành công!
```

→ Tự động xử lý, không downtime

---

## 🧪 Testing

Chạy test script:

```bash
python test_token_manager.py
```

Output mẫu:

```
============================================================
🔐 TEST FACEBOOK TOKEN MANAGER
============================================================

[Test 1] Kiểm tra thông tin token hiện tại...
------------------------------------------------------------
Token preview: EAAY6EPwzr3YBQH7s9pm...
Valid: True
User: Your Page Name
Expires at: 2025-12-26 15:31:58

[Test 2] Lấy token hợp lệ (auto-refresh nếu cần)...
------------------------------------------------------------
✅ Token hợp lệ: EAAY6EPwzr3YBQH7s9pm...

[Test 3] Validate lại (kiểm tra cache)...
------------------------------------------------------------
✅ Token từ cache: EAAY6EPwzr3YBQH7s9pm...
Cache hit: True

============================================================
✅ TEST HOÀN TẤT
============================================================
```

---

## 📚 Documentation

-   **Chi tiết**: Xem `TOKEN_REFRESH_GUIDE.md`
-   **API Docs**: Xem docstrings trong `core/token_manager.py`
-   **Example Config**: Xem `config.example.json`

---

## ⚠️ Breaking Changes

**NONE** - Tất cả thay đổi đều backward compatible.

Nếu không thêm app credentials, hệ thống vẫn hoạt động như cũ, chỉ cần nhập token thủ công khi hết hạn (nhưng giờ có hướng dẫn rõ ràng hơn).

---

## 🎯 Roadmap

-   [ ] Thêm monitoring để track token expiry
-   [ ] Notification khi token sắp hết hạn
-   [ ] Support multiple tokens (rotation)
-   [ ] Webhooks để auto-refresh từ Facebook

---

## 👥 Contributors

-   dev-snake (2025-11-26)

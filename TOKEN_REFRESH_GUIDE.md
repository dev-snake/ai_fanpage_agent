
# 🔐 Hướng Dẫn Tự Động Refresh Facebook Token

## Tính Năng Mới

Agent giờ đây có khả năng **tự động kiểm tra và refresh Facebook access token** khi hết hạn, không cần copy-paste thủ công nữa!

## Cách Hoạt Động

### 1. **Tự động validate token**

Mỗi khi khởi động hoặc trước khi gọi Facebook API, hệ thống sẽ:

-   ✅ Kiểm tra token còn hợp lệ không
-   ✅ Kiểm tra thời gian hết hạn
-   ✅ Tự động refresh trước 1 giờ khi token sắp hết hạn

### 2. **Auto-refresh khi token expired**

Khi token hết hạn (error code 190), hệ thống tự động:

1. Thử refresh token qua Facebook OAuth (nếu có app credentials)
2. Nếu không thành công → Mở browser để lấy token mới
3. Lưu token mới vào `config.json` tự động

### 3. **Caching thông minh**

-   Token được cache trong memory để tránh validate nhiều lần
-   Tự động refresh trước 1 giờ khi sắp hết hạn

---

## Cấu Hình

### Option 1: Auto-refresh với App Credentials (Khuyến nghị)

Thêm vào `config.json`:

```json
{
  "graph_access_token": "${GRAPH_ACCESS_TOKEN}",
  "facebook_app_id": "${FACEBOOK_APP_ID}",
  "facebook_app_secret": "${FACEBOOK_APP_SECRET}",
  ...
}
```

Hoặc tạo file `.env`:

```env
GRAPH_ACCESS_TOKEN=your_token_here
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
```

#### Lấy App Credentials:

1. Truy cập: https://developers.facebook.com/apps/
2. Tạo app mới (hoặc dùng app có sẵn)
3. Copy **App ID** và **App Secret**
4. Thêm vào config

### Option 2: Semi-Auto (Không cần App Credentials)

Nếu không có app credentials:

-   Khi token hết hạn, hệ thống sẽ mở Facebook Graph API Explorer
-   Bạn chỉ cần click "Generate Token" và copy vào terminal
-   Token mới sẽ được lưu tự động

---

## Log Messages

### ✅ Token hợp lệ

```
2025-11-26 15:45:00 | INFO | Token hợp lệ, expires: 2025-12-26 15:45:00
2025-11-26 15:45:00 | INFO | ✅ Token hợp lệ, sẵn sàng hoạt động
```

### ⚠️ Token sắp hết hạn

```
2025-11-26 15:45:00 | INFO | Token sắp hết hạn, đang refresh...
2025-11-26 15:45:01 | INFO | ✅ Refresh token thành công!
```

### ❌ Token hết hạn (Auto-handling)

```
2025-11-26 15:45:00 | WARNING | Token không hợp lệ: Session has expired
2025-11-26 15:45:00 | INFO | Token hết hạn, đang thử refresh...
2025-11-26 15:45:01 | INFO | ✅ Refresh token thành công!
```

### 🔧 Cần intervention thủ công (hiếm khi)

```
2025-11-26 15:45:00 | WARNING | Không thể refresh token tự động
2025-11-26 15:45:00 | INFO | Đang mở Graph API Explorer...
➡️  Nhập Facebook Access Token: [nhập token ở đây]
```

---

## So Sánh Trước và Sau

### ❌ Trước (Thủ công)

```
2025-11-26 15:31:58 | WARNING | published_posts failed: 400 Client Error
Error: Session has expired on Wednesday, 26-Nov-25 00:00:00 PST
```

→ Phải lên trang Graph API, copy token, paste vào config, restart app

### ✅ Sau (Tự động)

```
2025-11-26 15:31:58 | WARNING | Token hết hạn, đang thử refresh...
2025-11-26 15:31:59 | INFO | ✅ Refresh token thành công!
2025-11-26 15:32:00 | INFO | published_posts: fetched 5 posts
```

→ Không cần làm gì, hệ thống tự xử lý!

---

## FAQ

### Q: Token bao lâu thì hết hạn?

A:

-   Short-lived token: 1-2 giờ
-   Long-lived token: 60 ngày
-   Page token: không hết hạn (nếu được cấp đúng cách)

### Q: Có cần App Credentials không?

A:

-   **Không bắt buộc**, nhưng khuyến nghị để auto-refresh hoàn toàn tự động
-   Nếu không có, hệ thống vẫn có thể lấy token mới qua browser

### Q: Token được lưu ở đâu?

A:

-   Token được lưu trong `config.json` tại field `graph_access_token`
-   Tự động cập nhật khi refresh thành công

### Q: Có cache token không?

A:

-   Có! Token được cache trong memory
-   Tự động validate lại trước 1 giờ khi sắp hết hạn

### Q: Làm sao biết token sắp hết hạn?

A:

-   Check log khởi động: `Token expires at: 2025-12-26 15:45:00`
-   Hoặc check token info qua TokenManager API

---

## API Usage (For Developers)

```python
from core.token_manager import TokenManager

# Khởi tạo
token_mgr = TokenManager(
    config_path=Path("config.json"),
    logger=logger,
    context=browser_context  # Optional, để lấy token từ browser
)

# Lấy token hợp lệ (auto-refresh nếu cần)
token = token_mgr.get_valid_token()

# Force refresh
token = token_mgr.get_valid_token(force_refresh=True)

# Check token info
info = token_mgr.get_token_info()
print(info["expires_at"])
```

---

## Troubleshooting

### Issue: "Không thể refresh token"

**Solution:**

1. Kiểm tra `facebook_app_id` và `facebook_app_secret` trong config
2. Đảm bảo token ban đầu có quyền `manage_pages`
3. Thử generate token mới từ Graph API Explorer

### Issue: "Token validation timeout"

**Solution:**

1. Kiểm tra kết nối internet
2. Thử tăng timeout trong `token_manager.py`

### Issue: "Config file không tồn tại"

**Solution:**

1. Đảm bảo `config.json` tồn tại trong thư mục gốc
2. Hoặc truyền đúng path vào TokenManager

---

## Kết Luận

Với tính năng này, bạn không cần lo lắng về token expiry nữa! Agent sẽ tự động xử lý mọi thứ. 🎉

Nếu có vấn đề, check log để biết chi tiết và follow hướng dẫn troubleshooting ở trên.

# ⚡ Quick Start - Token Auto-Refresh

## 🎯 Vấn đề đã giải quyết

### ❌ Trước đây:

```
2025-11-26 15:31:58 | WARNING | Error validating access token: Session has expired
```

→ Phải:

1. Lên https://developers.facebook.com/tools/explorer/
2. Generate token mới
3. Copy và paste vào config.json
4. Restart ứng dụng
   → **Downtime: 5-10 phút**

### ✅ Bây giờ:

```
2025-11-26 15:31:58 | INFO | Token hết hạn, đang thử refresh...
2025-11-26 15:31:59 | INFO | ✅ Refresh token thành công!
```

→ **Downtime: 0 giây** (tự động xử lý)

---

## 🚀 Cách sử dụng

### Option 1: Tự động hoàn toàn (Khuyến nghị)

**Bước 1:** Lấy App Credentials

1. Vào: https://developers.facebook.com/apps/
2. Tạo app mới hoặc dùng app có sẵn
3. Copy **App ID** và **App Secret**

**Bước 2:** Thêm vào `.env`

```env
FACEBOOK_APP_ID=your_app_id_here
FACEBOOK_APP_SECRET=your_app_secret_here
```

**Bước 3:** Chạy bình thường

```bash
python main.py
```

→ Token sẽ tự động refresh khi hết hạn!

---

### Option 2: Bán tự động (Không cần App Credentials)

**Chạy bình thường:**

```bash
python main.py
```

**Khi token hết hạn:**

-   Browser sẽ tự động mở Graph API Explorer
-   Click "Generate Access Token"
-   Copy và paste vào terminal
-   Token mới được lưu tự động

→ Chỉ cần nhập 1 lần khi hết hạn!

---

## 🧪 Test thử

```bash
python test_token_manager.py
```

Output:

```
============================================================
🔐 TEST FACEBOOK TOKEN MANAGER
============================================================

[Test 1] Kiểm tra thông tin token hiện tại...
Token preview: EAAY6EPwzr3YBQH7s9pm...
Valid: True
Expires at: 2025-12-26 15:31:58

✅ TEST HOÀN TẤT
============================================================
```

---

## 📋 Checklist

-   [ ] Thêm `FACEBOOK_APP_ID` và `FACEBOOK_APP_SECRET` vào `.env` (optional)
-   [ ] Chạy test: `python test_token_manager.py`
-   [ ] Chạy app: `python main.py`
-   [ ] Kiểm tra log: Token validation messages
-   [ ] ✅ Done! Token tự động refresh

---

## ❓ FAQ

**Q: Token bao lâu thì hết hạn?**
A: 60 ngày (long-lived token). Hệ thống tự refresh trước 1 giờ khi sắp hết hạn.

**Q: Có bắt buộc phải có App Credentials không?**
A: KHÔNG. Nếu không có, hệ thống sẽ mở browser để nhập token thủ công.

**Q: Token được lưu ở đâu?**
A: Trong `config.json` tại field `graph_access_token`. Tự động update khi refresh.

**Q: Có an toàn không?**
A: CÓ. Token được validate với Facebook API trước khi sử dụng.

---

## 📚 Tài liệu đầy đủ

-   [TOKEN_REFRESH_GUIDE.md](TOKEN_REFRESH_GUIDE.md) - Hướng dẫn chi tiết
-   [CHANGELOG_TOKEN.md](CHANGELOG_TOKEN.md) - Log các thay đổi
-   [config.example.json](config.example.json) - Template config

---

## 🐛 Troubleshooting

### "Không thể refresh token"

→ Check `facebook_app_id` và `facebook_app_secret` trong config

### "Token validation timeout"

→ Check internet connection

### "Config file không tồn tại"

→ Đảm bảo `config.json` tồn tại trong thư mục gốc

---

## 💡 Tips

1. **Setup App Credentials ngay từ đầu** để tránh downtime
2. **Check log thường xuyên** để biết token expires khi nào
3. **Test trước** bằng `test_token_manager.py`
4. **Backup config.json** trước khi thay đổi

---

Bất kỳ vấn đề gì, check log để biết chi tiết! 🎉

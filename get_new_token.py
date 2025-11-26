"""
Script để lấy Facebook Access Token mới một cách dễ dàng
"""

import webbrowser
import time

print("\n" + "=" * 60)
print("🔑 LẤY FACEBOOK ACCESS TOKEN MỚI")
print("=" * 60 + "\n")

print("Đang mở Facebook Graph API Explorer trong browser...")
print("Vui lòng làm theo các bước sau:\n")

print("1️⃣  Đăng nhập Facebook (nếu chưa)")
print("2️⃣  Click 'Generate Access Token'")
print("3️⃣  Chọn Page của bạn")
print("4️⃣  Chọn permissions:")
print("    - pages_manage_posts")
print("    - pages_read_engagement")
print("    - pages_manage_engagement")
print("5️⃣  Click 'Generate Token'")
print("6️⃣  Copy token và paste vào đây\n")

# Mở browser
url = "https://developers.facebook.com/tools/explorer/"
webbrowser.open(url)

time.sleep(2)

print("=" * 60)
token = input("\n➡️  Paste Facebook Access Token vào đây: ").strip()

if not token:
    print("\n❌ Token trống! Vui lòng thử lại.")
    exit(1)

if len(token) < 50:
    print("\n⚠️  Token có vẻ ngắn bất thường. Bạn chắc chắn đã copy đúng?")
    confirm = input("Tiếp tục? (y/n): ").strip().lower()
    if confirm != "y":
        exit(1)

# Lưu vào .env
print("\n📝 Đang cập nhật .env file...")

try:
    with open(".env", "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Tìm và replace dòng GRAPH_ACCESS_TOKEN
    updated = False
    for i, line in enumerate(lines):
        if line.startswith("GRAPH_ACCESS_TOKEN="):
            lines[i] = f"GRAPH_ACCESS_TOKEN={token}\n"
            updated = True
            break

    # Nếu không tìm thấy, thêm vào cuối
    if not updated:
        lines.append(f"\nGRAPH_ACCESS_TOKEN={token}\n")

    # Ghi lại file
    with open(".env", "w", encoding="utf-8") as f:
        f.writelines(lines)

    print("\n✅ Đã cập nhật token mới vào .env!")
    print("\n" + "=" * 60)
    print("🎉 HOÀN TẤT!")
    print("=" * 60)
    print("\nBạn có thể chạy agent ngay bây giờ:")
    print("  python main.py\n")

except Exception as e:
    print(f"\n❌ Lỗi khi cập nhật .env: {e}")
    print("\nVui lòng cập nhật thủ công:")
    print(f"  GRAPH_ACCESS_TOKEN={token}\n")

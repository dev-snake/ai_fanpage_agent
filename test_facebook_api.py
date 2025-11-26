"""
Script để test Facebook Graph API - Xem posts và comments thật
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

from main import load_config
from utils.logger import setup_logger
from core.comments import CommentFetcher
from core.actions import ActionExecutor
from core.token_manager import TokenManager


def test_fetch_posts():
    """Test lấy posts từ Page"""
    print("\n" + "=" * 60)
    print("📝 TEST LẤY POSTS TỪ FACEBOOK PAGE")
    print("=" * 60 + "\n")

    # Load config
    cfg = load_config("config.json")
    logger = setup_logger("DEBUG")

    # Khởi tạo TokenManager
    config_path = Path("config.json")
    token_manager = TokenManager(config_path, logger, config_dict=cfg)

    # Validate token
    print("🔐 Kiểm tra token...")
    token = token_manager.get_valid_token()
    if not token:
        print("❌ Token không hợp lệ!")
        return

    print(f"✅ Token OK: {token[:30]}...\n")

    # Lấy thông tin Page
    page_id = cfg.get("page_id")
    version = cfg.get("graph_version", "v24.0")

    print(f"📄 Page ID: {page_id}")
    print(f"🔗 API Version: {version}\n")

    # Test API call trực tiếp
    import requests

    print("=" * 60)
    print("1️⃣  FETCH RECENT POSTS")
    print("=" * 60)

    # Lấy posts gần đây
    url = f"https://graph.facebook.com/{version}/{page_id}/posts"
    params = {
        "access_token": token,
        "fields": "id,message,created_time,permalink_url",
        "limit": 5,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        posts = data.get("data", [])
        print(f"\n✅ Tìm thấy {len(posts)} posts:\n")

        for i, post in enumerate(posts, 1):
            print(f"📌 Post #{i}")
            print(f"   ID: {post.get('id')}")
            print(f"   Message: {post.get('message', '(no message)')[:80]}...")
            print(f"   Created: {post.get('created_time')}")
            print(f"   URL: {post.get('permalink_url', 'N/A')}")
            print()

        return posts

    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        print(f"Response: {e.response.text if e.response else 'N/A'}")
        return []
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return []


def test_fetch_comments(post_id=None):
    """Test lấy comments từ một post"""
    print("\n" + "=" * 60)
    print("💬 TEST LẤY COMMENTS TỪ POST")
    print("=" * 60 + "\n")

    # Load config
    cfg = load_config("config.json")
    logger = setup_logger("DEBUG")

    # Khởi tạo TokenManager
    config_path = Path("config.json")
    token_manager = TokenManager(config_path, logger, config_dict=cfg)

    token = token_manager.get_valid_token()
    if not token:
        print("❌ Token không hợp lệ!")
        return

    # Nếu không có post_id, lấy post đầu tiên
    if not post_id:
        posts = test_fetch_posts()
        if not posts:
            print("❌ Không có post nào!")
            return
        post_id = posts[0]["id"]
        print(f"\n📍 Sử dụng post đầu tiên: {post_id}\n")

    print("=" * 60)
    print("2️⃣  FETCH COMMENTS FROM POST")
    print("=" * 60)

    version = cfg.get("graph_version", "v24.0")
    url = f"https://graph.facebook.com/{version}/{post_id}/comments"

    params = {
        "access_token": token,
        "fields": "id,from,message,created_time,permalink_url",
        "filter": "stream",
        "order": "reverse_chronological",
        "limit": 10,
    }

    import requests

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        comments = data.get("data", [])
        print(f"\n✅ Tìm thấy {len(comments)} comments:\n")

        if not comments:
            print("ℹ️  Post này chưa có comment nào!")
            print(
                "💡 Tip: Thử comment vào post trên Facebook rồi chạy lại script này\n"
            )
            return []

        for i, comment in enumerate(comments, 1):
            from_user = comment.get("from", {})
            print(f"💬 Comment #{i}")
            print(f"   ID: {comment.get('id')}")
            print(
                f"   From: {from_user.get('name', 'Unknown')} (ID: {from_user.get('id')})"
            )
            print(f"   Message: {comment.get('message', '(no message)')}")
            print(f"   Created: {comment.get('created_time')}")
            print(f"   URL: {comment.get('permalink_url', 'N/A')}")
            print()

        return comments

    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        print(f"Response: {e.response.text if e.response else 'N/A'}")
        return []
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return []


def test_reply_to_comment():
    """Test reply vào một comment"""
    print("\n" + "=" * 60)
    print("💬 TEST REPLY TO COMMENT")
    print("=" * 60 + "\n")

    # Load config
    cfg = load_config("config.json")
    logger = setup_logger("DEBUG")

    # Khởi tạo TokenManager
    config_path = Path("config.json")
    token_manager = TokenManager(config_path, logger, config_dict=cfg)

    token = token_manager.get_valid_token()
    if not token:
        print("❌ Token không hợp lệ!")
        return

    # Lấy comment đầu tiên
    comments = test_fetch_comments()
    if not comments:
        print("❌ Không có comment nào để reply!")
        return

    comment = comments[0]
    comment_id = comment["id"]

    print("=" * 60)
    print("3️⃣  REPLY TO COMMENT")
    print("=" * 60)
    print(f"\n📌 Comment ID: {comment_id}")
    print(f"📝 Original message: {comment.get('message', '(no message)')}\n")

    reply_text = input("➡️  Nhập nội dung reply (Enter để skip): ").strip()

    if not reply_text:
        print("\n⏭️  Bỏ qua reply")
        return

    # Test reply
    version = cfg.get("graph_version", "v24.0")
    url = f"https://graph.facebook.com/{version}/{comment_id}/comments"

    import requests

    try:
        resp = requests.post(
            url, params={"access_token": token, "message": reply_text}, timeout=10
        )
        resp.raise_for_status()
        data = resp.json()

        print(f"\n✅ Reply thành công!")
        print(f"   Reply ID: {data.get('id')}")
        print(f"   Message: {reply_text}\n")

    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        print(f"Response: {e.response.text if e.response else 'N/A'}")
    except Exception as e:
        print(f"\n❌ Error: {e}")


def main():
    print("\n" + "=" * 60)
    print("🧪 FACEBOOK GRAPH API TESTER")
    print("=" * 60)

    print("\nChọn test:")
    print("1. Xem posts gần đây")
    print("2. Xem comments trong post")
    print("3. Reply vào comment")
    print("4. Test tất cả")

    choice = input("\n➡️  Nhập lựa chọn (1-4): ").strip()

    if choice == "1":
        test_fetch_posts()
    elif choice == "2":
        test_fetch_comments()
    elif choice == "3":
        test_reply_to_comment()
    elif choice == "4":
        test_fetch_posts()
        test_fetch_comments()
        print("\n💡 Nếu muốn test reply, chạy lại với option 3")
    else:
        print("❌ Lựa chọn không hợp lệ!")

    print("\n" + "=" * 60)
    print("✅ TEST HOÀN TẤT!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Đã hủy bởi user")
    except Exception as e:
        print(f"\n\n❌ Lỗi: {e}")
        import traceback

        traceback.print_exc()

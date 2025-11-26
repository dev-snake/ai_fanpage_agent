"""
Test trực tiếp Graph API để xem response thật
"""

import requests
import json
import os

# Load env
env_file = ".env"
for line in open(env_file):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, val = line.split("=", 1)
        os.environ[key.strip()] = val.strip()

token = os.getenv("GRAPH_ACCESS_TOKEN")
page_id = os.getenv("PAGE_ID")

print(f"Token: {token[:50]}...")
print(f"Page ID: {page_id}")

# Test 1: Get page posts
print("\n" + "=" * 60)
print("TEST 1: Fetch posts")
url = f"https://graph.facebook.com/v24.0/{page_id}/published_posts"
response = requests.get(url, params={"access_token": token, "limit": 2})
print(f"Status: {response.status_code}")
posts = response.json().get("data", [])
print(f"Found {len(posts)} posts")
if posts:
    post_id = posts[0]["id"]
    print(f"First post ID: {post_id}")

    # Test 2: Get comments WITH from field
    print("\n" + "=" * 60)
    print("TEST 2: Fetch comments with 'from' field")
    url2 = f"https://graph.facebook.com/v24.0/{post_id}/comments"

    response2 = requests.get(
        url2,
        params={
            "access_token": token,
            "filter": "stream",
            "limit": 10,  # Lấy nhiều hơn để tìm user comment
            "fields": "from{id,name,picture},message,created_time,permalink_url,id",
        },
    )
    print(f"Status: {response2.status_code}")
    data = response2.json()
    comments = data.get("data", [])
    print(f"Total comments: {len(comments)}")

    user_comments = []
    page_comments = []

    for comment in comments:
        from_id = comment.get("from", {}).get("id")
        if from_id == page_id:
            page_comments.append(comment)
        else:
            user_comments.append(comment)

    print(f"  - User comments: {len(user_comments)}")
    print(f"  - Page self-replies: {len(page_comments)}")

    if user_comments:
        print("\n🎯 USER COMMENTS (thật):")
        for i, c in enumerate(user_comments[:3]):
            print(f"\n  Comment {i+1}:")
            print(f"    From: {c.get('from', {}).get('name', 'Unknown')}")
            print(f"    From ID: {c.get('from', {}).get('id', 'N/A')}")
            print(f"    Message: {c.get('message', '(empty)')[:80]}")
            print(
                f"    Avatar: {c.get('from', {}).get('picture', {}).get('data', {}).get('url', 'N/A')[:80]}"
            )
    else:
        print("\n⚠️  NO USER COMMENTS FOUND - Tất cả comments đều là page tự reply!")

    if page_comments:
        print("\n📄 PAGE SELF-REPLIES:")
        for i, c in enumerate(page_comments[:2]):
            print(f"  Reply {i+1}: {c.get('message', '')[:60]}")
else:
    print("No posts found!")

# Test 3: Check token permissions
print("\n" + "=" * 60)
print("TEST 3: Check token permissions")
debug_url = "https://graph.facebook.com/v24.0/debug_token"
response3 = requests.get(
    debug_url, params={"input_token": token, "access_token": token}
)
debug_data = response3.json().get("data", {})
print(f"Token type: {debug_data.get('type')}")
print(f"App ID: {debug_data.get('app_id')}")
print(f"User ID: {debug_data.get('user_id')}")
print(f"Scopes: {debug_data.get('scopes', [])}")
print(f"Expires: {debug_data.get('expires_at', 'Never')}")

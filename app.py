from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import time
import json
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Register optional external route modules
try:
    from messenger import register_messenger_routes
    register_messenger_routes(app)
except Exception:
    # If messenger module is missing or raises on import, continue without it.
    pass

# ==============================
# 🔐 CẤU HÌNH
# ==============================
APP_ID = "539235329188410"
APP_SECRET = "87ac73c3ab4666955d2ca00b9900b051"

TOKEN_FILE = "fb_system_user_token.txt"

PAGE_TOKENS = {}
PAGE_TOKENS_FETCHED_AT = 0
PAGE_TOKENS_TTL = 60 * 60  # 1 giờ cache

# ==============================
# 🔐 TOKEN FILE HANDLING
# ==============================
def get_system_user_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return os.getenv("FB_SYSTEM_USER_TOKEN", "").strip()


def save_system_user_token(token: str):
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(token.strip())
    print("💾 Saved System User Token to file.")


# ==============================
# 🔄 FETCH PAGE TOKENS
# ==============================
def normalize_id(value):
    """Loại bỏ BOM, ký tự ẩn và ép về string"""
    if value is None:
        return ""
    return str(value).replace("\ufeff", "").replace("\u200b", "").strip()


def fetch_page_tokens(force=False):
    global PAGE_TOKENS, PAGE_TOKENS_FETCHED_AT

    token = get_system_user_token()
    if not token:
        raise Exception("System User Token chưa được cấu hình. Gọi /api/update-token")

    now = time.time()

    if not force and PAGE_TOKENS and (now - PAGE_TOKENS_FETCHED_AT) < PAGE_TOKENS_TTL:
        print("ℹ️ Using cached PAGE_TOKENS")
        return

    print("📡 Fetching PAGE_TOKENS from Facebook...")

    url = "https://graph.facebook.com/v18.0/me/accounts"
    res = requests.get(url, params={"access_token": token})
    data = res.json()

    if "error" in data:
        print("❌ Error from Facebook:", data["error"])
        raise Exception(f"Lỗi khi lấy page token: {data['error']}")

    if "data" not in data:
        raise Exception(f"Lỗi bất thường khi lấy page token: {data}")

    PAGE_TOKENS = {}

    for p in data["data"]:
        pid = normalize_id(p["id"])
        PAGE_TOKENS[pid] = {
            "pageId": pid,
            "name": p.get("name", ""),
            "access_token": p["access_token"],
        }

    PAGE_TOKENS_FETCHED_AT = now
    print(f"✅ Cached {len(PAGE_TOKENS)} page tokens.")
    print("🔎 PAGE_TOKENS keys:", list(PAGE_TOKENS.keys()))


# ==============================
# 🌐 API ENDPOINTS
# ==============================
@app.route("/api/get-token")
def get_token():
    try:
        fetch_page_tokens(force=False)
        return jsonify(PAGE_TOKENS)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "timestamp": int(time.time()),
        "pages_cached": len(PAGE_TOKENS),
    })


@app.route("/api/update-token", methods=["POST"])
def update_token():
    global PAGE_TOKENS, PAGE_TOKENS_FETCHED_AT

    try:
        data = request.get_json(force=True) or {}
        token = data.get("token", "").strip()

        if not token:
            return jsonify({"error": "Thiếu trường 'token'"}), 400

        save_system_user_token(token)

        PAGE_TOKENS = {}
        PAGE_TOKENS_FETCHED_AT = 0

        fetch_page_tokens(force=True)

        return jsonify({
            "message": "✅ System User Token updated successfully",
            "pages_cached": len(PAGE_TOKENS),
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# 🗑 API DELETE COMMENT
# ==============================
@app.route("/api/delete-comment", methods=["POST"])
def delete_comment():
    """
    {
        "commentId": "123",
        "pageId": "881733028346164"
    }
    """
    try:
        data = request.get_json(force=True) or {}

        comment_id = normalize_id(data.get("commentId", ""))
        page_id = normalize_id(data.get("pageId", ""))

        if not comment_id or not page_id:
            return jsonify({"error": "Thiếu commentId hoặc pageId"}), 400

        # load tokens
        fetch_page_tokens(force=False)

        # Debug log
        print("===================================")
        print("📝 DEBUG_KEYS:", list(PAGE_TOKENS.keys()))
        print("📝 DEBUG_PAGE_ID:", repr(page_id))
        print("===================================")

        if page_id not in PAGE_TOKENS:
            return jsonify({
                "error": f"Không tìm thấy pageId = {page_id} trong PAGE_TOKENS",
                "pages_available": list(PAGE_TOKENS.keys())
            }), 400

        page_token = PAGE_TOKENS[page_id]["access_token"]

        fb_url = f"https://graph.facebook.com/{comment_id}"
        fb_res = requests.delete(fb_url, params={"access_token": page_token})
        fb_data = fb_res.json()

        if "error" in fb_data:
            return jsonify({
                "status": "warning",
                "message": "Comment có thể đã bị xoá trước hoặc không tồn tại",
                "facebook": fb_data
            }), 200

        return jsonify({
            "status": "success",
            "deletedCommentId": comment_id,
            "facebook": fb_data
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# 🚀 RUN SERVER
# ==============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

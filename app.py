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

# File lưu System User Token
TOKEN_FILE = "fb_system_user_token.txt"

# Cache page tokens trong RAM
PAGE_TOKENS = {}
PAGE_TOKENS_FETCHED_AT = 0
PAGE_TOKENS_TTL = 60 * 60  # 1 giờ cache

# ==============================
# 🔐 TOKEN: ALWAYS READ FROM FILE
# ==============================
def get_system_user_token():
    """
    Luôn đọc token mới nhất từ file.
    Không dùng biến toàn cục SYSTEM_USER_TOKEN nữa.
    """
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            token = f.read().strip()
            return token

    # fallback (ít khi dùng)
    return os.getenv("FB_SYSTEM_USER_TOKEN", "").strip()


def save_system_user_token(token: str):
    """
    Ghi System User Token vào file.
    API sẽ tự động đọc token mới trong các request tiếp theo.
    """
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(token.strip())
    print("💾 Saved System User Token to file.")


# ==============================
# 🔄 LẤY PAGE TOKENS
# ==============================
def fetch_page_tokens(force=False):
    """
    Lấy danh sách page (pageId + pageAccessToken) từ System User Token.
    Cache 1 giờ.
    Nếu force=True → gọi lại Facebook ngay.
    """

    global PAGE_TOKENS, PAGE_TOKENS_FETCHED_AT

    token = get_system_user_token()

    if not token:
        raise Exception("System User Token chưa được cấu hình. Gọi /api/update-token")

    now = time.time()

    # Dùng cache nếu còn hạn và không force
    if not force and PAGE_TOKENS and (now - PAGE_TOKENS_FETCHED_AT) < PAGE_TOKENS_TTL:
        print("ℹ️ Using cached PAGE_TOKENS.")
        return

    print("📡 Fetching PAGE_TOKENS from Facebook...")

    url = "https://graph.facebook.com/v18.0/me/accounts"
    params = {"access_token": token}
    res = requests.get(url, params=params)
    data = res.json()

    if "error" in data:
        print("❌ Error from Facebook:", data["error"])
        raise Exception(f"Lỗi khi lấy page token: {data['error']}")

    if "data" not in data:
        raise Exception(f"Lỗi bất thường khi lấy page token: {data}")

    PAGE_TOKENS = {
        p["id"]: {
            "pageId": p["id"],
            "name": p.get("name", ""),
            "access_token": p["access_token"],
        }
        for p in data["data"]
    }

    PAGE_TOKENS_FETCHED_AT = now
    print(f"✅ Cached {len(PAGE_TOKENS)} page tokens.")


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
    """
    Cập nhật System User Token mới.
    Body JSON:
    {
      "token": "EAAG....."
    }
    """
    global PAGE_TOKENS, PAGE_TOKENS_FETCHED_AT

    try:
        print("📥 Nhận request /api/update-token")
        data = request.get_json(force=True) or {}
        token = data.get("token", "").strip()

        if not token:
            return jsonify({"error": "Thiếu trường 'token' trong request body"}), 400

        # Lưu token mới vào file
        save_system_user_token(token)

        # Reset cache
        PAGE_TOKENS = {}
        PAGE_TOKENS_FETCHED_AT = 0

        # Fetch lại token mới
        fetch_page_tokens(force=True)

        return jsonify({
            "message": "✅ System User Token updated successfully",
            "pages_cached": len(PAGE_TOKENS),
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

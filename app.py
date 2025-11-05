from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import time
import os

app = Flask(__name__)

# ✅ Cho phép request từ bất kỳ domain nào (tạm thời)
# Bạn có thể giới hạn lại sau: CORS(app, resources={r"/*": {"origins": ["https://autopostfb.duckdns.org"]}})
CORS(app, resources={r"/*": {"origins": "*"}})

# =============================
# ⚙️ Cấu hình cơ bản
# =============================
APP_ID = "539235329188410"
APP_SECRET = "87ac73c3ab4666955d2ca00b9900b051"
LONG_LIVED_USER_TOKEN = "EAAHqboIZCIjoBP6uMGtxqZCZAJMZBbRmMXg5umw5ZAanJrlj8bBYnZCF1ZBb6ZBcpU9oRBaVTk15RmmEUtTZAD9nnGaf8t3PcawnZByAkpjZCLwAfW9X848wiCX5kOQZAe8LtZBW6UpQ9j3r3hFKGbqnuZAZCnUbtPeqDMH6CxRgUwW33Qb3UaTjL9VwbouxZCJpUWhtSm6RfwZDZD"

PAGE_TOKENS = {}
TOKEN_EXPIRE = int(time.time()) + 60 * 60 * 24 * 50  # Giả định 50 ngày, cập nhật sau khi debug

# =============================
# 🔁 Hàm lấy Page Access Tokens
# =============================
def fetch_page_tokens():
    global PAGE_TOKENS, TOKEN_EXPIRE
    url = "https://graph.facebook.com/v18.0/me/accounts"
    params = {"access_token": LONG_LIVED_USER_TOKEN}
    res = requests.get(url, params=params).json()

    if "data" not in res:
        raise Exception(f"Lỗi khi lấy page token: {res}")

    PAGE_TOKENS = {
        page["id"]: {
            "pageId": page["id"],
            "name": page["name"],
            "access_token": page["access_token"],
        }
        for page in res["data"]
    }

    # 🔎 Kiểm tra hạn dùng user token
    debug_url = "https://graph.facebook.com/v18.0/debug_token"
    app_token = f"{APP_ID}|{APP_SECRET}"
    params = {"input_token": LONG_LIVED_USER_TOKEN, "access_token": app_token}
    debug_res = requests.get(debug_url, params=params).json()

    if "data" in debug_res:
        TOKEN_EXPIRE = debug_res["data"].get("expires_at", TOKEN_EXPIRE)

# =============================
# 🧠 API: Lấy danh sách / token
# =============================
@app.route("/get-token", methods=["GET"])
def get_token():
    """Trả về token của page theo page_id hoặc page_name"""
    global PAGE_TOKENS, TOKEN_EXPIRE

    now = int(time.time())
    if not PAGE_TOKENS or now > TOKEN_EXPIRE - 3600:
        fetch_page_tokens()

    page_id = request.args.get("page_id")
    page_name = request.args.get("page_name")

    if page_id and page_id in PAGE_TOKENS:
        pdata = PAGE_TOKENS[page_id]
        return jsonify({
            "page_id": pdata["pageId"],
            "page_name": pdata["name"],
            "access_token": pdata["access_token"],
            "expires_at": TOKEN_EXPIRE
        })

    elif page_name:
        for pid, pdata in PAGE_TOKENS.items():
            if pdata["name"].lower() == page_name.lower():
                return jsonify({
                    "page_id": pid,
                    "page_name": pdata["name"],
                    "access_token": pdata["access_token"],
                    "expires_at": TOKEN_EXPIRE
                })
        return jsonify({"error": "Không tìm thấy page với tên đó"}), 404

    return jsonify({
        "pages": list(PAGE_TOKENS.values()),
        "expires_at": TOKEN_EXPIRE
    })

# =============================
# 🆕 API: Cập nhật token thủ công
# =============================
@app.route("/update-token", methods=["POST"])
def update_token():
    """Cập nhật LONG_LIVED_USER_TOKEN từ client"""
    global LONG_LIVED_USER_TOKEN, PAGE_TOKENS, TOKEN_EXPIRE

    data = request.get_json(force=True)
    new_token = data.get("token")
    if not new_token:
        return jsonify({"error": "Thiếu token mới"}), 400

    LONG_LIVED_USER_TOKEN = new_token
    try:
        fetch_page_tokens()
        return jsonify({
            "message": "✅ Token đã được cập nhật thành công!",
            "expires_at": TOKEN_EXPIRE,
            "pages": list(PAGE_TOKENS.values())
        })
    except Exception as e:
        return jsonify({"error": f"❌ Token không hợp lệ: {e}"}), 400

# =============================
# 🩺 API: Health check
# =============================
@app.route("/status", methods=["GET"])
def status():
    now = int(time.time())
    remain_days = round((TOKEN_EXPIRE - now) / 86400, 2)
    return jsonify({
        "status": "ok",
        "pages_loaded": len(PAGE_TOKENS),
        "token_expires_in_days": remain_days
    })

# =============================
# 🚀 Run server
# =============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

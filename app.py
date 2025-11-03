from flask import Flask, jsonify, request
import requests
import time

app = Flask(__name__)

# =============================
# Cấu hình cơ bản
# =============================
#APP_ID = "23979385011735799"
APP_ID = "539235329188410"
#APP_SECRET = "8ad64b82ac289af14d25b3b45647f046"
APP_SECRET = "87ac73c3ab4666955d2ca00b9900b051"
#LONG_LIVED_USER_TOKEN = "EAFUxH6WOjPcBPjHJsT1dSFsteinRntF7yUFK5ngONpQga03PHtPGFQCTam8qpbIGmvmNqApLVs6NBrZBAAd5ZAuv427oX8dxeZAQXtiqwWP3TNUk2aEUHLPlHdQszcxhWTI636FZC6stVheGlj0UIVTZB5h2vnZASTB1xBpglPCn4TXgO4KgxIoKgkZC2Lps8VchwZDZD"
LONG_LIVED_USER_TOKEN = "EAAHqboIZCIjoBP6uMGtxqZCZAJMZBbRmMXg5umw5ZAanJrlj8bBYnZCF1ZBb6ZBcpU9oRBaVTk15RmmEUtTZAD9nnGaf8t3PcawnZByAkpjZCLwAfW9X848wiCX5kOQZAe8LtZBW6UpQ9j3r3hFKGbqnuZAZCnUbtPeqDMH6CxRgUwW33Qb3UaTjL9VwbouxZCJpUWhtSm6RfwZDZD"

# Cache để lưu page token và hạn dùng
PAGE_TOKENS = {}
TOKEN_EXPIRE = int(time.time()) + 60*60*24*50  # giả định 50 ngày, sẽ update khi debug


# =============================
# Hàm lấy Page Access Tokens
# =============================
def fetch_page_tokens():
    global PAGE_TOKENS, TOKEN_EXPIRE
    url = "https://graph.facebook.com/v18.0/me/accounts"
    params = {"access_token": LONG_LIVED_USER_TOKEN}
    res = requests.get(url, params=params).json()

    if "data" not in res:
        raise Exception(f"Lỗi khi lấy page token: {res}")

    PAGE_TOKENS = {}
    for page in res["data"]:
        PAGE_TOKENS[page["id"]] = {
    "pageId": page["id"],
    "name": page["name"],
    "access_token": page["access_token"]
}


    # Kiểm tra hạn dùng user token
    debug_url = "https://graph.facebook.com/v18.0/debug_token"
    app_token = f"{APP_ID}|{APP_SECRET}"
    params = {"input_token": LONG_LIVED_USER_TOKEN, "access_token": app_token}
    debug_res = requests.get(debug_url, params=params).json()
    if "data" in debug_res:
        TOKEN_EXPIRE = debug_res["data"].get("expires_at", TOKEN_EXPIRE)


# =============================
# API endpoint
# =============================

@app.route("/get-token", methods=["GET"])
def get_token():
    """Trả về token của page theo page_id hoặc page_name"""
    global PAGE_TOKENS, TOKEN_EXPIRE

    # Nếu token chưa có hoặc sắp hết hạn thì refresh
    now = int(time.time())
    if not PAGE_TOKENS or now > TOKEN_EXPIRE - 3600:
        fetch_page_tokens()

    page_id = request.args.get("page_id")
    page_name = request.args.get("page_name")

    if page_id and page_id in PAGE_TOKENS:
        return jsonify({
            "page_id": page_id,
            "page_name": PAGE_TOKENS[page_id]["name"],
            "access_token": PAGE_TOKENS[page_id]["access_token"]
        })
    elif page_name:
        for pid, pdata in PAGE_TOKENS.items():
            if pdata["name"].lower() == page_name.lower():
                return jsonify({
                    "page_id": pid,
                    "page_name": pdata["name"],
                    "access_token": pdata["access_token"]
                })
        return jsonify({"error": "Không tìm thấy page với tên đó"}), 404
    else:
        return jsonify(PAGE_TOKENS)


# =============================
# Run server
# =============================
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))  # Railway sẽ tự set PORT
    app.run(host="0.0.0.0", port=port)

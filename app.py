from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import time
import json
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

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
# 🔐 HÀM ĐỌC / GHI TOKEN TỪ FILE
# ==============================
def load_system_user_token():
  """
  Đọc System User Token từ file.
  Nếu không có file thì dùng tạm env / hard-code (tuỳ bạn).
  """
  global SYSTEM_USER_TOKEN

  if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
      token = f.read().strip()
      if token:
        SYSTEM_USER_TOKEN = token
        print("✅ Loaded System User Token from file.")
        return

  # fallback: hard-code hoặc biến môi trường
  SYSTEM_USER_TOKEN = os.getenv("FB_SYSTEM_USER_TOKEN", "").strip()
  if SYSTEM_USER_TOKEN:
    print("⚠️ Using System User Token from ENV (chưa ghi file).")
  else:
    print("❌ Chưa cấu hình System User Token! Hãy gọi /api/update-token để cập nhật.")


def save_system_user_token(token: str):
  """
  Ghi System User Token vào file.
  """
  global SYSTEM_USER_TOKEN
  SYSTEM_USER_TOKEN = token.strip()
  with open(TOKEN_FILE, "w", encoding="utf-8") as f:
    f.write(SYSTEM_USER_TOKEN)
  print("💾 Saved System User Token to file.")


# Gọi ngay khi server start
load_system_user_token()


# ==============================
# 🔄 HÀM LẤY PAGE TOKENS TỪ FACEBOOK
# ==============================
def fetch_page_tokens(force=False):
  """
  Lấy danh sách page (pageId + pageAccessToken) từ System User Token.
  Có cache 1 giờ; nếu force=True thì luôn gọi lại.
  """
  global PAGE_TOKENS, PAGE_TOKENS_FETCHED_AT, SYSTEM_USER_TOKEN

  # Kiểm tra đã có token chưa
  if not SYSTEM_USER_TOKEN:
    raise Exception("System User Token chưa được cấu hình. Hãy gọi /api/update-token.")

  now = time.time()
  # Dùng cache nếu còn hạn và không force
  if not force and PAGE_TOKENS and (now - PAGE_TOKENS_FETCHED_AT) < PAGE_TOKENS_TTL:
    print("ℹ️ Using cached PAGE_TOKENS.")
    return

  print("📡 Fetching PAGE_TOKENS from Facebook...")
  url = "https://graph.facebook.com/v18.0/me/accounts"
  params = {"access_token": SYSTEM_USER_TOKEN}
  res = requests.get(url, params=params)
  data = res.json()

  if "error" in data:
    print("❌ Error from Facebook:", data["error"])
    raise Exception(f"Lỗi khi lấy page token: {data['error']}")

  if "data" not in data:
    raise Exception(f"Lỗi bất thường khi lấy page token: {data}")

  # Map pageId -> info
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
  """
  Trả về danh sách page token để FE chọn fanpage.
  Format:
  {
    "123456789": {
      "pageId": "123456789",
      "name": "Page ABC",
      "access_token": "EAAG..."
    },
    "999999999": { ... }
  }
  """
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
  Cho phép cập nhật System User Token mới (nếu bạn regenerate trong Business).
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

    # Lưu token mới vào file + RAM
    save_system_user_token(token)

    # Reset cache page
    PAGE_TOKENS = {}
    PAGE_TOKENS_FETCHED_AT = 0

    # Fetch lại page token
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
  # Chạy dev, production thì nên dùng gunicorn/uwsgi
  app.run(host="0.0.0.0", port=8000, debug=True)

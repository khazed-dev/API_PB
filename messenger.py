from flask import request, jsonify
import requests
import os


# Optional: hard-code page id and access token here. Leave empty to use
# environment variables or token file `fb_system_user_token.txt`.
FB_PAGE_ID = "107521941056856"  # e.g. "107521941056856"
FB_PAGE_ACCESS_TOKEN = "EAAZAmeBmEFmIBPw4fLsBJKa0IVZC9wG3XENKBV4dCBMC2ZCu2jfJwEDAqIEppHYFdUwJ9tteuagBglEf6zEiX1SakTJNHE8E7Iu1uTRImHBZCfeUbMzwx62uU9bVZAJwGWAz5EJiZC5tHgkwNshBzFQh0virkCoJ2KJqkUl5WmrR709ZBa5h3VmK5UtdI95m6xmh7YXYpjHSsbZAyWdjjnEZD"


def register_messenger_routes(app):
    """
    Register /send-messenger-message route on the provided Flask `app`.

    Resolution order for configuration:
    1. Hard-coded constants in this file (`FB_PAGE_ID`, `FB_PAGE_ACCESS_TOKEN`) if set.
    2. Environment variables: `FB_PAGE_ID`, `FB_PAGE_ACCESS_TOKEN`.
    3. Fallback token file: `fb_system_user_token.txt` (only for access token).
    """

    def _get_access_token():
        # 1) constant
        if FB_PAGE_ACCESS_TOKEN:
            return FB_PAGE_ACCESS_TOKEN.strip()

        # 2) env
        token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "").strip()
        if token:
            return token

        # 3) token file
        token_file = "fb_system_user_token.txt"
        if os.path.exists(token_file):
            try:
                with open(token_file, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass

        return ""

    def _get_page_id():
        # 1) constant
        if FB_PAGE_ID:
            return FB_PAGE_ID.strip()

        # 2) env
        return os.environ.get("FB_PAGE_ID", "").strip()

    @app.route('/send-messenger-message', methods=['POST'])
    def send_message():
        data = request.get_json(silent=True) or {}

        recipient_id = data.get('recipient_id')
        message_text = data.get('message_text')

        if not recipient_id or not message_text:
            return jsonify({"error": "Missing recipient_id or message_text"}), 400

        page_id = _get_page_id()
        access_token = _get_access_token()

        if not page_id:
            return jsonify({"error": "FB_PAGE_ID not configured. Set FB_PAGE_ID env var or fill FB_PAGE_ID in messenger.py"}), 500

        if not access_token:
            return jsonify({"error": "Access token not configured. Set FB_PAGE_ACCESS_TOKEN env var or create fb_system_user_token.txt or fill FB_PAGE_ACCESS_TOKEN in messenger.py"}), 500

        # Use the documented Send API endpoint. Passing the page access token via
        # Authorization header is supported, but some errors are clearer when
        # calling /me/messages and letting Graph infer the page from the token.
        facebook_api_url = "https://graph.facebook.com/v23.0/me/messages"

        # Include messaging_type (required by Send API for many requests).
        payload = {
            "messaging_type": "RESPONSE",
            "recipient": {"id": recipient_id},
            "message": {"text": message_text}
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        try:
            resp = requests.post(facebook_api_url, headers=headers, json=payload, timeout=10)
            resp.raise_for_status()
            return jsonify(resp.json()), 200
        except requests.exceptions.HTTPError as he:
            # Try to return the raw JSON/text from Facebook to help debugging
            details = None
            try:
                details = he.response.json()
            except Exception:
                try:
                    details = he.response.text
                except Exception:
                    details = str(he)
            return jsonify({"error": "Failed to send message to Facebook API", "details": details}), he.response.status_code if he.response is not None else 500
        except requests.exceptions.RequestException as e:
            return jsonify({"error": "Failed to send message to Facebook API", "details": str(e)}), 500

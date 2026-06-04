from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# 模擬的資料庫與 FAQ 知識庫（期末 RAG 的資料來源）
MOCK_DATABASE = {
    "orders": {
        "12345": {"status": "已出貨", "carrier": "7-11超商取貨", "payment": "已付款"},
        "67890": {"status": "備貨中", "carrier": "宅配到府", "payment": "貨到付款"}
    },
    "products": {
        "書本": "熱銷商品：《Python與AI微專題實作》，售價 $450 元，庫存充足。",
        "購物車": "智慧縮小版推車模型，售價 $299 元，補貨中。"
    },
    "faq": {
        "refund": "【退換貨說明】我們提供 7 天鑑賞期，請保持商品全新包裝於後台申請退貨。",
        "shipping": "【配送方式】支援 7-11、全家超商取貨（運費 $60），滿 $499 免運費。",
        "payment": "【付款狀態】支援信用卡、ATM 轉帳、LINE Pay 以及貨到付款。",
        "general": "【常見問題】若有其他疑問，歡迎撥打客服專線或於上班時間聯繫專人。"
    }
}

@app.route('/')
def home():
    # 渲染前端網頁
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json() or {}
    message = data.get('message', '').strip()
    action = data.get('action', '')  # 用來判斷是不是點擊分類方塊

    # 1. 處理點擊「分類方塊」的快速回覆
    if action:
        if action == "order_status":
            return jsonify({"reply": "🤖 訂單查詢：請輸入您的【訂單編號】（例如：12345），系統將為您查詢進度。"})
        elif action == "product_search":
            return jsonify({"reply": "🤖 商品查詢：請問您想尋找什麼商品呢？可以輸入關鍵字（例如：書本、購物車）。"})
        elif action == "refund_info":
            return jsonify({"reply": f"🤖 {MOCK_DATABASE['faq']['refund']}"})
        elif action == "shipping_info":
            return jsonify({"reply": f"🤖 {MOCK_DATABASE['faq']['shipping']}"})
        elif action == "payment_info":
            return jsonify({"reply": f"🤖 {MOCK_DATABASE['faq']['payment']}"})
        elif action == "faq_info":
            return jsonify({"reply": f"🤖 {MOCK_DATABASE['faq']['general']}"})

    # 2. 處理輸入框文字對話（簡易 RAG / 關鍵字比對邏輯）
    if not message:
        return jsonify({"reply": "請輸入您的問題！"})

    # 檢查是否為訂單編號查詢
    if message in MOCK_DATABASE["orders"]:
        order = MOCK_DATABASE["orders"][message]
        return jsonify({"reply": f"📦 訂單【{message}】查詢結果：<br>付款狀態：{order['payment']}<br>配送方式：{order['carrier']}<br>目前進度：<strong>{order['status']}</strong>"})
    
    # 檢查是否為商品關鍵字查詢
    for prod_key, prod_val in MOCK_DATABASE["products"].items():
        if prod_key in message:
            return jsonify({"reply": f"🔍 商品查詢結果：{prod_val}"})

    # FAQ 模糊比對
    if "退" in message or "換" in message:
        return jsonify({"reply": MOCK_DATABASE["faq"]["refund"]})
    elif "運費" in message or "配送" in message or "寄送" in message:
        return jsonify({"reply": MOCK_DATABASE["faq"]["shipping"]})
    elif "付" in message or "刷卡" in message:
        return jsonify({"reply": MOCK_DATABASE["faq"]["payment"]})
    
    # 預設回覆
    return jsonify({"reply": f"🤖 收到您的訊息：「{message}」。針對此問題，您可以點擊上方的分類方塊獲取即時解答，或輸入測試單號「12345」體驗訂單查詢功能！"})

if __name__ == '__main__':
    # 這裡已經幫你修改為 port=5001 避開 Mac 的 AirPlay 衝突囉！
    app.run(host='0.0.0.0', port=5001, debug=True)
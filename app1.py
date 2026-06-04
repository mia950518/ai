from flask import Flask, request, jsonify, render_template
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForCausalLM
import numpy as np
import json
import csv
import os
import torch

app = Flask(__name__)

# 模擬的資料庫與 FAQ 知識庫
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
        "payment": "【付款方式】支援信用卡、ATM 轉帳、LINE Pay 以及貨到付款。",
        "general": "【常見問題】若有其他疑問，歡迎撥打客服專線或於上班時間聯繫專人。"
    }
}

# 1. 載入 BGE 向量模型 (BAAI/bge-small-zh-v1.5)
print("正在載入 BGE 向量模型 (BAAI/bge-small-zh-v1.5)...")
embedding_model = SentenceTransformer("BAAI/bge-small-zh-v1.5")

# 2. 載入 Qwen/Qwen2.5-3B-Instruct 客服大語言模型
LLM_MODEL_NAME = "Qwen/Qwen2.5-3B-Instruct"
device = "mps" if torch.backends.mps.is_available() else "cpu"

print(f"正在載入 Qwen 客服大模型 ({LLM_MODEL_NAME}) 到裝置: {device}...")
tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL_NAME)
llm_model = AutoModelForCausalLM.from_pretrained(
    LLM_MODEL_NAME,
    torch_dtype=torch.float16 if device == "mps" else torch.float32,
    device_map=None
).to(device)
print("大語言模型載入完成！")

# 3. 載入 FAQ 與書籍資料，並建立統一的 RAG 知識檢索庫
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
knowledge_base = []

# A. 載入 FAQ
FAQ_PATH = os.path.join(BASE_DIR, "data", "faq.json")
try:
    with open(FAQ_PATH, "r", encoding="utf-8") as f:
        faq_data = json.load(f)
    for item in faq_data:
        knowledge_base.append({
            "type": "faq",
            "search_text": f"常見問題：{item['question']} 官方解答：{item['answer']}",
            "payload": item
        })
    print(f"成功載入 FAQ 知識庫，共 {len(faq_data)} 筆資料。")
except Exception as e:
    print(f"載入 FAQ 知識庫失敗: {e}")

# B. 載入 CSV 書籍資料
BOOKS_CSV_PATH = os.path.join(BASE_DIR, "books_products.csv")
try:
    with open(BOOKS_CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        books_count = 0
        for row in reader:
            search_text = (
                f"書名：{row.get('書名', '')} "
                f"作者：{row.get('作者', '')} "
                f"分類：{row.get('商品分類', '')} "
                f"出版社：{row.get('出版社', '')} "
                f"大分類：{row.get('大分類', '')}"
            )
            knowledge_base.append({
                "type": "book",
                "search_text": search_text,
                "payload": row
            })
            books_count += 1
    print(f"成功載入圖書資料庫，共 {books_count} 筆資料。")
except Exception as e:
    print(f"載入圖書資料庫失敗: {e}")

# 對整個知識庫編碼向量
print("正在將知識庫向量化 (BGE-small)...")
knowledge_texts = [item["search_text"] for item in knowledge_base]
knowledge_embeddings = embedding_model.encode(knowledge_texts)
print("所有知識庫向量編碼完成，系統準備就緒！")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    action = data.get("action", "")
    user_message = data.get("message", "").strip()

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

    # 2. 處理輸入框對話邏輯
    if not user_message:
        return jsonify({"reply": "請輸入您的問題。"})

    # A. 檢查是否為訂單編號查詢
    if user_message in MOCK_DATABASE["orders"]:
        order = MOCK_DATABASE["orders"][user_message]
        return jsonify({"reply": f"📦 訂單【{user_message}】查詢結果：<br>付款方式：{order['payment']}<br>配送方式：{order['carrier']}<br>目前進度：<strong>{order['status']}</strong>"})

    # B. 檢查是否為商品關鍵字查詢
    for prod_key, prod_val in MOCK_DATABASE["products"].items():
        if prod_key in user_message:
            return jsonify({"reply": f"🔍 商品查詢結果：{prod_val}"})

    # C. RAG 語意相似度檢索 (整合 FAQ 與 CSV 書籍)
    user_embedding = embedding_model.encode([user_message])[0]
    similarities = []
    for k_emb in knowledge_embeddings:
        similarity = cosine_similarity(user_embedding, k_emb)
        similarities.append(similarity)

    best_index = int(np.argmax(similarities))
    best_score = similarities[best_index]
    matched_item = knowledge_base[best_index]

    # 設定語意匹配閾值 (BGE 餘弦相似度設為 0.60)
    if best_score >= 0.60:
        if matched_item["type"] == "book":
            book = matched_item["payload"]
            context = (
                f"書籍名稱：{book.get('書名', '')}\n"
                f"作者：{book.get('作者', '')}\n"
                f"譯者：{book.get('譯者', '')}\n"
                f"出版社：{book.get('出版社', '')}\n"
                f"出版日期：{book.get('出版日期', '')}\n"
                f"語言：{book.get('語言', '')}\n"
                f"價格：NT$ {book.get('價格', '')} 元\n"
                f"庫存量：{book.get('庫存量', '')}\n"
                f"ISBN：{book.get('ISBN', '')}\n"
                f"大分類：{book.get('大分類', '')}\n"
                f"商品分類：{book.get('商品分類', '')}\n"
                f"商品網址：{book.get('商品網址', '')}"
            )
            
            system_prompt = (
                "你是一個親切有禮的 Book-in-Cart 智慧圖書客服助理。請根據以下提供的「官方參考書籍資料」簡短回答。"
                "請務必「使用繁體中文（台灣）」回答。"
                "你的回答必須溫暖、簡潔、有禮貌。向使用者推薦介紹書籍，「必須附帶」商品網址。字數限制在 60 至 100 字之內，語氣要親切。"
            )
            user_prompt = f"【官方參考書籍資料】\n{context}\n\n【使用者問題】\n{user_message}"
        else:
            # FAQ 類型
            faq = matched_item["payload"]
            context = f"常見問題：{faq.get('question', '')}\n官方解答：{faq.get('answer', '')}"
            
            system_prompt = (
                "你是一個親切有禮的 Book-in-Cart 智慧客服助理。請根據以下提供的「官方參考資料」簡短回答。"
                "請務必「使用繁體中文（台灣）」回答。"
                "回答必須專業、溫暖、精簡，且「完全符合」官方參考資料的內容。字數限制在 40 至 70 字之內，不要冗長。"
            )
            user_prompt = f"【官方參考資料】\n{context}\n\n【使用者問題】\n{user_message}"
    else:
        system_prompt = (
            "你是一個親切有禮的 Book-in-Cart 智慧客服助理。"
            "請務必「使用繁體中文（台灣）」回答。"
            "很抱歉，目前官方圖書庫與知識庫中沒有此問題的解答。請用一兩句簡短有禮的話向使用者說明，"
            "並主動引導他們可以點擊畫面上的「分類方塊」尋找幫助，或輸入測試訂單編號「12345」進行查詢，或聯繫人工客服。字數限制在 50 至 80 字之內，語氣要溫馨。"
        )
        user_prompt = user_message

    # 使用 Qwen Chat Template 組合對話並生成回應
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        model_inputs = tokenizer([text], return_tensors="pt").to(device)
        
        with torch.no_grad():
            generated_ids = llm_model.generate(
                **model_inputs,
                max_new_tokens=150,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                repetition_penalty=1.1
            )
        
        generated_ids = [
            output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]
        reply = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
    except Exception as e:
        # 降級備份回覆 (萬一 LLM 生成超時或出錯)
        if best_score >= 0.60:
            if matched_item["type"] == "book":
                book = matched_item["payload"]
                reply = f"您好，我們有賣這本書喔！《{book.get('書名', '')}》由{book.get('作者', '')}著作，價格為 NT$ {book.get('價格', '')} 元。商品詳情請參考：{book.get('商品網址', '')}"
            else:
                faq = matched_item["payload"]
                reply = f"您好，根據官方客服資料：{faq.get('answer', '')}"
        else:
            reply = f"🤖 收到您的訊息：「{user_message}」。針對此問題，您可以點擊上方的分類方塊獲取即時解答，或輸入測試單號「12345」體驗訂單查詢功能！"

    return jsonify({"reply": reply})

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True, use_reloader=False)
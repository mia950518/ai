from __future__ import annotations

import csv
import base64
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from typing import Any

from flask import Flask, jsonify, render_template, request


app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WOOCOMMERCE_BASE_URL = os.environ.get("WOOCOMMERCE_BASE_URL", "").rstrip("/")
WOOCOMMERCE_CONSUMER_KEY = os.environ.get("WOOCOMMERCE_CONSUMER_KEY", "")
WOOCOMMERCE_CONSUMER_SECRET = os.environ.get("WOOCOMMERCE_CONSUMER_SECRET", "")
app.logger.info("BASE_URL: %s", WOOCOMMERCE_BASE_URL or "(not set)")
app.logger.info("KEY exists: %s", bool(WOOCOMMERCE_CONSUMER_KEY))
app.logger.info("SECRET exists: %s", bool(WOOCOMMERCE_CONSUMER_SECRET))


ORDERS: dict[str, dict[str, str]] = {
    "140": {
        "status": "完成",
        "carrier": "購物網站 API",
        "payment": "依 WooCommerce 訂單資料為準",
        "items": "WordPress / WooCommerce 訂單",
    },
    "12345": {
        "status": "已出貨",
        "carrier": "7-11 超商取貨",
        "payment": "已付款",
        "items": "被討厭的勇氣 1 本",
    },
    "67890": {
        "status": "備貨中",
        "carrier": "宅配到府",
        "payment": "貨到付款",
        "items": "臺灣漫遊錄 1 本",
    },
    "A1001": {
        "status": "配送中",
        "carrier": "黑貓宅急便",
        "payment": "信用卡已付款",
        "items": "Rewire-神經可塑性 1 本",
    },
}

DEFAULT_FAQ = [
    {
        "question": "可以退貨嗎",
        "answer": "商品收到後 7 天內可以申請退貨，商品需保持完整包裝。",
    },
    {
        "question": "付款方式有哪些",
        "answer": "目前支援信用卡、ATM 轉帳、超商付款與貨到付款。",
    },
    {
        "question": "配送需要多久",
        "answer": "一般宅配約 2 到 3 個工作天，超商取貨約 3 到 5 個工作天。",
    },
    {
        "question": "如何查詢訂單進度",
        "answer": "您可以輸入訂單編號，例如 12345、67890 或 A1001，系統會協助查詢訂單狀態。",
    },
    {
        "question": "商品缺貨怎麼辦",
        "answer": "若商品缺貨，您可以等待補貨通知，或聯絡客服詢問預計補貨時間。",
    },
]


def load_products() -> list[dict[str, str]]:
    path = os.path.join(BASE_DIR, "books_products.csv")
    products: list[dict[str, str]] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            product = {key: (value or "").strip() for key, value in row.items()}
            if product.get("書名"):
                products.append(product)
    return products


def load_faq() -> list[dict[str, str]]:
    path = os.path.join(BASE_DIR, "data", "faq.json")
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else DEFAULT_FAQ
    except (OSError, json.JSONDecodeError):
        return DEFAULT_FAQ


PRODUCTS = load_products()
FAQ = load_faq()


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def tokenize(text: str) -> set[str]:
    normalized = normalize(text)
    words = set(re.findall(r"[a-z0-9]+", normalized))
    chars = {char for char in normalized if "\u4e00" <= char <= "\u9fff"}
    return words | chars


def product_document(product: dict[str, str]) -> str:
    fields = [
        product.get("書名", ""),
        product.get("作者", ""),
        product.get("出版社", ""),
        product.get("大分類", ""),
        product.get("商品分類", ""),
        product.get("ISBN", ""),
    ]
    return " ".join(fields)


KNOWLEDGE_BASE: list[dict[str, Any]] = []
for item in FAQ:
    KNOWLEDGE_BASE.append(
        {
            "type": "faq",
            "text": f"{item.get('question', '')} {item.get('answer', '')}",
            "payload": item,
        }
    )

for item in PRODUCTS:
    KNOWLEDGE_BASE.append(
        {
            "type": "product",
            "text": product_document(item),
            "payload": item,
        }
    )

for item in KNOWLEDGE_BASE:
    item["tokens"] = tokenize(item["text"])


def rag_search(message: str) -> tuple[dict[str, Any] | None, float]:
    query_tokens = tokenize(message)
    query_text = normalize(message)
    if not query_tokens and not query_text:
        return None, 0.0

    best_item: dict[str, Any] | None = None
    best_score = 0.0
    for item in KNOWLEDGE_BASE:
        item_tokens = item["tokens"]
        overlap = len(query_tokens & item_tokens) / max(len(query_tokens), 1)
        text_ratio = SequenceMatcher(None, query_text, normalize(item["text"])).ratio()
        score = overlap * 0.75 + text_ratio * 0.25
        if score > best_score:
            best_item = item
            best_score = score

    return best_item, best_score


def render_product_reply(product: dict[str, str]) -> str:
    stock = product.get("庫存量") or "未標示"
    return (
        "您好，根據商品資料庫查到："
        f"《{product.get('書名', '')}》由 {product.get('作者', '未標示')} 著作，"
        f"出版社為 {product.get('出版社', '未標示')}，價格 NT$ {product.get('價格', '未標示')}，"
        f"庫存 {stock}。商品頁面：{product.get('商品網址', '')}"
    )


def render_faq_reply(faq: dict[str, str]) -> str:
    return f"您好，根據客服 FAQ：{faq.get('answer', '目前沒有對應解答。')}"


def extract_order_id(message: str) -> str | None:
    normalized = message.strip().upper()
    if normalized in ORDERS:
        return normalized

    match = re.search(r"(?:訂單|ORDER|#)?\s*([A-Z]?\d{3,})", normalized)
    return match.group(1) if match else None


def woo_status_label(status: str) -> str:
    labels = {
        "pending": "等待付款",
        "processing": "處理中",
        "on-hold": "保留中",
        "completed": "完成",
        "cancelled": "已取消",
        "refunded": "已退款",
        "failed": "付款失敗",
        "trash": "已刪除",
    }
    return labels.get(status, status or "未標示")


def log_woo_error(step: str, order_id: str, error: Exception) -> None:
    if isinstance(error, urllib.error.HTTPError):
        app.logger.warning(
            "WooCommerce order lookup failed at %s for order %s: HTTP %s",
            step,
            order_id,
            error.code,
        )
        return

    app.logger.warning(
        "WooCommerce order lookup failed at %s for order %s: %s",
        step,
        order_id,
        error.__class__.__name__,
    )


def fetch_woocommerce_order(order_id: str) -> dict[str, Any] | None:
    if not (WOOCOMMERCE_BASE_URL and WOOCOMMERCE_CONSUMER_KEY and WOOCOMMERCE_CONSUMER_SECRET):
        app.logger.warning("WooCommerce environment variables are not fully configured.")
        return None

    url = f"{WOOCOMMERCE_BASE_URL}/wp-json/wc/v3/orders/{urllib.parse.quote(order_id)}"
    credentials = f"{WOOCOMMERCE_CONSUMER_KEY}:{WOOCOMMERCE_CONSUMER_SECRET}".encode("utf-8")
    request_obj = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {base64.b64encode(credentials).decode('ascii')}",
            "Accept": "application/json",
            "User-Agent": "Book-in-Cart-AI-Customer-Service/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request_obj, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as error:
        log_woo_error("basic-auth", order_id, error)
        query = urllib.parse.urlencode(
            {
                "consumer_key": WOOCOMMERCE_CONSUMER_KEY,
                "consumer_secret": WOOCOMMERCE_CONSUMER_SECRET,
            }
        )
        fallback_url = f"{url}?{query}"
        fallback_request = urllib.request.Request(
            fallback_url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Book-in-Cart-AI-Customer-Service/1.0",
            },
        )
        try:
            with urllib.request.urlopen(fallback_request, timeout=8) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as fallback_error:
            log_woo_error("query-auth", order_id, fallback_error)
            return None


def inspect_woocommerce_order(order_id: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "base_url": WOOCOMMERCE_BASE_URL or None,
        "key_exists": bool(WOOCOMMERCE_CONSUMER_KEY),
        "secret_exists": bool(WOOCOMMERCE_CONSUMER_SECRET),
        "order_id": order_id,
        "basic_auth_status": None,
        "query_auth_status": None,
        "success": False,
    }

    if not (WOOCOMMERCE_BASE_URL and WOOCOMMERCE_CONSUMER_KEY and WOOCOMMERCE_CONSUMER_SECRET):
        result["error"] = "WooCommerce environment variables are not fully configured."
        return result

    url = f"{WOOCOMMERCE_BASE_URL}/wp-json/wc/v3/orders/{urllib.parse.quote(order_id)}"
    credentials = f"{WOOCOMMERCE_CONSUMER_KEY}:{WOOCOMMERCE_CONSUMER_SECRET}".encode("utf-8")
    request_obj = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {base64.b64encode(credentials).decode('ascii')}",
            "Accept": "application/json",
            "User-Agent": "Book-in-Cart-AI-Customer-Service/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request_obj, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
            result["basic_auth_status"] = response.status
            result["success"] = True
            result["order"] = summarize_woocommerce_order(data)
            return result
    except urllib.error.HTTPError as error:
        result["basic_auth_status"] = error.code
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        result["basic_auth_error"] = error.__class__.__name__

    query = urllib.parse.urlencode(
        {
            "consumer_key": WOOCOMMERCE_CONSUMER_KEY,
            "consumer_secret": WOOCOMMERCE_CONSUMER_SECRET,
        }
    )
    fallback_request = urllib.request.Request(
        f"{url}?{query}",
        headers={
            "Accept": "application/json",
            "User-Agent": "Book-in-Cart-AI-Customer-Service/1.0",
        },
    )

    try:
        with urllib.request.urlopen(fallback_request, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
            result["query_auth_status"] = response.status
            result["success"] = True
            result["order"] = summarize_woocommerce_order(data)
            return result
    except urllib.error.HTTPError as error:
        result["query_auth_status"] = error.code
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        result["query_auth_error"] = error.__class__.__name__

    return result


def summarize_woocommerce_order(order: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": order.get("id"),
        "status": order.get("status"),
        "total": order.get("total"),
        "currency": order.get("currency"),
        "payment_method_title": order.get("payment_method_title"),
        "line_item_count": len(order.get("line_items") or []),
    }


def render_woocommerce_order_reply(order: dict[str, Any]) -> str:
    line_items = order.get("line_items") or []
    item_names = [item.get("name", "未命名商品") for item in line_items[:3]]
    items_text = "、".join(item_names) if item_names else "未標示"
    total = order.get("total") or "未標示"
    currency = order.get("currency") or "TWD"
    payment = order.get("payment_method_title") or order.get("payment_method") or "未標示"
    status = woo_status_label(str(order.get("status", "")))

    return (
        f"訂單【{order.get('id', '')}】查詢結果：<br>"
        f"目前狀態：<strong>{status}</strong><br>"
        f"商品內容：{items_text}<br>"
        f"付款方式：{payment}<br>"
        f"訂單金額：{currency} {total}"
    )


def render_mock_order_reply(order_id: str, order: dict[str, str]) -> str:
    return (
        f"訂單【{order_id}】查詢結果：<br>"
        f"商品內容：{order['items']}<br>"
        f"付款狀態：{order['payment']}<br>"
        f"配送方式：{order['carrier']}<br>"
        f"目前進度：<strong>{order['status']}</strong>"
    )


@app.route("/")
def index():
    return render_template(
        "index.html",
        products=PRODUCTS[:24],
        product_count=len(PRODUCTS),
        faq_count=len(FAQ),
        order_count=len(ORDERS),
    )


@app.route("/widget")
def widget():
    return render_template(
        "widget.html",
        order_id=request.args.get("order_id", "").strip(),
    )


@app.route("/api/products")
def api_products():
    return jsonify({"products": PRODUCTS, "count": len(PRODUCTS)})


@app.route("/api/woocommerce/check")
def api_woocommerce_check():
    order_id = request.args.get("order_id", "140").strip() or "140"
    return jsonify(inspect_woocommerce_order(order_id))


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    action = data.get("action", "")
    message = str(data.get("message", "")).strip()

    quick_replies = {
        "order_status": "請輸入您的訂單編號，例如 WooCommerce 訂單 140，或測試訂單 12345、67890、A1001，我會幫您查詢付款、物流與出貨進度。",
        "product_search": "請輸入書名、作者、分類或 ISBN，例如「心理學」、「楊双子」或「被討厭的勇氣」。",
        "refund_info": render_faq_reply(DEFAULT_FAQ[0]),
        "shipping_info": render_faq_reply(DEFAULT_FAQ[2]),
        "payment_info": render_faq_reply(DEFAULT_FAQ[1]),
        "faq_info": "您可以詢問退換貨、付款、配送、缺貨與訂單進度。客服資料來源包含 FAQ JSON、商品 CSV 與模擬訂單資料。",
    }
    if action:
        return jsonify({"reply": quick_replies.get(action, "請輸入想查詢的問題，我會使用 RAG 資料庫協助回答。")})

    if not message:
        return jsonify({"reply": "請輸入您的問題或訂單編號。"})

    order_id = extract_order_id(message)
    if order_id:
        woo_order = fetch_woocommerce_order(order_id)
        if woo_order:
            return jsonify({"reply": render_woocommerce_order_reply(woo_order)})

        if order_id in ORDERS:
            return jsonify({"reply": render_mock_order_reply(order_id, ORDERS[order_id])})

        return jsonify(
            {
                "reply": (
                    f"目前查不到訂單【{order_id}】。請確認訂單編號是否正確；"
                    "若是 WooCommerce 訂單，請確認 Render 已設定 WooCommerce API 金鑰。"
                )
            }
        )

    matched_item, score = rag_search(message)
    if matched_item and score >= 0.28:
        if matched_item["type"] == "product":
            reply = render_product_reply(matched_item["payload"])
        else:
            reply = render_faq_reply(matched_item["payload"])
        return jsonify({"reply": reply})

    return jsonify(
        {
            "reply": (
                f"收到您的訊息：「{message}」。目前 FAQ、商品 CSV 與訂單資料沒有找到足夠相近的答案，"
                "您可以改用書名、作者、商品分類，或輸入測試訂單編號 12345 查詢。"
            )
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)

# Book-in-Cart 智慧圖書商城與 AI 客服系統

這是雲端運算期末專題，主題是「購物網站與 AI 智能客服整合」。專案使用 Flask 建立智慧客服與商品展示頁，並部署到 Render。AI 客服可查詢商品資料、FAQ、測試訂單，也能串接同學負責的 WooCommerce 購物網站訂單 API。

## 專案功能

- 顯示圖書商品資料，資料來源為 `books_products.csv`
- 提供 AI 智能客服聊天介面
- 支援訂單進度查詢
- 支援 FAQ 查詢，例如退換貨、付款方式、配送時間
- 支援商品查詢，例如書名、作者、商品分類、ISBN
- 可串接 WooCommerce REST API 查詢真實購物網站訂單
- 使用 Gunicorn 作為正式部署的 WSGI Server
- 提供 Nginx Reverse Proxy 設定範例

## 專案架構

```text
.
├── app.py
├── app1.py
├── books_products.csv
├── data/
│   └── faq.json
├── static/
│   ├── ChatGPT Image 2026年5月21日 下午12_51_54.png
│   ├── script.js
│   └── style.css
├── templates/
│   ├── index.html
│   └── index1.html
├── gunicorn_config.py
├── nginx.conf
├── requirements.txt
├── render.yaml
├── Procfile
└── deploy_guide.md
```

## 主要檔案說明

| 檔案 | 說明 |
| --- | --- |
| `app.py` | Render 部署使用的主程式，包含 Flask 路由、RAG 檢索、訂單查詢與 WooCommerce API 串接 |
| `app1.py` | 本機大型模型實驗版，使用 BGE / Qwen，因雲端免費方案資源有限，Render 不使用此檔 |
| `books_products.csv` | 商品資料來源，包含書名、作者、出版社、價格、庫存、商品分類與網址 |
| `data/faq.json` | FAQ 常見問題資料 |
| `templates/index.html` | 購物網站首頁與 AI 客服介面 |
| `gunicorn_config.py` | Gunicorn 正式部署設定，會讀取 Render 的 `PORT` |
| `render.yaml` | Render Web Service 部署設定 |
| `Procfile` | 雲端平台啟動指令 |
| `nginx.conf` | 自架 VPS 時可使用的 Nginx Reverse Proxy 範例 |
| `deploy_guide.md` | 部署流程與期末報告架構說明 |

## 系統流程

```text
使用者
  ↓
Render Web Service
  ↓
Gunicorn
  ↓
Flask app.py
  ↓
AI 客服 / 商品頁面
  ↓
RAG 檢索資料
  ├── books_products.csv
  ├── data/faq.json
  ├── 測試訂單資料
  └── WooCommerce 訂單 API
```

## Render 部署設定

Build Command:

```bash
pip install -r requirements.txt
```

Start Command:

```bash
gunicorn --config gunicorn_config.py app:app
```

## WooCommerce API 串接設定

AI 客服查詢 WooCommerce 訂單時，會在 `app.py` 中自動組出 API 路徑：

```text
WOOCOMMERCE_BASE_URL + /wp-json/wc/v3/orders/訂單ID
```

例如使用者輸入：

```text
查詢訂單 140
```

程式會自動查詢：

```text
http://52.140.202.58/wp-json/wc/v3/orders/140
```

### Render Environment Variables

請到 Render 後台設定，不要寫進程式碼，也不要推到 GitHub。

```text
WOOCOMMERCE_BASE_URL=http://52.140.202.58
WOOCOMMERCE_CONSUMER_KEY=你的 WooCommerce Consumer Key
WOOCOMMERCE_CONSUMER_SECRET=你的 WooCommerce Consumer Secret
```

設定後要重新部署：

```text
Manual Deploy -> Deploy latest commit
```

## 測試方式

部署完成後，打開 Render 網站，在 AI 客服輸入：

```text
查詢訂單 140
```

如果 WooCommerce VM 有開、API 金鑰正確，客服會回傳真實訂單資料，例如訂單狀態、商品內容、付款方式與訂單金額。

如果 VM 沒有開或 API 連線失敗，系統會使用備用測試資料回覆，避免展示時完全無法查詢。

## 期末展示可說明重點

- 購物網站與 AI 客服已整合在同一個介面
- 商品資料來自 CSV，FAQ 來自 JSON
- AI 客服使用 RAG 概念，先從資料來源檢索，再產生客服回覆
- 訂單查詢支援測試訂單與 WooCommerce 真實訂單 API
- 正式部署使用 Gunicorn，不使用 Flask 內建開發伺服器
- Render 平台負責對外服務與 HTTPS；若自架 VPS，可使用 Nginx 作 Reverse Proxy

## 遇到的困難

- 原本大型模型版本需要較多記憶體，Render 免費方案不適合直接載入 Qwen 3B
- 改成輕量 RAG 檢索版本，降低部署成本與啟動時間
- Render 需要使用平台提供的 `PORT`，不能固定寫死本機 port
- WooCommerce API 需要用 Environment Variables 管理金鑰，避免密鑰外洩
- 若同學的購物網站 VM 沒開，AI 客服就無法取得真實訂單資料

## 本機啟動

```bash
pip install -r requirements.txt
python app.py
```

預設會啟動在：

```text
http://127.0.0.1:5001
```

正式部署請使用 Gunicorn：

```bash
gunicorn --config gunicorn_config.py app:app
```

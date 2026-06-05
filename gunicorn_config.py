# gunicorn_config.py
import os

# Render 會提供 PORT；VPS/Nginx 部署時可自行設定 PORT=5002
bind = f"0.0.0.0:{os.environ.get('PORT', '5002')}"

# RAG 資料會載入記憶體，雲端免費方案使用 1 worker 較穩定
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))

# 每個工作行程的執行緒數
threads = 2

# 工作模式 (使用 gthread 以支援高併發與執行緒)
worker_class = "gthread"

# 逾時時間 (秒)
timeout = 120

# 背景執行 (Daemon 模式，若交由 systemd 管理請設為 False)
daemon = False

# 日誌設定：使用 "-" 代表輸出至 stdout / stderr，便於 systemd 或容器收集
accesslog = "-"
errorlog = "-"
loglevel = "info"

# 程序名稱 (便於 ps 查詢辨識)
proc_name = "gunicorn_flask_ai_bot"

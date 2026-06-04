# gunicorn_config.py
import multiprocessing

# 綁定 IP 與 Port (本機 5002 連接埠，供 Nginx 反向代理轉發)
bind = "127.0.0.1:5002"

# 工作行程數（建議公式：CPU 核心數 * 2 + 1）
workers = multiprocessing.cpu_count() * 2 + 1

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

# Dockerfile phiên bản "chống đạn" - v3
# Sử dụng base image Python chính thức
FROM python:3.11-slim

# Thiết lập các biến môi trường cần thiết
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Cài đặt các gói cơ bản và thêm nguồn (repository) của Google Chrome
# Đây là cách làm đáng tin cậy nhất để cài đặt Chrome
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    wget \
    --no-install-recommends \
    && curl -sS -o - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /etc/apt/trusted.gpg.d/google-chrome.gpg \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# Bây giờ, cài đặt Google Chrome từ nguồn chính thức đã thêm
# Cùng với các font và dependencies cần thiết
RUN apt-get update && apt-get install -y \
    google-chrome-stable \
    fonts-liberation \
    libnss3 \
    --no-install-recommends \
    # Dọn dẹp để giảm dung lượng image
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc
WORKDIR /app

# Sao chép file requirements.txt và cài đặt thư viện Python
# Bước này tận dụng cache nếu requirements.txt không đổi
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ code còn lại
COPY . .

# Lệnh khởi chạy ứng dụng, trỏ tới file main.py
CMD ["python", "main.py"]

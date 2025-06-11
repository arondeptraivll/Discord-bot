# Dockerfile phiên bản Production - v6 (Siêu Ổn Định)
# Sử dụng base image Python chính thức
FROM python:3.11-slim

# Thiết lập các biến môi trường cần thiết
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Cài đặt các gói cơ bản, bao gồm jq để xử lý JSON và unzip để giải nén
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    wget \
    unzip \
    jq \
    --no-install-recommends

# Thêm PPA chính thức của Google để đảm bảo cài đặt thành công
RUN curl -sS -o - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /etc/apt/trusted.gpg.d/google-chrome.gpg \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# Cài đặt phiên bản ổn định mới nhất của Google Chrome
RUN apt-get update && apt-get install -y google-chrome-stable --no-install-recommends

# Tự động tải phiên bản chromedriver cho phiên bản Chrome ổn định mới nhất
# Phương pháp mới, đơn giản và đáng tin cậy nhất từ Google
RUN CHROMEDRIVER_URL=$(curl -s 'https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json' | jq -r .channels.Stable.downloads.chromedriver[0].url) \
    && wget -q ${CHROMEDRIVER_URL} -O /tmp/chromedriver.zip \
    && unzip -o /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/bin/chromedriver \
    && chmod +x /usr/bin/chromedriver \
    && rm -rf /tmp/chromedriver.zip /tmp/chromedriver-linux64

# Dọn dẹp các file không cần thiết để giảm dung lượng
RUN apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc
WORKDIR /app

# Sao chép file requirements.txt và cài đặt thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ code còn lại
COPY . .

# Lệnh khởi chạy ứng dụng, trỏ tới file main.py
CMD ["python", "main.py"]

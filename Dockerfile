# Dockerfile phiên bản Production - v4
# Sử dụng base image Python chính thức
FROM python:3.11-slim

# Thiết lập các biến môi trường cần thiết
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Cài đặt các gói cơ bản và thêm nguồn (repository) của Google Chrome
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    wget \
    unzip \
    --no-install-recommends

# Thêm PPA chính thức của Google để đảm bảo cài đặt thành công
RUN curl -sS -o - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /etc/apt/trusted.gpg.d/google-chrome.gpg
RUN echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# Cài đặt một phiên bản Chrome cụ thể để đảm bảo tính ổn định
# và các font chữ cần thiết
RUN apt-get update && apt-get install -y \
    google-chrome-stable \
    fonts-liberation \
    libnss3 \
    --no-install-recommends

# Tự động tìm và cài đặt phiên bản chromedriver tương ứng
# Đây là phương pháp mới và ổn định nhất của Google
RUN CHROME_VERSION=$(google-chrome --version | cut -f 3 -d ' ' | cut -d '.' -f 1-3)
RUN CHROMEDRIVER_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json" | jq -r ".versions[] | select(.version==\"$CHROME_VERSION\") | .downloads.chromedriver[0].url")
RUN wget -q ${CHROMEDRIVER_VERSION} -O /tmp/chromedriver.zip \
    && unzip /tmp/chromedriver.zip -d /usr/bin \
    && mv /usr/bin/chromedriver-linux64/chromedriver /usr/bin/chromedriver \
    && chmod +x /usr/bin/chromedriver \
    && rm -rf /tmp/chromedriver.zip /usr/bin/chromedriver-linux64

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

# Lệnh khởi chạy ứng dụng
CMD ["python", "main.py"]

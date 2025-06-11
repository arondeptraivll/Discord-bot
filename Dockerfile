

# Sử dụng base image Python 3.11 chính thức
# "slim" là phiên bản nhẹ hơn, giúp quá trình build nhanh hơn
FROM python:3.11-slim

# Thiết lập biến môi trường để các gói được cài đặt mà không cần hỏi
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Cập nhật danh sách gói và cài đặt các dependencies cần thiết cho Chrome và các thư viện khác
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    # Các gói phụ thuộc của Chrome
    libgconf-2-4 \
    libnss3 \
    libxss1 \
    libasound2 \
    libxtst6 \
    # Font chữ để hiển thị trang web đúng cách
    fonts-liberation \
    # Lựa chọn để không cài đặt các gói không cần thiết
    --no-install-recommends \
    # Xóa cache để giảm dung lượng cuối cùng của image
    && rm -rf /var/lib/apt/lists/*

# Tải và cài đặt phiên bản Google Chrome ổn định mới nhất
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
# Chạy trình cài đặt, nếu lỗi dependency thì apt-get -fy install sẽ tự sửa
RUN dpkg -i google-chrome-stable_current_amd64.deb || apt-get -fy install
# Dọn dẹp file cài đặt đã tải về
RUN rm google-chrome-stable_current_amd64.deb

# Tạo thư mục làm việc cho ứng dụng
WORKDIR /app

# Sao chép file requirements.txt vào trước để tận dụng cache của Docker
# Nếu file này không đổi, Docker sẽ không cần cài lại các thư viện ở những lần build sau
COPY requirements.txt .

# Cài đặt các thư viện Python
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ code của bạn vào trong image
COPY . .

# Lệnh để khởi chạy ứng dụng của bạn
# Nó sẽ thực thi file main.py, file này sẽ tự khởi động Gunicorn
CMD ["python", "main.py"]


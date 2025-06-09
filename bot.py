# bot.py

import discord
import os
import re
from keep_alive import keep_alive # <-- Import hàm từ file riêng

# ==============================================================================
# PHẦN CODE CHÍNH CỦA DISCORD BOT
# ==============================================================================

# Biến toàn cục để kiểm soát quy tắc cho admin
admin_exemption_enabled = True

# Thiết lập Intents (quyền của bot)
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

client = discord.Client(intents=intents)

# Biểu thức chính quy để tìm URL
URL_REGEX = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"

# Sự kiện khi bot đã sẵn sàng
@client.event
async def on_ready():
    print(f'Bot đã đăng nhập với tên {client.user}')
    print('-----------------------------------------')

# Sự kiện khi có tin nhắn mới
@client.event
async def on_message(message):
    # 1. Bỏ qua tin nhắn của chính bot
    if message.author == client.user:
        return

    # 2. Xử lý lệnh từ admin để thay đổi quy tắc
    if message.author.guild_permissions.administrator:
        global admin_exemption_enabled
        
        if message.content.lower() == '!norule':
            admin_exemption_enabled = True
            await message.channel.send('✅ Chế độ miễn trừ cho Admin đã được **BẬT**. (Tin nhắn này sẽ tự xóa)', delete_after=3.0)
            print("Chế độ miễn trừ cho Admin: BẬT")
            try:
                await message.delete()
            except discord.errors.Forbidden:
                print(f"Lỗi: Bot không có quyền xóa tin nhắn lệnh của admin trong kênh {message.channel.name}.")
            return
        
        elif message.content.lower() == '!rule':
            admin_exemption_enabled = False
            await message.channel.send('🅾️ Chế độ miễn trừ cho Admin đã được **TẮT**. (Tin nhắn này sẽ tự xóa)', delete_after=3.0)
            print("Chế độ miễn trừ cho Admin: TẮT")
            try:
                await message.delete()
            except discord.errors.Forbidden:
                print(f"Lỗi: Bot không có quyền xóa tin nhắn lệnh của admin trong kênh {message.channel.name}.")
            return

    # 3. Kiểm tra xem có nên bỏ qua tin nhắn của admin không
    if admin_exemption_enabled and message.author.guild_permissions.administrator:
        return

    # 4. Kiểm tra tin nhắn chứa link hoặc tệp đính kèm
    contains_link = re.search(URL_REGEX, message.content)
    has_attachment = len(message.attachments) > 0

    # 5. Nếu có link HOẶC tệp đính kèm, thực hiện xóa/cảnh báo
    if contains_link or has_attachment:
        reason_text = ""
        log_text = ""
        
        if contains_link and has_attachment:
            reason_text = "gửi đồng thời liên kết và tệp"
            log_text = "link và tệp"
        elif contains_link:
            reason_text = "gửi liên kết"
            log_text = "link"
        elif has_attachment:
            reason_text = "gửi tệp"
            log_text = "tệp"

        try:
            await message.delete()
            await message.channel.send(
                f'{message.author.mention}, Bạn không được {reason_text} trong kênh chat này ❌',
                delete_after=10.0
            )
            print(f'Đã xóa tin nhắn từ {message.author} vì chứa {log_text}.')
        except discord.errors.Forbidden:
            print(f'Lỗi: Bot không có quyền xóa tin nhắn trong kênh {message.channel.name}.')
        except Exception as e:
            print(f'Đã xảy ra lỗi không xác định: {e}')

# ==============================================================================
# CHẠY BOT
# ==============================================================================

# Khởi động web server để giữ bot sống 24/7 trên Render
keep_alive()

# Lấy token từ biến môi trường của Render và chạy bot
TOKEN = os.environ.get('DISCORD_TOKEN')

if TOKEN is None:
    print("Lỗi: Không tìm thấy biến môi trường 'DISCORD_TOKEN'.")
    print("Vui lòng thiết lập biến này trên trang cấu hình của Render.")
else:
    client.run(TOKEN)
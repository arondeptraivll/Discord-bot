# bot.py
import discord
from discord import app_commands, ui
import os
import datetime
import asyncio
import time
from typing import Optional

print("--- [DEBUG] Bắt đầu thực thi file bot.py ---")

from keep_alive import keep_alive
from spammer import SpamManager

# ==============================================================================
# BƯỚC 1: CÀI ĐẶT
# ==============================================================================

# Lấy các biến môi trường từ Render
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
KEYGEN_ACCOUNT_ID = os.environ.get('KEYGEN_ACCOUNT_ID')
KEYGEN_PRODUCT_TOKEN = os.environ.get('KEYGEN_PRODUCT_TOKEN')

# ID của kênh mà bot sẽ hoạt động - !!! THAY THẾ ID KÊNH CỦA BẠN VÀO ĐÂY !!!
SPAM_CHANNEL_ID = 1381799563488399452 

print("--- [DEBUG] Đang tải các biến cấu hình... ---")
print(f"    DISCORD_TOKEN: ...{DISCORD_TOKEN[-4:] if DISCORD_TOKEN else 'None'}")
print(f"    KEYGEN_ACCOUNT_ID: {KEYGEN_ACCOUNT_ID}")
print(f"    KEYGEN_PRODUCT_TOKEN: {'Có' if KEYGEN_PRODUCT_TOKEN else 'None'}")
print(f"    SPAM_CHANNEL_ID: {SPAM_CHANNEL_ID}")
print("--- [DEBUG] Tải cấu hình hoàn tất. ---")

print("--- [DEBUG] Đang khởi tạo SpamManager... ---")
spam_manager = SpamManager(account_id=KEYGEN_ACCOUNT_ID, product_token=KEYGEN_PRODUCT_TOKEN)
print("--- [DEBUG] Khởi tạo SpamManager thành công. ---")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

user_sessions = {}

# ==============================================================================
# BƯỚC 2: CÁC LỚP UI (NÚT BẤM, FORM)
# ==============================================================================

class KeyEntryModal(ui.Modal, title='Nhập License Key'):
    key_input = ui.TextInput(label='License Key', placeholder='Dán license key của bạn vào đây...', style=discord.TextStyle.short)
    
    async def on_submit(self, interaction: discord.Interaction):
        license_key = self.key_input.value
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        validation_result = spam_manager.validate_license(license_key)

        if validation_result.get("valid"):
            user_sessions[interaction.user.id] = {"key": license_key, "expiry": validation_result["expiry"]}
            expiry_dt = datetime.datetime.fromisoformat(validation_result['expiry'].replace("Z", "+00:00"))
            expiry_str = expiry_dt.strftime('%d/%m/%Y %H:%M:%S UTC')
            
            view = SpamControlView(user_id=interaction.user.id)
            await interaction.followup.send(f"✅ Key hợp lệ!\n**Hiệu lực tới:** {expiry_str}", view=view, ephemeral=True)
        else:
            code = validation_result.get("code", "UNKNOWN_ERROR")
            error_messages = {
                "FINGERPRINT_SCOPE_MISMATCH": "Key này không hợp lệ với sản phẩm này.",
                "NOT_FOUND": "Key không tồn tại hoặc không hợp lệ.",
                "EXPIRED": "Key đã hết hạn.",
                "SUSPENDED": "Key đã bị tạm ngưng. Vui lòng liên hệ admin.",
                "REQUEST_ERROR": "Lỗi kết nối đến máy chủ xác thực. Vui lòng thử lại sau.",
            }
            await interaction.followup.send(f"❌ **Lỗi:** {error_messages.get(code, f'Đã xảy ra lỗi không xác định. Mã lỗi: {code}')}", ephemeral=True)


class SpamConfigModal(ui.Modal, title='Cấu hình phiên Spam'):
    target_input = ui.TextInput(label='Locket Target (Username hoặc Link)', required=True)
    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id
        
    async def on_submit(self, interaction: discord.Interaction):
        target = self.target_input.value
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        active_view = ActiveSpamView(user_id=self.user_id, interaction=interaction)
        
        async def update_callback(status: str, stats: Optional[dict] = None, message: Optional[str] = None):
            await active_view.update_message(status, stats, message)
            
        spam_manager.start_spam_session(user_id=self.user_id, target=target, update_callback=update_callback)

class SpamControlView(ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        
    @ui.button(label='Bắt Đầu Spam', style=discord.ButtonStyle.green, emoji='🚀')
    async def start_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(SpamConfigModal(user_id=self.user_id))
        self.stop()
        try: await interaction.message.edit(view=None) 
        except: pass
        
    @ui.button(label='Hủy', style=discord.ButtonStyle.grey)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        self.stop()
        await interaction.response.edit_message(content='Đã hủy.', view=None)

class ActiveSpamView(ui.View):
    def __init__(self, user_id: int, interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.interaction = interaction
        self.message = None
        
    async def update_message(self, status: str, stats: Optional[dict] = None, message: Optional[str] = None):
        if not self.interaction: return

        if status == "started":
            self.message = await self.interaction.followup.send(message, view=self, ephemeral=True)
            return

        if self.message is None:
            if status == "error":
                await self.interaction.followup.send(f"❌ Lỗi: {message}", ephemeral=True)
            return

        try:
            if status == "running":
                elapsed_time = datetime.timedelta(seconds=int(time.time() - stats['start_time']))
                embed = discord.Embed(title="🚀 Trạng thái Spam", color=discord.Color.blue())
                embed.add_field(name="Thành Công", value=f"✅ {stats.get('success', 0)}", inline=True).add_field(name="Thất Bại", value=f"❌ {stats.get('failed', 0)}", inline=True).add_field(name="Thời Gian Chạy", value=f"⏳ {str(elapsed_time)}", inline=False)
                embed.set_footer(text="Cập nhật mỗi 5 giây...")
                await self.message.edit(content="", embed=embed, view=self)
            elif status == "stopped":
                self.stop()
                elapsed_time = datetime.timedelta(seconds=int(time.time() - stats['start_time']))
                embed = discord.Embed(title="🛑 Phiên Spam Đã Dừng", color=discord.Color.default())
                embed.add_field(name="Tổng Thành Công", value=f"✅ {stats.get('success', 0)}", inline=True).add_field(name="Tổng Thất Bại", value=f"❌ {stats.get('failed', 0)}", inline=True).add_field(name="Tổng Thời Gian", value=f"⏳ {str(elapsed_time)}", inline=False)
                await self.message.edit(content="", embed=embed, view=None)
        except discord.errors.NotFound:
            # Tin nhắn đã bị xóa hoặc hết hạn, không thể edit được nữa
            self.stop()

    @ui.button(label='Dừng Spam', style=discord.ButtonStyle.red, emoji='🛑')
    async def stop_button(self, interaction: discord.Interaction, button: ui.Button):
        was_stopped = spam_manager.stop_spam_session(self.user_id)
        if was_stopped:
            await interaction.response.defer()
            button.disabled = True
            await self.message.edit(view=self)
        else:
             await interaction.response.send_message("Không có phiên spam nào đang chạy để dừng.", ephemeral=True)

class InitialView(ui.View):
    def __init__(self): super().__init__(timeout=300)
    @ui.button(label='Nhập Key', style=discord.ButtonStyle.primary, emoji='🔑')
    async def enter_key_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(KeyEntryModal())

# ==============================================================================
# BƯỚC 3: CÁC LỆNH (COMMANDS)
# ==============================================================================

@tree.command(name="start", description="Bắt đầu một phiên làm việc với zLocket Spammer.")
async def start_command(interaction: discord.Interaction):
    print(f"--- [DEBUG] NHẬN ĐƯỢỢC LỆNH /start TỪ user {interaction.user.id} TRONG CHANNEL {interaction.channel.id} ---")

    # Bước 1: Trả lời Discord ngay lập tức để tránh lỗi timeout
    try:
        await interaction.response.defer(ephemeral=True, thinking=False) # thinking=False vì chúng ta sẽ trả lời ngay
    except discord.errors.InteractionResponded:
        print(f"--- [DEBUG] Lệnh /start từ user {interaction.user.id} đã được trả lời trước đó. Bỏ qua. ---")
        return
        
    # Bước 2: Kiểm tra kênh
    if interaction.channel.id != SPAM_CHANNEL_ID:
        print(f"--- [DEBUG] Lỗi: Sai kênh ({interaction.channel.id}). Đã từ chối lệnh của user {interaction.user.id}. ---")
        await interaction.followup.send(f"Lệnh này chỉ có thể được sử dụng trong kênh <#{SPAM_CHANNEL_ID}>.", ephemeral=True)
        return
    
    # Bước 3: Gửi tin nhắn đầy đủ
    print(f"--- [DEBUG] Kênh hợp lệ. Đang gửi phản hồi ban đầu cho user {interaction.user.id}. ---")
    embed = discord.Embed(title="Chào mừng đến với zLocket Bot Spammer", description="Vui lòng nhấn nút bên dưới để nhập License Key và bắt đầu.", color=discord.Color.purple())
    embed.set_footer(text="Mọi tương tác của bạn với bot tại đây đều là riêng tư.")
    await interaction.followup.send(embed=embed, view=InitialView(), ephemeral=True)

@tree.command(name="hello", description="Lệnh test đơn giản để kiểm tra phản hồi của bot.")
async def hello_command(interaction: discord.Interaction):
    print(f"--- [DEBUG] NHẬN ĐƯỢC LỆNH /hello TỪ user {interaction.user.id} ---")
    await interaction.response.send_message(f"Xin chào, {interaction.user.name}! Bot đang hoạt động và nhận được lệnh.", ephemeral=True)

# ==============================================================================
# BƯỚC 4: KHỞI CHẠY BOT
# ==============================================================================

@client.event
async def on_ready():
    print("--- [DEBUG] Sự kiện on_ready đã được kích hoạt. Chuẩn bị đồng bộ lệnh... ---")
    try:
        await tree.sync()
        print("--- [DEBUG] Đồng bộ lệnh (tree.sync) hoàn tất. ---")
    except Exception as e:
        print(f"!!! [ERROR] Đã xảy ra lỗi khi đồng bộ lệnh: {e}")

    print(f'Bot đã đăng nhập với tên {client.user}')
    print('-----------------------------------------')
    if not spam_manager.FIREBASE_APP_CHECK_TOKEN:
        print("!!! [WARNING] App Check Token không thể lấy được. Spam có thể không hoạt động.")

# Kiểm tra các biến môi trường trước khi chạy
if any(v is None for v in [DISCORD_TOKEN, KEYGEN_ACCOUNT_ID, KEYGEN_PRODUCT_TOKEN]):
    print("!!! [CRITICAL ERROR] Thiếu một hoặc nhiều biến môi trường (DISCORD_TOKEN, KEYGEN_ACCOUNT_ID, KEYGEN_PRODUCT_TOKEN). Bot sẽ không khởi chạy. !!!")
else:
    print("--- [DEBUG] Đang khởi chạy web server (keep_alive)... ---")
    keep_alive()
    print("--- [DEBUG] Đang khởi chạy client.run(DISCORD_TOKEN)... ---")
    client.run(DISCORD_TOKEN)

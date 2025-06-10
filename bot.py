# bot.py
import discord
from discord import app_commands, ui
import os
import datetime
import asyncio
from typing import Optional

from keep_alive import keep_alive
from spammer import SpamManager

# ==============================================================================
# BƯỚC 1: CÀI ĐẶT
# ==============================================================================

# Lấy các biến môi trường từ Render
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
KEYGEN_ACCOUNT_ID = os.environ.get('KEYGEN_ACCOUNT_ID')
KEYGEN_PRODUCT_TOKEN = os.environ.get('KEYGEN_PRODUCT_TOKEN')

# ID của kênh mà bot sẽ hoạt động
SPAM_CHANNEL_ID = 1381799563488399452 # !!! THAY THẾ ID KÊNH CỦA BẠN VÀO ĐÂY !!!

# Khởi tạo đối tượng SpamManager
spam_manager = SpamManager(account_id=KEYGEN_ACCOUNT_ID, product_token=KEYGEN_PRODUCT_TOKEN)

# Thiết lập Intents
intents = discord.Intents.default()
intents.message_content = False # Không cần intent message nữa vì dùng slash command

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Dictionary để lưu trữ thông tin session của người dùng
# { user_id: {"key": "...", "expiry": "..."} }
user_sessions = {}

# ==============================================================================
# BƯỚC 2: CÁC LỚP UI (NÚT BẤM, FORM)
# ==============================================================================

# --- Modal (Form) để nhập Key ---
class KeyEntryModal(ui.Modal, title='Nhập License Key'):
    key_input = ui.TextInput(label='License Key', placeholder='Dán license key của bạn vào đây...', style=discord.TextStyle.short)

    async def on_submit(self, interaction: discord.Interaction):
        license_key = self.key_input.value
        await interaction.response.defer(ephemeral=True, thinking=True) # "Bot is thinking..."

        validation_result = spam_manager.validate_license(license_key)

        if validation_result["valid"]:
            user_sessions[interaction.user.id] = {
                "key": license_key,
                "expiry": validation_result["expiry"]
            }
            expiry_dt = datetime.datetime.fromisoformat(validation_result['expiry'])
            expiry_str = expiry_dt.strftime('%d/%m/%Y %H:%M:%S UTC')
            
            view = SpamControlView(user_id=interaction.user.id)
            await interaction.followup.send(
                f"✅ Key hợp lệ!\n**Hiệu lực tới:** {expiry_str}", 
                view=view, 
                ephemeral=True
            )
        else:
            code = validation_result.get("code", "UNKNOWN_ERROR")
            error_messages = {
                "FINGERPRINT_SCOPE_MISMATCH": "Key này không hợp lệ với sản phẩm này.",
                "NOT_FOUND": "Key không tồn tại hoặc đã bị xóa.",
                "EXPIRED": "Key đã hết hạn.",
                "SUSPENDED": "Key đã bị tạm ngưng. Vui lòng liên hệ admin.",
                "REQUEST_ERROR": "Lỗi kết nối đến máy chủ xác thực. Vui lòng thử lại sau.",
            }
            await interaction.followup.send(f"❌ **Lỗi:** {error_messages.get(code, 'Đã xảy ra lỗi không xác định.')}", ephemeral=True)

# --- Modal (Form) để cấu hình Spam ---
class SpamConfigModal(ui.Modal, title='Cấu hình phiên Spam'):
    target_input = ui.TextInput(label='Locket Target (Username hoặc Link)', placeholder='Ví dụ: @username hoặc locket.cam/abc...', required=True)

    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        target = self.target_input.value
        await interaction.response.defer(ephemeral=True, thinking=True) # Báo cho Discord là sẽ mất thời gian xử lý

        active_view = ActiveSpamView(user_id=self.user_id, interaction=interaction)
        
        # Hàm callback để spammer gửi cập nhật về
        async def update_callback(status: str, stats: Optional[dict] = None, message: Optional[str] = None):
            await active_view.update_message(status, stats, message)

        spam_manager.start_spam_session(user_id=self.user_id, target=target, update_callback=update_callback)

# --- View chứa các nút điều khiển ---
class SpamControlView(ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300) # View hết hạn sau 5 phút
        self.user_id = user_id
    
    @ui.button(label='Bắt Đầu Spam', style=discord.ButtonStyle.green, emoji='🚀')
    async def start_button(self, interaction: discord.Interaction, button: ui.Button):
        # Mở form nhập target
        await interaction.response.send_modal(SpamConfigModal(user_id=self.user_id))
        
        # Vô hiệu hóa view cũ sau khi nhấn nút
        self.stop()
        await interaction.message.edit(view=None)

    @ui.button(label='Hủy', style=discord.ButtonStyle.grey)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        self.stop()
        await interaction.response.edit_message(content='Đã hủy.', view=None)

# --- View khi spam đang chạy ---
class ActiveSpamView(ui.View):
    def __init__(self, user_id: int, interaction: discord.Interaction):
        super().__init__(timeout=None) # Không hết hạn
        self.user_id = user_id
        self.interaction = interaction # Lưu lại interaction ban đầu để update
        self.message = None # Sẽ lưu tin nhắn để edit

    async def update_message(self, status: str, stats: Optional[dict] = None, message: Optional[str] = None):
        if status == "started":
            # Gửi tin nhắn ban đầu
            self.message = await self.interaction.followup.send(message, view=self, ephemeral=True)
            return

        if self.message is None: return

        if status == "running":
            elapsed_time = datetime.timedelta(seconds=int(time.time() - stats['start_time']))
            embed = discord.Embed(title="🚀 Trạng thái Spam", color=discord.Color.blue())
            embed.add_field(name="Thành Công", value=f"✅ {stats.get('success', 0)}", inline=True)
            embed.add_field(name="Thất Bại", value=f"❌ {stats.get('failed', 0)}", inline=True)
            embed.add_field(name="Thời Gian Chạy", value=f"⏳ {str(elapsed_time)}", inline=False)
            embed.set_footer(text="Cập nhật mỗi 5 giây...")
            await self.message.edit(content="", embed=embed, view=self)

        elif status == "stopped":
            self.stop() # Dừng view này
            elapsed_time = datetime.timedelta(seconds=int(time.time() - stats['start_time']))
            embed = discord.Embed(title="🛑 Phiên Spam Đã Dừng", color=discord.Color.default())
            embed.add_field(name="Tổng Thành Công", value=f"✅ {stats.get('success', 0)}", inline=True)
            embed.add_field(name="Tổng Thất Bại", value=f"❌ {stats.get('failed', 0)}", inline=True)
            embed.add_field(name="Tổng Thời Gian", value=f"⏳ {str(elapsed_time)}", inline=False)
            await self.message.edit(content="", embed=embed, view=None)

        elif status == "error":
             await self.interaction.followup.send(f"❌ Lỗi: {message}", ephemeral=True)

    @ui.button(label='Dừng Spam', style=discord.ButtonStyle.red, emoji='🛑')
    async def stop_button(self, interaction: discord.Interaction, button: ui.Button):
        # Gửi tín hiệu dừng cho spammer
        was_stopped = spam_manager.stop_spam_session(self.user_id)
        if was_stopped:
            await interaction.response.defer() # Chỉ cần xác nhận, không cần trả lời
            button.disabled = True
            await interaction.message.edit(view=self)
        else:
             await interaction.response.send_message("Không có phiên spam nào đang chạy để dừng.", ephemeral=True)
             
# --- View khởi đầu, chỉ có nút nhập key ---
class InitialView(ui.View):
    def __init__(self):
        super().__init__(timeout=300) # View hết hạn sau 5 phút

    @ui.button(label='Nhập Key', style=discord.ButtonStyle.primary, emoji='🔑')
    async def enter_key_button(self, interaction: discord.Interaction, button: ui.Button):
        # Mở Modal nhập key
        await interaction.response.send_modal(KeyEntryModal())


# ==============================================================================
# BƯỚC 3: CÁC LỆNH (COMMANDS)
# ==============================================================================

@tree.command(name="start", description="Bắt đầu một phiên làm việc với zLocket Spammer.")
async def start_command(interaction: discord.Interaction):
    # Chỉ cho phép lệnh hoạt động trong kênh đã chỉ định
    if interaction.channel.id != SPAM_CHANNEL_ID:
        await interaction.response.send_message(f"Lệnh này chỉ có thể được sử dụng trong kênh <#{SPAM_CHANNEL_ID}>.", ephemeral=True)
        return
        
    embed = discord.Embed(
        title="Chào mừng đến với zLocket Bot Spammer",
        description="Vui lòng nhấn nút bên dưới để nhập License Key và bắt đầu.",
        color=discord.Color.purple()
    )
    embed.set_footer(text="Mọi tương tác của bạn với bot tại đây đều là riêng tư.")
    await interaction.response.send_message(embed=embed, view=InitialView(), ephemeral=True)

# ==============================================================================
# BƯỚC 4: KHỞI CHẠY BOT
# ==============================================================================
@client.event
async def on_ready():
    await tree.sync() # Đồng bộ các slash command lên Discord
    print(f'Bot đã đăng nhập với tên {client.user}')
    print('-----------------------------------------')
    if not spam_manager.FIREBASE_APP_CHECK_TOKEN:
        print("CẢNH BÁO: App Check Token không thể lấy được. Spam có thể không hoạt động.")

if any(v is None for v in [DISCORD_TOKEN, KEYGEN_ACCOUNT_ID, KEYGEN_PRODUCT_TOKEN]):
    print("Lỗi: Thiếu một hoặc nhiều biến môi trường quan trọng (DISCORD_TOKEN, KEYGEN_ACCOUNT_ID, KEYGEN_PRODUCT_TOKEN).")
else:
    keep_alive()
    client.run(DISCORD_TOKEN)
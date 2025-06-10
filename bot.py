# bot.py
import discord
from discord import app_commands, ui
import os
import datetime
import time
from typing import Optional

print("--- [LAUNCH] Botกำลัง khởi chạy, phiên bản ổn định... ---")

from keep_alive import keep_alive
from spammer import SpamManager
import keygen

# ==============================================================================
# 1. CÀI ĐẶT
# ==============================================================================

# Lấy các biến môi trường
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
ADMIN_USER_ID = os.environ.get('ADMIN_USER_ID')
SPAM_CHANNEL_ID = 1381799563488399452  # !!! THAY BẰNG ID KÊNH CỦA BẠN !!!

# Kiểm tra cấu hình trước khi làm bất cứ điều gì
if not DISCORD_TOKEN or not ADMIN_USER_ID:
    print("!!! [CRITICAL] Thiếu DISCORD_TOKEN hoặc ADMIN_USER_ID. Bot sẽ không khởi chạy. !!!")
    exit() # Thoát hoàn toàn nếu thiếu

print("--- [CONFIG] Cấu hình đã được tải thành công. ---")

# Khởi tạo các thành phần
spam_manager = SpamManager()
intents = discord.Intents.default()


# ==============================================================================
# 2. CÁC LỚP UI (Views & Modals)
# ==============================================================================

class KeyEntryModal(ui.Modal, title='Nhập License Key'):
    key_input = ui.TextInput(label='License Key', placeholder='Dán key của bạn vào đây...', required=True)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        result = spam_manager.validate_license(self.key_input.value)
        if result.get("valid"):
            expiry_dt = datetime.datetime.fromisoformat(result['expiry'].replace("Z", "+00:00"))
            await interaction.followup.send(f"✅ Key hợp lệ! Hết hạn lúc: {expiry_dt:%H:%M ngày %d/%m/%Y}", view=SpamControlView(interaction.user.id), ephemeral=True)
        else:
            errors = {"NOT_FOUND": "Key không tồn tại hoặc không hợp lệ.", "EXPIRED": "Key đã hết hạn.", "SUSPENDED": "Key đã bị tạm ngưng."}
            await interaction.followup.send(f"❌ Lỗi: {errors.get(result.get('code'), 'Lỗi không xác định.')}", ephemeral=True)

class SpamConfigModal(ui.Modal, title='Cấu hình Spam'):
    target_input = ui.TextInput(label='Locket Target (Username/Link)', required=True)
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True) # "Bot is thinking..."
        active_view = ActiveSpamView(self.user_id, interaction)
        def update_callback(status: str, stats: Optional[dict] = None, message: Optional[str] = None):
            asyncio.run_coroutine_threadsafe(active_view.update_message(status, stats, message), client.loop)
        spam_manager.start_spam_session(self.user_id, self.target_input.value, update_callback)

class InitialView(ui.View):
    def __init__(self): super().__init__(timeout=300)
    @ui.button(label='Nhập Key', style=discord.ButtonStyle.primary, emoji='🔑')
    async def enter_key(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(KeyEntryModal())

class SpamControlView(ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
    @ui.button(label='Bắt Đầu Spam', style=discord.ButtonStyle.green, emoji='🚀')
    async def start_spam(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(SpamConfigModal(self.user_id))
        self.stop() # Tự hủy view này
    @ui.button(label='Hủy', style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content='Đã hủy.', view=None)

class ActiveSpamView(ui.View):
    def __init__(self, user_id: int, interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.original_interaction = interaction
        self.status_message = None
    async def update_message(self, status: str, stats: Optional[dict]=None, message: Optional[str]=None):
        if status == "started":
            self.status_message = await self.original_interaction.followup.send(message, view=self, ephemeral=True)
            return
        if status == "error":
            await self.original_interaction.followup.send(f"❌ Lỗi: {message}", ephemeral=True)
            return
        if self.status_message is None: return

        try:
            if status == "running":
                embed = discord.Embed(title="🚀 Trạng thái Spam", color=discord.Color.blue()).add_field(name="Thành Công", value=f"✅ {stats['success']}").add_field(name="Thất Bại", value=f"❌ {stats['failed']}").add_field(name="Thời Gian", value=f"⏳ {datetime.timedelta(seconds=int(time.time() - stats['start_time']))}")
                await self.status_message.edit(embed=embed)
            elif status == "stopped":
                self.stop()
                embed = discord.Embed(title="🛑 Phiên Spam Đã Dừng", color=discord.Color.dark_grey()).add_field(name="Tổng Thành Công", value=f"✅ {stats['success']}").add_field(name="Tổng Thất Bại", value=f"❌ {stats['failed']}").add_field(name="Tổng Thời Gian", value=f"⏳ {datetime.timedelta(seconds=int(time.time() - stats['start_time']))}")
                await self.status_message.edit(embed=embed, view=None)
        except discord.NotFound: self.stop()

    @ui.button(label='Dừng Spam', style=discord.ButtonStyle.red, emoji='🛑')
    async def stop_spam(self, interaction: discord.Interaction, button: ui.Button):
        if spam_manager.stop_spam_session(self.user_id):
            await interaction.response.defer()
            button.disabled = True
            await self.status_message.edit(view=self)
        else: await interaction.response.send_message("Không tìm thấy phiên spam để dừng.", ephemeral=True)

# ==============================================================================
# 3. CẤU TRÚC CLIENT VÀ LỆNH
# ==============================================================================

class MyBotClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # Đây là cách đồng bộ lệnh an toàn và được khuyến nghị
        await self.tree.sync()
        print("--- [SYNC] Đồng bộ lệnh lên Discord thành công. ---")

    async def on_ready(self):
        print(f'--- [READY] Bot đã đăng nhập với tên {self.user} (ID: {self.user.id}) ---')
        print('----------------------------------------------------')

client = MyBotClient(intents=intents)

@client.tree.command(name="start", description="Bắt đầu một phiên làm việc.")
async def start(interaction: discord.Interaction):
    if interaction.channel_id != SPAM_CHANNEL_ID:
        await interaction.response.send_message(f"Lệnh này chỉ dùng được trong <#{SPAM_CHANNEL_ID}>.", ephemeral=True)
        return
    embed = discord.Embed(title="zLocket Bot Spammer", description="Chào mừng! Nhấn nút bên dưới để nhập License Key.", color=discord.Color.purple())
    await interaction.response.send_message(embed=embed, view=InitialView(), ephemeral=True)

@client.tree.command(name="genkey", description="[Admin] Tạo key cho người dùng.")
@app_commands.describe(user="Người dùng sẽ nhận key.", duration_days="Số ngày hiệu lực (ví dụ: 7, 30).")
async def genkey(interaction: discord.Interaction, user: discord.User, duration_days: int):
    if str(interaction.user.id) != ADMIN_USER_ID:
        await interaction.response.send_message("❌ Bạn không có quyền sử dụng lệnh này.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        new_key_info = keygen.add_key(duration_days, user.id, interaction.user.id)
        key = new_key_info['key']
        expiry_dt = new_key_info['expires_at']
        await interaction.followup.send(f"✅ Đã tạo key `{key}` cho {user.mention}, hết hạn vào {expiry_dt:%H:%M %d/%m/%Y}.", ephemeral=True)
        try: await user.send(f"🎉 Bạn đã nhận được key `{key}` từ admin, có hiệu lực trong {duration_days} ngày. Dùng `/start` để sử dụng.")
        except discord.Forbidden: await interaction.followup.send(f"⚠️ Không thể gửi DM cho {user.mention}. Hãy gửi key thủ công.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi khi tạo key: {e}", ephemeral=True)

@client.tree.command(name="hello", description="Kiểm tra xem bot có hoạt động không.")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("Xin chào! Tôi đang hoạt động tốt.", ephemeral=True)


# ==============================================================================
# 4. KHỞI CHẠY BOT
# ==============================================================================

# Khởi chạy Web Server trước
keep_alive()
# Chạy bot
client.run(DISCORD_TOKEN)

# bot.py
import discord
from discord import app_commands, ui
import os
import datetime
import time
from typing import Optional

print("--- Bot đang khởi chạy... ---")

from keep_alive import keep_alive
from spammer import SpamManager
import keygen

# --- Cài đặt ---
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
ADMIN_USER_ID = os.environ.get('ADMIN_USER_ID')
SPAM_CHANNEL_ID = 1381799563488399452  # !!! THAY BẰNG ID KÊNH CỦA BẠN !!!

# --- Kiểm tra cấu hình ---
if not DISCORD_TOKEN: print("!!! CRITICAL: Biến môi trường DISCORD_TOKEN bị thiếu !!!")
if not ADMIN_USER_ID: print("!!! WARNING: Biến môi trường ADMIN_USER_ID bị thiếu, /genkey sẽ không an toàn. !!!")

# --- Khởi tạo ---
spam_manager = SpamManager()
intents = discord.Intents.default()
class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
    async def setup_hook(self):
        # Đây là nơi tốt nhất để đồng bộ các lệnh
        await self.tree.sync()
client = MyClient(intents=intents)

# ================= UI LỚP =================

class KeyEntryModal(ui.Modal, title='Nhập License Key'):
    key_input = ui.TextInput(label='License Key', placeholder='Dán license key của bạn vào đây...')
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        result = spam_manager.validate_license(self.key_input.value)
        if result.get("valid"):
            expiry_dt = datetime.datetime.fromisoformat(result['expiry'].replace("Z", "+00:00"))
            await interaction.followup.send(f"✅ Key hợp lệ! Hiệu lực tới: {expiry_dt:%d/%m/%Y %H:%M:%S} UTC", view=SpamControlView(), ephemeral=True)
        else:
            errors = {"NOT_FOUND": "Key không tồn tại/hợp lệ.", "EXPIRED": "Key đã hết hạn.", "SUSPENDED": "Key đã bị tạm ngưng."}
            await interaction.followup.send(f"❌ Lỗi: {errors.get(result.get('code'), 'Lỗi không xác định.')}", ephemeral=True)

class SpamConfigModal(ui.Modal, title='Cấu hình Spam'):
    target_input = ui.TextInput(label='Locket Target (Username/Link)', required=True)
    async def on_submit(self, interaction: discord.Interaction):
        # Bắt đầu defer ở đây
        await interaction.response.defer(ephemeral=True, thinking=True)
        active_view = ActiveSpamView(interaction)
        async def update_callback(status: str, stats: Optional[dict] = None, message: Optional[str] = None):
            await active_view.update_message(status, stats, message)
        spam_manager.start_spam_session(interaction.user.id, self.target_input.value, update_callback)

class InitialView(ui.View):
    def __init__(self): super().__init__(timeout=300)
    @ui.button(label='Nhập Key', style=discord.ButtonStyle.primary, emoji='🔑')
    async def enter_key(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(KeyEntryModal())

class SpamControlView(ui.View):
    def __init__(self): super().__init__(timeout=300)
    @ui.button(label='Bắt Đầu Spam', style=discord.ButtonStyle.green, emoji='🚀')
    async def start_spam(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(SpamConfigModal())
        self.stop()
    @ui.button(label='Hủy', style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content='Đã hủy.', view=None)

class ActiveSpamView(ui.View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.interaction = interaction
        self.message = None
    async def update_message(self, status: str, stats: Optional[dict]=None, message: Optional[str]=None):
        if status == "started":
            self.message = await self.interaction.followup.send(message, view=self, ephemeral=True)
        elif status == "error":
             await self.interaction.followup.send(f"❌ Lỗi: {message}", ephemeral=True)
        if self.message is None: return
        try:
            if status == "running":
                embed = discord.Embed(title="🚀 Trạng thái Spam", color=discord.Color.blue()).add_field(name="Thành Công", value=f"✅ {stats['success']}").add_field(name="Thất Bại", value=f"❌ {stats['failed']}").add_field(name="Thời Gian", value=f"⏳ {datetime.timedelta(seconds=int(time.time() - stats['start_time']))}")
                await self.message.edit(embed=embed, view=self)
            elif status == "stopped":
                self.stop()
                embed = discord.Embed(title="🛑 Phiên Spam Đã Dừng", color=discord.Color.dark_grey()).add_field(name="Tổng Thành Công", value=f"✅ {stats['success']}").add_field(name="Tổng Thất Bại", value=f"❌ {stats['failed']}").add_field(name="Tổng Thời Gian", value=f"⏳ {datetime.timedelta(seconds=int(time.time() - stats['start_time']))}")
                await self.message.edit(embed=embed, view=None)
        except discord.NotFound: self.stop()
    @ui.button(label='Dừng Spam', style=discord.ButtonStyle.red, emoji='🛑')
    async def stop_spam(self, interaction: discord.Interaction, button: ui.Button):
        if spam_manager.stop_spam_session(interaction.user.id):
            await interaction.response.defer()
            button.disabled = True
            await self.message.edit(view=self)
        else: await interaction.response.send_message("Không có phiên spam nào.", ephemeral=True)


# ================= COMMANDS =================

@client.tree.command(name="start", description="Bắt đầu một phiên làm việc.")
async def start(interaction: discord.Interaction):
    if interaction.channel_id != SPAM_CHANNEL_ID:
        await interaction.response.send_message(f"Lệnh này chỉ dùng được trong <#{SPAM_CHANNEL_ID}>.", ephemeral=True)
        return
    embed = discord.Embed(title="zLocket Bot Spammer", description="Nhấn nút để nhập License Key.", color=discord.Color.purple())
    await interaction.response.send_message(embed=embed, view=InitialView(), ephemeral=True)

@client.tree.command(name="genkey", description="[Admin] Tạo key cho người dùng.")
@app_commands.describe(user="Người dùng nhận key.", duration_days="Số ngày hiệu lực.")
async def genkey(interaction: discord.Interaction, user: discord.User, duration_days: int):
    if str(interaction.user.id) != ADMIN_USER_ID:
        await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        new_key_info = keygen.add_key(duration_days, user.id, interaction.user.id)
        key = new_key_info['key']
        expiry_dt = new_key_info['expires_at']
        await interaction.followup.send(f"✅ Đã tạo key `{key}` cho {user.mention} (hiệu lực tới {expiry_dt:%d/%m/%Y}).", ephemeral=True)
        try: await user.send(f"🎉 Bạn nhận được key `{key}` từ admin, hiệu lực {duration_days} ngày. Dùng lệnh `/start` để kích hoạt.")
        except discord.Forbidden: await interaction.followup.send(f"⚠️ Không gửi DM được cho {user.mention}.", ephemeral=True)
    except Exception as e: await interaction.followup.send(f"Lỗi khi tạo key: {e}", ephemeral=True)

@client.tree.command(name="hello", description="Kiểm tra bot.")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("Xin chào!", ephemeral=True)

# ================= EVENTS =================
@client.event
async def on_ready():
    print(f'Đã đăng nhập với tên {client.user} (ID: {client.user.id})')
    print('-----------------------------------------')

# ================= RUN =================
if __name__ == "__main__":
    if DISCORD_TOKEN and ADMIN_USER_ID:
        keep_alive()
        client.run(DISCORD_TOKEN)
    else:
        print("!!! BOT SHUTDOWN: Thiếu DISCORD_TOKEN hoặc ADMIN_USER_ID trong biến môi trường.")

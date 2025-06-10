# bot.py
import discord
from discord import app_commands, ui
import os
import datetime
import time
from typing import Optional

print("--- [DEBUG] Bot đang khởi chạy với hệ thống key nội bộ. ---")

# Các file của chúng ta
from keep_alive import keep_alive
from spammer import SpamManager
import keygen # Import module keygen của chúng ta

# --- Cài đặt ---
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
ADMIN_USER_ID = os.environ.get('ADMIN_USER_ID') # ID Discord của Admin
SPAM_CHANNEL_ID = 1381799563488399452 # !!! THAY THẾ BẰNG ID KÊNH CỦA BẠN !!!

if not ADMIN_USER_ID:
    print("!!! CRITICAL WARNING: Biến môi trường ADMIN_USER_ID chưa được thiết lập. Lệnh /genkey sẽ không hoạt động an toàn!!!")

# --- Khởi tạo ---
spam_manager = SpamManager() # Không cần truyền tham số nữa
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
user_sessions = {}

# === CÁC LỚP UI (Modal, View) GIỮ NGUYÊN NHƯ CŨ, KHÔNG CẦN THAY ĐỔI ===
# Tôi sẽ rút gọn phần này để dễ đọc, bạn chỉ cần giữ nguyên code UI đã có.
class KeyEntryModal(ui.Modal, title='Nhập License Key'):
    # ... code giữ nguyên ...
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
            #... phần code báo lỗi giữ nguyên...
            code = validation_result.get("code", "UNKNOWN_ERROR")
            error_messages = {"NOT_FOUND": "Key không tồn tại hoặc không hợp lệ.", "EXPIRED": "Key đã hết hạn.", "SUSPENDED": "Key đã bị tạm ngưng."}
            await interaction.followup.send(f"❌ **Lỗi:** {error_messages.get(code, f'Lỗi không xác định. Mã: {code}')}", ephemeral=True)
# ... Các class UI khác (SpamConfigModal, SpamControlView, ActiveSpamView, InitialView) giữ nguyên y hệt...
class SpamConfigModal(ui.Modal, title='Cấu hình phiên Spam'):
    target_input = ui.TextInput(label='Locket Target (Username hoặc Link)', required=True)
    def __init__(self, user_id: int):
        super().__init__(); self.user_id = user_id
    async def on_submit(self, interaction: discord.Interaction):
        target = self.target_input.value
        await interaction.response.defer(ephemeral=True, thinking=True)
        active_view = ActiveSpamView(user_id=self.user_id, interaction=interaction)
        async def update_callback(status: str, stats: Optional[dict] = None, message: Optional[str] = None): await active_view.update_message(status, stats, message)
        spam_manager.start_spam_session(user_id=self.user_id, target=target, update_callback=update_callback)
class SpamControlView(ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300); self.user_id = user_id
    @ui.button(label='Bắt Đầu Spam', style=discord.ButtonStyle.green, emoji='🚀')
    async def start_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(SpamConfigModal(user_id=self.user_id))
        self.stop(); await interaction.message.edit(view=None)
    @ui.button(label='Hủy', style=discord.ButtonStyle.grey)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        self.stop(); await interaction.response.edit_message(content='Đã hủy.', view=None)
class ActiveSpamView(ui.View):
    def __init__(self, user_id: int, interaction: discord.Interaction):
        super().__init__(timeout=None); self.user_id = user_id; self.interaction = interaction; self.message = None
    async def update_message(self, status: str, stats: Optional[dict] = None, message: Optional[str] = None):
        if not self.interaction: return
        if status == "started": self.message = await self.interaction.followup.send(message, view=self, ephemeral=True); return
        if self.message is None:
            if status == "error": await self.interaction.followup.send(f"❌ Lỗi: {message}", ephemeral=True)
            return
        try:
            if status == "running":
                embed = discord.Embed(title="🚀 Trạng thái Spam", color=discord.Color.blue()).add_field(name="Thành Công", value=f"✅ {stats.get('success', 0)}").add_field(name="Thất Bại", value=f"❌ {stats.get('failed', 0)}").add_field(name="Thời Gian Chạy", value=f"⏳ {datetime.timedelta(seconds=int(time.time() - stats['start_time']))}")
                await self.message.edit(embed=embed, view=self)
            elif status == "stopped":
                self.stop()
                embed = discord.Embed(title="🛑 Phiên Spam Đã Dừng", color=discord.Color.default()).add_field(name="Tổng Thành Công", value=f"✅ {stats.get('success', 0)}").add_field(name="Tổng Thất Bại", value=f"❌ {stats.get('failed', 0)}").add_field(name="Tổng Thời Gian", value=f"⏳ {datetime.timedelta(seconds=int(time.time() - stats['start_time']))}")
                await self.message.edit(embed=embed, view=None)
        except discord.errors.NotFound: self.stop()
    @ui.button(label='Dừng Spam', style=discord.ButtonStyle.red, emoji='🛑')
    async def stop_button(self, interaction: discord.Interaction, button: ui.Button):
        if spam_manager.stop_spam_session(self.user_id):
            await interaction.response.defer(); button.disabled = True
            await self.message.edit(view=self)
        else: await interaction.response.send_message("Không có phiên spam nào đang chạy.", ephemeral=True)
class InitialView(ui.View):
    def __init__(self): super().__init__(timeout=300)
    @ui.button(label='Nhập Key', style=discord.ButtonStyle.primary, emoji='🔑')
    async def enter_key_button(self, interaction: discord.Interaction, button: ui.Button): await interaction.response.send_modal(KeyEntryModal())

# --- LỆNH MỚI CHO ADMIN ---
@tree.command(name="genkey", description="[Admin] Tạo một license key mới cho người dùng.")
@app_commands.describe(user="Người dùng sẽ nhận được key.", duration_days="Số ngày hiệu lực của key.")
async def genkey_command(interaction: discord.Interaction, user: discord.User, duration_days: int):
    # Kiểm tra xem người gõ lệnh có phải admin không
    if str(interaction.user.id) != ADMIN_USER_ID:
        await interaction.response.send_message("❌ Bạn không có quyền sử dụng lệnh này.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        new_key_info = keygen.add_key(
            duration_days=duration_days,
            created_for_user_id=user.id,
            creator_id=interaction.user.id
        )
        
        key = new_key_info['key']
        expiry_dt = new_key_info['expires_at']
        expiry_str = expiry_dt.strftime('%d/%m/%Y %H:%M:%S UTC')

        # Gửi key cho admin một cách riêng tư
        await interaction.followup.send(
            f"✅ Đã tạo key thành công cho người dùng {user.mention}.\n"
            f"Key: `{key}`\n"
            f"Hiệu lực: {duration_days} ngày (tới {expiry_str})",
            ephemeral=True
        )

        # Gửi key cho người dùng qua DM
        try:
            dm_message = (
                f"🎉 Bạn đã nhận được một license key cho zLocket Bot Spammer!\n\n"
                f"**Key của bạn:** `{key}`\n"
                f"**Hiệu lực:** {duration_days} ngày.\n\n"
                f"Để sử dụng, hãy vào kênh <#{SPAM_CHANNEL_ID}> và gõ lệnh `/start`."
            )
            await user.send(dm_message)
        except discord.Forbidden:
            await interaction.followup.send(
                f"⚠️ Không thể gửi DM cho người dùng {user.mention}. Hãy gửi key cho họ bằng tay.",
                ephemeral=True
            )

    except Exception as e:
        await interaction.followup.send(f"Đã xảy ra lỗi khi tạo key: {e}", ephemeral=True)

# --- Các lệnh cũ ---
@tree.command(name="start", description="Bắt đầu một phiên làm việc với zLocket Spammer.")
async def start_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if interaction.channel.id != SPAM_CHANNEL_ID:
        await interaction.followup.send(f"Lệnh này chỉ có thể được sử dụng trong kênh <#{SPAM_CHANNEL_ID}>.", ephemeral=True)
        return
    embed = discord.Embed(title="Chào mừng đến với zLocket Bot Spammer", description="Vui lòng nhấn nút bên dưới để nhập License Key.", color=discord.Color.purple())
    embed.set_footer(text="Mọi tương tác của bạn với bot tại đây đều là riêng tư.")
    await interaction.followup.send(embed=embed, view=InitialView(), ephemeral=True)

@tree.command(name="hello", description="Lệnh test đơn giản.")
async def hello_command(interaction: discord.Interaction):
    await interaction.response.send_message(f"Xin chào, {interaction.user.name}!", ephemeral=True)

# --- Khởi chạy Bot ---
@client.event
async def on_ready():
    await tree.sync()
    print(f'Bot đã đăng nhập với tên {client.user}')

if DISCORD_TOKEN and ADMIN_USER_ID:
    keep_alive()
    client.run(DISCORD_TOKEN)
else:
    print("!!! CRITICAL ERROR: Thiếu DISCORD_TOKEN hoặc ADMIN_USER_ID. Bot không thể khởi chạy. !!!")

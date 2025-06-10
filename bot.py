# bot.py (phiên bản 4.1 - Chẩn đoán thời gian)
import discord
from discord import app_commands, ui
import os
import datetime
import time
import asyncio
from typing import Optional

print("--- [LAUNCH] Bot đang khởi chạy, phiên bản 4.1 (Chẩn đoán thời gian)... ---")

from keep_alive import keep_alive
from spammer import SpamManager
import keygen

# ==============================================================================
# 1. CÀI ĐẶT
# ==============================================================================
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
ADMIN_USER_ID = os.environ.get('ADMIN_USER_ID')
SPAM_CHANNEL_ID = 1381799563488399452 # ID Kênh đã được cập nhật

if not DISCORD_TOKEN or not ADMIN_USER_ID:
    print("!!! [CRITICAL] Thiếu DISCORD_TOKEN hoặc ADMIN_USER_ID. Bot sẽ không khởi chạy.")
    exit()

# ... (Toàn bộ các lớp UI và các hàm khác giữ nguyên y hệt phiên bản trước)
# Để cho ngắn gọn, tôi sẽ chỉ dán lại phần client và các lệnh đã được sửa

# CÁC CLASS UI (KeyEntryModal, SpamConfigModal, ...) Giữ Nguyên

def format_time_left(expires_at_str):
    expires_dt = datetime.datetime.fromisoformat(expires_at_str.replace("Z", "+00:00")); delta = expires_dt - datetime.datetime.now(datetime.timezone.utc)
    if delta.total_seconds() <= 0: return "Hết hạn"
    d, h, m = delta.days, delta.seconds // 3600, (delta.seconds % 3600) // 60
    if d > 0: return f"{d} ngày {h} giờ"
    if h > 0: return f"{h} giờ {m} phút"
    return f"{m} phút"
class KeyEntryModal(ui.Modal, title='Nhập License Key'):
    key_input = ui.TextInput(label='License Key', placeholder='Dán key của bạn vào đây...'); async def on_submit(self, interaction: discord.Interaction):
        start_time = time.perf_counter()
        await interaction.response.defer(ephemeral=True); print(f"--- [TIMING] Defer KeyEntryModal mất: {time.perf_counter() - start_time:.4f} giây ---")
        result = spam_manager.validate_license(self.key_input.value)
        if result.get("valid"):
            key_info = result['key_info']; embed = discord.Embed(title=f"🔑 Key `{self.key_input.value}` đã kích hoạt!", description=f"Thời gian còn lại: **{format_time_left(key_info['expires_at'])}**", color=discord.Color.green())
            await interaction.followup.send(embed=embed, view=SpamControlView(self.key_input.value, key_info), ephemeral=True)
        else: await interaction.followup.send(f"❌ Lỗi: {result.get('code', 'Lỗi không xác định.')}", ephemeral=True)
class SpamConfigModal(ui.Modal, title='Cấu hình Spam'):
    target_input = ui.TextInput(label='Locket Target (Username/Link)');
    def __init__(self, key: str, key_info: dict, user_id: int): super().__init__(timeout=None); self.key, self.key_info, self.user_id = key, key_info, user_id
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True); active_view = ActiveSpamView(self.key, self.key_info, interaction)
        def update_callback(status, stats=None, message=None): asyncio.run_coroutine_threadsafe(active_view.update_message(status, stats, message), client.loop)
        spam_manager.start_spam_session(self.user_id, self.target_input.value, update_callback)
class InitialView(ui.View):
    def __init__(self): super().__init__(timeout=None)
    @ui.button(label='Nhập Key', style=discord.ButtonStyle.primary, emoji='🔑')
    async def enter_key(self, interaction: discord.Interaction, button: ui.Button): await interaction.response.send_modal(KeyEntryModal())
class SpamControlView(ui.View):
    def __init__(self, key: str, key_info: dict): super().__init__(timeout=600); self.key, self.key_info = key, key_info
    @ui.button(label='Bắt Đầu Spam', style=discord.ButtonStyle.green, emoji='🚀')
    async def start_spam(self, interaction: discord.Interaction, button: ui.Button): await interaction.response.send_modal(SpamConfigModal(self.key, self.key_info, interaction.user.id))
class ActiveSpamView(ui.View):
    def __init__(self, key: str, key_info: dict, original_interaction: discord.Interaction): super().__init__(timeout=None); self.key, self.key_info, self.original_interaction, self.status_message = key, key_info, original_interaction, None
    async def update_message(self, status, stats=None, message=None):
        if status == "started": self.status_message = await self.original_interaction.followup.send(message, view=self, ephemeral=True); return
        if status == "error": await self.original_interaction.followup.send(f"❌ Lỗi: {message}", ephemeral=True); return
        if not self.status_message: return
        embed = discord.Embed()
        if status == "running": embed.title="🚀 Trạng thái Spam"; embed.color=discord.Color.blue(); embed.add_field(name="Thành Công", value=f"✅ {stats['success']}").add_field(name="Thất Bại", value=f"❌ {stats['failed']}").add_field(name="Thời Gian", value=f"⏳ {datetime.timedelta(seconds=int(time.time() - stats['start_time']))}"); await self.status_message.edit(embed=embed)
        elif status == "stopped":
            self.stop(); embed.title="🛑 Phiên Spam Đã Dừng"; embed.color=discord.Color.dark_grey(); embed.add_field(name="Tổng Thành Công", value=f"✅ {stats['success']}").add_field(name="Tổng Thất Bại", value=f"❌ {stats['failed']}")
            final_view = ui.View(timeout=None); final_view.add_item(ui.Button(label="🚀 Spam Target Mới", style=discord.ButtonStyle.success, custom_id=f"spam_again:{self.key}")); final_view.add_item(ui.Button(label="Thoát", style=discord.ButtonStyle.grey, custom_id="exit"))
            await self.status_message.edit(embed=embed, view=final_view)
    @ui.button(label='Dừng Spam', style=discord.ButtonStyle.red, emoji='🛑')
    async def stop_spam(self, interaction: discord.Interaction, button: ui.Button):
        if spam_manager.stop_spam_session(interaction.user.id): button.disabled = True; await interaction.response.edit_message(view=self)
        else: await interaction.response.send_message("Không tìm thấy phiên spam.", ephemeral=True)
class MyBotClient(discord.Client):
    def __init__(self, *, intents: discord.Intents): super().__init__(intents=intents); self.tree = app_commands.CommandTree(self)
    async def setup_hook(self): await self.tree.sync(); print("--- [SYNC] Đồng bộ lệnh thành công. ---")
    async def on_ready(self): print(f'--- [READY] Bot đã đăng nhập: {self.user} ---')
    async def on_interaction(self, interaction: discord.Interaction):
        custom_id = interaction.data.get("custom_id") if interaction.data else None
        if custom_id:
            if custom_id.startswith("spam_again:"):
                key = custom_id.split(":", 1)[1]; await interaction.response.defer(ephemeral=True, thinking=True); result = spam_manager.validate_license(key)
                if result.get("valid"):
                    embed = discord.Embed(title=f"🔑 Key `{key}`!", description=f"Thời gian còn lại: **{format_time_left(result['key_info']['expires_at'])}**", color=discord.Color.green())
                    await interaction.followup.send(embed=embed, view=SpamControlView(key, result['key_info']), ephemeral=True)
                else: await interaction.followup.send("Key đã hết hạn.", ephemeral=True)
                try: await interaction.message.delete()
                except: pass
            elif custom_id == "exit": await interaction.response.edit_message(content="Đã đóng.", view=None, embed=None)
        # Truyền interaction cho tree để xử lý các lệnh slash command
        await self.tree.on_error(interaction, NotImplementedError)
client = MyBotClient(intents=intents)

@client.tree.command(name="genkey", description="[Admin] Tạo key.")
@app_commands.describe(user="Người dùng nhận key.", days="Số ngày hiệu lực.")
async def genkey(interaction: discord.Interaction, user: discord.User, days: int):
    start_time = time.perf_counter()
    print("--- [CMD] Nhận lệnh /genkey ---")
    if str(interaction.user.id) != ADMIN_USER_ID: await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True); return
    
    await interaction.response.defer(ephemeral=True)
    print(f"--- [TIMING] Defer /genkey mất: {time.perf_counter() - start_time:.4f} giây ---")

    key_info = keygen.add_key(days, user.id, interaction.user.id)
    await interaction.followup.send(f"✅ Đã tạo key `{key_info['key']}` cho {user.mention}.", ephemeral=True)
    try: await user.send(f"🎉 Bạn nhận được key `{key_info['key']}` (hiệu lực {days} ngày).")
    except: await interaction.followup.send(f"⚠️ Không gửi DM được.", ephemeral=True)

# ... các lệnh khác giữ nguyên cấu trúc tương tự ...
@client.tree.command(name="start", description="Bắt đầu phiên làm việc.")
async def start(interaction: discord.Interaction):
    start_time = time.perf_counter()
    print("--- [CMD] Nhận lệnh /start ---")
    if interaction.channel_id != SPAM_CHANNEL_ID: await interaction.response.send_message(f"Lệnh chỉ dùng trong <#{SPAM_CHANNEL_ID}>.", ephemeral=True); return
    await interaction.response.send_message(view=InitialView(), ephemeral=True) # Send message không cần defer
    print(f"--- [TIMING] Phản hồi /start mất: {time.perf_counter() - start_time:.4f} giây ---")
    
# ==============================================================================
# 4. KHỞI CHẠY
# ==============================================================================
keep_alive()
client.run(DISCORD_TOKEN)

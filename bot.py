# bot.py (phiên bản cuối cùng, ổn định v3.1)
import discord
from discord import app_commands, ui
import os
import datetime
import time
import asyncio
from typing import Optional

print("--- [LAUNCH] Bot đang khởi chạy, phiên bản ổn định v3.1... ---")

from keep_alive import keep_alive
from spammer import SpamManager
import keygen

# ==============================================================================
# 1. CÀI ĐẶT
# ==============================================================================
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
ADMIN_USER_ID = os.environ.get('ADMIN_USER_ID')
SPAM_CHANNEL_ID = 1381799563488399452  # ID Kênh đã được cập nhật

if not DISCORD_TOKEN or not ADMIN_USER_ID:
    print("!!! [CRITICAL] Thiếu DISCORD_TOKEN hoặc ADMIN_USER_ID. Bot sẽ không khởi chạy.")
    exit()

print("--- [CONFIG] Cấu hình đã được tải thành công. ---")
spam_manager = SpamManager()
intents = discord.Intents.default()

# ==============================================================================
# 2. HELPER & UI
# ==============================================================================
def format_time_left(expires_at_str):
    expires_dt = datetime.datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
    delta = expires_dt - datetime.datetime.now(datetime.timezone.utc)
    if delta.total_seconds() <= 0: return "Hết hạn"
    d, h, m = delta.days, delta.seconds // 3600, (delta.seconds % 3600) // 60
    if d > 0: return f"{d} ngày {h} giờ"
    if h > 0: return f"{h} giờ {m} phút"
    return f"{m} phút"

class KeyEntryModal(ui.Modal, title='Nhập License Key'):
    key_input = ui.TextInput(label='License Key', placeholder='Dán key của bạn vào đây...')
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        result = spam_manager.validate_license(self.key_input.value)
        if result.get("valid"):
            key_info = result['key_info']
            embed = discord.Embed(title=f"🔑 Key `{self.key_input.value}` đã kích hoạt!", description=f"Thời gian còn lại: **{format_time_left(key_info['expires_at'])}**", color=discord.Color.green())
            await interaction.followup.send(embed=embed, view=SpamControlView(self.key_input.value, key_info), ephemeral=True)
        else:
            errors = {"NOT_FOUND": "Key không tồn tại hoặc không hợp lệ.", "EXPIRED": "Key đã hết hạn.", "SUSPENDED": "Key đã bị tạm ngưng."}
            await interaction.followup.send(f"❌ Lỗi: {errors.get(result.get('code'), 'Lỗi không xác định.')}", ephemeral=True)

class SpamConfigModal(ui.Modal, title='Cấu hình Spam'):
    target_input = ui.TextInput(label='Locket Target (Username/Link)')
    def __init__(self, key: str, key_info: dict, parent_interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.key, self.key_info, self.parent_interaction = key, key_info, parent_interaction
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        active_view = ActiveSpamView(self.key, self.key_info, self.parent_interaction)
        def update_callback(status, stats=None, message=None): asyncio.run_coroutine_threadsafe(active_view.update_message(status, stats, message), client.loop)
        spam_manager.start_spam_session(interaction.user.id, self.target_input.value, update_callback)

class InitialView(ui.View):
    def __init__(self): super().__init__(timeout=None)
    @ui.button(label='Nhập Key', style=discord.ButtonStyle.primary, emoji='🔑')
    async def enter_key(self, interaction: discord.Interaction, button: ui.Button): await interaction.response.send_modal(KeyEntryModal())

class SpamControlView(ui.View):
    def __init__(self, key: str, key_info: dict):
        super().__init__(timeout=600); self.key, self.key_info = key, key_info
    @ui.button(label='Bắt Đầu Spam', style=discord.ButtonStyle.green, emoji='🚀')
    async def start_spam(self, interaction: discord.Interaction, button: ui.Button): await interaction.response.send_modal(SpamConfigModal(self.key, self.key_info, interaction))
    async def on_timeout(self):
        try:
            if hasattr(self, 'message') and self.message: await self.message.delete()
        except: pass

class ActiveSpamView(ui.View):
    def __init__(self, key: str, key_info: dict, parent_interaction: discord.Interaction):
        super().__init__(timeout=None); self.key, self.key_info, self.parent_interaction, self.status_message = key, key_info, parent_interaction, None
    async def update_message(self, status, stats=None, message=None):
        if status == "started": self.status_message = await self.parent_interaction.followup.send(message, view=self, ephemeral=True); return
        if status == "error": await self.parent_interaction.followup.send(f"❌ Lỗi: {message}", ephemeral=True); return
        if not self.status_message: return
        embed = discord.Embed()
        if status == "running":
            embed.title = "🚀 Trạng thái Spam"; embed.color=discord.Color.blue()
            embed.add_field(name="Thành Công", value=f"✅ {stats['success']}").add_field(name="Thất Bại", value=f"❌ {stats['failed']}").add_field(name="Thời Gian", value=f"⏳ {datetime.timedelta(seconds=int(time.time() - stats['start_time']))}")
            await self.status_message.edit(embed=embed)
        elif status == "stopped":
            self.stop()
            embed.title = "🛑 Phiên Spam Đã Dừng"; embed.color=discord.Color.dark_grey()
            embed.add_field(name="Tổng Thành Công", value=f"✅ {stats['success']}").add_field(name="Tổng Thất Bại", value=f"❌ {stats['failed']}")
            view = ui.View(timeout=None)
            view.add_item(ui.Button(label="🚀 Spam Target Mới", style=discord.ButtonStyle.success, custom_id=f"spam_again:{self.key}"))
            view.add_item(ui.Button(label="Thoát", style=discord.ButtonStyle.grey, custom_id="exit"))
            await self.status_message.edit(embed=embed, view=view)
    @ui.button(label='Dừng Spam', style=discord.ButtonStyle.red, emoji='🛑')
    async def stop_spam(self, interaction: discord.Interaction, button: ui.Button):
        if spam_manager.stop_spam_session(interaction.user.id): button.disabled = True; await interaction.response.edit_message(view=self)
        else: await interaction.response.send_message("Không tìm thấy phiên spam.", ephemeral=True)

class MyBotClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents); self.tree = app_commands.CommandTree(self)
    async def setup_hook(self): await self.tree.sync(); print("--- [SYNC] Đồng bộ lệnh lên Discord thành công. ---")
    async def on_ready(self): print(f'--- [READY] Bot đã đăng nhập: {self.user} ---')
    async def on_interaction(self, interaction: discord.Interaction):
        # Xử lý các nút bấm được tạo động
        if interaction.type == discord.InteractionType.component and interaction.data and "custom_id" in interaction.data:
            custom_id = interaction.data["custom_id"]
            if custom_id.startswith("spam_again:"):
                key = custom_id.split(":")[1]
                await interaction.response.defer(ephemeral=True)
                result = spam_manager.validate_license(key)
                if result.get("valid"):
                    embed = discord.Embed(title=f"🔑 Key `{key}` vẫn hoạt động!", description=f"Thời gian còn lại: **{format_time_left(result['key_info']['expires_at'])}**", color=discord.Color.green())
                    await interaction.followup.send(embed=embed, view=SpamControlView(key, result['key_info']), ephemeral=True)
                else: await interaction.followup.send("Key của bạn đã hết hạn hoặc không hợp lệ.", ephemeral=True)
                try: await interaction.message.delete()
                except: pass
            elif custom_id == "exit": await interaction.response.edit_message(content="Đã đóng.", view=None, embed=None)
        await self.tree.on_error(interaction, NotImplementedError) # Để các lệnh khác vẫn chạy
client = MyBotClient(intents=intents)

@client.tree.command(name="start", description="Bắt đầu phiên làm việc.")
async def start(interaction: discord.Interaction):
    if interaction.channel_id != SPAM_CHANNEL_ID: await interaction.response.send_message(f"Lệnh này chỉ dùng trong <#{SPAM_CHANNEL_ID}>.", ephemeral=True); return
    await interaction.response.send_message(embed=discord.Embed(title="zLocket Bot", description="Nhấn nút để nhập Key.", color=discord.Color.purple()), view=InitialView(), ephemeral=True)

@client.tree.command(name="listkeys", description="[Admin] Xem các key.")
async def listkeys(interaction: discord.Interaction):
    if str(interaction.user.id) != ADMIN_USER_ID: await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    #... code giữ nguyên ...
    keys_data = keygen.load_keys(); active_keys = {k: v for k,v in keys_data.items() if v.get('is_active', False) and datetime.datetime.fromisoformat(v['expires_at']) > datetime.datetime.now(datetime.timezone.utc)};
    if not active_keys: await interaction.followup.send("Không có key nào hoạt động.", ephemeral=True); return
    desc = "```" + "Key               | User ID             | Thời Gian Còn Lại\n" + "------------------|---------------------|--------------------\n"
    for key, info in list(active_keys.items())[:20]: desc += f"{key:<17} | {info.get('user_id', 'N/A'):<19} | {format_time_left(info['expires_at'])}\n"
    await interaction.followup.send(embed=discord.Embed(title=f"🔑 Key Hoạt Động ({len(active_keys)})", description=desc+"```", color=discord.Color.blue()), ephemeral=True)

@client.tree.command(name="delkey", description="[Admin] Vô hiệu hóa key.")
async def delkey(interaction: discord.Interaction, key: str):
    if str(interaction.user.id) != ADMIN_USER_ID: await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True); return
    if keygen.delete_key(key): await interaction.response.send_message(f"✅ Key `{key}` đã được vô hiệu hóa.", ephemeral=True)
    else: await interaction.response.send_message(f"❌ Không tìm thấy key `{key}`.", ephemeral=True)

@client.tree.command(name="genkey", description="[Admin] Tạo key.")
async def genkey(interaction: discord.Interaction, user: discord.User, days: int):
    if str(interaction.user.id) != ADMIN_USER_ID: await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    try:
        key_info = keygen.add_key(days, user.id, interaction.user.id)
        await interaction.followup.send(f"✅ Đã tạo key `{key_info['key']}` cho {user.mention} (hiệu lực {days} ngày).", ephemeral=True)
        try: await user.send(f"🎉 Bạn nhận được key `{key_info['key']}` (hiệu lực {days} ngày). Dùng `/start` để sử dụng.")
        except: await interaction.followup.send(f"⚠️ Không gửi DM được.", ephemeral=True)
    except Exception as e: await interaction.followup.send(f"❌ Lỗi: {e}", ephemeral=True)

keep_alive()
client.run(DISCORD_TOKEN)

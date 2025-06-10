# bot.py (Version 4.6 - Library Mode)
import discord
from discord import app_commands, ui
import os
import datetime
import time
import asyncio
from typing import Optional

# === CHANGED === Thay đổi thông báo khởi động
print("--- [BOT MODULE] Bot module loaded. ---")

# Import các file khác như một thư viện
from spammer import SpamManager
import keygen

# CÀI ĐẶT
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
ADMIN_USER_ID = os.environ.get('ADMIN_USER_ID')
SPAM_CHANNEL_ID = int(os.environ.get('SPAM_CHANNEL_ID', 1381799563488399452))

if not DISCORD_TOKEN or not ADMIN_USER_ID:
    print("!!! [CRITICAL] Thiếu DISCORD_TOKEN hoặc ADMIN_USER_ID.")
    exit()

spam_manager = SpamManager()
intents = discord.Intents.default()

# HELPER
def format_time_left(expires_at_str):
    expires_dt = datetime.datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
    delta = expires_dt - datetime.datetime.now(datetime.timezone.utc)
    if delta.total_seconds() <= 0: return "Hết hạn"
    d, h, m = delta.days, delta.seconds // 3600, (delta.seconds % 3600) // 60
    if d > 0: return f"{d} ngày {h} giờ"
    if h > 0: return f"{h} giờ {m} phút"
    return f"{m} phút"

# === UI CLASSES ===
class KeyEntryModal(ui.Modal, title='Nhập License Key'):
    key_input = ui.TextInput(label='License Key', placeholder='Dán key của bạn vào đây...')
    def __init__(self, original_message: discord.WebhookMessage):
        super().__init__(timeout=None)
        self.original_message = original_message
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        key_value = self.key_input.value; result = spam_manager.validate_license(key_value)
        if result.get("valid"):
            key_info = result['key_info']
            embed = discord.Embed(title="✅ Kích hoạt Key thành công!", description=f"Key của bạn còn **{format_time_left(key_info['expires_at'])}**.", color=discord.Color.green())
            await self.original_message.edit(embed=embed, view=SpamControlView(key_value, self.original_message))
            await interaction.followup.send("Key hợp lệ!", ephemeral=True)
        else:
            errors = {"NOT_FOUND":"Key không tồn tại...","EXPIRED":"Key đã hết hạn...","SUSPENDED":"Key đã bị tạm ngưng..."}
            await interaction.followup.send(f"❌ Lỗi: {errors.get(result.get('code'), 'Lỗi không xác định.')}", ephemeral=True)

class SpamConfigModal(ui.Modal, title='Cấu hình Spam'):
    target_input = ui.TextInput(label='Locket Target (Username/Link)')
    custom_name_input = ui.TextInput(label='Tên Custom cho tài khoản spam', required=False, max_length=20)
    threads_input = ui.TextInput(label='Số luồng (1-50, mặc định 25)', default="25", max_length=2)
    def __init__(self, key: str, control_message: discord.WebhookMessage):
        super().__init__(timeout=None)
        self.key, self.control_message = key, control_message
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            num_threads = int(self.threads_input.value)
            if not 1 <= num_threads <= 50: raise ValueError
        except (ValueError, TypeError):
            await interaction.followup.send("❌ Số luồng không hợp lệ (1-50).", ephemeral=True)
            return
        active_view = ActiveSpamView(interaction)
        def update_callback(status, stats=None, message=None):
            asyncio.run_coroutine_threadsafe(active_view.update_message(status, stats, message), client.loop)
        custom_name = self.custom_name_input.value or "zLocket Tool Pro"
        async def run_spam(): await spam_manager.start_spam_session(interaction.user.id, self.target_input.value, custom_name, num_threads, update_callback)
        asyncio.create_task(run_spam())
        await self.control_message.delete()

class InitialView(ui.View):
    def __init__(self, original_message: Optional[discord.WebhookMessage]=None): super().__init__(timeout=300); self.original_message = original_message
    @ui.button(label='Nhập Key', style=discord.ButtonStyle.primary, emoji='🔑')
    async def enter_key(self, i: discord.Interaction, b: ui.Button): await i.response.send_modal(KeyEntryModal(self.original_message))
    async def on_timeout(self):
        try:
            embed=self.original_message.embeds[0]; embed.description="Phiên làm việc đã hết hạn."; embed.color=discord.Color.dark_grey()
            await self.original_message.edit(embed=embed, view=None)
        except: pass

class SpamControlView(ui.View):
    def __init__(self, key: str, control_message: discord.WebhookMessage): super().__init__(timeout=600); self.key,self.control_message=key,control_message
    @ui.button(label='Bắt Đầu Spam', style=discord.ButtonStyle.green, emoji='🚀')
    async def start_spam(self, i: discord.Interaction, b: ui.Button): await i.response.send_modal(SpamConfigModal(self.key, self.control_message))
    async def on_timeout(self):
        try:
            embed=self.control_message.embeds[0]; embed.title="⌛ Phiên làm việc đã hết hạn"; embed.description="Dùng `/start` để bắt đầu lại."; embed.color=discord.Color.dark_grey()
            await self.control_message.edit(embed=embed, view=None)
        except: pass

class ActiveSpamView(ui.View):
    def __init__(self, i: discord.Interaction): super().__init__(timeout=None); self.original_interaction=i; self.status_message=None
    async def update_message(self, status, stats=None, message=None):
        if status=="started": self.status_message=await self.original_interaction.followup.send(message,view=self,ephemeral=True);return
        if status=="error": await self.original_interaction.followup.send(f"❌ **Lỗi:** {message}",ephemeral=True);self.stop();return
        if not self.status_message: return
        embed = discord.Embed()
        try:
            if status=="running":
                embed.title,embed.color="🚀 Trạng thái Spam: Đang Chạy",discord.Color.blue()
                runtime=datetime.timedelta(seconds=int(time.time()-stats['start_time']))
                embed.add_field(name="✅ Accounts", value=f"{stats['accounts']}", inline=True).add_field(name="💌 Yêu cầu", value=f"{stats['requests']}", inline=True)
                embed.add_field(name="❌ Lỗi", value=f"{stats['failed']}", inline=True).add_field(name="⏳ Thời gian", value=f"{runtime}", inline=False)
                await self.status_message.edit(embed=embed)
            elif status=="stopped":
                self.stop(); embed.title,embed.color="🛑 Phiên Spam Đã Dừng",discord.Color.dark_grey()
                embed.description="Hoàn thành hoặc dừng bởi người dùng."
                embed.add_field(name="✅ Tổng Accounts", value=f"{stats['accounts']}", inline=True).add_field(name="💌 Tổng Yêu Cầu", value=f"{stats['requests']}", inline=True).add_field(name="❌ Tổng Lỗi", value=f"{stats['failed']}", inline=True)
                await self.status_message.edit(content="Hoàn tất!", embed=embed, view=None)
        except(discord.errors.NotFound, asyncio.CancelledError): self.stop()
        except Exception: self.stop()
    @ui.button(label='Dừng Spam', style=discord.ButtonStyle.red, emoji='🛑')
    async def stop_spam(self, i: discord.Interaction, b: ui.Button):
        if spam_manager.stop_spam_session(i.user.id): b.disabled=True; await i.response.edit_message(content="*Đang xử lý yêu cầu dừng...*", view=self)
        else: await i.response.send_message("Không tìm thấy phiên spam.", ephemeral=True)

# CLIENT & COMMANDS
class MyBotClient(discord.Client):
    def __init__(self, *, intents: discord.Intents): super().__init__(intents=intents); self.tree = app_commands.CommandTree(self)
    async def setup_hook(self): await self.tree.sync(); print("--- [BOT MODULE] Đồng bộ lệnh thành công ---")
    async def on_ready(self): print(f'--- [BOT MODULE] Bot đã đăng nhập: {self.user} ---')

client = MyBotClient(intents=intents)

@client.tree.command(name="start", description="Bắt đầu một phiên làm việc mới.")
async def start(i: discord.Interaction):
    if i.channel.id != SPAM_CHANNEL_ID: return await i.response.send_message(f"Dùng lệnh trong <#{SPAM_CHANNEL_ID}>.",ephemeral=True)
    await i.response.defer(ephemeral=True)
    embed = discord.Embed(title="👋 Chào mừng đến với ZLocket Spammer",description="Nhập License Key để bắt đầu.",color=discord.Color.purple())
    embed.add_field(name="Cách có Key?", value="Liên hệ Admin.").set_footer(text="Bot by Zenn.")
    msg = await i.followup.send(embed=embed,ephemeral=True); await msg.edit(view=InitialView(msg))

# Các lệnh admin (giữ nguyên)
@client.tree.command(name="genkey",description="[Admin] Tạo key.")
@app_commands.describe(user="Người dùng",days="Số ngày")
async def genkey(i: discord.Interaction, user: discord.User, days: int):
    if str(i.user.id)!=ADMIN_USER_ID:return await i.response.send_message("❌ Bạn không có quyền.",ephemeral=True)
    await i.response.defer(ephemeral=True)
    try:
        k_info=keygen.add_key(days,user.id,i.user.id)
        await i.followup.send(f"✅ **Key:** `{k_info['key']}`\ncho {user.mention} (hiệu lực {days} ngày).",ephemeral=True)
    except Exception as e: await i.followup.send(f"❌ Lỗi: {e}",ephemeral=True)

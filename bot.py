# bot.py (Phiên bản 4.5 - Hoàn thiện Async/Await)
import discord
from discord import app_commands, ui
import os
import datetime
import time
import asyncio
from typing import Optional

print("--- [LAUNCH] Bot đang khởi chạy, phiên bản 4.5 (Hoàn thiện)... ---")

from keep_alive import keep_alive
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
        key_value = self.key_input.value
        result = spam_manager.validate_license(key_value)
        if result.get("valid"):
            key_info = result['key_info']
            embed = discord.Embed(title="✅ Kích hoạt Key thành công!", description=f"Key của bạn còn **{format_time_left(key_info['expires_at'])}** sử dụng.", color=discord.Color.green())
            embed.set_footer(text=f"Key: {key_value}")
            await self.original_message.edit(embed=embed, view=SpamControlView(key_value, self.original_message))
            await interaction.followup.send("Key hợp lệ! Bảng điều khiển đã được cập nhật.", ephemeral=True)
        else:
            errors = {"NOT_FOUND": "Key không tồn tại...", "EXPIRED": "Key đã hết hạn...", "SUSPENDED": "Key đã bị tạm ngưng..."}
            await interaction.followup.send(f"❌ Lỗi: {errors.get(result.get('code'), 'Lỗi không xác định.')}", ephemeral=True)


class SpamConfigModal(ui.Modal, title='Cấu hình Spam'):
    target_input = ui.TextInput(label='Locket Target (Username/Link)', placeholder='ví dụ: usernamecuaban hoặc link locket...')
    custom_name_input = ui.TextInput(label='Tên Custom cho tài khoản spam', placeholder='(Bỏ trống để dùng tên mặc định)', required=False, max_length=20)
    threads_input = ui.TextInput(label='Số luồng (threads)', placeholder='(1-50, mặc định 25)', default="25", max_length=2)

    def __init__(self, key: str, control_message: discord.WebhookMessage):
        super().__init__(timeout=None)
        self.key, self.control_message = key, control_message
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True) 
        
        try:
            num_threads = int(self.threads_input.value)
            if not 1 <= num_threads <= 50: raise ValueError
        except (ValueError, TypeError):
            await interaction.followup.send("❌ Số luồng không hợp lệ. Vui lòng nhập một số từ 1 đến 50.", ephemeral=True)
            return

        active_view = ActiveSpamView(interaction)
        def update_callback(status, stats=None, message=None):
            asyncio.run_coroutine_threadsafe(active_view.update_message(status, stats, message), client.loop)
        
        custom_name = self.custom_name_input.value or "zLocket Tool Pro"
        
        async def run_spam():
            await spam_manager.start_spam_session(interaction.user.id, self.target_input.value, custom_name, num_threads, update_callback)
        
        asyncio.create_task(run_spam())
        await self.control_message.delete()


class InitialView(ui.View):
    def __init__(self, original_message: Optional[discord.WebhookMessage] = None):
        super().__init__(timeout=300)
        self.original_message = original_message
    @ui.button(label='Nhập Key', style=discord.ButtonStyle.primary, emoji='🔑')
    async def enter_key(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(KeyEntryModal(original_message=self.original_message))
    async def on_timeout(self):
        try:
            embed = self.original_message.embeds[0]; embed.description = "Phiên làm việc đã hết hạn."; embed.color = discord.Color.dark_grey()
            await self.original_message.edit(embed=embed, view=None)
        except: pass


class SpamControlView(ui.View):
    def __init__(self, key: str, control_message: discord.WebhookMessage):
        super().__init__(timeout=600)
        self.key, self.control_message = key, control_message
    @ui.button(label='Bắt Đầu Spam', style=discord.ButtonStyle.green, emoji='🚀')
    async def start_spam(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(SpamConfigModal(self.key, self.control_message))
    async def on_timeout(self):
        try:
            embed = self.control_message.embeds[0]; embed.title = "⌛ Phiên làm việc đã hết hạn"; embed.description = "Dùng `/start` để bắt đầu lại."; embed.color = discord.Color.dark_grey()
            await self.control_message.edit(embed=embed, view=None)
        except: pass


class ActiveSpamView(ui.View):
    def __init__(self, original_interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.original_interaction = original_interaction
        self.status_message = None
        
    async def update_message(self, status, stats=None, message=None):
        if status == "started": 
            self.status_message = await self.original_interaction.followup.send(message, view=self, ephemeral=True)
            return
        if status == "error":
            await self.original_interaction.followup.send(f"❌ **Lỗi Khởi Động:** {message}", ephemeral=True)
            self.stop()
            return
        if not self.status_message: return

        embed = discord.Embed(title="🚀 Trạng thái Spam: Đang Chạy", color=discord.Color.blue())
        try:
            if status == "running":
                runtime = datetime.timedelta(seconds=int(time.time() - stats['start_time']))
                embed.add_field(name="✅ Accounts Tạo", value=f"{stats['accounts']}", inline=True)
                embed.add_field(name="💌 Y/c Gửi", value=f"{stats['requests']}", inline=True)
                embed.add_field(name="❌ Lỗi", value=f"{stats['failed']}", inline=True)
                embed.add_field(name="⏳ Thời gian", value=f"{runtime}", inline=False)
                await self.status_message.edit(embed=embed)
            elif status == "stopped":
                self.stop()
                embed.title, embed.color = "🛑 Phiên Spam Đã Dừng", discord.Color.dark_grey()
                embed.description = "Đã hoàn thành hoặc dừng bởi người dùng."
                embed.add_field(name="✅ Tổng Accounts", value=f"{stats['accounts']}", inline=True)
                embed.add_field(name="💌 Tổng Yêu Cầu", value=f"{stats['requests']}", inline=True)
                embed.add_field(name="❌ Tổng Lỗi", value=f"{stats['failed']}", inline=True)
                await self.status_message.edit(content="Hoàn tất!", embed=embed, view=None)
        except (discord.errors.NotFound, asyncio.CancelledError):
             self.stop() 
        except Exception: 
            self.stop()

    @ui.button(label='Dừng Spam', style=discord.ButtonStyle.red, emoji='🛑')
    async def stop_spam(self, interaction: discord.Interaction, button: ui.Button):
        if spam_manager.stop_spam_session(interaction.user.id):
            button.disabled = True
            await interaction.response.edit_message(content="*Đang xử lý yêu cầu dừng...*", view=self)
        else: await interaction.response.send_message("Không tìm thấy phiên spam.", ephemeral=True)

# CLIENT & COMMANDS
class MyBotClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents); self.tree = app_commands.CommandTree(self)
    async def setup_hook(self):
        await self.tree.sync(); print("--- [SYNC] Đồng bộ lệnh thành công ---")
    async def on_ready(self):
        print(f'--- [READY] Bot đã đăng nhập: {self.user} ---')

client = MyBotClient(intents=intents)

@client.tree.command(name="start", description="Bắt đầu một phiên làm việc mới.")
async def start(interaction: discord.Interaction):
    if interaction.channel.id != SPAM_CHANNEL_ID: return await interaction.response.send_message(f"Dùng lệnh trong <#{SPAM_CHANNEL_ID}>.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(title="👋 Chào mừng đến với ZLocket Spammer", description="Nhập License Key để bắt đầu.", color=discord.Color.purple())
    embed.add_field(name="Làm thế nào để có Key?", value="Liên hệ Admin để được cấp key.").set_footer(text="Bot được phát triển bởi Zenn.")
    msg = await interaction.followup.send(embed=embed, ephemeral=True)
    await msg.edit(view=InitialView(original_message=msg))

@client.tree.command(name="genkey", description="[Admin] Tạo key.")
@app_commands.describe(user="Người dùng nhận key.", days="Số ngày hiệu lực.")
async def genkey(interaction: discord.Interaction, user: discord.User, days: int):
    if str(interaction.user.id) != ADMIN_USER_ID: await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True); return
    try: await interaction.response.defer(ephemeral=True)
    except: return
    try:
        key_info = keygen.add_key(days, user.id, interaction.user.id)
        await interaction.followup.send(f"✅ **Đã tạo key!**\n\n**Người dùng:** {user.mention}\n**Hiệu lực:** {days} ngày\n**Key:** `{key_info['key']}`\n\n*Sao chép và gửi cho người dùng.*", ephemeral=True)
    except Exception as e: await interaction.followup.send(f"❌ Lỗi khi tạo key: {e}", ephemeral=True)

@client.tree.command(name="listkeys", description="[Admin] Xem các key.")
async def listkeys(interaction: discord.Interaction):
    if str(interaction.user.id) != ADMIN_USER_ID: await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    keys = {k: v for k, v in keygen.load_keys().items() if v.get('is_active') and datetime.datetime.fromisoformat(v['expires_at']) > datetime.datetime.now(datetime.timezone.utc)}
    if not keys: await interaction.followup.send("Không có key nào hoạt động.", ephemeral=True); return
    desc = "```" + "Key               | User ID             | Thời Gian Còn Lại\n" + "------------------|---------------------|--------------------\n"
    for k, v in list(keys.items())[:20]: desc += f"{k:<17} | {v.get('user_id', 'N/A'):<19} | {format_time_left(v['expires_at'])}\n"
    await interaction.followup.send(embed=discord.Embed(title=f"🔑 Key Hoạt Động ({len(keys)})", description=desc + "```"), ephemeral=True)

@client.tree.command(name="delkey", description="[Admin] Vô hiệu hóa key.")
@app_commands.describe(key="Key cần xóa.")
async def delkey(interaction: discord.Interaction, key: str):
    if str(interaction.user.id) != ADMIN_USER_ID: await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    if keygen.delete_key(key): await interaction.followup.send(f"✅ Key `{key}` đã bị vô hiệu hóa.", ephemeral=True)
    else: await interaction.followup.send(f"❌ Không tìm thấy key `{key}`.", ephemeral=True)

# KHỞI CHẠY
if __name__ == "__main__":
    try:
        keep_alive()
        client.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"!!! [CRITICAL] Lỗi khởi chạy bot: {e}")

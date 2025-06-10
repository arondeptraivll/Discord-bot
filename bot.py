# bot.py (Phiên bản 5.0 - Prestige Edition)
import discord
from discord import app_commands, ui
import os
import datetime
import time
import asyncio
from typing import Optional, Callable
from threading import Thread
from flask import Flask

from spammer import SpamManager
import keygen

print("--- [LAUNCH] Bot đang khởi chạy, phiên bản 5.0 (Prestige Edition)... ---")

# ==============================================================================
# 1. CÀI ĐẶT
# ==============================================================================
app = Flask('')
@app.route('/')
def home():
    return "Bot is alive and running!"

DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
ADMIN_USER_ID = os.environ.get('ADMIN_USER_ID')
SPAM_CHANNEL_ID = int(os.environ.get('SPAM_CHANNEL_ID', 1381799563488399452))

if not DISCORD_TOKEN or not ADMIN_USER_ID:
    print("!!! [CRITICAL] Thiếu DISCORD_TOKEN hoặc ADMIN_USER_ID.")

spam_manager = SpamManager()
intents = discord.Intents.default()

# ==============================================================================
# 2. HELPER & UI
# ==============================================================================
def format_time_left(expires_at_str):
    try:
        expires_dt = datetime.datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        delta = expires_dt - datetime.datetime.now(datetime.timezone.utc)
        if delta.total_seconds() <= 0: return "Hết hạn"
        d, h, m = delta.days, delta.seconds // 3600, (delta.seconds % 3600) // 60
        if d > 0: return f"{d} ngày {h} giờ"
        if h > 0: return f"{h} giờ {m} phút"
        return f"{m} phút"
    except: return "Không xác định"

class KeyEntryModal(ui.Modal, title='🔑 Nhập License Key'):
    key_input = ui.TextInput(label='License Key', placeholder='Dán key của bạn vào đây...')

    def __init__(self, original_message: discord.WebhookMessage):
        super().__init__(timeout=None)
        self.original_message = original_message
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        result = spam_manager.validate_license(self.key_input.value)
        if result.get("valid"):
            key_info = result['key_info']
            embed = discord.Embed(title="✅ Key Hợp Lệ - Bảng Điều Khiển", color=discord.Color.green())
            await self.original_message.edit(embed=embed, view=SpamConfigView(self.key_input.value, key_info, self.original_message))
            await interaction.followup.send("Kích hoạt thành công! Vui lòng cấu hình phiên spam.", ephemeral=True)
        else:
            errors = {"NOT_FOUND": "Key không tồn tại.", "EXPIRED": "Key đã hết hạn.", "SUSPENDED": "Key đã bị tạm ngưng."}
            await interaction.followup.send(f"❌ Lỗi: {errors.get(result.get('code'), 'Lỗi không xác định.')}", ephemeral=True)

# === NEW: MODAL CẤU HÌNH TẤT CẢ TRONG MỘT ===
class SpamSetupModal(ui.Modal, title='🛠️ Cấu hình phiên Spam'):
    target_input = ui.TextInput(label='🎯 Locket Target (Username/Link)', placeholder='Ví dụ: mylocketuser hoặc link invite', required=True)
    name_input = ui.TextInput(label='👤 Custom Username (Tối đa 20 ký tự)', placeholder='Để trống để dùng tên mặc định', required=False, max_length=20)
    emoji_input = ui.TextInput(label='🎨 Sử dụng Emoji ngẫu nhiên? (y/n)', placeholder='y (có) hoặc n (không) - mặc định là có', required=False, max_length=1)

    def __init__(self, key: str, original_message: discord.WebhookMessage):
        super().__init__(timeout=None)
        self.key = key
        self.original_message = original_message
        
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        target = self.target_input.value
        custom_name = self.name_input.value if self.name_input.value else "zLocket Tool"
        use_emojis = self.emoji_input.value.lower() != 'n'

        await self.original_message.delete()
        
        active_view = ActiveSpamView(target=target)

        def update_callback(status: str, stats: Optional[dict]=None, message: Optional[str]=None):
            asyncio.run_coroutine_threadsafe(
                active_view.update_message(status, stats, message), 
                client.loop
            )
        
        spam_manager.start_spam_session(interaction.user.id, target, custom_name, use_emojis, update_callback)
        await interaction.followup.send("Cấu hình hoàn tất, phiên spam đang được khởi động!", ephemeral=True, view=active_view)

# === NEW: VIEW CẤU HÌNH SPAM ===
class SpamConfigView(ui.View):
    def __init__(self, key: str, key_info: dict, original_message: discord.WebhookMessage):
        super().__init__(timeout=600)
        self.key = key
        self.key_info = key_info
        self.original_message = original_message
        self.update_embed()

    def update_embed(self):
        embed = self.original_message.embeds[0]
        embed.description = (
            f"Key của bạn còn **{format_time_left(self.key_info.get('expires_at'))}**.\n"
            "Nhấn nút bên dưới để bắt đầu cấu hình và khởi chạy phiên spam của bạn."
        )
        embed.set_footer(text=f"Key: {self.key}")

    @ui.button(label='🚀 Cấu hình & Bắt đầu', style=discord.ButtonStyle.success, emoji='🛠️')
    async def setup_and_start(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(SpamSetupModal(self.key, self.original_message))
    
    async def on_timeout(self):
        try:
            embed = self.original_message.embeds[0]
            embed.title, embed.description = "⌛ Phiên làm việc đã hết hạn", "Vui lòng dùng `/start` để bắt đầu lại."
            embed.color = discord.Color.dark_grey()
            await self.original_message.edit(embed=embed, view=None)
        except: pass

class InitialView(ui.View):
    def __init__(self, original_message: Optional[discord.WebhookMessage]=None):
        super().__init__(timeout=300)
        self.original_message = original_message

    @ui.button(label='Nhập Key', style=discord.ButtonStyle.primary, emoji='🔑')
    async def enter_key(self, interaction: discord.Interaction, button: ui.Button):
        if not self.original_message: return await interaction.response.send_message("Lỗi: Phiên đã hết hạn.", ephemeral=True)
        await interaction.response.send_modal(KeyEntryModal(original_message=self.original_message))
    
    async def on_timeout(self):
        try:
            if self.original_message and self.original_message.embeds:
                embed = self.original_message.embeds[0]
                embed.description, embed.color = "Phiên làm việc đã hết hạn.", discord.Color.dark_grey()
                await self.original_message.edit(embed=embed, view=None)
        except: pass
        
class ActiveSpamView(ui.View):
    def __init__(self, target: str):
        super().__init__(timeout=None)
        self.target = target

    async def update_message(self, status: str, stats: Optional[dict] = None, message: Optional[str] = None):
        # The view now is only for stopping, the status is a separate message
        pass # The logic is now handled in the interaction.followup.send from the modal

    @ui.button(label='Dừng Spam', style=discord.ButtonStyle.red, emoji='🛑')
    async def stop_spam(self, interaction: discord.Interaction, button: ui.Button):
        if spam_manager.stop_spam_session(interaction.user.id):
            button.disabled = True
            await interaction.response.edit_message(content="✅ Đã gửi yêu cầu dừng spam! Luồng sẽ kết thúc sau ít giây.", view=self)
        else: await interaction.response.send_message("Không tìm thấy phiên spam để dừng.", ephemeral=True)

# ==============================================================================
# 3. CLIENT & LỆNH
# ==============================================================================
class MyBotClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("--- [SYNC] Đồng bộ lệnh lên Discord thành công. ---")

    async def on_ready(self):
        print(f'--- [READY] Bot đã đăng nhập: {self.user} ---')

client = MyBotClient(intents=intents)

@client.tree.command(name="start", description="Bắt đầu một phiên làm việc mới.")
async def start(interaction: discord.Interaction):
    if interaction.channel.id != SPAM_CHANNEL_ID: return await interaction.response.send_message(f"Lệnh chỉ dùng được trong <#{SPAM_CHANNEL_ID}>.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(title="🌟 ZLocket Spammer Bot - Prestige Edition 🌟", description="Chào mừng bạn! Vui lòng nhập License Key để tiếp tục.", color=discord.Color.blurple())
    embed.add_field(name="Cách có Key?", value=f"Liên hệ Admin <@{ADMIN_USER_ID}> để được cấp.", inline=False)
    embed.set_footer(text=f"Phiên bản {client.get_user(client.application_id).name} 5.0")
    message = await interaction.followup.send(embed=embed, ephemeral=True, wait=True)
    await message.edit(view=InitialView(original_message=message))

# (Các lệnh admin giữ nguyên)
@client.tree.command(name="genkey", description="[Admin] Tạo một license key mới.")
@app_commands.describe(user="Người dùng nhận key.", days="Số ngày hiệu lực.")
async def genkey(interaction: discord.Interaction, user: discord.User, days: int):
    #...
    pass

# ==============================================================================
# 4. KHỞI CHẠY
# ==============================================================================
def run_bot():
    if DISCORD_TOKEN:
        print("--- [BOT] Đang khởi chạy bot Discord trong một luồng riêng...")
        client.run(DISCORD_TOKEN)

bot_thread = Thread(target=run_bot)
bot_thread.daemon = True
bot_thread.start()

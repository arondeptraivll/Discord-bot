# bot.py (phiên bản có cải tiến)
import discord
from discord import app_commands, ui
import os
import datetime
import time
import asyncio
from typing import Optional

print("--- [LAUNCH] Bot đang khởi chạy, phiên bản nâng cao... ---")

from keep_alive import keep_alive
from spammer import SpamManager
import keygen

# ==============================================================================
# 1. CÀI ĐẶT
# ==============================================================================
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
ADMIN_USER_ID = os.environ.get('ADMIN_USER_ID') # THIẾT LẬP TRÊN RENDER
SPAM_CHANNEL_ID = 1381799563488399452  # !!! THAY BẰNG ID KÊNH CỦA BẠN !!!
if not DISCORD_TOKEN or not ADMIN_USER_ID: exit("!!! LỖI: Thiếu biến môi trường quan trọng.")

spam_manager = SpamManager()
intents = discord.Intents.default()

# ==============================================================================
# 2. CẤU TRÚC CLIENT VÀ LỚP UI (Views & Modals)
# ==============================================================================

# Helper function để tính thời gian còn lại
def format_time_left(expires_at_str):
    expires_dt = datetime.datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
    now = datetime.datetime.now(datetime.timezone.utc)
    delta = expires_dt - now
    if delta.total_seconds() <= 0: return "Hết hạn"
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    if days > 0: return f"{days} ngày {hours} giờ"
    minutes, _ = divmod(remainder, 60)
    if hours > 0: return f"{hours} giờ {minutes} phút"
    return f"{minutes} phút"

class KeyEntryModal(ui.Modal, title='Nhập License Key'):
    key_input = ui.TextInput(label='License Key', placeholder='Dán key của bạn vào đây...')
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        result = spam_manager.validate_license(self.key_input.value)
        if result.get("valid"):
            key_info = result['key_info']
            embed = discord.Embed(
                title=f"🔑 Key `{self.key_input.value}` đã được kích hoạt!",
                description=f"Thời gian còn lại: **{format_time_left(key_info['expires_at'])}**",
                color=discord.Color.green()
            )
            # Truyền key và thông tin key vào view tiếp theo
            await interaction.followup.send(embed=embed, view=SpamControlView(key=self.key_input.value, key_info=key_info), ephemeral=True)
        else:
            errors = {"NOT_FOUND": "Key không tồn tại hoặc không hợp lệ.", "EXPIRED": "Key đã hết hạn.", "SUSPENDED": "Key đã bị tạm ngưng."}
            await interaction.followup.send(f"❌ Lỗi: {errors.get(result.get('code'), 'Lỗi không xác định.')}", ephemeral=True)

class SpamConfigModal(ui.Modal, title='Cấu hình Spam'):
    target_input = ui.TextInput(label='Locket Target (Username/Link)')
    def __init__(self, key: str, key_info: dict, parent_view_interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.key = key
        self.key_info = key_info
        self.parent_view_interaction = parent_view_interaction
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        active_view = ActiveSpamView(self.key, self.key_info, self.parent_view_interaction, interaction.user.id)
        def update_callback(status, stats=None, message=None):
            asyncio.run_coroutine_threadsafe(active_view.update_message(status, stats, message), client.loop)
        spam_manager.start_spam_session(interaction.user.id, self.target_input.value, update_callback)

class InitialView(ui.View):
    def __init__(self): super().__init__(timeout=300)
    @ui.button(label='Nhập Key', style=discord.ButtonStyle.primary, emoji='🔑')
    async def enter_key(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(KeyEntryModal())

class SpamControlView(ui.View):
    def __init__(self, key: str, key_info: dict):
        super().__init__(timeout=600) # Tăng timeout lên 10 phút
        self.key = key
        self.key_info = key_info
    @ui.button(label='Bắt Đầu Spam', style=discord.ButtonStyle.green, emoji='🚀')
    async def start_spam(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(SpamConfigModal(self.key, self.key_info, interaction))
    async def on_timeout(self):
        try:
            # Tự xóa tin nhắn khi view hết hạn
            if self.message: await self.message.delete()
        except: pass

class ActiveSpamView(ui.View):
    def __init__(self, key: str, key_info: dict, parent_interaction: discord.Interaction, user_id: int):
        super().__init__(timeout=None)
        self.key, self.key_info = key, key_info
        self.parent_interaction = parent_interaction
        self.status_message, self.user_id = None, user_id
    async def update_message(self, status, stats=None, message=None):
        if status == "started":
            # Xóa tin nhắn "đang nghĩ" của modal
            await self.parent_interaction.delete_original_response()
            self.status_message = await self.parent_interaction.followup.send(message, view=self, ephemeral=True)
        elif status == "error":
             await self.parent_interaction.followup.send(f"❌ Lỗi: {message}", ephemeral=True)
        if not self.status_message: return

        if status == "running":
            embed = discord.Embed(title="🚀 Trạng thái Spam", color=discord.Color.blue()).add_field(name="Thành Công", value=f"✅ {stats['success']}").add_field(name="Thất Bại", value=f"❌ {stats['failed']}").add_field(name="Thời Gian", value=f"⏳ {datetime.timedelta(seconds=int(time.time() - stats['start_time']))}")
            await self.status_message.edit(embed=embed, view=self)
        elif status == "stopped":
            self.clear_items() # Xóa nút Dừng Spam
            self.add_item(ui.Button(label="🚀 Spam Target Mới", style=discord.ButtonStyle.success, custom_id="spam_again"))
            self.add_item(ui.Button(label="Thoát", style=discord.ButtonStyle.grey, custom_id="exit"))
            embed = discord.Embed(title="🛑 Phiên Spam Đã Dừng", color=discord.Color.dark_grey()).add_field(name="Tổng Thành Công", value=f"✅ {stats['success']}").add_field(name="Tổng Thất Bại", value=f"❌ {stats['failed']}")
            await self.status_message.edit(content="", embed=embed, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Xử lý các nút bấm được thêm vào sau khi spam dừng
        if interaction.data.get("custom_id") == "spam_again":
            # Xóa tin nhắn hiện tại và quay về màn hình điều khiển
            await interaction.response.defer()
            await interaction.delete_original_response()
            embed = discord.Embed(title=f"🔑 Key `{self.key}` vẫn hoạt động!", description=f"Thời gian còn lại: **{format_time_left(self.key_info['expires_at'])}**", color=discord.Color.green())
            await interaction.followup.send(embed=embed, view=SpamControlView(self.key, self.key_info), ephemeral=True)
        elif interaction.data.get("custom_id") == "exit":
            await interaction.response.edit_message(content="Đã đóng phiên làm việc.", embed=None, view=None)
        return True

    @ui.button(label='Dừng Spam', style=discord.ButtonStyle.red, emoji='🛑')
    async def stop_spam(self, interaction: discord.Interaction, button: ui.Button):
        if spam_manager.stop_spam_session(self.user_id):
            await interaction.response.defer(); button.disabled = True
            await self.status_message.edit(view=self)
        else: await interaction.response.send_message("Không tìm thấy phiên spam.", ephemeral=True)

class MyBotClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents); self.tree = app_commands.CommandTree(self)
    async def setup_hook(self):
        await self.tree.sync(); print("--- [SYNC] Đồng bộ lệnh lên Discord thành công. ---")
    async def on_ready(self):
        print(f'--- [READY] Bot đã đăng nhập: {self.user} ---')

client = MyBotClient(intents=intents)

# ==============================================================================
# 3. COMMANDS
# ==============================================================================
@client.tree.command(name="start", description="Bắt đầu một phiên làm việc.")
async def start(interaction: discord.Interaction):
    if interaction.channel_id != SPAM_CHANNEL_ID: await interaction.response.send_message(f"Lệnh này chỉ dùng được trong <#{SPAM_CHANNEL_ID}>.", ephemeral=True); return
    embed = discord.Embed(title="zLocket Bot Spammer", description="Chào mừng! Nhấn nút để nhập License Key.", color=discord.Color.purple())
    await interaction.response.send_message(embed=embed, view=InitialView(), ephemeral=True)

# Lệnh admin
@client.tree.command(name="listkeys", description="[Admin] Xem danh sách các key đang hoạt động.")
async def listkeys(interaction: discord.Interaction):
    if str(interaction.user.id) != ADMIN_USER_ID: await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    keys_data = keygen.load_keys()
    active_keys = {k: v for k, v in keys_data.items() if v.get('is_active', False) and datetime.datetime.fromisoformat(v['expires_at'].replace("Z", "+00:00")) > datetime.datetime.now(datetime.timezone.utc)}
    if not active_keys: await interaction.followup.send("Không có key nào đang hoạt động.", ephemeral=True); return
    
    description = "```"
    description += "Key               | User ID             | Thời Gian Còn Lại\n"
    description += "------------------|---------------------|--------------------\n"
    for key, info in list(active_keys.items())[:20]: # Giới hạn 20 key để tránh tin nhắn quá dài
        user_id = info.get('user_id', 'N/A')
        time_left = format_time_left(info['expires_at'])
        description += f"{key:<17} | {user_id:<19} | {time_left}\n"
    description += "```"
    
    embed = discord.Embed(title=f"🔑 Danh sách Key Hoạt Động ({len(active_keys)} key)", description=description, color=discord.Color.blue())
    await interaction.followup.send(embed=embed, ephemeral=True)

@client.tree.command(name="delkey", description="[Admin] Vô hiệu hóa một key.")
@app_commands.describe(key_to_delete="Key cần xóa.")
async def delkey(interaction: discord.Interaction, key_to_delete: str):
    if str(interaction.user.id) != ADMIN_USER_ID: await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True); return
    if keygen.delete_key(key_to_delete): await interaction.response.send_message(f"✅ Key `{key_to_delete}` đã được vô hiệu hóa.", ephemeral=True)
    else: await interaction.response.send_message(f"❌ Không tìm thấy key `{key_to_delete}`.", ephemeral=True)

@client.tree.command(name="genkey", description="[Admin] Tạo key cho người dùng.")
@app_commands.describe(user="Người dùng nhận key.", duration_days="Số ngày hiệu lực.")
async def genkey(interaction: discord.Interaction, user: discord.User, duration_days: int):
    #... Giữ nguyên code lệnh genkey ...
    if str(interaction.user.id) != ADMIN_USER_ID: await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    try:
        new_key_info = keygen.add_key(duration_days, user.id, interaction.user.id)
        key = new_key_info['key']
        expiry_dt = new_key_info['expires_at']
        await interaction.followup.send(f"✅ Đã tạo key `{key}` cho {user.mention} (hết hạn lúc {expiry_dt:%H:%M %d/%m/%Y}).", ephemeral=True)
        try: await user.send(f"🎉 Bạn nhận được key `{key}` từ admin, hiệu lực {duration_days} ngày. Dùng `/start` để sử dụng.")
        except: await interaction.followup.send(f"⚠️ Không gửi DM được cho {user.mention}.", ephemeral=True)
    except Exception as e: await interaction.followup.send(f"❌ Lỗi khi tạo key: {e}", ephemeral=True)

# ==============================================================================
# 4. KHỞI CHẠY BOT
# ==============================================================================
keep_alive()
client.run(DISCORD_TOKEN)

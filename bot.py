# bot.py (Phiên bản Cải Tiến Lớn - Dual Key Systems - Sửa lỗi Acknowledge)
import discord
from discord import app_commands, ui
import os
import datetime
import time
import asyncio
from typing import Optional

from flask import Flask

# Import các module logic đã tách
from spammer import SpamManager
import keygen # Key system cho Locket
import aov_keygen # Key system mới cho AOV
import account_manager

print("--- [LAUNCH] Bot đang khởi chạy, phiên bản cải tiến... ---")

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
AOV_CHANNEL_ID = 1382203422094266390

if not DISCORD_TOKEN or not ADMIN_USER_ID:
    print("!!! [CRITICAL] Thiếu DISCORD_TOKEN hoặc ADMIN_USER_ID.")

spam_manager = SpamManager()
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ==============================================================================
# 2. HELPER & UI CHUNG
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

# ==============================================================================
# 3. UI VÀ LOGIC CHO CHỨC NĂNG SPAM LOCKET (/start)
# ==============================================================================
# (Toàn bộ phần này không thay đổi, bạn có thể giữ nguyên)
class KeyEntryModal(ui.Modal, title='🔑 Nhập License Key Locket'):
    key_input = ui.TextInput(label='License Key', placeholder='Dán key của bạn vào đây...')
    def __init__(self, original_message: discord.WebhookMessage): super().__init__(timeout=None); self.original_message = original_message
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        result = spam_manager.validate_license(self.key_input.value)
        if result.get("valid"): key_info = result['key_info']; embed = discord.Embed(title="✅ Key Hợp Lệ - Bảng Điều Khiển Spam", color=discord.Color.green()); await self.original_message.edit(embed=embed, view=SpamConfigView(self.key_input.value, key_info, self.original_message)); await interaction.followup.send("Kích hoạt thành công! Vui lòng cấu hình phiên spam.", ephemeral=True)
        else: errors = {"NOT_FOUND": "Key không tồn tại.", "EXPIRED": "Key đã hết hạn.", "SUSPENDED": "Key đã bị tạm ngưng."}; await interaction.followup.send(f"❌ Lỗi: {errors.get(result.get('code'), 'Lỗi không xác định.')}", ephemeral=True)
class SpamSetupModal(ui.Modal, title='🛠️ Cấu hình phiên Spam'):
    target_input = ui.TextInput(label='🎯 Locket Target (Username/Link)', placeholder='Ví dụ: mylocketuser hoặc link invite', required=True); name_input = ui.TextInput(label='👤 Custom Username (Tối đa 20 ký tự)', placeholder='Để trống để dùng tên mặc định', required=False, max_length=20); emoji_input = ui.TextInput(label='🎨 Sử dụng Emoji ngẫu nhiên? (y/n)', placeholder='y (có) hoặc n (không) - mặc định là có', required=False, max_length=1)
    def __init__(self, key: str, original_message: discord.WebhookMessage): super().__init__(timeout=None); self.key, self.original_message = key, original_message
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        target = self.target_input.value; custom_name = self.name_input.value if self.name_input.value.strip() else "zLocket Tool"; use_emojis = self.emoji_input.value.lower().strip() != 'n'; await self.original_message.delete()
        status_view = ActiveSpamView(); status_embed = discord.Embed(title="🔄 Khởi động phiên spam...", description=f"**Target:** `{target}`\n**Username:** `{custom_name}`\n**Emoji:** {'Bật' if use_emojis else 'Tắt'}", color=discord.Color.orange())
        status_message = await interaction.followup.send(embed=status_embed, ephemeral=True, view=status_view, wait=True)
        status_view.set_message(status_message)
        def update_callback(status: str, stats: Optional[dict]=None, message: Optional[str]=None):
            if client and client.loop: asyncio.run_coroutine_threadsafe(status_view.update_message(status, stats, message), client.loop)
        spam_manager.start_spam_session(interaction.user.id, target, custom_name, use_emojis, update_callback)
class SpamConfigView(ui.View):
    def __init__(self, key: str, key_info: dict, original_message: discord.WebhookMessage): super().__init__(timeout=600); self.key, self.key_info, self.original_message = key, key_info, original_message; self.update_embed()
    def update_embed(self): embed = self.original_message.embeds[0]; embed.description = f"Key còn **{format_time_left(self.key_info.get('expires_at'))}**.\nNhấn nút bên dưới để cấu hình và chạy."; embed.set_footer(text=f"Key: {self.key}")
    @ui.button(label='🚀 Cấu hình & Bắt đầu', style=discord.ButtonStyle.success, emoji='🛠️')
    async def setup_and_start(self, interaction: discord.Interaction, button: ui.Button): await interaction.response.send_modal(SpamSetupModal(self.key, self.original_message))
    async def on_timeout(self):
        try: embed = self.original_message.embeds[0]; embed.title, embed.description = "⌛ Phiên làm việc đã hết hạn", "Dùng `/start` để bắt đầu lại."; embed.color, embed.clear_fields(); await self.original_message.edit(embed=embed, view=None)
        except: pass
class InitialView(ui.View):
    def __init__(self, original_message: Optional[discord.WebhookMessage]=None): super().__init__(timeout=300); self.original_message = original_message
    @ui.button(label='Nhập Key Locket', style=discord.ButtonStyle.primary, emoji='🔑')
    async def enter_key(self, interaction: discord.Interaction, button: ui.Button):
        if not self.original_message: return await interaction.response.send_message("Lỗi: Phiên đã hết hạn.", ephemeral=True)
        await interaction.response.send_modal(KeyEntryModal(original_message=self.original_message))
    async def on_timeout(self):
        try:
            if self.original_message and self.original_message.embeds: embed = self.original_message.embeds[0]; embed.description = "Phiên làm việc đã hết hạn."; embed.color = discord.Color.dark_grey(); await self.original_message.edit(embed=embed, view=None)
        except: pass
class ActiveSpamView(ui.View):
    def __init__(self): super().__init__(timeout=None); self.status_message = None
    def set_message(self, message: discord.WebhookMessage): self.status_message = message
    async def update_message(self, status: str, stats: Optional[dict] = None, message_text: Optional[str] = None):
        if not self.status_message: return
        embed = self.status_message.embeds[0]
        if status == "error": embed.title="❌ Lỗi nghiêm trọng"; embed.description = message_text; embed.color=discord.Color.red(); await self.status_message.edit(embed=embed, view=None); self.stop(); return
        try:
            if status == "running": embed.title = "🚀 Trạng thái Spam: Đang Chạy"; embed.color = discord.Color.blue(); embed.clear_fields(); embed.add_field(name="Thành Công", value=f"✅ {stats['success']}", inline=True); embed.add_field(name="Thất Bại", value=f"❌ {stats['failed']}", inline=True); runtime = datetime.timedelta(seconds=int(time.time() - stats['start_time'])); embed.add_field(name="Thời Gian", value=f"⏳ {runtime}", inline=True); await self.status_message.edit(embed=embed)
            elif status == "stopped": self.stop(); embed.title, embed.color = "🛑 Phiên Spam Đã Dừng", discord.Color.dark_grey(); embed.clear_fields(); embed.add_field(name="Tổng Thành Công", value=f"✅ {stats['success']}").add_field(name="Tổng Thất Bại", value=f"❌ {stats['failed']}"); await self.status_message.edit(content="Hoàn tất!", embed=embed, view=None)
        except discord.errors.NotFound: self.stop()
        except Exception: self.stop()
    @ui.button(label='Dừng Spam', style=discord.ButtonStyle.red, emoji='🛑')
    async def stop_spam(self, interaction: discord.Interaction, button: ui.Button):
        if spam_manager.stop_spam_session(interaction.user.id): button.disabled = True; await interaction.response.edit_message(content="✅ Đã gửi yêu cầu dừng! Luồng sẽ kết thúc sau ít giây.", view=self)
        else: await interaction.response.send_message("Không tìm thấy phiên spam để dừng.", ephemeral=True)

# ==============================================================================
# 4. UI VÀ LOGIC MỚI CHO CHỨC NĂNG LIÊN QUÂN (/start1)
# ==============================================================================
class AOVKeyEntryModal(ui.Modal, title='🔑 Nhập Key Liên Quân'):
    key_input = ui.TextInput(label='License Key', placeholder='Dán key AOV của bạn vào đây...')
    def __init__(self, original_message: discord.WebhookMessage):
        super().__init__(timeout=None)
        self.original_message = original_message

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        key_value = self.key_input.value
        result = aov_keygen.validate_key(key_value)
        if result.get("valid"):
            account = account_manager.get_random_account()
            if account:
                success_embed = discord.Embed(title="✅ Lấy Tài Khoản Thành Công", description=f"Cảm ơn bạn đã sử dụng key `{key_value}`.", color=discord.Color.green())
                success_embed.add_field(name="🔐 Tài khoản", value=f"```{account['username']}```", inline=False)
                success_embed.add_field(name="🔑 Mật khẩu", value=f"```{account['password']}```", inline=False)
                success_embed.set_footer(text="Vui lòng đăng nhập bằng Garena. Không thể đổi mật khẩu.")
                await self.original_message.edit(embed=success_embed, view=None)
                await interaction.followup.send("Lấy tài khoản thành công!", ephemeral=True)
                aov_keygen.delete_key(key_value)
            else: await interaction.followup.send("❌ Đã xác thực key nhưng kho tài khoản đã hết. Vui lòng liên hệ Admin.", ephemeral=True)
        else:
            errors = {"NOT_FOUND": "Key không tồn tại.", "EXPIRED": "Key đã hết hạn.", "SUSPENDED": "Key đã bị sử dụng hoặc vô hiệu hóa."}
            await interaction.followup.send(f"❌ Lỗi: {errors.get(result.get('code'), 'Lỗi không xác định.')}", ephemeral=True)
class AOVInitialView(ui.View):
    def __init__(self, original_message: Optional[discord.WebhookMessage]=None):
        super().__init__(timeout=300); self.original_message = original_message
    @ui.button(label='Nhập Key Liên Quân', style=discord.ButtonStyle.success, emoji='🔑')
    async def enter_aov_key(self, interaction: discord.Interaction, button: ui.Button):
        if not self.original_message: return await interaction.response.send_message("Lỗi: Phiên đã hết hạn, vui lòng dùng lại lệnh /start1.", ephemeral=True)
        await interaction.response.send_modal(AOVKeyEntryModal(original_message=self.original_message))
    async def on_timeout(self):
        try:
            if self.original_message and self.original_message.embeds: embed = self.original_message.embeds[0]; embed.description = "Phiên làm việc đã hết hạn. Vui lòng dùng lệnh `/start1` để bắt đầu lại."; embed.color = discord.Color.dark_grey(); await self.original_message.edit(embed=embed, view=None)
        except: pass

# ==============================================================================
# 5. LỆNH & EVENTS
# ==============================================================================
@client.event
async def on_ready(): await tree.sync(); print(f'--- [READY] Bot đã đăng nhập: {client.user} ---')
@tree.command(name="start", description="Bắt đầu một phiên spam Locket (yêu cầu key).")
@app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
async def start(interaction: discord.Interaction):
    if interaction.channel.id != SPAM_CHANNEL_ID: return await interaction.response.send_message(f"Lệnh chỉ dùng được trong <#{SPAM_CHANNEL_ID}>.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(title="🌟 GemLogin Spam Locket Tool 🌟", description="Chào mừng bạn! Vui lòng nhập License Key Locket để tiếp tục.", color=discord.Color.blurple())
    embed.add_field(name="Cách có Key?", value=f"Liên hệ Admin <@{ADMIN_USER_ID}> để được cấp.", inline=False)
    message = await interaction.followup.send(embed=embed, ephemeral=True, wait=True)
    await message.edit(view=InitialView(original_message=message))
@tree.command(name="start1", description="Nhận một tài khoản Liên Quân (yêu cầu key).")
@app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
async def start1(interaction: discord.Interaction):
    if interaction.channel.id != AOV_CHANNEL_ID: return await interaction.response.send_message(f"Lệnh này chỉ dùng được trong <#{AOV_CHANNEL_ID}>.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(title="🎁 Nhận Tài Khoản Liên Quân 🎁", description="Chức năng này yêu cầu một License Key để sử dụng. Mỗi key chỉ dùng được một lần.", color=discord.Color.gold())
    embed.add_field(name="Cách có Key?", value=f"Liên hệ Admin <@{ADMIN_USER_ID}> để được cấp.", inline=False)
    message = await interaction.followup.send(embed=embed, ephemeral=True, wait=True)
    await message.edit(view=AOVInitialView(original_message=message))

# --- Lệnh Admin cho Locket (/genkey, /listkeys, /delkey) ---
@tree.command(name="genkey", description="[Admin] Tạo một key Locket mới.")
@app_commands.describe(user="Người dùng nhận key.", days="Số ngày hiệu lực.")
async def genkey(interaction: discord.Interaction, user: discord.User, days: int):
    if str(interaction.user.id) != ADMIN_USER_ID: return await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    key_info = keygen.add_key(days, user.id, interaction.user.id)
    await interaction.followup.send(f"✅ **Đã tạo key Locket!**\n\n**Người dùng:** {user.mention}\n**Hiệu lực:** {days} ngày\n**Key:** `{key_info['key']}`", ephemeral=True)
@tree.command(name="listkeys", description="[Admin] Xem danh sách các key Locket đang hoạt động.")
async def listkeys(interaction: discord.Interaction):
    if str(interaction.user.id) != ADMIN_USER_ID: return await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    keys = {k: v for k, v in keygen.load_keys().items() if v.get('is_active') and datetime.datetime.fromisoformat(v['expires_at']) > datetime.datetime.now(datetime.timezone.utc)}
    if not keys: return await interaction.followup.send("Không có key Locket nào hoạt động.", ephemeral=True)
    desc = "```" + "Key (Locket)      | User ID             | Thời Gian Còn Lại\n" + "------------------|---------------------|--------------------\n"
    for k, v in list(keys.items())[:20]: desc += f"{k:<17} | {v.get('user_id', 'N/A'):<19} | {format_time_left(v['expires_at'])}\n"
    if len(keys) > 20: desc += f"\n... và {len(keys) - 20} key khác."
    await interaction.followup.send(embed=discord.Embed(title=f"🔑 {len(keys)} Keys Locket đang hoạt động", description=desc + "```"), ephemeral=True)
@tree.command(name="delkey", description="[Admin] Vô hiệu hóa một key Locket.")
@app_commands.describe(key="Key Locket cần xóa.")
async def delkey(interaction: discord.Interaction, key: str):
    if str(interaction.user.id) != ADMIN_USER_ID: return await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True)
    await interaction.response.defer(ephemeral=True);
    if keygen.delete_key(key): await interaction.followup.send(f"✅ Key Locket `{key}` đã được vô hiệu hóa.", ephemeral=True)
    else: await interaction.followup.send(f"❌ Không tìm thấy key Locket `{key}`.", ephemeral=True)

# --- Lệnh Admin MỚI cho Liên Quân (/keygen1, /listkeys1, /delkey1) ---
@tree.command(name="keygen1", description="[Admin] Tạo một key Liên Quân mới.")
@app_commands.describe(user="Người dùng nhận key.", days="Số ngày hiệu lực (key sẽ bị hủy sau khi dùng).")
async def genkey1(interaction: discord.Interaction, user: discord.User, days: int = 1):
    if str(interaction.user.id) != ADMIN_USER_ID: return await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    key_info = aov_keygen.add_key(days, user.id, interaction.user.id)
    await interaction.followup.send(f"✅ **Đã tạo key Liên Quân!**\n\n**Người dùng:** {user.mention}\n**Hiệu lực:** {days} ngày\n**Key:** `{key_info['key']}`", ephemeral=True)
@tree.command(name="listkeys1", description="[Admin] Xem danh sách các key Liên Quân chưa sử dụng.")
async def listkeys1(interaction: discord.Interaction):
    if str(interaction.user.id) != ADMIN_USER_ID: return await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    keys = {k: v for k, v in aov_keygen.load_keys().items() if v.get('is_active') and datetime.datetime.fromisoformat(v['expires_at']) > datetime.datetime.now(datetime.timezone.utc)}
    if not keys: return await interaction.followup.send("Không có key Liên Quân nào hoạt động.", ephemeral=True)
    desc = "```" + "Key (AOV)         | User ID             | Thời Gian Còn Lại\n" + "------------------|---------------------|--------------------\n"
    for k, v in list(keys.items())[:20]: desc += f"{k:<17} | {v.get('user_id', 'N/A'):<19} | {format_time_left(v['expires_at'])}\n"
    if len(keys) > 20: desc += f"\n... và {len(keys) - 20} key khác."
    await interaction.followup.send(embed=discord.Embed(title=f"🔑 {len(keys)} Keys Liên Quân đang hoạt động", description=desc + "```"), ephemeral=True)
@tree.command(name="delkey1", description="[Admin] Vô hiệu hóa một key Liên Quân.")
@app_commands.describe(key="Key Liên Quân cần xóa.")
async def delkey1(interaction: discord.Interaction, key: str):
    if str(interaction.user.id) != ADMIN_USER_ID: return await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    if aov_keygen.delete_key(key): await interaction.followup.send(f"✅ Key Liên Quân `{key}` đã được vô hiệu hóa.", ephemeral=True)
    else: await interaction.followup.send(f"❌ Không tìm thấy key Liên Quân `{key}`.", ephemeral=True)

# ==============================================================================
# 6. ERROR HANDLER THÔNG MINH
# ==============================================================================
async def handle_error_response(interaction: discord.Interaction, message: str):
    """Gửi tin nhắn lỗi một cách an toàn, dùng followup nếu cần."""
    if interaction.response.is_done():
        # Nếu đã defer() hoặc trả lời, dùng followup
        await interaction.followup.send(message, ephemeral=True)
    else:
        # Nếu chưa, dùng response ban đầu
        await interaction.response.send_message(message, ephemeral=True)

# Đăng ký handler cho tất cả các lệnh
@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await handle_error_response(interaction, f"Bạn đang dùng lệnh quá nhanh! Vui lòng chờ {error.retry_after:.1f} giây.")
    elif isinstance(error, app_commands.MissingPermissions) or isinstance(error, app_commands.CheckFailure):
        await handle_error_response(interaction, "❌ Bạn không có quyền hoặc không thể thực hiện lệnh này tại đây.")
    elif isinstance(error, app_commands.CommandInvokeError):
        # Đây là các lỗi xảy ra bên trong code của lệnh
        print(f"Lỗi CommandInvokeError trong lệnh '{interaction.command.name}': {error.original}")
        await handle_error_response(interaction, "🙁 Đã có lỗi xảy ra trong quá trình xử lý lệnh. Vui lòng thử lại sau.")
    else:
        # Các lỗi khác không lường trước
        print(f"Lỗi không xác định: {error}")

# bot.py (Final Fix for Unknown Message, No Images)
import discord
from discord import app_commands, ui
import os
import re 
import datetime
import time
import asyncio
from typing import Optional
from flask import Flask

# Import các module tùy chỉnh
from spammer import SpamManager
import keygen
import aov_keygen 
import account_manager
import cooldown_manager 

print("--- [LAUNCH] Bot đang khởi chạy... ---")

# ==============================================================================
# ✨ CONFIG GIAO DIỆN AOV - "Professional & Stable" Edition ✨
# ==============================================================================
class AOV_UI_CONFIG:
    COLOR_BRAND = 0x3498db
    COLOR_SUCCESS = 0x2ecc71
    COLOR_ERROR = 0xe74c3c
    COLOR_WAITING = 0xf39c12
    EMOJI_KEY = "🔑"
    EMOJI_USER = "👤"
    EMOJI_PASSWORD = "🔑" 
    EMOJI_CHANGE = "🔄"
    EMOJI_COPY = "📋"
    EMOJI_GEAR = "⚙️"

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

if not DISCORD_TOKEN or not ADMIN_USER_ID: print("!!! [CRITICAL] Thiếu DISCORD_TOKEN hoặc ADMIN_USER_ID.")

spam_manager = SpamManager()
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ==============================================================================
# 2. HELPER & UI CHUNG (Giữ nguyên)
# ...
def format_time_left(expires_at_str):
    try:
        expires_dt = datetime.datetime.fromisoformat(expires_at_str.replace("Z", "+00:00")); delta = expires_dt - datetime.datetime.now(datetime.timezone.utc)
        if delta.total_seconds() <= 0: return "Hết hạn"
        d, h, m = delta.days, delta.seconds // 3600, (delta.seconds % 3600) // 60
        if d > 0: return f"{d} ngày {h} giờ"
        if h > 0: return f"{h} giờ {m} phút"
        return f"{m} phút"
    except: return "Không xác định"
# ==============================================================================
# 3. UI VÀ LOGIC CHO CHỨC NĂNG SPAM LOCKET (/start) (Giữ nguyên)
# ...
class KeyEntryModal(ui.Modal, title='🔑 Nhập License Key Locket'):
    key_input = ui.TextInput(label='License Key', placeholder='Dán key của bạn vào đây...')
    def __init__(self, original_message: discord.WebhookMessage): super().__init__(timeout=None); self.original_message = original_message
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        result = keygen.validate_key(self.key_input.value)
        if result.get("valid"): key_info = result['key_info']; embed = discord.Embed(title="✅ Key Hợp Lệ - Bảng Điều Khiển Spam", color=discord.Color.green()); await self.original_message.edit(embed=embed, view=SpamConfigView(self.key_input.value, key_info, self.original_message)); await interaction.followup.send("Kích hoạt thành công! Vui lòng cấu hình phiên spam.", ephemeral=True)
        else: errors = {"NOT_FOUND": "Key không tồn tại.", "EXPIRED": "Key đã hết hạn.", "SUSPENDED": "Key đã bị tạm ngưng."}; await interaction.followup.send(f"❌ Lỗi: {errors.get(result.get('code'), 'Lỗi không xác định.')}", ephemeral=True)
class SpamSetupModal(ui.Modal, title='🛠️ Cấu hình phiên Spam'):
    target_input = ui.TextInput(label='🎯 Locket Target (Username/Link)', placeholder='Ví dụ: mylocketuser hoặc link invite', required=True)
    name_input = ui.TextInput(label='👤 Custom Username (Tối đa 20 ký tự)', placeholder='Để trống để dùng tên mặc định', required=False, max_length=20)
    emoji_input = ui.TextInput(label='🎨 Sử dụng Emoji ngẫu nhiên? (y/n)', placeholder='y (có) hoặc n (không) - mặc định là có', required=False, max_length=1)
    def __init__(self, key: str, original_message: discord.WebhookMessage): super().__init__(timeout=None); self.key, self.original_message = key, original_message
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        target = self.target_input.value; custom_name = self.name_input.value if self.name_input.value.strip() else "zLocket Tool"; use_emojis = self.emoji_input.value.lower().strip() != 'n'; await self.original_message.delete()
        status_view = ActiveSpamView(); status_embed = discord.Embed(title="🔄 Khởi động phiên spam...", description=f"**Target:** `{target}`\n**Username:** `{custom_name}`\n**Emoji:** {'Bật' if use_emojis else 'Tắt'}", color=discord.Color.orange()); status_message = await interaction.followup.send(embed=status_embed, ephemeral=True, view=status_view, wait=True)
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
        try:
            embed = self.status_message.embeds[0]
            if status == "error": embed.title="❌ Lỗi nghiêm trọng"; embed.description = message_text; embed.color=discord.Color.red(); await self.status_message.edit(embed=embed, view=None); self.stop(); return
            if status == "running": embed.title = "🚀 Trạng thái Spam: Đang Chạy"; embed.color = discord.Color.blue(); embed.clear_fields(); embed.add_field(name="Thành Công", value=f"✅ {stats['success']}", inline=True); embed.add_field(name="Thất Bại", value=f"❌ {stats['failed']}", inline=True); runtime = datetime.timedelta(seconds=int(time.time() - stats['start_time'])); embed.add_field(name="Thời Gian", value=f"⏳ {runtime}", inline=True); await self.status_message.edit(embed=embed)
            elif status == "stopped": self.stop(); embed.title, embed.color = "🛑 Phiên Spam Đã Dừng", discord.Color.dark_grey(); embed.clear_fields(); embed.add_field(name="Tổng Thành Công", value=f"✅ {stats['success']}").add_field(name="Tổng Thất Bại", value=f"❌ {stats['failed']}"); await self.status_message.edit(content="Hoàn tất!", embed=embed, view=None)
        except discord.errors.NotFound: self.stop()
        except Exception: self.stop()
    @ui.button(label='Dừng Spam', style=discord.ButtonStyle.red, emoji='🛑')
    async def stop_spam(self, interaction: discord.Interaction, button: ui.Button):
        try:
            if spam_manager.stop_spam_session(interaction.user.id): button.disabled = True; await interaction.response.edit_message(content="✅ Đã gửi yêu cầu dừng! Luồng sẽ kết thúc sau ít giây.", view=self)
            else: await interaction.response.send_message("Không tìm thấy phiên spam để dừng.", ephemeral=True)
        except discord.errors.NotFound: pass

# ==============================================================================
# 4. UI VÀ LOGIC MỚI CHO CHỨC NĂNG LIÊN QUÂN (/start1) - Final Fix
# ==============================================================================

class AOVAccountDashboardView(ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Persistent View
        self.current_username = "" # Dùng để loại trừ
        
    def set_current_account(self, username: str):
        self.current_username = username

    @ui.button(label='Sao chép Tên TK', style=discord.ButtonStyle.secondary, emoji=AOV_UI_CONFIG.EMOJI_COPY)
    async def copy_username_callback(self, interaction: discord.Interaction, button: ui.Button):
        # Lấy username từ field của tin nhắn gốc mà nút được đính kèm
        username = "Không tìm thấy"
        embed = interaction.message.embeds[0]
        for field in embed.fields:
            if "Tài Khoản" in field.name:
                username = field.value.strip("`")
                break
        await interaction.response.send_message(f"```{username}```", ephemeral=True)

    @ui.button(label='Sao chép Mật Khẩu', style=discord.ButtonStyle.secondary, emoji=AOV_UI_CONFIG.EMOJI_COPY)
    async def copy_password_callback(self, interaction: discord.Interaction, button: ui.Button):
        # Lấy password từ field của tin nhắn gốc mà nút được đính kèm
        password = "Không tìm thấy"
        embed = interaction.message.embeds[0]
        for field in embed.fields:
            if "Mật Khẩu" in field.name:
                password = field.value.strip("`")
                break
        await interaction.response.send_message(f"```{password}```", ephemeral=True)
    
    @ui.button(label='Đổi Tài Khoản', style=discord.ButtonStyle.success, emoji=AOV_UI_CONFIG.EMOJI_CHANGE, row=1)
    async def change_account(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        cooldown_status = cooldown_manager.check_and_use_change(interaction.user.id)
        if not cooldown_status["allowed"]:
            retry_seconds = cooldown_status.get('retry_after', 3600)
            minutes, seconds = divmod(int(retry_seconds), 60)
            return await interaction.followup.send(
                f"❌ Bạn đã hết lượt đổi. Vui lòng thử lại sau **{minutes} phút {seconds} giây**.", ephemeral=True
            )
        
        # Lấy username cũ từ View, được gán lúc ban đầu
        old_username = self.current_username
        new_account = account_manager.get_random_account(exclude_username=old_username)
        
        if not new_account:
            return await interaction.followup.send("Rất tiếc, kho đã hết tài khoản để đổi.", ephemeral=True)

        # Cập nhật lại username hiện tại trong View
        self.current_username = new_account["username"]
        
        # **Giải pháp:** Gửi một tin nhắn mới hoàn toàn
        embed = discord.Embed(
            title="✅ Tài khoản đã được làm mới",
            description=f"Dưới đây là thông tin tài khoản mới của bạn, **{interaction.user.display_name}**.",
            color=AOV_UI_CONFIG.COLOR_SUCCESS
        )
        embed.set_author(name="GemLogin | Hệ thống Cung cấp Tài khoản", icon_url=client.user.display_avatar.url)
        embed.add_field(name=f"{AOV_UI_CONFIG.EMOJI_USER} Tài Khoản", value=f"```{new_account['username']}```", inline=True)
        embed.add_field(name=f"{AOV_UI_CONFIG.EMOJI_PASSWORD} Mật Khẩu", value=f"```{new_account['password']}```", inline=True)
        embed.set_footer(text=f"Tin nhắn này là tạm thời.")
        
        # Gửi tin nhắn mới này cho người dùng. Cách này luôn hoạt động.
        await interaction.followup.send(embed=embed, ephemeral=True, view=self)

class AOVKeyEntryModal(ui.Modal, title='Xác thực License Key'):
    key_input = ui.TextInput(label='License Key', placeholder='Dán key của bạn vào đây...')
    def __init__(self, original_message: discord.WebhookMessage): 
        super().__init__(timeout=None)
        self.original_message = original_message
        
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        key_value = self.key_input.value
        
        processing_embed = discord.Embed(
            description=f"{AOV_UI_CONFIG.EMOJI_GEAR} Đang xử lý yêu cầu của bạn...", 
            color=AOV_UI_CONFIG.COLOR_WAITING
        )
        # Sửa tin nhắn tạm thời của lệnh /start1
        await interaction.edit_original_response(embed=processing_embed, view=None)
        
        result = aov_keygen.validate_key(key_value)
        if not result.get("valid"):
            errors = {"NOT_FOUND": "Key không tồn tại.", "EXPIRED": "Key đã hết hạn.", "SUSPENDED": "Key đã bị sử dụng hoặc vô hiệu hóa."}
            error_embed = discord.Embed(
                title="❌ Xác Thực Thất Bại", 
                description=f"**Lý do:** {errors.get(result.get('code'), 'Lỗi không xác định.')}", 
                color=AOV_UI_CONFIG.COLOR_ERROR
            )
            return await interaction.edit_original_response(embed=error_embed)

        account = account_manager.get_random_account()
        if not account:
            error_embed = discord.Embed(
                title="❌ Kho tài khoản trống", 
                description="Key hợp lệ nhưng kho tài khoản đã hết. Vui lòng liên hệ Admin.", 
                color=AOV_UI_CONFIG.COLOR_ERROR
            )
            return await interaction.edit_original_response(embed=error_embed)
            
        aov_keygen.delete_key(key_value)
        
        # View này sẽ được đính kèm với tin nhắn kết quả
        dashboard_view = AOVAccountDashboardView()
        dashboard_view.set_current_account(account["username"]) # Gán username ban đầu

        success_embed = discord.Embed(
            title="✅ Kích hoạt thành công!",
            description=f"Key `{key_value}` đã được kích hoạt cho **{interaction.user.display_name}**.",
            color=AOV_UI_CONFIG.COLOR_SUCCESS
        )
        success_embed.set_author(name="GemLogin | Bảng Điều Khiển Tài Khoản", icon_url=client.user.display_avatar.url)
        success_embed.add_field(name=f"{AOV_UI_CONFIG.EMOJI_USER} Tài Khoản", value=f"```{account['username']}```", inline=True)
        success_embed.add_field(name=f"{AOV_UI_CONFIG.EMOJI_PASSWORD} Mật Khẩu", value=f"```{account['password']}```", inline=True)
        success_embed.set_footer(text="Sử dụng các nút bên dưới để quản lý tài khoản.")

        await interaction.edit_original_response(embed=success_embed, view=dashboard_view)
        
class AOVInitialView(ui.View):
    def __init__(self, original_message: Optional[discord.Interaction]=None): 
        super().__init__(timeout=300)
        # Sửa: lưu trữ interaction thay vì message
        self.original_interaction = original_message
        
    @ui.button(label='Kích Hoạt License Key', style=discord.ButtonStyle.primary, emoji=AOV_UI_CONFIG.EMOJI_KEY)
    async def enter_aov_key(self, interaction: discord.Interaction, button: ui.Button):
        # Sử dụng interaction.followup.send thay vì message.edit
        await interaction.response.send_modal(AOVKeyEntryModal(interaction))
        
    async def on_timeout(self):
        try:
            embed = discord.Embed(
                title="Hệ thống Cung cấp Tài khoản GemLogin",
                description="Phiên làm việc đã hết hạn. Vui lòng dùng lệnh `/start1` để bắt đầu lại.",
                color=discord.Color.dark_grey()
            )
            await self.original_interaction.edit_original_response(embed=embed, view=None)
        except: pass

# ==============================================================================
# 5. LỆNH & EVENTS
# ==============================================================================
@client.event
async def on_ready():
    client.add_view(AOVAccountDashboardView()) 
    await tree.sync()
    account_manager.load_accounts_into_cache()
    print(f'--- [READY] Bot đã đăng nhập: {client.user} ---')

@tree.command(name="start1", description="Nhận một tài khoản Liên Quân (yêu cầu key).")
@app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
async def start1(interaction: discord.Interaction):
    if interaction.channel.id != AOV_CHANNEL_ID: 
        return await handle_error_response(interaction, f"Lệnh này chỉ dùng được trong <#{AOV_CHANNEL_ID}>.")
    
    await interaction.response.defer(ephemeral=True)
    
    embed = discord.Embed(
        title="Hệ thống Cung cấp Tài khoản GemLogin", 
        description=(
            f"Chào mừng {interaction.user.mention}!\n\n"
            f"> Để nhận tài khoản, bạn cần có một **License Key** hợp lệ.\n"
            f"> Liên hệ Admin <@{ADMIN_USER_ID}> để được cấp key."
        ),
        color=AOV_UI_CONFIG.COLOR_BRAND
    )
    embed.set_footer(text="An toàn - Nhanh chóng - Tiện lợi")

    # Sửa: lưu trữ interaction để dùng sau này
    await interaction.followup.send(embed=embed, ephemeral=True, view=AOVInitialView(interaction))

# ... các lệnh còn lại giữ nguyên
async def handle_error_response(interaction: discord.Interaction, message: str):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except (discord.errors.NotFound, discord.errors.HTTPException) as e:
        print(f"Không thể gửi tin nhắn lỗi cho một tương tác đã mất: {e}")
        pass
@tree.command(name="start", description="Bắt đầu một phiên spam Locket (yêu cầu key).")
@app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
async def start(interaction: discord.Interaction):
    if interaction.channel.id != SPAM_CHANNEL_ID: return await handle_error_response(interaction, f"Lệnh chỉ dùng được trong <#{SPAM_CHANNEL_ID}>.")
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(title="🌟 GemLogin Spam Locket Tool 🌟", description="Chào mừng bạn! Vui lòng nhập License Key Locket để tiếp tục.", color=discord.Color.blurple())
    embed.add_field(name="Cách có Key?", value=f"Liên hệ Admin <@{ADMIN_USER_ID}> để được cấp.", inline=False)
    message = await interaction.followup.send(embed=embed, ephemeral=True, wait=True)
    await message.edit(view=InitialView(original_message=message))
async def admin_command_wrapper(interaction: discord.Interaction, admin_logic):
    if str(interaction.user.id) != ADMIN_USER_ID: return await handle_error_response(interaction, "❌ Bạn không có quyền.")
    await interaction.response.defer(ephemeral=True)
    await admin_logic(interaction)
@tree.command(name="genkey", description="[Admin] Tạo một key Locket mới.")
@app_commands.describe(user="Người dùng nhận key.", days="Số ngày hiệu lực.")
async def genkey(interaction: discord.Interaction, user: discord.User, days: int):
    async def logic(inter): key_info = keygen.add_key(days, user.id, inter.user.id); await inter.followup.send(f"✅ **Đã tạo key Locket!**\n\n**Người dùng:** {user.mention}\n**Hiệu lực:** {days} ngày\n**Key:** `{key_info['key']}`", ephemeral=True)
    await admin_command_wrapper(interaction, logic)
@tree.command(name="listkeys", description="[Admin] Xem danh sách các key Locket đang hoạt động.")
async def listkeys(interaction: discord.Interaction):
    async def logic(inter):
        keys = {k: v for k, v in keygen.load_keys().items() if v.get('is_active') and datetime.datetime.fromisoformat(v['expires_at']) > datetime.datetime.now(datetime.timezone.utc)}
        if not keys: return await inter.followup.send("Không có key Locket nào hoạt động.", ephemeral=True)
        desc = "```" + "Key (Locket)      | User ID             | Thời Gian Còn Lại\n" + "------------------|---------------------|--------------------\n"
        for k, v in list(keys.items())[:20]: desc += f"{k:<17} | {v.get('user_id', 'N/A'):<19} | {format_time_left(v['expires_at'])}\n"
        if len(keys) > 20: desc += f"\n... và {len(keys) - 20} key khác."
        await inter.followup.send(embed=discord.Embed(title=f"🔑 {len(keys)} Keys Locket đang hoạt động", description=desc + "```"), ephemeral=True)
    await admin_command_wrapper(interaction, logic)
@tree.command(name="delkey", description="[Admin] Vô hiệu hóa một key Locket.")
@app_commands.describe(key="Key Locket cần xóa.")
async def delkey(interaction: discord.Interaction, key: str):
    async def logic(inter):
        if keygen.delete_key(key): await inter.followup.send(f"✅ Key Locket `{key}` đã được vô hiệu hóa.", ephemeral=True)
        else: await inter.followup.send(f"❌ Không tìm thấy key Locket `{key}`.", ephemeral=True)
    await admin_command_wrapper(interaction, logic)
@tree.command(name="keygen1", description="[Admin] Tạo một key Liên Quân mới.")
@app_commands.describe(user="Người dùng nhận key.", days="Số ngày hiệu lực (key sẽ bị hủy sau khi dùng).")
async def genkey1(interaction: discord.Interaction, user: discord.User, days: int = 1):
    async def logic(inter): key_info = aov_keygen.add_key(days, user.id, inter.user.id); await inter.followup.send(f"✅ **Đã tạo key Liên Quân!**\n\n**Người dùng:** {user.mention}\n**Hiệu lực:** {days} ngày\n**Key:** `{key_info['key']}`", ephemeral=True)
    await admin_command_wrapper(interaction, logic)
@tree.command(name="listkeys1", description="[Admin] Xem danh sách các key Liên Quân chưa sử dụng.")
async def listkeys1(interaction: discord.Interaction):
    async def logic(inter):
        keys = {k: v for k, v in aov_keygen.load_keys().items() if v.get('is_active') and datetime.datetime.fromisoformat(v['expires_at']) > datetime.datetime.now(datetime.timezone.utc)}
        if not keys: return await inter.followup.send("Không có key Liên Quân nào hoạt động.", ephemeral=True)
        desc = "```" + "Key (AOV)         | User ID             | Thời Gian Còn Lại\n" + "------------------|---------------------|--------------------\n"
        for k, v in list(keys.items())[:20]: desc += f"{k:<17} | {v.get('user_id', 'N/A'):<19} | {format_time_left(v['expires_at'])}\n"
        if len(keys) > 20: desc += f"\n... và {len(keys) - 20} key khác."
        await inter.followup.send(embed=discord.Embed(title=f"🔑 {len(keys)} Keys Liên Quân đang hoạt động", description=desc + "```"), ephemeral=True)
    await admin_command_wrapper(interaction, logic)
@tree.command(name="delkey1", description="[Admin] Vô hiệu hóa một key Liên Quân.")
@app_commands.describe(key="Key Liên Quân cần xóa.")
async def delkey1(interaction: discord.Interaction, key: str):
    async def logic(inter):
        if aov_keygen.delete_key(key): await inter.followup.send(f"✅ Key Liên Quân `{key}` đã được vô hiệu hóa.", ephemeral=True)
        else: await inter.followup.send(f"❌ Không tìm thấy key Liên Quân `{key}`.", ephemeral=True)
    await admin_command_wrapper(interaction, logic)
@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await handle_error_response(interaction, f"Bạn đang dùng lệnh quá nhanh! Vui lòng chờ {error.retry_after:.1f} giây.")
    elif isinstance(error, app_commands.CheckFailure):
        await handle_error_response(interaction, "❌ Bạn không thể thực hiện lệnh này tại đây.")
    elif isinstance(error, app_commands.CommandInvokeError):
        print(f"Lỗi CommandInvokeError trong lệnh '{interaction.command.name}': {error.original}")
        await handle_error_response(interaction, "🙁 Đã có lỗi xảy ra. Vui lòng thử lại sau ít phút.")
    else:
        print(f"Lỗi không xác định: {type(error)} - {error}")

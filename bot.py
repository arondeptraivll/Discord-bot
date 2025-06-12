# bot.py (Phiên bản Async triệt để)
import discord
from discord import app_commands, ui
import os
import datetime
import time
import asyncio
from typing import Optional
from flask import Flask

from spammer import SpamManager
import keygen, aov_keygen, account_manager # Đảm bảo aov_keygen đã là bản async

# ... (Mục 1, 2, 3 không thay đổi) ...

# ==============================================================================
# 1. CÀI ĐẶT
# ==============================================================================
app = Flask('')
@app.route('/')
def home():
    return "Bot is alive and running!"
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN'); ADMIN_USER_ID = os.environ.get('ADMIN_USER_ID')
SPAM_CHANNEL_ID = int(os.environ.get('SPAM_CHANNEL_ID', 1381799563488399452)); AOV_CHANNEL_ID = 1382203422094266390
if not DISCORD_TOKEN or not ADMIN_USER_ID: print("!!! [CRITICAL] Thiếu DISCORD_TOKEN hoặc ADMIN_USER_ID.")
spam_manager = SpamManager(); intents = discord.Intents.default(); client = discord.Client(intents=intents); tree = app_commands.CommandTree(client)

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
        if m > 0: return f"{m} phút"
        return f"{int(delta.total_seconds())} giây"
    except: return "Không xác định"
    
# ==============================================================================
# 3. UI VÀ LOGIC CHO CHỨC NĂNG SPAM LOCKET (/start)
# (Để an toàn nhất, phần này cũng nên được chuyển sang async)
# Tạm thời để nguyên, vì lỗi chủ yếu ở phần AOV
# ...
class KeyEntryModal(ui.Modal, title='🔑 Nhập License Key Locket'):
    key_input = ui.TextInput(label='License Key', placeholder='Dán key của bạn vào đây...')
    def __init__(self, original_message: discord.WebhookMessage): super().__init__(timeout=None); self.original_message = original_message
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        # TODO: Chuyển keygen.py sang async và await ở đây
        result = spam_manager.validate_license(self.key_input.value)
        if result.get("valid"): key_info = result['key_info']; embed = discord.Embed(title="✅ Key Hợp Lệ - Bảng Điều Khiển Spam", color=discord.Color.green()); await self.original_message.edit(embed=embed, view=SpamConfigView(self.key_input.value, key_info, self.original_message)); await interaction.followup.send("Kích hoạt thành công!", ephemeral=True)
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
# 4. UI VÀ LOGIC MỚI CHO CHỨC NĂNG LIÊN QUÂN (/start1) - [ASYNC]
# ==============================================================================
class AOVAccountView(ui.View):
    def __init__(self, key: str, initial_attempts: int):
        super().__init__(timeout=7200)
        self.key = key
        self.message = None
        self.change_account_button.label = f"Đổi tài khoản (Còn lại {initial_attempts} lần)"
        if initial_attempts <= 0:
            self.change_account_button.disabled = True
            self.change_account_button.label = "Hết lượt đổi, vui lòng chờ"
    
    def set_message(self, message: discord.WebhookMessage):
        self.message = message

    @ui.button(label="Đổi tài khoản", style=discord.ButtonStyle.secondary, emoji="🔁", custom_id="change_aov_account")
    async def change_account_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        try:
            key_info = await aov_keygen.get_key_info(self.key)
            if not key_info:
                button.disabled = True; button.label = "Key không hợp lệ"
                await self.message.edit(content="❌ **Lỗi:** Key của bạn không còn hợp lệ hoặc đã bị xóa.", embed=None, view=self)
                return self.stop()
            
            cooldown_ts_str = key_info.get('cooldown_until')
            if cooldown_ts_str:
                cooldown_dt = datetime.datetime.fromisoformat(cooldown_ts_str.replace("Z", "+00:00"))
                if cooldown_dt > datetime.datetime.now(datetime.timezone.utc):
                    time_left = format_time_left(cooldown_dt.isoformat())
                    button.disabled = True; button.label = f"Chờ {time_left}"
                    await self.message.edit(view=self)
                    return await interaction.followup.send(f"⏳ Bạn đang trong thời gian chờ. Vui lòng thử lại sau **{time_left}**.", ephemeral=True)
                else:
                    key_info['change_attempts'] = 3
                    key_info['cooldown_until'] = None
                    await aov_keygen.update_key_state(self.key, {"change_attempts": 3, "cooldown_until": None})

            attempts_left = key_info.get('change_attempts', 0)
            if attempts_left <= 0:
                button.disabled = True; button.label = "Hết lượt, vui lòng chờ"
                await self.message.edit(view=self)
                return await interaction.followup.send("❌ Bạn đã hết lượt đổi.", ephemeral=True)

            new_account = account_manager.get_random_account()
            if not new_account:
                return await interaction.followup.send("❌ Kho tài khoản tạm thời đã hết.", ephemeral=True)

            embed = self.message.embeds[0]; embed.title = "✅ Đổi Tài Khoản Thành Công"; embed.clear_fields()
            embed.add_field(name="🔐 Tài khoản", value=f"```{new_account['username']}```", inline=False)
            embed.add_field(name="🔑 Mật khẩu", value=f"```{new_account['password']}```", inline=False)
            
            new_attempts = attempts_left - 1
            update_payload = {"change_attempts": new_attempts}
            if new_attempts == 0:
                cooldown_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
                update_payload["cooldown_until"] = cooldown_time.isoformat()
                button.label = f"Hết lượt (Chờ 1 giờ)"; button.disabled = True
            else:
                button.label = f"Đổi tài khoản (Còn lại {new_attempts} lần)"; button.disabled = False

            await aov_keygen.update_key_state(self.key, update_payload)
            await self.message.edit(embed=embed, view=self)

        except Exception as e:
            print(f"!!! [ERROR] Lỗi trong change_account_button: {e}")
            await interaction.followup.send("🙁 Lỗi, vui lòng thử lại sau.", ephemeral=True)

    async def on_timeout(self):
        try:
            self.change_account_button.disabled = True
            await self.message.edit(view=self)
        except (discord.errors.NotFound, AttributeError):
            pass

class AOVKeyEntryModal(ui.Modal, title='🔑 Nhập Key Liên Quân'):
    key_input = ui.TextInput(label='License Key', placeholder='Dán key AOV của bạn vào đây...')
    def __init__(self, original_message: discord.WebhookMessage): super().__init__(timeout=None); self.original_message = original_message

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        key_value = self.key_input.value
        
        result = await aov_keygen.validate_key(key_value)

        if result.get("valid"):
            key_info = result['key_info']
            cooldown_ts_str = key_info.get('cooldown_until')
            if cooldown_ts_str:
                cooldown_dt = datetime.datetime.fromisoformat(cooldown_ts_str.replace("Z", "+00:00"))
                if cooldown_dt > datetime.datetime.now(datetime.timezone.utc):
                    time_left = format_time_left(cooldown_dt.isoformat())
                    return await interaction.followup.send(f"❌ Key đang chờ. Thử lại sau {time_left}.", ephemeral=True)
            
            account = account_manager.get_random_account()
            if account:
                embed = discord.Embed(title="✅ Lấy Tài Khoản Thành Công", description=f"Key: `{key_value}`.", color=discord.Color.green())
                embed.add_field(name="🔐 Tài khoản", value=f"```{account['username']}```", inline=False)
                embed.add_field(name="🔑 Mật khẩu", value=f"```{account['password']}```", inline=False)
                embed.set_footer(text="Nếu tài khoản lỗi, hãy nhấn 'Đổi tài khoản'.")
                view = AOVAccountView(key=key_value, initial_attempts=key_info.get('change_attempts', 3))
                message = await self.original_message.edit(content=None, embed=embed, view=view)
                view.set_message(message)
                await interaction.followup.send("Thành công!", ephemeral=True)
            else:
                await interaction.followup.send("❌ Hết tài khoản trong kho.", ephemeral=True)
        else:
            errors = {"NOT_FOUND": "Key không tồn tại.", "EXPIRED": "Key đã hết hạn.", "SUSPENDED": "Key đã bị vô hiệu hóa."}
            await interaction.followup.send(f"❌ Lỗi: {errors.get(result.get('code'), 'Lỗi.')}", ephemeral=True)

class AOVInitialView(ui.View):
    def __init__(self, original_message: Optional[discord.WebhookMessage]=None):
        super().__init__(timeout=300); self.original_message = original_message
    @ui.button(label='Nhập Key Liên Quân', style=discord.ButtonStyle.success, emoji='🔑')
    async def enter_aov_key(self, interaction: discord.Interaction, button: ui.Button):
        if not self.original_message: return await interaction.response.send_message("Lỗi: Phiên đã hết hạn.", ephemeral=True)
        await interaction.response.send_modal(AOVKeyEntryModal(original_message=self.original_message))
    async def on_timeout(self):
        try:
            if self.original_message and self.original_message.embeds:
                embed = self.original_message.embeds[0]; embed.description = "Phiên đã hết hạn. Dùng `/start1` để bắt đầu lại."
                embed.color = discord.Color.dark_grey(); await self.original_message.edit(embed=embed, view=None)
        except: pass

# ... (Mục 5 và 6 không thay đổi) ...

# ==============================================================================
# 5. LỆNH & EVENTS
# ==============================================================================
@client.event
async def on_ready():
    # Sử dụng file account_manager đã có cache
    account_manager.load_accounts_into_cache()
    await tree.sync()
    print(f'--- [READY] Bot đã đăng nhập: {client.user} ---')

@tree.command(name="start", description="Bắt đầu một phiên spam Locket (yêu cầu key).")
@app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
async def start(interaction: discord.Interaction):
    if interaction.channel.id != SPAM_CHANNEL_ID: return await handle_error_response(interaction, f"Lệnh chỉ dùng được trong <#{SPAM_CHANNEL_ID}>.")
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(title="🌟 GemLogin Spam Locket Tool 🌟", description="Chào mừng bạn! Vui lòng nhập License Key Locket để tiếp tục.", color=discord.Color.blurple()); embed.add_field(name="Cách có Key?", value=f"Liên hệ Admin <@{ADMIN_USER_ID}> để được cấp.", inline=False)
    message = await interaction.followup.send(embed=embed, ephemeral=True, wait=True)
    await message.edit(view=InitialView(original_message=message))

@tree.command(name="start1", description="Nhận một tài khoản Liên Quân (yêu cầu key).")
@app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
async def start1(interaction: discord.Interaction):
    if interaction.channel.id != AOV_CHANNEL_ID: return await handle_error_response(interaction, f"Lệnh này chỉ dùng được trong <#{AOV_CHANNEL_ID}>.")
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(title="🎁 Nhận Tài Khoản Liên Quân 🎁", description="Chức năng này yêu cầu một License Key để sử dụng.", color=discord.Color.gold()); embed.add_field(name="Cách có Key?", value=f"Liên hệ Admin <@{ADMIN_USER_ID}> để được cấp.", inline=False)
    message = await interaction.followup.send(embed=embed, ephemeral=True, wait=True)
    await message.edit(view=AOVInitialView(original_message=message))

# --- LỆNH ADMIN ---
async def admin_command_wrapper(interaction: discord.Interaction, admin_logic):
    if str(interaction.user.id) != ADMIN_USER_ID: return await handle_error_response(interaction, "❌ Bạn không có quyền.")
    await interaction.response.defer(ephemeral=True)
    await admin_logic(interaction)

@tree.command(name="genkey", description="[Admin] Tạo một key Locket mới.")
@app_commands.describe(user="Người dùng nhận key.", days="Số ngày hiệu lực.")
async def genkey(interaction: discord.Interaction, user: discord.User, days: int):
    # async def logic(inter): key_info = await keygen.add_key(days, user.id, inter.user.id); await inter.followup.send(f"✅ Đã tạo key Locket! **Người dùng:** {user.mention} **Hiệu lực:** {days} ngày **Key:** `{key_info['key']}`", ephemeral=True)
    async def logic(inter): key_info = keygen.add_key(days, user.id, inter.user.id); await inter.followup.send(f"✅ Đã tạo key Locket! **Người dùng:** {user.mention} **Hiệu lực:** {days} ngày **Key:** `{key_info['key']}`", ephemeral=True)
    await admin_command_wrapper(interaction, logic)
    
@tree.command(name="listkeys", description="[Admin] Xem danh sách các key Locket đang hoạt động.")
async def listkeys(interaction: discord.Interaction):
    # async def logic(inter): keys_data = await keygen.load_keys() ...
    async def logic(inter):
        keys = {k: v for k, v in keygen.load_keys().items() if v.get('is_active') and datetime.datetime.fromisoformat(v['expires_at'].replace("Z", "+00:00")) > datetime.datetime.now(datetime.timezone.utc)}
        if not keys: return await inter.followup.send("Không có key Locket nào hoạt động.", ephemeral=True)
        desc = "```" + "Key (Locket)      | User ID             | Thời Gian Còn Lại\n" + "------------------|---------------------|--------------------\n"
        for k, v in list(keys.items())[:20]: desc += f"{k:<17} | {v.get('user_id', 'N/A'):<19} | {format_time_left(v['expires_at'])}\n"
        if len(keys) > 20: desc += f"\n... và {len(keys) - 20} key khác."
        await inter.followup.send(embed=discord.Embed(title=f"🔑 {len(keys)} Keys Locket đang hoạt động", description=desc + "```"), ephemeral=True)
    await admin_command_wrapper(interaction, logic)
    
@tree.command(name="delkey", description="[Admin] Vô hiệu hóa một key Locket.")
@app_commands.describe(key="Key Locket cần xóa.")
async def delkey(interaction: discord.Interaction, key: str):
    # async def logic(inter): res = await keygen.delete_key(key)...
    async def logic(inter):
        if keygen.delete_key(key): await inter.followup.send(f"✅ Key Locket `{key}` đã được vô hiệu hóa.", ephemeral=True)
        else: await inter.followup.send(f"❌ Không tìm thấy key Locket `{key}`.", ephemeral=True)
    await admin_command_wrapper(interaction, logic)

@tree.command(name="keygen1", description="[Admin] Tạo một key Liên Quân mới.")
@app_commands.describe(user="Người dùng nhận key.", days="Số ngày hiệu lực.")
async def genkey1(interaction: discord.Interaction, user: discord.User, days: int = 1):
    async def logic(inter): key_info = await aov_keygen.add_key(days, user.id, inter.user.id); await inter.followup.send(f"✅ **Đã tạo key LQ!**\n**Người dùng:** {user.mention}\n**Hiệu lực:** {days} ngày\n**Key:** `{key_info['key']}`", ephemeral=True)
    await admin_command_wrapper(interaction, logic)
    
@tree.command(name="listkeys1", description="[Admin] Xem danh sách các key Liên Quân chưa sử dụng.")
async def listkeys1(interaction: discord.Interaction):
    async def logic(inter):
        keys_data = await aov_keygen.load_keys()
        keys = {k: v for k, v in keys_data.items() if v.get('is_active') and datetime.datetime.fromisoformat(v['expires_at'].replace("Z", "+00:00")) > datetime.datetime.now(datetime.timezone.utc)}
        if not keys: return await inter.followup.send("Không có key LQ nào hoạt động.", ephemeral=True)
        desc = "```" + "Key (AOV)         | User ID             | Thời Gian Còn Lại\n" + "------------------|---------------------|--------------------\n"
        for k, v in list(keys.items())[:20]: desc += f"{k:<17} | {v.get('user_id', 'N/A'):<19} | {format_time_left(v['expires_at'])}\n"
        if len(keys) > 20: desc += f"\n... và {len(keys) - 20} key khác."
        await inter.followup.send(embed=discord.Embed(title=f"🔑 {len(keys)} Keys Liên Quân đang hoạt động", description=desc + "```"), ephemeral=True)
    await admin_command_wrapper(interaction, logic)

@tree.command(name="delkey1", description="[Admin] Vô hiệu hóa một key Liên Quân.")
@app_commands.describe(key="Key Liên Quân cần xóa.")
async def delkey1(interaction: discord.Interaction, key: str):
    async def logic(inter):
        if await aov_keygen.delete_key(key): await inter.followup.send(f"✅ Key LQ `{key}` đã bị vô hiệu hóa.", ephemeral=True)
        else: await inter.followup.send(f"❌ Không tìm thấy key LQ `{key}`.", ephemeral=True)
    await admin_command_wrapper(interaction, logic)


# ==============================================================================
# 6. ERROR HANDLER HOÀN CHỈNH
# ==============================================================================
async def handle_error_response(interaction: discord.Interaction, message: str):
    try:
        if interaction.response.is_done(): await interaction.followup.send(message, ephemeral=True)
        else: await interaction.response.send_message(message, ephemeral=True)
    except (discord.errors.NotFound, discord.errors.HTTPException) as e:
        print(f"Không thể gửi tin nhắn lỗi cho một tương tác đã mất: {e}")

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

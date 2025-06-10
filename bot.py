# bot.py (Phiên bản 4.3.3 - Render Deploy Fix)
import discord
from discord import app_commands, ui
import os
import datetime
import time
import asyncio
from typing import Optional, Callable
from threading import Thread

print("--- [LAUNCH] Bot đang khởi chạy, phiên bản 4.3.3 (Render Deploy Fix)... ---")

from keep_alive import app # Thay đổi: nhập Flask app
from spammer import SpamManager
import keygen

# ==============================================================================
# 1. CÀI ĐẶT
# ==============================================================================
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
ADMIN_USER_ID = os.environ.get('ADMIN_USER_ID')
SPAM_CHANNEL_ID = int(os.environ.get('SPAM_CHANNEL_ID', 1381799563488399452)) 

if not DISCORD_TOKEN or not ADMIN_USER_ID:
    print("!!! [CRITICAL] Thiếu DISCORD_TOKEN hoặc ADMIN_USER_ID. Bot sẽ không khởi chạy.")
    # Không exit() ở đây nữa vì web server có thể vẫn cần chạy

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
    except (ValueError, TypeError):
        return "Không xác định"

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
            embed = discord.Embed(
                title="✅ Kích hoạt Key thành công!",
                description=f"Key của bạn còn **{format_time_left(key_info.get('expires_at'))}** sử dụng.",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Key: {key_value}")
            await self.original_message.edit(embed=embed, view=SpamControlView(key_value, key_info, self.original_message))
            await interaction.followup.send("Key hợp lệ! Bảng điều khiển đã được cập nhật.", ephemeral=True)
        else:
            errors = {"NOT_FOUND": "Key không tồn tại hoặc không hợp lệ.", "EXPIRED": "Key đã hết hạn.", "SUSPENDED": "Key đã bị tạm ngưng."}
            error_message = errors.get(result.get('code'), 'Lỗi không xác định.')
            await interaction.followup.send(f"❌ Lỗi: {error_message} Vui lòng thử lại.", ephemeral=True)

class SpamConfigModal(ui.Modal, title='Cấu hình Spam'):
    target_input = ui.TextInput(label='Locket Target (Username/Link)', placeholder='Ví dụ: mylocketuser hoặc link invite')
    
    def __init__(self, key: str, key_info: dict, user_id: int, control_message: discord.WebhookMessage):
        super().__init__(timeout=None)
        self.key, self.key_info, self.user_id = key, key_info, user_id
        self.control_message = control_message
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True) 
        active_view = ActiveSpamView(key=self.key, original_interaction=interaction)
        def update_callback(status: str, stats: Optional[dict] = None, message: Optional[str] = None):
            asyncio.run_coroutine_threadsafe(
                active_view.update_message(status, stats, message), 
                client.loop
            )
        spam_manager.start_spam_session(self.user_id, self.target_input.value, update_callback)
        await self.control_message.delete()

class InitialView(ui.View):
    def __init__(self, original_message: Optional[discord.WebhookMessage] = None):
        super().__init__(timeout=300)
        self.original_message = original_message

    @ui.button(label='Nhập Key', style=discord.ButtonStyle.primary, emoji='🔑')
    async def enter_key(self, interaction: discord.Interaction, button: ui.Button):
        if not self.original_message:
            return await interaction.response.send_message("Lỗi: Tin nhắn gốc đã hết hạn hoặc không tồn tại.", ephemeral=True)
        await interaction.response.send_modal(KeyEntryModal(original_message=self.original_message))
    
    async def on_timeout(self):
        try:
            if self.original_message and self.original_message.embeds:
                embed = self.original_message.embeds[0]
                embed.description = "Phiên làm việc đã hết hạn. Vui lòng dùng `/start` để bắt đầu lại."
                embed.color = discord.Color.dark_grey()
                await self.original_message.edit(embed=embed, view=None)
        except discord.NotFound: pass
        except Exception as e:
            print(f"Lỗi khi xử lý on_timeout cho InitialView: {e}")

class SpamControlView(ui.View):
    def __init__(self, key: str, key_info: dict, control_message: discord.WebhookMessage):
        super().__init__(timeout=600)
        self.key, self.key_info, self.control_message = key, key_info, control_message
    
    @ui.button(label='Bắt Đầu Spam', style=discord.ButtonStyle.green, emoji='🚀')
    async def start_spam(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(SpamConfigModal(self.key, self.key_info, interaction.user.id, self.control_message))
    
    async def on_timeout(self):
        try:
            if self.control_message and self.control_message.embeds:
                embed = self.control_message.embeds[0]
                embed.title = "⌛ Phiên làm việc đã hết hạn"
                embed.description = "Vui lòng dùng `/start` để bắt đầu lại."
                embed.color = discord.Color.dark_grey()
                await self.control_message.edit(embed=embed, view=None)
        except discord.NotFound: pass
        except Exception as e:
            print(f"Lỗi khi xử lý on_timeout cho SpamControlView: {e}")

class ActiveSpamView(ui.View):
    def __init__(self, key: str, original_interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.key, self.original_interaction, self.status_message = key, original_interaction, None
        
    async def update_message(self, status: str, stats: Optional[dict] = None, message: Optional[str] = None):
        if status == "started": 
            self.status_message = await self.original_interaction.followup.send(message, view=self, ephemeral=True)
            return
        if status == "error":
            await self.original_interaction.followup.send(f"❌ **Lỗi Khởi Động:** {message}", ephemeral=True)
            self.stop()
            return
        if not self.status_message: return
        embed = discord.Embed()
        try:
            if status == "running":
                embed.title, embed.color = "🚀 Trạng thái Spam: Đang Chạy", discord.Color.blue()
                embed.add_field(name="Thành Công", value=f"✅ {stats['success']}", inline=True).add_field(name="Thất Bại", value=f"❌ {stats['failed']}", inline=True).add_field(name="Thời Gian", value=f"⏳ {datetime.timedelta(seconds=int(time.time() - stats['start_time']))}", inline=True)
                await self.status_message.edit(embed=embed)
            elif status == "stopped":
                self.stop()
                embed.title, embed.color = "🛑 Phiên Spam Đã Dừng", discord.Color.dark_grey()
                embed.add_field(name="Tổng Thành Công", value=f"✅ {stats['success']}").add_field(name="Tổng Thất Bại", value=f"❌ {stats['failed']}")
                await self.status_message.edit(content="Hoàn tất! Bạn có thể đóng tin nhắn này hoặc dùng `/start` để bắt đầu lại.", embed=embed, view=None)
        except discord.NotFound: self.stop()
        except Exception as e:
            print(f"Lỗi khi cập nhật ActiveSpamView: {e}")
            self.stop()

    @ui.button(label='Dừng Spam', style=discord.ButtonStyle.red, emoji='🛑')
    async def stop_spam(self, interaction: discord.Interaction, button: ui.Button):
        if spam_manager.stop_spam_session(interaction.user.id):
            button.disabled = True
            await interaction.response.edit_message(content="Đang xử lý yêu cầu dừng...", view=self)
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
    if interaction.channel.id != SPAM_CHANNEL_ID:
        return await interaction.response.send_message(f"Lệnh này chỉ dùng được trong <#{SPAM_CHANNEL_ID}>.", ephemeral=True)
    
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(title="👋 Chào mừng đến với ZLocket Spammer Bot", description="Để bắt đầu, vui lòng nhập License Key của bạn.", color=discord.Color.purple())
    embed.add_field(name="Làm thế nào để có Key?", value="Vui lòng liên hệ với Admin để được cấp key.", inline=False).set_footer(text="Bot được phát triển bởi Zenn.")
    
    # Gửi tin nhắn và lấy đối tượng của nó
    initial_message = await interaction.followup.send(embed=embed, ephemeral=True, wait=True)
    # Tạo View với tham chiếu đến tin nhắn đó
    view = InitialView(original_message=initial_message)
    # Chỉnh sửa tin nhắn để thêm View vào
    await initial_message.edit(view=view)

@client.tree.command(name="genkey", description="[Admin] Tạo một license key mới.")
@app_commands.describe(user="Người dùng sẽ nhận key này.", days="Số ngày hiệu lực của key.")
async def genkey(interaction: discord.Interaction, user: discord.User, days: int):
    if str(interaction.user.id) != ADMIN_USER_ID:
        return await interaction.response.send_message("❌ Bạn không có quyền để thực hiện lệnh này.", ephemeral=True)
    
    await interaction.response.defer(ephemeral=True)
    try:
        key_info = keygen.add_key(days, user.id, interaction.user.id)
        await interaction.followup.send(f"✅ **Đã tạo key thành công!**\n\n**Người dùng:** {user.mention}\n**Hiệu lực:** {days} ngày\n**Key:** `{key_info['key']}`\n\n👉 *Hãy sao chép và gửi key này cho người dùng.*", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Đã xảy ra lỗi khi tạo key: {e}", ephemeral=True)

@client.tree.command(name="listkeys", description="[Admin] Xem danh sách các key đang hoạt động.")
async def listkeys(interaction: discord.Interaction):
    if str(interaction.user.id) != ADMIN_USER_ID: 
        return await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True)
    
    await interaction.response.defer(ephemeral=True)
    keys = {k: v for k, v in keygen.load_keys().items() if v.get('is_active') and datetime.datetime.fromisoformat(v['expires_at']) > datetime.datetime.now(datetime.timezone.utc)}
    if not keys: 
        return await interaction.followup.send("Không có key nào đang hoạt động.", ephemeral=True)

    desc = "```" + "Key               | User ID             | Thời Gian Còn Lại\n" + "------------------|---------------------|--------------------\n"
    for k, v in list(keys.items())[:20]:
        desc += f"{k:<17} | {v.get('user_id', 'N/A'):<19} | {format_time_left(v['expires_at'])}\n"
    if len(keys) > 20: 
        desc += f"\n... và {len(keys) - 20} key khác."
        
    embed = discord.Embed(title=f"🔑 {len(keys)} Keys đang hoạt động", description=desc + "```", color=discord.Color.blue())
    await interaction.followup.send(embed=embed, ephemeral=True)

@client.tree.command(name="delkey", description="[Admin] Vô hiệu hóa một key.")
@app_commands.describe(key="Key cần xóa.")
async def delkey(interaction: discord.Interaction, key: str):
    if str(interaction.user.id) != ADMIN_USER_ID: 
        return await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    if keygen.delete_key(key): 
        await interaction.followup.send(f"✅ Key `{key}` đã được vô hiệu hóa thành công.", ephemeral=True)
    else: 
        await interaction.followup.send(f"❌ Không tìm thấy key `{key}` trong hệ thống.", ephemeral=True)


# ==============================================================================
# 4. KHỞI CHẠY (LOGIC MỚI CHO RENDER)
# ==============================================================================

# Hàm chạy bot discord trong một luồng riêng
def run_bot():
    if not DISCORD_TOKEN:
        print("!!! [CRITICAL] Thiếu DISCORD_TOKEN, bot không thể chạy.")
        return
    try:
        # Cần một vòng lặp sự kiện mới cho luồng này
        asyncio.run(client.start(DISCORD_TOKEN))
    except discord.errors.LoginFailure:
        print("!!! [CRITICAL] Lỗi LoginFailure: DISCORD_TOKEN không hợp lệ.")
    except Exception as e:
        print(f"!!! [CRITICAL] Lỗi khi chạy bot trong luồng: {e}")


if __name__ == "__main__":
    # Bắt đầu luồng chạy bot Discord
    bot_thread = Thread(target=run_bot)
    bot_thread.daemon = True # Đảm bảo luồng bot tắt khi luồng chính tắt
    bot_thread.start()
    
    # Lấy cổng từ biến môi trường của Render
    port = int(os.environ.get('PORT', 8080))
    # Chạy Flask app (web server) ở luồng chính. 
    # Render sẽ kết nối với cổng này.
    print(f"--- [WEB] Web server đang khởi chạy trên cổng {port}... ---")
    app.run(host='0.0.0.0', port=port)

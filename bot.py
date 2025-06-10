# bot.py (phiên bản 4.3.1 - Sửa lỗi Unknown Message)
import discord
from discord import app_commands, ui
import os
import datetime
import time
import asyncio
from typing import Optional

print("--- [LAUNCH] Bot đang khởi chạy, phiên bản 4.3.1 (Sửa lỗi Unknown Message)... ---")

from keep_alive import keep_alive
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
    exit()

spam_manager = SpamManager()
intents = discord.Intents.default()

# ==============================================================================
# 2. HELPER & UI (Các hàm không thay đổi giữ nguyên)
# ==============================================================================
def format_time_left(expires_at_str):
    expires_dt = datetime.datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
    delta = expires_dt - datetime.datetime.now(datetime.timezone.utc)
    if delta.total_seconds() <= 0: return "Hết hạn"
    d, h, m = delta.days, delta.seconds // 3600, (delta.seconds % 3600) // 60
    if d > 0: return f"{d} ngày {h} giờ"
    if h > 0: return f"{h} giờ {m} phút"
    return f"{m} phút"

# === CHANGED === Sửa lại luồng xử lý Modal để tránh lỗi 10008
class KeyEntryModal(ui.Modal, title='Nhập License Key'):
    key_input = ui.TextInput(label='License Key', placeholder='Dán key của bạn vào đây...')

    # === NEW === Thêm một biến để lưu tin nhắn gốc cần chỉnh sửa
    def __init__(self, original_message: discord.WebhookMessage):
        super().__init__()
        self.original_message = original_message
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True) # Phản hồi tạm thời
        
        key_value = self.key_input.value
        result = spam_manager.validate_license(key_value)

        if result.get("valid"):
            key_info = result['key_info']
            embed = discord.Embed(
                title="✅ Kích hoạt Key thành công!",
                description=f"Key của bạn còn **{format_time_left(key_info['expires_at'])}** sử dụng.",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Key: {key_value}")
            # === CHANGED === Chỉnh sửa tin nhắn gốc đã được truyền vào
            await self.original_message.edit(embed=embed, view=SpamControlView(key_value, key_info, self.original_message))
            await interaction.followup.send("Key hợp lệ! Bảng điều khiển đã được cập nhật.", ephemeral=True)

        else:
            errors = {
                "NOT_FOUND": "Key không tồn tại hoặc không hợp lệ.",
                "EXPIRED": "Key đã hết hạn.",
                "SUSPENDED": "Key đã bị tạm ngưng."
            }
            error_message = errors.get(result.get('code'), 'Lỗi không xác định.')
            await interaction.followup.send(f"❌ Lỗi: {error_message} Vui lòng thử lại.", ephemeral=True)


class InitialView(ui.View):
    # === NEW === Thêm biến để lưu tin nhắn gốc
    def __init__(self, original_message: discord.WebhookMessage):
        super().__init__(timeout=None)
        self.original_message = original_message

    @ui.button(label='Nhập Key', style=discord.ButtonStyle.primary, emoji='🔑')
    async def enter_key(self, interaction: discord.Interaction, button: ui.Button):
        # === CHANGED === Truyền tin nhắn gốc vào Modal
        await interaction.response.send_modal(KeyEntryModal(original_message=self.original_message))


class SpamControlView(ui.View):
    # === NEW === Lưu tin nhắn điều khiển
    def __init__(self, key: str, key_info: dict, control_message: discord.WebhookMessage):
        super().__init__(timeout=600)
        self.key = key
        self.key_info = key_info
        self.control_message = control_message
    
    @ui.button(label='Bắt Đầu Spam', style=discord.ButtonStyle.green, emoji='🚀')
    async def start_spam(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(SpamConfigModal(self.key, self.key_info, interaction.user.id, self.control_message))

    async def on_timeout(self):
        try:
            embed = self.control_message.embeds[0]
            embed.title = "⌛ Phiên làm việc đã hết hạn"
            embed.description = "Vui lòng dùng `/start` để bắt đầu lại."
            embed.color = discord.Color.dark_grey()
            await self.control_message.edit(embed=embed, view=None)
        except Exception as e:
            # print(f"Lỗi khi on_timeout: {e}") # Bỏ comment để debug nếu cần
            pass

# === CHANGED === SpamConfigModal cần biết tin nhắn gốc để xóa
class SpamConfigModal(ui.Modal, title='Cấu hình Spam'):
    target_input = ui.TextInput(label='Locket Target (Username/Link)', placeholder='Ví dụ: mylocketuser hoặc link invite')
    
    def __init__(self, key: str, key_info: dict, user_id: int, control_message: discord.WebhookMessage):
        super().__init__(timeout=None)
        self.key, self.key_info, self.user_id = key, key_info, user_id
        self.control_message = control_message
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True) 

        active_view = ActiveSpamView(self.key, self.key_info, interaction)

        def update_callback(status, stats=None, message=None):
            asyncio.run_coroutine_threadsafe(
                active_view.update_message(status, stats, message), 
                client.loop
            )

        spam_manager.start_spam_session(self.user_id, self.target_input.value, update_callback)
        
        # === CHANGED === Xóa tin nhắn điều khiển ban đầu đi để không gian gọn gàng
        await self.control_message.delete()


# Lớp ActiveSpamView và các lớp khác giữ nguyên, không cần thay đổi.
# ... (dán code ActiveSpamView, MyBotClient từ phiên bản 4.3 vào đây) ...
class ActiveSpamView(ui.View):
    def __init__(self, key: str, key_info: dict, original_interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.key, self.key_info, self.original_interaction, self.status_message = key, key_info, original_interaction, None
        
    async def update_message(self, status, stats=None, message=None):
        if status == "started": 
            self.status_message = await self.original_interaction.followup.send(message, view=self, ephemeral=True)
            return
        if status == "error":
            await self.original_interaction.followup.send(f"❌ **Lỗi Khởi Động:** {message}", ephemeral=True)
            return
        if not self.status_message: return
        embed = discord.Embed()
        try:
            if status == "running":
                embed.title = "🚀 Trạng thái Spam: Đang Chạy"
                embed.color = discord.Color.blue()
                embed.add_field(name="Thành Công", value=f"✅ {stats['success']}", inline=True)
                embed.add_field(name="Thất Bại", value=f"❌ {stats['failed']}", inline=True)
                runtime = datetime.timedelta(seconds=int(time.time() - stats['start_time']))
                embed.add_field(name="Thời Gian", value=f"⏳ {runtime}", inline=True)
                await self.status_message.edit(embed=embed)
            elif status == "stopped":
                self.stop()
                embed.title = "🛑 Phiên Spam Đã Dừng"
                embed.color = discord.Color.dark_grey()
                embed.add_field(name="Tổng Thành Công", value=f"✅ {stats['success']}", inline=True)
                embed.add_field(name="Tổng Thất Bại", value=f"❌ {stats['failed']}", inline=True)
                final_view = ui.View(timeout=None)
                final_view.add_item(ui.Button(label="🚀 Bắt đầu lại", style=discord.ButtonStyle.success, custom_id=f"spam_again:{self.key}"))
                final_view.add_item(ui.Button(label="Thoát", style=discord.ButtonStyle.grey, custom_id="exit"))
                await self.status_message.edit(content="Hoàn tất!", embed=embed, view=final_view)
        except Exception:
            self.stop()

    @ui.button(label='Dừng Spam', style=discord.ButtonStyle.red, emoji='🛑')
    async def stop_spam(self, interaction: discord.Interaction, button: ui.Button):
        if spam_manager.stop_spam_session(interaction.user.id):
            await interaction.response.defer()
            button.disabled = True
            await interaction.edit_original_response(view=self)
        else:
            await interaction.response.send_message("Không tìm thấy phiên spam đang chạy để dừng.", ephemeral=True)

class MyBotClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("--- [SYNC] Đồng bộ lệnh lên Discord thành công. ---")

    async def on_ready(self):
        print(f'--- [READY] Bot đã đăng nhập: {self.user} ---')
        
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            await super().on_interaction(interaction) # Cho các lệnh slash xử lý
            return

        custom_id = interaction.data.get("custom_id")
        if not custom_id:
            return
            
        if custom_id.startswith("spam_again:"):
            # Chức năng này tạo một tin nhắn mới, không phải ephemeral
            key = custom_id.split(":", 1)[1]
            # Defer the original interaction (clicking 'Bắt đầu lại')
            await interaction.response.defer(ephemeral=False, thinking=True) # Send a thinking state

            result = spam_manager.validate_license(key)
            if result.get("valid"):
                key_info = result['key_info']
                embed = discord.Embed(
                    title="✅ Kích hoạt lại Key!",
                    description=f"Key của bạn còn **{format_time_left(key_info['expires_at'])}** sử dụng.",
                    color=discord.Color.green()
                )
                # === NEW === Gửi tin nhắn mới thay vì cố edit
                new_message = await interaction.followup.send(
                    embed=embed, 
                    view=SpamControlView(key, key_info, interaction.message), # Pass the message object to control it
                    ephemeral=True # Make this new control panel ephemeral
                )
                await interaction.message.delete() # Xóa tin nhắn "Hoàn tất" cũ
            else:
                await interaction.followup.send("Key đã hết hạn hoặc không hợp lệ khi thử lại.", ephemeral=True)
                await interaction.message.delete()
        elif custom_id == "exit":
            try:
                await interaction.response.defer()
                await interaction.message.delete()
            except: pass
        else:
             # Đây là nơi xử lý các button khác nếu không phải là spam_again hoặc exit
             # Vì chúng ta đã có luồng riêng cho các view kia nên không cần code ở đây
             pass

# ==============================================================================
# 3. LỆNH (chỉ thay đổi /start)
# ==============================================================================

# ... (dán code client, /genkey, /listkeys, /delkey từ phiên bản 4.3 vào đây) ...

client = MyBotClient(intents=intents)

# === CHANGED === Sửa lại toàn bộ lệnh /start để hoạt động chính xác
@client.tree.command(name="start", description="Bắt đầu một phiên làm việc mới.")
async def start(interaction: discord.Interaction):
    if interaction.channel.id != SPAM_CHANNEL_ID:
        await interaction.response.send_message(f"Lệnh này chỉ có thể được sử dụng trong kênh <#{SPAM_CHANNEL_ID}>.", ephemeral=True)
        return
    
    # Phản hồi tạm thời tới lệnh /start để tránh "Interaction failed"
    await interaction.response.defer(ephemeral=True)
        
    embed = discord.Embed(
        title="👋 Chào mừng đến với ZLocket Spammer Bot",
        description="Để bắt đầu, vui lòng nhập License Key của bạn.",
        color=discord.Color.purple()
    )
    embed.add_field(name="Làm thế nào để có Key?", value="Vui lòng liên hệ với Admin để được cấp key.", inline=False)
    embed.set_footer(text="Bot được phát triển bởi Zenn.")
    
    # Gửi tin nhắn ban đầu bằng followup.send, đây sẽ là tin nhắn chúng ta chỉnh sửa.
    # Nó là ephemeral nên chỉ người dùng đó thấy.
    initial_message = await interaction.followup.send(
        embed=embed, 
        view=InitialView(original_message=None), # Sẽ cập nhật ngay sau
        ephemeral=True
    )
    # Cập nhật view với tham chiếu đến chính nó để có thể truyền vào Modal
    view = InitialView(original_message=initial_message)
    await initial_message.edit(view=view)
    
# Các lệnh khác giữ nguyên...
# === CHANGED === Lệnh /genkey không còn gửi DM
@client.tree.command(name="genkey", description="[Admin] Tạo một license key mới.")
@app_commands.describe(user="Người dùng sẽ nhận key này.", days="Số ngày hiệu lực của key.")
async def genkey(interaction: discord.Interaction, user: discord.User, days: int):
    if str(interaction.user.id) != ADMIN_USER_ID:
        await interaction.response.send_message("❌ Bạn không có quyền để thực hiện lệnh này.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        key_info = keygen.add_key(days, user.id, interaction.user.id)
        await interaction.followup.send(
            f"✅ **Đã tạo key thành công!**\n\n"
            f"**Người dùng:** {user.mention}\n"
            f"**Hiệu lực:** {days} ngày\n"
            f"**Key:** `{key_info['key']}`\n\n"
            f"👉 *Hãy sao chép và gửi key này cho người dùng.*",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Đã xảy ra lỗi khi tạo key: {e}", ephemeral=True)

@client.tree.command(name="listkeys", description="[Admin] Xem danh sách các key đang hoạt động.")
async def listkeys(interaction: discord.Interaction):
    if str(interaction.user.id) != ADMIN_USER_ID:
        await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True); return
    try: await interaction.response.defer(ephemeral=True)
    except: return
    keys = {k: v for k, v in keygen.load_keys().items() if v.get('is_active') and datetime.datetime.fromisoformat(v['expires_at']) > datetime.datetime.now(datetime.timezone.utc)}
    if not keys:
        await interaction.followup.send("Không có key nào đang hoạt động.", ephemeral=True); return
    desc = "```" + "Key               | User ID             | Thời Gian Còn Lại\n" + "------------------|---------------------|--------------------\n"
    for k, v in list(keys.items())[:20]:
        desc += f"{k:<17} | {v.get('user_id', 'N/A'):<19} | {format_time_left(v['expires_at'])}\n"
    if len(keys) > 20:
        desc += f"\n... và {len(keys) - 20} key khác."
    await interaction.followup.send(embed=discord.Embed(title=f"🔑 {len(keys)} Keys đang hoạt động", description=desc + "```"), ephemeral=True)

@client.tree.command(name="delkey", description="[Admin] Vô hiệu hóa một key.")
@app_commands.describe(key="Key cần xóa.")
async def delkey(interaction: discord.Interaction, key: str):
    if str(interaction.user.id) != ADMIN_USER_ID:
        await interaction.response.send_message("❌ Bạn không có quyền.", ephemeral=True); return
    try: await interaction.response.defer(ephemeral=True)
    except: return
    if keygen.delete_key(key):
        await interaction.followup.send(f"✅ Key `{key}` đã được vô hiệu hóa thành công.", ephemeral=True)
    else:
        await interaction.followup.send(f"❌ Không tìm thấy key `{key}` trong hệ thống.", ephemeral=True)

# ==============================================================================
# 4. KHỞI CHẠY
# ==============================================================================
if __name__ == "__main__":
    try:
        keep_alive()
        client.run(DISCORD_TOKEN)
    except discord.errors.LoginFailure:
        print("!!! [CRITICAL] Lỗi LoginFailure: DISCORD_TOKEN không hợp lệ.")
    except Exception as e:
        print(f"!!! [CRITICAL] Đã xảy ra lỗi không xác định khi khởi chạy bot: {e}")

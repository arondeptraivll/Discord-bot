# bot.py (phiên bản 4.3 - Cải thiện UI/UX)
import discord
from discord import app_commands, ui
import os
import datetime
import time
import asyncio
from typing import Optional

print("--- [LAUNCH] Bot đang khởi chạy, phiên bản 4.3 (Cải thiện UI/UX)... ---")

from keep_alive import keep_alive
from spammer import SpamManager
import keygen

# ==============================================================================
# 1. CÀI ĐẶT
# ==============================================================================
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
ADMIN_USER_ID = os.environ.get('ADMIN_USER_ID')
# === CHANGED === Đưa ID kênh vào biến môi trường để linh hoạt hơn
SPAM_CHANNEL_ID = int(os.environ.get('SPAM_CHANNEL_ID', 1381799563488399452)) 

if not DISCORD_TOKEN or not ADMIN_USER_ID:
    print("!!! [CRITICAL] Thiếu DISCORD_TOKEN hoặc ADMIN_USER_ID. Bot sẽ không khởi chạy.")
    exit()

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

    # === CHANGED === Cải tiến luồng xử lý để edit tin nhắn gốc
    async def on_submit(self, interaction: discord.Interaction):
        # Tạm hoãn phản hồi để có thời gian xử lý
        await interaction.response.defer(ephemeral=True, thinking=True)
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
            # Chỉnh sửa tin nhắn gốc thay vì gửi tin nhắn mới
            await interaction.message.edit(embed=embed, view=SpamControlView(key_value, key_info))
            await interaction.followup.send("Key hợp lệ! Bảng điều khiển đã xuất hiện.", ephemeral=True)

        else:
            errors = {
                "NOT_FOUND": "Key không tồn tại hoặc không hợp lệ.",
                "EXPIRED": "Key đã hết hạn.",
                "SUSPENDED": "Key đã bị tạm ngưng."
            }
            error_message = errors.get(result.get('code'), 'Lỗi không xác định.')
            # Chỉ gửi phản hồi lỗi, không thay đổi tin nhắn gốc
            await interaction.followup.send(f"❌ Lỗi: {error_message}", ephemeral=True)


class SpamConfigModal(ui.Modal, title='Cấu hình Spam'):
    target_input = ui.TextInput(label='Locket Target (Username/Link)', placeholder='Ví dụ: mylocketuser hoặc link invite')
    
    def __init__(self, key: str, key_info: dict, user_id: int):
        super().__init__(timeout=None)
        self.key, self.key_info, self.user_id = key, key_info, user_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True) # Phản hồi tạm thời tới modal submission

        # Chuẩn bị View cho phiên đang chạy
        active_view = ActiveSpamView(self.key, self.key_info, interaction)

        # Callback để cập nhật giao diện từ luồng spam
        def update_callback(status, stats=None, message=None):
            # Đảm bảo chạy code bất đồng bộ trong luồng chính của bot
            asyncio.run_coroutine_threadsafe(
                active_view.update_message(status, stats, message), 
                client.loop
            )

        # Bắt đầu phiên spam, truyền callback vào
        spam_manager.start_spam_session(self.user_id, self.target_input.value, update_callback)
        
        # === NEW === Xóa tin nhắn cấu hình sau khi đã bắt đầu
        await interaction.message.delete()


class InitialView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @ui.button(label='Nhập Key', style=discord.ButtonStyle.primary, emoji='🔑')
    async def enter_key(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(KeyEntryModal())

class SpamControlView(ui.View):
    def __init__(self, key: str, key_info: dict):
        super().__init__(timeout=600)
        self.key = key
        self.key_info = key_info
    
    @ui.button(label='Bắt Đầu Spam', style=discord.ButtonStyle.green, emoji='🚀')
    async def start_spam(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(SpamConfigModal(self.key, self.key_info, interaction.user.id))

    async def on_timeout(self):
        try:
            if hasattr(self, 'message') and self.message:
                embed = self.message.embeds[0]
                embed.title = "⌛ Phiên làm việc đã hết hạn"
                embed.description = "Vui lòng dùng `/start` để bắt đầu lại."
                embed.color = discord.Color.dark_grey()
                await self.message.edit(embed=embed, view=None)
        except:
            pass

class ActiveSpamView(ui.View):
    def __init__(self, key: str, key_info: dict, original_interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.key, self.key_info, self.original_interaction, self.status_message = key, key_info, original_interaction, None
        
    async def update_message(self, status, stats=None, message=None):
        if status == "started": 
            # === NEW === Tin nhắn bắt đầu được gửi như một tin nhắn mới và lưu lại để cập nhật
            self.status_message = await self.original_interaction.followup.send(message, view=self, ephemeral=True)
            return

        if status == "error":
            # === NEW === Gửi tin nhắn lỗi riêng biệt
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
                self.stop() # Dừng view, vô hiệu hóa các nút
                embed.title = "🛑 Phiên Spam Đã Dừng"
                embed.color = discord.Color.dark_grey()
                embed.add_field(name="Tổng Thành Công", value=f"✅ {stats['success']}", inline=True)
                embed.add_field(name="Tổng Thất Bại", value=f"❌ {stats['failed']}", inline=True)
                final_view = ui.View(timeout=None)
                final_view.add_item(ui.Button(label="🚀 Spam Target Mới", style=discord.ButtonStyle.success, custom_id=f"spam_again:{self.key}"))
                final_view.add_item(ui.Button(label="Thoát", style=discord.ButtonStyle.grey, custom_id="exit"))
                await self.status_message.edit(content="Hoàn tất!", embed=embed, view=final_view)
        except Exception: # Nếu có lỗi khi edit (vd: tin nhắn bị xóa), dừng view
            self.stop()

    @ui.button(label='Dừng Spam', style=discord.ButtonStyle.red, emoji='🛑')
    async def stop_spam(self, interaction: discord.Interaction, button: ui.Button):
        if spam_manager.stop_spam_session(interaction.user.id):
            await interaction.response.defer() # Chỉ cần ack interaction, callback sẽ xử lý edit
            button.disabled = True
            await interaction.edit_original_response(view=self)
        else:
            await interaction.response.send_message("Không tìm thấy phiên spam đang chạy để dừng.", ephemeral=True)

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
        
    async def on_interaction(self, interaction: discord.Interaction):
        # === CHANGED === Cải tiến xử lý custom_id
        if interaction.type != discord.InteractionType.component:
            return # Chỉ xử lý tương tác từ component (nút, select) ở đây

        custom_id = interaction.data.get("custom_id")
        if not custom_id:
            return

        if custom_id.startswith("spam_again:"):
            key = custom_id.split(":", 1)[1]
            await interaction.response.defer(ephemeral=True, thinking=True)
            result = spam_manager.validate_license(key)
            if result.get("valid"):
                key_info = result['key_info']
                embed = discord.Embed(
                    title="✅ Kích hoạt lại Key!",
                    description=f"Key của bạn còn **{format_time_left(key_info['expires_at'])}** sử dụng.",
                    color=discord.Color.green()
                )
                # Edit tin nhắn "Hoàn tất" thành tin nhắn điều khiển mới
                await interaction.message.edit(embed=embed, view=SpamControlView(key, key_info))
                await interaction.followup.send("Sẵn sàng cho phiên mới!", ephemeral=True)
            else:
                await interaction.followup.send("Key đã hết hạn hoặc không hợp lệ khi thử lại.", ephemeral=True)
                await interaction.message.delete()

        elif custom_id == "exit":
            try:
                # Xóa tin nhắn thay vì edit thành "Đã đóng"
                await interaction.response.defer()
                await interaction.message.delete()
            except:
                pass

client = MyBotClient(intents=intents)

# === CHANGED === Lệnh /start với Embed đẹp hơn
@client.tree.command(name="start", description="Bắt đầu một phiên làm việc mới.")
async def start(interaction: discord.Interaction):
    if interaction.channel.id != SPAM_CHANNEL_ID:
        await interaction.response.send_message(f"Lệnh này chỉ có thể được sử dụng trong kênh <#{SPAM_CHANNEL_ID}>.", ephemeral=True)
        return
        
    embed = discord.Embed(
        title="👋 Chào mừng đến với ZLocket Spammer Bot",
        description="Để bắt đầu, vui lòng nhập License Key của bạn.",
        color=discord.Color.purple()
    )
    embed.add_field(name="Làm thế nào để có Key?", value="Vui lòng liên hệ với Admin để được cấp key.", inline=False)
    embed.set_footer(text="Bot được phát triển bởi Zenn.")
    
    await interaction.response.send_message(embed=embed, view=InitialView(), ephemeral=True)


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
        # === CHANGED === Thông báo rõ ràng hơn cho admin
        await interaction.followup.send(
            f"✅ **Đã tạo key thành công!**\n\n"
            f"**Người dùng:** {user.mention}\n"
            f"**Hiệu lực:** {days} ngày\n"
            f"**Key:** `{key_info['key']}`\n\n"
            f"👉 *Hãy sao chép và gửi key này cho người dùng.*",
            ephemeral=True
        )
        # === REMOVED === Xóa bỏ phần tự động gửi DM
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
        await interaction.followup.send("Không có key nào đang hoạt động.", ephemeral=True)
        return

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
    # Đảm bảo bot chỉ chạy nếu đây là file chính
    try:
        keep_alive()
        client.run(DISCORD_TOKEN)
    except discord.errors.LoginFailure:
        print("!!! [CRITICAL] Lỗi LoginFailure: DISCORD_TOKEN không hợp lệ.")
    except Exception as e:
        print(f"!!! [CRITICAL] Đã xảy ra lỗi không xác định khi khởi chạy bot: {e}")

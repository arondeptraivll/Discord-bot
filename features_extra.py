

# features_extra.py - Cog cho các tính năng ở kênh mới
import discord
from discord import app_commands
from discord.ext import commands
import os

# --- THAY ĐỔI: Thêm xử lý lỗi để bot không bị crash khi thiếu ID ---
NEW_CHANNEL_ID = 0
try:
    # Cố gắng lấy ID kênh từ biến môi trường
    raw_id = os.environ.get('NEW_CHANNEL_ID')
    if raw_id:
        NEW_CHANNEL_ID = int(raw_id)
    else:
        # In ra cảnh báo nếu biến không được thiết lập
        print("!!! [WARNING] Biến môi trường 'NEW_CHANNEL_ID' không được thiết lập cho features_extra.py. Các lệnh trong cog này sẽ không hoạt động.")
except ValueError:
    print(f"!!! [ERROR] Giá trị của 'NEW_CHANNEL_ID' ({os.environ.get('NEW_CHANNEL_ID')}) không phải là một số hợp lệ.")

class ExtraFeaturesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        print("--- [COG LOAD] Cog 'ExtraFeatures' đã được tải. ---")

    async def is_in_correct_channel(self, interaction: discord.Interaction) -> bool:
        # Nếu ID kênh không hợp lệ (bằng 0), luôn từ chối và thông báo lỗi
        if NEW_CHANNEL_ID == 0:
            await interaction.response.send_message(
                "Lệnh này chưa được cấu hình đúng. Vui lòng liên hệ Admin để thiết lập 'NEW_CHANNEL_ID'.", 
                ephemeral=True
            )
            return False

        if interaction.channel.id != NEW_CHANNEL_ID:
            await interaction.response.send_message(
                f"Lệnh này chỉ có thể được sử dụng trong kênh <#{NEW_CHANNEL_ID}>.", 
                ephemeral=True
            )
            return False
        return True

    @app_commands.command(name="userinfo", description="Xem thông tin chi tiết về một người dùng.")
    @app_commands.describe(user="Người dùng bạn muốn xem thông tin (để trống là bạn).")
    async def userinfo(self, interaction: discord.Interaction, user: discord.Member = None):
        if not await self.is_in_correct_channel(interaction):
            return

        target_user = user or interaction.user
        embed = discord.Embed(
            title=f"Thông tin của {target_user.display_name}",
            color=target_user.color
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)
        embed.add_field(name="Tên", value=str(target_user), inline=True)
        embed.add_field(name="ID", value=target_user.id, inline=True)
        embed.add_field(name="Trạng thái", value=str(target_user.status).title(), inline=True)
        created_at = discord.utils.format_dt(target_user.created_at, style='R')
        joined_at = discord.utils.format_dt(target_user.joined_at, style='R')
        embed.add_field(name="Tạo tài khoản", value=created_at, inline=True)
        embed.add_field(name="Gia nhập server", value=joined_at, inline=True)
        roles = [role.mention for role in target_user.roles[1:]]
        roles.reverse()
        if roles:
            embed.add_field(name=f"Roles [{len(roles)}]", value=" ".join(roles), inline=False)
        embed.set_footer(text=f"Yêu cầu bởi {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(ExtraFeaturesCog(bot))



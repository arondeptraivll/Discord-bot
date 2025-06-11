# browser_cog.py - Cog để điều khiển trình duyệt ảo

import discord
from discord import app_commands
from discord.ext import commands
import os

# Imports cho Selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ID kênh được phép
BROWSER_CHANNEL_ID = 1382203422094266390

class BrowserCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Khởi tạo options cho Chrome để chạy ở chế độ "headless" trên server
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")  # Chạy không cần giao diện đồ họa
        chrome_options.add_argument("--no-sandbox") # Bắt buộc khi chạy với quyền root (mặc định trong Docker)
        chrome_options.add_argument("--disable-dev-shm-usage") # Khắc phục lỗi tài nguyên
        chrome_options.add_argument("--disable-gpu") # Tắt GPU, không cần thiết cho headless
        chrome_options.add_argument("window-size=1920,1080") # Đặt kích thước cửa sổ ảo

        self.chrome_options = chrome_options
        print("--- [COG LOAD] Cog 'Browser' đã được tải. ---")

    @app_commands.command(name="start-browser-task", description="Khởi động một tác vụ trên trình duyệt ảo.")
    async def start_browser_task(self, interaction: discord.Interaction):
        # 1. Kiểm tra xem có đúng kênh không
        if interaction.channel.id != BROWSER_CHANNEL_ID:
            await interaction.response.send_message(
                f"Lệnh này chỉ dùng được trong <#{BROWSER_CHANNEL_ID}>.", 
                ephemeral=True
            )
            return
        
        # 2. Phản hồi tạm thời để người dùng biết bot đang xử lý
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Sử dụng with statement để đảm bảo trình duyệt luôn được đóng
            with webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=self.chrome_options) as driver:
                
                # Truy cập trang web
                driver.get("https://muahacker.com/randomacclienquan/?nocache=1749613527280")
                
                # Đợi cho đến khi button có thể được click (tối đa 10 giây)
                # Đây là cách làm ổn định hơn là sleep
                button_xpath = "/html/body/div[6]/div/div[6]/button[1]"
                wait = WebDriverWait(driver, 10)
                
                # Tìm và click button
                # EC.element_to_be_clickable kiểm tra xem phần tử có hiển thị và bật không
                button = wait.until(EC.element_to_be_clickable((By.XPATH, button_xpath)))
                button.click()

            # 3. Gửi thông báo thành công
            await interaction.followup.send("✅ Bot đã click thành công!", ephemeral=True)

        except Exception as e:
            # 4. Báo lỗi nếu có sự cố
            print(f"Lỗi Selenium: {e}") # In ra console để bạn debug
            await interaction.followup.send(f"❌ Đã có lỗi xảy ra trong quá trình điều khiển trình duyệt. Lỗi: {type(e).__name__}", ephemeral=True)

# Hàm setup để discord.py nạp Cog này
async def setup(bot: commands.Bot):
    await bot.add_cog(BrowserCog(bot))

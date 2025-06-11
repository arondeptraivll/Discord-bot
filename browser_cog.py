# browser_cog.py
import discord
from discord import app_commands
from discord.ext import commands
import os
import threading # <-- Thêm thư viện threading

# Imports cho Selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

BROWSER_CHANNEL_ID = 1382203422094266390

class BrowserCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        print("--- [COG LOAD] Cog 'Browser' đã được tải. ---")
        
    def run_selenium_task(self, interaction: discord.Interaction):
        """Hàm này sẽ chạy công việc của Selenium trong một luồng riêng."""
        try:
            # Di chuyển việc cấu hình options vào đây để mỗi luồng có 1 instance riêng
            chrome_options = webdriver.ChromeOptions()
            chrome_options.binary_location = "/usr/bin/google-chrome-stable" # <-- DÙNG ĐƯỜNG DẪN ĐẦY ĐỦ VÀ CHẮC CHẮN NHẤT
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("window-size=1920,1080")

            with webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options) as driver:
                driver.get("https://muahacker.com/randomacclienquan/?nocache=1749613527280")
                
                button_xpath = "/html/body/div[6]/div/div[6]/button[1]"
                wait = WebDriverWait(driver, 10)
                button = wait.until(EC.element_to_be_clickable((By.XPATH, button_xpath)))
                button.click()
            
            # Sử dụng followup.send để gửi tin nhắn sau khi đã defer
            self.bot.loop.create_task(interaction.followup.send("✅ Bot đã click thành công!", ephemeral=True))
            
        except Exception as e:
            error_message = f"❌ Đã có lỗi xảy ra: {type(e).__name__}"
            print(f"Lỗi Selenium: {e}")
            self.bot.loop.create_task(interaction.followup.send(error_message, ephemeral=True))

    @app_commands.command(name="start1", description="Khởi động tác vụ #1 trên trình duyệt ảo.")
    async def start1(self, interaction: discord.Interaction):
        if interaction.channel.id != BROWSER_CHANNEL_ID:
            await interaction.response.send_message(f"Lệnh này chỉ dùng được trong <#{BROWSER_CHANNEL_ID}>.", ephemeral=True)
            return
        
        # Bước 1: Phản hồi ngay lập tức cho Discord để tránh lỗi timeout
        await interaction.response.send_message("🚀 Đã nhận lệnh! Bắt đầu xử lý tác vụ trình duyệt...", ephemeral=True)

        # Bước 2: Tạo và khởi chạy công việc Selenium trong một luồng riêng
        # Điều này cho phép bot tiếp tục hoạt động mà không bị chặn
        thread = threading.Thread(target=self.run_selenium_task, args=(interaction,))
        thread.start()

async def setup(bot: commands.Bot):
    await bot.add_cog(BrowserCog(bot))

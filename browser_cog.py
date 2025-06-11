# browser_cog.py
import discord
from discord import app_commands
from discord.ext import commands
import os
import threading

# Imports cho Selenium
from selenium import webdriver
# KHÔNG CẦN import Service hay webdriver_manager nữa

BROWSER_CHANNEL_ID = 1382203422094266390

class BrowserCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Cấu hình options có thể được tạo một lần ở đây
        self.chrome_options = webdriver.ChromeOptions()
        # Đường dẫn này phải khớp với những gì Dockerfile cài đặt
        self.chrome_options.binary_location = "/usr/bin/google-chrome-stable" 
        self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("window-size=1920,1080")
        print("--- [COG LOAD] Cog 'Browser' đã được tải. ---")
        
    def run_selenium_task(self, interaction: discord.Interaction):
        """Hàm này chạy công việc của Selenium trong một luồng riêng."""
        try:
            # Bây giờ, khởi tạo webdriver rất đơn giản
            # Selenium sẽ tự động tìm chromedriver trong /usr/bin
            with webdriver.Chrome(options=self.chrome_options) as driver:
                driver.get("https://muahacker.com/randomacclienquan/?nocache=1749613527280")
                
                button_xpath = "/html/body/div[6]/div/div[6]/button[1]"
                # Logic còn lại giữ nguyên...
                wait = WebDriverWait(driver, 10)
                button = wait.until(EC.element_to_be_clickable((By.XPATH, button_xpath)))
                button.click()
            
            # Gửi tin nhắn thành công
            self.bot.loop.create_task(interaction.followup.send("✅ Bot đã click thành công!", ephemeral=True))
            
        except Exception as e:
            error_message = f"❌ Đã có lỗi xảy ra: {type(e).__name__}"
            print(f"Lỗi Selenium: {e}") # In lỗi chi tiết ra log của Render
            self.bot.loop.create_task(interaction.followup.send(error_message, ephemeral=True))

    @app_commands.command(name="start1", description="Khởi động tác vụ #1 trên trình duyệt ảo.")
    async def start1(self, interaction: discord.Interaction):
        if interaction.channel.id != BROWSER_CHANNEL_ID:
            await interaction.response.send_message(f"Lệnh này chỉ dùng được trong <#{BROWSER_CHANNEL_ID}>.", ephemeral=True)
            return
        
        await interaction.response.send_message("🚀 Đã nhận lệnh! Bắt đầu xử lý tác vụ trình duyệt...", ephemeral=True)

        thread = threading.Thread(target=self.run_selenium_task, args=(interaction,))
        thread.start()

async def setup(bot: commands.Bot):
    await bot.add_cog(BrowserCog(bot))



# browser_cog.py - Cog để điều khiển trình duyệt ảo
import discord
from discord import app_commands
from discord.ext import commands
import os
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
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("window-size=1920,1080")
        self.chrome_options = chrome_options
        print("--- [COG LOAD] Cog 'Browser' đã được tải. ---")

    # --- THAY ĐỔI: Đổi tên lệnh thành 'start1' ---
    @app_commands.command(name="start1", description="Khởi động tác vụ #1 trên trình duyệt ảo.")
    async def start1(self, interaction: discord.Interaction):
        if interaction.channel.id != BROWSER_CHANNEL_ID:
            await interaction.response.send_message(
                f"Lệnh này chỉ dùng được trong <#{BROWSER_CHANNEL_ID}>.", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Sử dụng with statement để đảm bảo trình duyệt luôn được đóng
            with webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=self.chrome_options) as driver:
                driver.get("https://muahacker.com/randomacclienquan/?nocache=1749613527280")
                
                button_xpath = "/html/body/div[6]/div/div[6]/button[1]"
                wait = WebDriverWait(driver, 10)
                button = wait.until(EC.element_to_be_clickable((By.XPATH, button_xpath)))
                button.click()

            await interaction.followup.send("✅ Bot đã click thành công!", ephemeral=True)

        except Exception as e:
            print(f"Lỗi Selenium: {e}")
            await interaction.followup.send(f"❌ Đã có lỗi xảy ra trong quá trình điều khiển trình duyệt. Lỗi: {type(e).__name__}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(BrowserCog(bot))


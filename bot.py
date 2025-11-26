import os
import re
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
GITHUB_URL_PATTERN = re.compile(r'https://github.com/([\w\-]+)/([\w\-]+)(?:/|$)')
GITHUB_API_URL = "https://api.github.com/repos"
GITHUB_HEADERS = {"Accept": "application/vnd.github.v3.raw"}

# Setup intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Create bot
bot = commands.Bot(command_prefix='!', intents=intents)

# Load token
with open('token.txt', 'r', encoding='utf-8') as f:
    TOKEN = f.read().strip()


@bot.event
async def on_ready() -> None:
    """Called when the bot is ready."""
    print(f'Logged in as {bot.user}')
    
    # Create aiohttp session if it doesn't exist
    if not hasattr(bot, "session"):
        bot.session = aiohttp.ClientSession()
    
    # Sync commands with Discord
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')


@bot.event
async def on_close() -> None:
    """Called when the bot is about to close."""
    if hasattr(bot, "session"):
        await bot.session.close()


@bot.event
async def on_message(message: discord.Message) -> None:
    """Handle incoming messages and detect GitHub links."""
    # Ignore messages from bots
    if message.author.bot:
        return

    match = GITHUB_URL_PATTERN.search(message.content)
    if match:
        owner, repo = match.groups()

        # Suppress embeds if possible
        try:
            await message.edit(suppress=True)
        except (discord.Forbidden, discord.HTTPException):
            pass

        # Fetch and send README
        readme_text = await fetch_github_readme(owner, repo)
        if readme_text:
            preview = readme_text[:500] + ("..." if len(readme_text) > 500 else "")
            embed = discord.Embed(
                title=f"{owner}/{repo} README",
                description=f"```\n{preview}\n```",
                color=0x1f6feb
            )
            await message.channel.send(embed=embed)
        else:
            await message.channel.send(
                f"README not found for **{owner}/{repo}**"
            )

    # Process other commands
    await bot.process_commands(message)


async def fetch_github_readme(owner: str, repo: str) -> Optional[str]:
    """Fetch README from a GitHub repository."""
    url = f"{GITHUB_API_URL}/{owner}/{repo}/readme"
    
    try:
        async with bot.session.get(url, headers=GITHUB_HEADERS) as resp:
            if resp.status == 200:
                return await resp.text()
    except Exception as e:
        print(f"Error fetching README: {e}")
    
    return None


@app_commands.checks.has_permissions(administrator=True)
@bot.tree.command(name="setupverify", description="認証用メッセージを送信します")
@app_commands.describe(role="認証時に付与するロール")
async def setupverify(interaction: discord.Interaction, role: discord.Role) -> None:
    """Setup verification message with a role button."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "このコマンドは管理者のみ実行できます。",
            ephemeral=True
        )
        return

    if role.permissions.administrator:
        await interaction.response.send_message(
            "管理者権限のあるロールは選択できません。",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="認証",
        description="以下のボタンを押して認証してください。",
        color=0x00ff00
    )

    view = discord.ui.View()
    view.add_item(VerifyButton(role.id))
    
    await interaction.response.send_message(embed=embed, view=view)


class VerifyButton(discord.ui.Button):
    """Button for user verification."""
    
    def __init__(self, role_id: int) -> None:
        super().__init__(
            label="認証する",
            style=discord.ButtonStyle.success,
            custom_id=f"verify_button_{role_id}",  # 一意化
        )
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle button click."""
        role = interaction.guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message(
                'ロールが見つかりませんでした。',
                ephemeral=True
            )
            return
        
        await interaction.user.add_roles(role)
        await interaction.response.send_message(
            '認証されました！',
            ephemeral=True
        )


# Start the bot
if __name__ == "__main__":
    bot.run(TOKEN)

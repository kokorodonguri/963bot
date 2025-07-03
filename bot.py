import os
import re
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# ========== 環境変数読み込み ==========
load_dotenv()
ROLE_ID = int(os.getenv('ROLE_ID', 0))

# ========== intents 設定 ==========
intents = discord.Intents.default()
intents.members = True  # ロール付与用
intents.message_content = True  # メッセージ内容を読む

# ========== Bot 作成 ==========
bot = commands.Bot(command_prefix='!', intents=intents)

# ========== GitHub リンクのパターン ==========
GITHUB_URL_PATTERN = re.compile(r'https://github.com/([\w\-]+)/([\w\-]+)(?:/|$)')

# ========== トークン読み込み ==========
with open('token.txt', 'r', encoding='utf-8') as f:
    TOKEN = f.read().strip()

# ========== 起動時 ==========
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    # aiohttp セッションを作る
    if not hasattr(bot, "session"):
        bot.session = aiohttp.ClientSession()
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

# ========== GitHub リンク検知 & README 取得 ==========
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    match = GITHUB_URL_PATTERN.search(message.content)
    if match:
        owner, repo = match.groups()

        # 埋め込みを消す
        try:
            await message.edit(suppress=True)
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

        # README を取得
        readme_text = await fetch_github_readme(owner, repo)
        if readme_text:
            preview = readme_text[:500] + ("..." if len(readme_text) > 500 else "")
            await message.channel.send(
                f"**{owner}/{repo} の README:**\n```\n{preview}\n```"
            )
        else:
            await message.channel.send(f"**{owner}/{repo}** の README は見つかりませんでした。")

    # 他のコマンドが使えるように
    await bot.process_commands(message)

# ========== GitHub README 取得関数 ==========
async def fetch_github_readme(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/readme"
    headers = {"Accept": "application/vnd.github.v3.raw"}
    async with bot.session.get(url, headers=headers) as resp:
        if resp.status == 200:
            return await resp.text()
    return None

# ========== 認証用のスラッシュコマンド ==========
@app_commands.checks.has_permissions(administrator=True)
@bot.tree.command(name="setupverify", description="認証用メッセージを送信します")
@app_commands.describe(role="認証時に付与するロール")
async def setupverify(interaction: discord.Interaction, role: discord.Role):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("このコマンドは管理者のみ実行できます。", ephemeral=True)
        return

    embed = discord.Embed(
        title="認証",
        description="以下のボタンを押して認証してください。",
        color=0x00ff00
    )

    view = discord.ui.View()

    if role.permissions.administrator:
        await interaction.response.send_message(
            "管理者権限のあるロールは選択できません。",
            ephemeral=True
        )
        return

    view.add_item(VerifyButton(role.id))
    await interaction.response.send_message(embed=embed, view=view)

# ========== 認証ボタン ==========
class VerifyButton(discord.ui.Button):
    def __init__(self, role_id):
        super().__init__(label="認証する", style=discord.ButtonStyle.success, custom_id="verify_button")
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message('ロールが見つかりませんでした。', ephemeral=True)
            return
        await interaction.user.add_roles(role)
        await interaction.response.send_message('認証されました！ruleを読んでね❣https://discord.com/channels/1390238430683729930/1390275674299830272', ephemeral=True)

# ========== Bot 起動 ==========
bot.run(TOKEN)

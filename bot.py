import discord
from discord import app_commands
from discord.ext import commands
import datetime
import json
import os

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ========================= CONFIG =========================
VOUCHES_CHANNEL_NAME = "vouches"
DATA_FILE = "vouches_data.json"
COOLDOWN_SECONDS = 300

# Auto role settings (change these to your Role IDs or leave None)
ROLE_10 = None
ROLE_20 = None
ROLE_50 = None
ROLE_100 = None

# Load data
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        vouch_data = json.load(f)
else:
    vouch_data = {}

user_cooldown = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(vouch_data, f, indent=4)

# ========================= BOT READY =========================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Full Vouch Bot is online as {bot.user}")

# ========================= VOUCH COMMAND =========================
@bot.tree.command(name="vouch", description="Vouch for a member with stars")
@app_commands.describe(
    user="User you want to vouch for",
    comment="Optional comment about the trade",
    proof="Optional proof link (image/screenshot)"
)
async def vouch(interaction: discord.Interaction, user: discord.Member, comment: str = None, proof: str = None):
    
    if user == interaction.user:
        return await interaction.response.send_message("❌ You can't vouch for yourself!", ephemeral=True)

    # Cooldown
    now = datetime.datetime.now().timestamp()
    if interaction.user.id in user_cooldown and now - user_cooldown[interaction.user.id] < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - (now - user_cooldown[interaction.user.id]))
        return await interaction.response.send_message(f"⏳ Wait **{remaining}s** before vouching again.", ephemeral=True)

    # Star menu
    select = discord.ui.Select(
        placeholder="Select star rating (1-5)",
        options=[
            discord.SelectOption(label="1 ⭐", value="1"),
            discord.SelectOption(label="2 ⭐⭐", value="2"),
            discord.SelectOption(label="3 ⭐⭐⭐", value="3"),
            discord.SelectOption(label="4 ⭐⭐⭐⭐", value="4"),
            discord.SelectOption(label="5 ⭐⭐⭐⭐⭐", value="5"),
        ]
    )

    async def select_callback(interaction2: discord.Interaction):
        stars = int(select.values[0])
        star_emojis = "⭐" * stars

        uid = str(user.id)
        if uid not in vouch_data:
            vouch_data[uid] = {"total_vouches": 0, "total_stars": 0, "vouches": []}

        vouch_data[uid]["total_vouches"] += 1
        vouch_data[uid]["total_stars"] += stars
        vouch_data[uid]["vouches"].append({
            "by": str(interaction.user.id),
            "stars": stars,
            "comment": comment,
            "proof": proof,
            "time": datetime.datetime.now().isoformat(),
            "message_id": None
        })

        user_cooldown[interaction.user.id] = now
        save_data()

        avg = round(vouch_data[uid]["total_stars"] / vouch_data[uid]["total_vouches"], 1)

        embed = discord.Embed(title="✅ New Vouch", color=0x00ff88, timestamp=datetime.datetime.now())
        embed.add_field(name="Vouched For", value=user.mention, inline=True)
        embed.add_field(name="Vouched By", value=interaction.user.mention, inline=True)
        embed.add_field(name="Rating", value=f"{star_emojis} **({stars}/5)**", inline=False)
        if comment:
            embed.add_field(name="Comment", value=comment, inline=False)
        if proof:
            embed.add_field(name="Proof", value=proof, inline=False)
        embed.set_footer(text=f"Total Vouches: {vouch_data[uid]['total_vouches']} • Avg: {avg}⭐")

        channel = discord.utils.get(interaction.guild.text_channels, name=VOUCHES_CHANNEL_NAME)
        if not channel:
            return await interaction2.response.send_message("❌ #vouches channel not found!", ephemeral=True)

        msg = await channel.send(embed=embed)

        vouch_data[uid]["vouches"][-1]["message_id"] = str(msg.id)
        save_data()

        # Auto role
        total = vouch_data[uid]["total_vouches"]
        if total >= 100 and ROLE_100:
            role = interaction.guild.get_role(ROLE_100)
            if role: await user.add_roles(role)
        elif total >= 50 and ROLE_50:
            role = interaction.guild.get_role(ROLE_50)
            if role: await user.add_roles(role)
        elif total >= 20 and ROLE_20:
            role = interaction.guild.get_role(ROLE_20)
            if role: await user.add_roles(role)
        elif total >= 10 and ROLE_10:
            role = interaction.guild.get_role(ROLE_10)
            if role: await user.add_roles(role)

        class VouchView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)

            @discord.ui.button(label="Delete Vouch", style=discord.ButtonStyle.red, custom_id=f"delete_vouch_{msg.id}")
            async def delete_button(self, interaction3: discord.Interaction, button: discord.ui.Button):
                if not interaction3.user.guild_permissions.manage_messages:
                    return await interaction3.response.send_message("❌ Only staff can delete vouches!", ephemeral=True)
                await msg.delete()
                await interaction3.response.send_message("🗑️ Vouch deleted.", ephemeral=True)

        await msg.edit(view=VouchView())
        await interaction2.response.send_message(f"✅ Vouch for {user.mention} posted!", ephemeral=True)

    select.callback = select_callback
    view = discord.ui.View(timeout=60)
    view.add_item(select)

    await interaction.response.send_message(f"⭐ Rate your experience with **{user.display_name}**", view=view, ephemeral=True)

# ========================= VIEW VOUCHES COMMAND =========================
@bot.tree.command(name="vouches", description="Check a user's vouch history")
@app_commands.describe(user="The user to check")
async def view_vouches(interaction: discord.Interaction, user: discord.Member):
    uid = str(user.id)
    if uid not in vouch_data or vouch_data[uid]["total_vouches"] == 0:
        return await interaction.response.send_message(f"❌ {user.mention} has no vouches yet.", ephemeral=True)

    data = vouch_data[uid]
    avg = round(data["total_stars"] / data["total_vouches"], 1)

    embed = discord.Embed(title=f"📊 Vouch History • {user.display_name}", color=0x00ff88)
    embed.add_field(name="Total Vouches", value=data["total_vouches"], inline=True)
    embed.add_field(name="Average Rating", value=f"{avg}⭐", inline=True)

    recent = data["vouches"][-8:]
    desc = ""
    for v in reversed(recent):
        by = bot.get_user(int(v["by"])) or "Unknown"
        stars = "⭐" * v["stars"]
        desc += f"{stars} by {by}\n"
        if v.get("comment"):
            desc += f"→ {v['comment'][:120]}\n\n"

    embed.description = desc.strip() or "No comments."
    await interaction.response.send_message(embed=embed)

# ========================= RUN BOT =========================
bot.run(os.getenv("TOKEN"))

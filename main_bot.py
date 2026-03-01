import os
import io
import json
import time
import discord
from discord.ext import commands, tasks
from discord.ui import Select, View
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
MOD_CHANNEL_ID = int(os.getenv('MOD_CHANNEL_ID'))
WELCOME_CHANNEL_ID = int(os.getenv('WELCOME_CHANNEL_ID'))
MOD_ROLE_ID = int(os.getenv('MOD_ROLE_ID'))
DRIVE_FOLDER_ID = os.getenv('DRIVE_FOLDER_ID')

ANSWERS = {1: 42, 2: 108, 3: 314} 

TIME_LIMITS = {
    1: 600, 
    2: 900
}

STATE_FILE = "game_state.json"
CHANNELS_FILE = "target_channels.json"
ROLES_FILE = "team_roles.json"
BROADCAST_SENT = False

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            data = json.load(f)
            return {int(k): v for k, v in data.items()}
    return {}

def load_target_channels():
    if os.path.exists(CHANNELS_FILE):
        with open(CHANNELS_FILE, "r") as f:
            data = json.load(f)
            return data.get("team_channels", [])
    return []

def load_team_roles():
    if os.path.exists(ROLES_FILE):
        with open(ROLES_FILE, "r") as f:
            data = json.load(f)
            return data.get("roles", [])
    return []

def get_time_text(q_num):
    limit = TIME_LIMITS.get(q_num)
    if limit:
        mins = limit // 60
        secs = limit % 60
        time_str = f"{mins}m {secs}s" if secs else f"{mins} minutes"
        return f"**Timed Question:** {time_str} limit."
    return "**Untimed Question:** No time limit."

game_state = load_state()

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
creds = service_account.Credentials.from_service_account_file('service_account.json', scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=creds)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

class TeamSelect(Select):
    def __init__(self, options_chunk, index, all_team_ids):
        super().__init__(
            placeholder=f"choose your team (page {index})...", 
            min_values=1, 
            max_values=1, 
            options=options_chunk, 
            custom_id=f"team_select_dropdown_{index}"
        )
        self.all_team_ids = all_team_ids

    async def callback(self, interaction: discord.Interaction):
        has_team = any(role.id in self.all_team_ids for role in interaction.user.roles)
        if has_team:
            await interaction.response.send_message("you are already locked into a team.", ephemeral=True)
            return
            
        role_id = int(self.values[0])
        role = interaction.guild.get_role(role_id)
        
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"successfully joined {role.name}", ephemeral=True)
        else:
            await interaction.response.send_message("error finding that role.", ephemeral=True)

class TeamView(View):
    def __init__(self):
        super().__init__(timeout=None) 
        teams = load_team_roles()
        all_team_ids = [t["id"] for t in teams]
        
        if not teams:
            self.add_item(Select(placeholder="no teams configured", options=[discord.SelectOption(label="none", value="0")], disabled=True))
            return

        for i in range(0, len(teams), 25):
            chunk = teams[i:i+25]
            options = []
            for t in chunk:
                options.append(discord.SelectOption(
                    label=t["label"], 
                    description=t.get("description", ""), 
                    value=str(t["id"])
                ))
            index = (i // 25) + 1
            self.add_item(TeamSelect(options, index, all_team_ids))

async def get_drive_file(filename):
    query = f"(name = '{filename}' or name = '{filename}.pdf') and '{DRIVE_FOLDER_ID}' in parents"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])
    
    if not items:
        return None
    
    file_id = items[0]['id']
    request = drive_service.files().get_media(fileId=file_id)
    file_stream = io.BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request)
    
    done = False
    while not done:
        _, done = downloader.next_chunk()
    
    file_stream.seek(0)
    return discord.File(fp=file_stream, filename=f"{filename}.pdf")

@tasks.loop(seconds=5)
async def game_timer_loop():
    now = time.time()
    for cid_str, state in game_state.items():
        cid = int(cid_str)
        if state.get("status") == "active" and not state.get("waiting_for_img"):
            q_num = state["q_num"]
            limit = TIME_LIMITS.get(q_num)
            
            if limit:
                start_t = state.get("start_time", now)
                if now - start_t > limit:
                    state["status"] = "waiting_for_prison"
                    state["prison_deadline"] = now + 1200 
                    save_state(game_state)
                    
                    team_chan = bot.get_channel(cid)
                    if team_chan:
                        await team_chan.send(
                            f"Time's up. You failed to solve Question {q_num} in time.\n"
                            f"Send a member to prison within **20 minutes** or you are disqualified."
                        )
                    
                    mod_chan = bot.get_channel(MOD_CHANNEL_ID)
                    if mod_chan:
                        msg = await mod_chan.send(
                            f"<@&{MOD_ROLE_ID}> 🚨 **Time Expired** for <#{cid}> on Q{q_num}.\n"
                            f"They have 20 mins to send a prisoner. React ✅ when prisoner arrives to resume."
                        )
                        await msg.add_reaction("✅")
        
        elif state.get("status") == "waiting_for_prison":
            deadline = state.get("prison_deadline", now + 1200)
            if now > deadline:
                state["status"] = "disqualified"
                save_state(game_state)
                
                team_chan = bot.get_channel(cid)
                if team_chan:
                    await team_chan.send("20 minutes passed. Team disqualified.")
                
                mod_chan = bot.get_channel(MOD_CHANNEL_ID)
                if mod_chan:
                    await mod_chan.send(f"<#{cid}> disqualified for missing prison deadline.")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    bot.add_view(TeamView())
    if not game_timer_loop.is_running():
        game_timer_loop.start()

@bot.command()
@commands.has_permissions(administrator=True)
async def disqualify(ctx, role: discord.Role):
    if ctx.channel.id != MOD_CHANNEL_ID:
        return
        
    target_channels = load_target_channels()
    target_cid = None
    
    for cid in target_channels:
        channel = bot.get_channel(cid)
        if channel:
            if role in channel.overwrites or (channel.category and role in channel.category.overwrites):
                target_cid = cid
                break
            
    if not target_cid:
        await ctx.send(f"could not find channel for `{role.name}`.")
        return
        
    if target_cid in game_state:
        game_state[target_cid]["status"] = "disqualified"
        save_state(game_state)
        
        team_chan = bot.get_channel(target_cid)
        if team_chan:
            await team_chan.send("Your team has been disqualified. All members are in prison.")
        await ctx.send(f"Disqualified {role.name} (<#{target_cid}>).")
    else:
        await ctx.send("team not active in game state.")

@bot.command()
@commands.has_permissions(administrator=True)
async def spawn_teams(ctx):
    if ctx.channel.id != WELCOME_CHANNEL_ID:
        return
    await ctx.send("select your team below. warning: this choice is permanent and cannot be changed.", view=TeamView())

@bot.command()
@commands.has_permissions(administrator=True)
async def configure_channels(ctx):
    if ctx.channel.id != MOD_CHANNEL_ID:
        return
        
    target_channels = load_target_channels()
    count = 0
    for cid in target_channels:
        channel = bot.get_channel(cid)
        if channel:
            await channel.edit(sync_permissions=True)
            overwrite = channel.overwrites_for(ctx.guild.default_role)
            overwrite.read_message_history = False
            overwrite.use_application_commands = True
            if hasattr(overwrite, 'use_external_apps'):
                overwrite.use_external_apps = True
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
            count += 1
    await ctx.send(f"synced and configured permissions for {count} channels.")

@bot.command()
@commands.has_permissions(administrator=True)
async def purge_channels(ctx):
    if ctx.channel.id != MOD_CHANNEL_ID:
        return
        
    target_channels = load_target_channels()
    await ctx.send("purging target channels. this might take a moment...")
    count = 0
    for cid in target_channels:
        channel = bot.get_channel(cid)
        if channel:
            await channel.purge(limit=None)
            count += 1
    await ctx.send(f"purged chat history in {count} channels.")

@bot.command()
@commands.has_permissions(administrator=True)
async def leaderboard(ctx):
    if ctx.channel.id != MOD_CHANNEL_ID:
        return
        
    if not game_state:
        await ctx.send("no active game state right now.")
        return
        
    sorted_teams = sorted(game_state.items(), key=lambda item: item[1]["q_num"], reverse=True)
    lines = []
    for rank, (cid, state) in enumerate(sorted_teams, 1):
        status_tag = f" ({state.get('status', 'active')})" if state.get('status') != "active" else ""
        lines.append(f"{rank}. <#{cid}> - question {state['q_num']}{status_tag}")
        
    chunk = "**leaderboard:**\n"
    for line in lines:
        if len(chunk) + len(line) > 1900:
            await ctx.send(chunk)
            chunk = ""
        chunk += line + "\n"
    if chunk:
        await ctx.send(chunk)

@bot.command()
@commands.has_permissions(administrator=True)
async def broadcast_start(ctx):
    global BROADCAST_SENT
    if ctx.channel.id != MOD_CHANNEL_ID:
        return

    if BROADCAST_SENT:
        await ctx.send("Broadcast already sent. Restart bot to reset.")
        return

    target_channels = load_target_channels()
    if not target_channels:
        await ctx.send("No channels found.")
        return

    for cid in target_channels:
        channel = bot.get_channel(cid)
        if channel:
            game_state[cid] = {
                "q_num": 1, 
                "waiting_for_img": False,
                "status": "active",
                "start_time": time.time()
            }
            file = await get_drive_file("1")
            time_msg = get_time_text(1)
            await channel.send(f"Game Started! Attach your working image and type the numerical answer in the SAME message.\n{time_msg}", file=file)
    
    BROADCAST_SENT = True
    save_state(game_state)
    await ctx.send("Broadcast sent and locked.")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id not in game_state:
        await bot.process_commands(message)
        return

    state = game_state[message.channel.id]
    
    if state.get("status") != "active":
        await bot.process_commands(message)
        return

    q_num = state["q_num"]
    user_input = message.content.strip()

    if not state.get("waiting_for_img", False):
        if user_input == str(ANSWERS.get(q_num)):
            if message.attachments:
                state["waiting_for_img"] = True
                save_state(game_state)
                
                mod_chan = bot.get_channel(MOD_CHANNEL_ID)
                if mod_chan:
                    forward = await mod_chan.send(
                        f"<@&{MOD_ROLE_ID}> Verification for <#{message.channel.id}> (Q{q_num}):",
                        file=await message.attachments[0].to_file()
                    )
                    await forward.add_reaction("✅")
                    await forward.add_reaction("❌")
                    await message.channel.send("Answer and image received. Sent to mods for verification.")
            else:
                await message.channel.send("Correct number, but you must attach your working image in the same message.")
        
        elif user_input.isdigit():
            await message.channel.send(f"{user_input} is incorrect for Q{q_num}.")

    await bot.process_commands(message)

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot or reaction.message.channel.id != MOD_CHANNEL_ID:
        return

    content = reaction.message.content
    try:
        target_id = int(content.split("<#")[1].split(">")[0])
    except:
        return
        
    if "Time Expired" in content:
        if str(reaction.emoji) == "✅" and game_state[target_id].get("status") == "waiting_for_prison":
            game_state[target_id]["status"] = "active"
            game_state[target_id]["start_time"] = time.time()
            save_state(game_state)
            
            q_num = game_state[target_id]["q_num"]
            file = await get_drive_file(str(q_num))
            time_msg = get_time_text(q_num)
            target_chan = bot.get_channel(target_id)
            
            if target_chan:
                await target_chan.send(f"Prisoner verified. Attempt Q{q_num} again. Timer restarted.\n{time_msg}", file=file)
            await reaction.message.channel.send(f"Resumed <#{target_id}> on Q{q_num}.")
        return

    if "Verification for" in content:
        if str(reaction.emoji) == "✅":
            game_state[target_id]["q_num"] += 1
            game_state[target_id]["waiting_for_img"] = False
            game_state[target_id]["start_time"] = time.time() 
            save_state(game_state)
            
            new_q = game_state[target_id]["q_num"]
            file = await get_drive_file(str(new_q))
            time_msg = get_time_text(new_q)
            target_chan = bot.get_channel(target_id)
            
            if target_chan:
                await target_chan.purge(limit=None)
                await target_chan.send(f"Verified. Moving to Question {new_q}:\n{time_msg}", file=file)
                
        elif str(reaction.emoji) == "❌":
            game_state[target_id]["waiting_for_img"] = False
            save_state(game_state)
            target_chan = bot.get_channel(target_id)
            if target_chan:
                await target_chan.send("Verification failed. Re-enter the answer and attach a clearer image in the same message.")

bot.run(TOKEN)
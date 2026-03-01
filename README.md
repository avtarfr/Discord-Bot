# Bot Commands  

**!purge_channels**: Purges all channels  
**!configure_channels**: Sets permissions for all channels  
**!spawn_teams**: Inititates the team-role selection procedure **(RAN IN #announcements)**  
**!broadcast_start**: Starts the game  
**!leaderboard**: Displays leaderboard  

# Danger Zone Commands  
**!disqualify @team_role**: Disqualifies the team  
**!reset_game**: Resets game_state.json (Resets the entire game)  
**!stop_bot**: Stops the Bot  


# Bot Working
The bot integrates Google Drive with channel IDs and role IDs.  
The process begins by purging all team channels and making sure that #announcements is clear of all messages.  
Next, all channels are configured to have a standard set of permissions. The permissions ensure users can't read the message history of messages sent while they were offline.  
Next, teams are requested to choose their team number, which grants them access to the respective team channels, i.e. team-X-chat and team-X-cmd. team-X-chat is used to communicate with moderators and team-X-cmd is used to communicate with the bot.  
Next, the game is initiated. This sends Q1 to all **active teams** (i.e., team roles with at least 1 member).  
The teams now have to enter a numerical value with an attached image. Since there is a 5-minute slow mode, spam is prevented. All string messages are ignored. All integer messages that are not the answer to the question are considered incorrect. If the correct answer is linked to an image, the image is forwarded to the mods-only channel, and the mods are pinged. The mods then have to verify the image. If the image is verified, the team moves on to the next question. If the team image is incorrect, they have to re-enter it.  
For timed questions, say a question has a timer of 5 minutes, then the team has to answer it in 5 minutes. If not, they are told to send a member to the prison (LHC) within 20 minutes, and the mods are sent a message to tick whether the prisoner has been received. If the prisoner isn't received, the team is disqualified. If the prisoner is received, the mod ticks the message, and the team is given the question to attempt again, and the process repeats until all members of the team are either in prison, resulting in disqualification (has to be done manually via command), or the team solves the question and all members of the team are released out of the prison.


# Role of Moderators
1) Make sure all images sent contain the entire team and the location is correct, and the images are verified/rejected immediately afterwards
2) Make sure prisoners are recorded on time, and the tick mark is done immediately afterwards

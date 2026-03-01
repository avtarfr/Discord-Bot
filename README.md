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
The bot is an integration between Google Drive and channel IDs and role IDs.  
The process begins by purging all team channels and making sure that #announcements is clear of all messages.  
Next, all channels are configured to have a standard set of permissions. The permissions are so that users can't read the message history of messages that were sent when they were offline.  
Next, teams are requested to choose their team number which grants them access to the respective team channels, i.e. team-X-chat and team-X-cmd. team-X-chat is used to communicate with moderators and team-X-cmd is used to communicate with the bot.  
Next, the game is initiated. This sends Q1 to all **active teams** (i.e., team roles with at least 1 member).  
The teams now have to enter a numerical value with an attached image. Since there is a slow mode of 5 minutes, spam is prevented. All string messages are ignored. All integer messages that are not the answer to the question are considered incorrect. If the correct answer is linked with an image, the image is then forwarded to the mods-only channel and the mods are pinged about it. The mods then have to verify the image. If the image is verified, the team moves on to the next question. If the team image is wrong, they have to enter the image again.  

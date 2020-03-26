import discord
import re
import mysql.connector
from mysql.connector import Error
import urllib.request
import subprocess
import time
import requests
import random
from discord.utils import get
import discord.utils
from datetime import datetime
from discord import Webhook, RequestsWebhookAdapter, File
import csv

webhook = { }
client = discord.Client()
server_monsters = { }
server_encounters = { }
server_party = { } 
server_party_chars = {} 
guild_settings = { }
monster_health = { }
available_points = { }

async def log_message(log_entry):
    current_time_obj = datetime.now()
    current_time_string = current_time_obj.strftime("%b %d, %Y-%H:%M:%S.%f")
    print(current_time_string + " - " + log_entry, flush = True)
    
async def commit_sql(sql_query, params = None):
    try:
        connection = mysql.connector.connect(host='localhost', database='CharaTron', user='REDACTED', password='REDACTED')    
        cursor = connection.cursor()
        result = cursor.execute(sql_query, params)
        connection.commit()
        return True
    except mysql.connector.Error as error:
        await log_message("Database error! " + str(error))
        return False
    finally:
        if(connection.is_connected()):
            cursor.close()
            connection.close()
            
                
async def select_sql(sql_query, params = None):
    try:
        connection = mysql.connector.connect(host='localhost', database='CharaTron', user='REDACTED', password='REDACTED')
        cursor = connection.cursor()
        result = cursor.execute(sql_query, params)
        records = cursor.fetchall()
        return records
    except mysql.connector.Error as error:
        await log_message("Database error! " + str(error))
        return None
    finally:
        if(connection.is_connected()):
            cursor.close()
            connection.close()

async def execute_sql(sql_query):
    try:
        connection = mysql.connector.connect(host='localhost', database='CharaTron', user='REDACTED', password='REDACTED')
        cursor = connection.cursor()
        result = cursor.execute(sql_query)
        return True
    except mysql.connector.Error as error:
        await log_message("Database error! " + str(error))
        return False
    finally:
        if(connection.is_connected()):
            cursor.close()
            connection.close()
            
            
async def send_message(message, response):
    await log_message("Message sent back to server " + message.guild.name + " channel " + message.channel.name + " in response to user " + message.author.name + "\n\n" + response)
    message_chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
    for chunk in message_chunks:
        await message.channel.send(">>> " + chunk)
        time.sleep(1)

async def admin_check(userid):
    if (userid != 610335542780887050):
        await log_message(str(userid) + " tried to call an admin message!")
        return False
    else:
        return True
        
async def calculate_damage(attack, defense, damage_multiplier, attacker_level, target_level):
    total_attack_power = attack * damage_multiplier
    level_difference = target_level / attacker_level
    effective_attack_power = total_attack_power * level_difference
    total_damage = effective_attack_power - defense
    if total_damage < 0:
        total_damage = 5
    return total_damage
    
async def calculate_dodge(attacker_agility, target_agility):
    dodge_chance = random.randint(0,100)
    if attacker_agility > target_agility:
        dodge = 20
    else:
        dodge = 40
    if (dodge_chance <= dodge):
        return True
    else:
        return False
        
async def calculate_xp(current_level, opponent_level, damage_done, number_in_party):
    if current_level < opponent_level:
        xp = ((opponent_level - current_level) * damage_done) / number_in_party
    else:
        xp = damage_done / number_in_party
    if xp < 10:
        return 10
    else:
        return xp
        
def role_check(role_required, user):
    for role in user.roles:
        if role.id == role_required:
            return True
            
    return False
    
@client.event
async def on_ready():
    global webhook
    global server_monsters
    global server_encounters
    global server_party
    global server_party_chars
    global guild_settings
    global available_points
    await log_message("Logged in!")
    
    for guild in client.guilds:
        available_points[guild.id] = {}
        server_encounters[guild.id] = False
        server_monsters[guild.id] = {} 
        server_party[guild.id] = {}
        server_party_chars[guild.id] = {}
        guild_settings[guild.id]  =  {}
        for user in guild.members:
            available_points[guild.id][user.id] ={}
            
        for channel in guild.text_channels:
            webhook[channel.id] = await channel.webhooks()
        records = await select_sql("""SELECT ServerId,IFNULL(AdminRole,'0'),IFNULL(GameModeratorRole,'0'),IFNULL(NPCRole,'0'),IFNULL(PlayerRole,'0') FROM GuildSettings;""")
    for row in records:
        server_id = int(row[0])
        guild_settings[server_id]["AdminRole"] = int(row[1])
        guild_settings[server_id]["GameModeratorRole"] = int(row[2])
        guild_settings[server_id]["NPCRole"] = int(row[3])
        guild_settings[server_id]["PlayerRole"] = int(row[4])
            
            
@client.event
async def on_guild_join(guild):
    global available_points
    global server_monsters
    global server_encounters
    global server_party
    global server_party_chars
    global guild_settings
    global monster_health
    await log_message("Joined guild " + guild.name)
    server_encounters[guild.id] = False
    server_monsters[guild.id] = {}     
    server_party[guild.id] = { }
    server_party_chars[guild.id] = { }
    guild_settings[guild.id] = {}
    available_points[guild.id] = { }
    for user in guild.members:
        available_points[guild.id][user.id] = 0
    
    
@client.event
async def on_guild_remove(guild):
    await log_message("Left guild " + guild.name)
    
@client.event
async def on_message(message):
    global webhook
    global server_monsters
    global server_encounters
    global server_party
    global server_party_chars
    global guild_settings
    global avvailable_points
    if message.author.bot:
        return
    if message.author == client.user:
        return
           
    if message.content.startswith('='):

            
        command_string = message.content.split(' ')
        command = command_string[0].replace('=','')
        parsed_string = message.content.replace("=" + command + " ","")
        await log_message("Command " + message.content + " called by " + message.author.name + " from server " + message.guild.name + " in channel " + message.channel.name)
        await log_message("Parsed string: " + parsed_string)
        
        
        if command == 'setadminrole':
            if message.author != message.guild.owner:
                await send_message(message, "Only the server owner can set the admin role!")
                return
            if len(message.role_mentions) > 1:
                await send_message(message, "Only one role can be defined as the admin role!")
                return
            role_id = message.role_mentions[0].id
            guild_settings[message.guild.id]["AdminRole"] = role_idAn
            result = await commit_sql("""INSERT INTO GuildSettings (ServerId,AdminRole) Values (%s,%s);""",  (str(message.guild.id), str(role_id)))
            if result:
                await send_message(message, "Admin role successfully set!")
            else:
                await send_message(message, "Database error!")
        if command == 'help' or command == 'info':
            if parsed_string == '=help' or parsed_string == '=info':
                response = "**Welcome to Chara-Tron, the Discord RP Bot Master!**\n\n*Using Help:*\n\nType =info or =help followed by one of these categories:\n\n**general**: Not commands, but information on how the bot works.\n**setup**: Commands for getting the bot running.\n**characters**: Commands for managing characters.\n**npcs**: Commands for managing NPCs.\n**monsters** Commands for managing monsters.\n**equipment**: Commands for managing equipment.\n**encounters**: Commands for managing encounters.\n**melee** Commands for managing melee attacks.\n**spells** Commands for managing spells.\n**sparring**: Commands for managing sparring.\n**inventory**: Commands for managing inventory.\n**economy**: Commands for buying, selling and the guild bank.\n**fun**: Commands for old time RP fun.\n"
            elif parsed_string == 'setup':
                response = "**SETUP COMMANDS**\n\n**=setadminrole @Role**: *Owner* Set the admin role. This must be done before any other setup. This can only be done by a server owner. See general for role descriptions.\n**=setplayerrole @Role** *Admin* Set the player role.\n**=setgmrole @Role** *Admin* Set the Game Moderator role.\n**=setnpcrole @Role** *Admin* Set the NPC manager role.\n**=listroles** *None* List the server roles.\n"
            elif parsed_string == 'characters':
                response = "**CHARACTER COMMANDS**\n\n**=getchartemplate** *None* Get the fields for a new character setup.\n**=newchar** *Player* Set up a new character. See the template for field format.\n**=setstattemplate** *None* Get the statistics template for characters.\n**=setcharstats** *Admin* Modify character statistics.\n**=editchar** *Player* Edit an existing character's profile.\n**=setcharbio** *Player* Set a character's biography (free text).\n**=setcharskills** *Player* Set the character's skills (free text).\n**=setcharstrengths** *Player* Set the character's strengths (free text).\n**=setcharweaknesses** *Player* Set the character's weaknesses (free text).\n**=setcharpowers** *Player* Set the character's powers and abilities (free text).\n**=setcharpersonality** *Player* Set the character's personality (free text).\n**=deletechar** *Player* Delete a character.\n**=getcharskills** *None* Get the current list of character spells and melee attacks.\n**=getcharprofile** *None* Get a character's complete profile.\n**=listmychars** *Player* List the current user's characters.\n**=listallchars** *None* List all server characters and their owners.\n**=listuserchars @User** *None* List a user's characters.\n"
            elif parsed_string == 'npcs':
                response = "**NPC COMMANDS**\n\n**=npctemplate** *None* Get the template for NPCs.\n**=newpc** *NPC* Create a new NPC.\n**=postnpc** *Player* Post as an NPC if you are in the allowed user list.\n**=editnpc** *NPC* Edit an NPC.\n**=deletenpc** *NPC* Delete an NPC.\n**=listnpcs**: *None* List all server NPCs.\n"
            elif parsed_string == 'monsters':
                response = "**MONSTER COMMANDS**\n\n**=newmonstertemplate** *None* Get the template for a new monster.\n**=newmonster** *Game Moderator* Add a new monster to the game.\n**=editmonster** *Game Moderator* Edit an existing monster.\n**=deletemonster** *Game Moderator* Delete a monster from the game.\n"
            elif parsed_string == 'equipment':
                response = "**EQUIPMENT COMMANDS**\n\n**=newequiptemplate** *None* Get the equipment template.\n**=newequip** *Admin* Add a new item to the game.\n**=editequip** Edit an existing item.\n**=deleteequip** Remove an item from the game.\n**=listequip** List all equipment on the server.\n"
            elif parsed_string == 'encounters':
                response = "**ENCOUNTER COMMANDS**\n\n**=newparty @user1 @user2** *Game Moderator* Set a new party with the specified users.\n**=disbandparty** *Game Moderator* Disband the current server party.\n**=setencounterchar <character name>** *Player* Set the player's character for the encounter.\n**=encountermonster <monster name>** *Game Moderator* Begin the monster encounter.\n**=monsterattack** *Game Moderator* Have the monster attack a random party member.\n**=castmonster <spell name>** *Player* Attack the monster with the specified spell.\n**attackmonster <melee attack name>** *Player* Attack the monster with the specified melee attack.\n**=abortencounter** *Game Moderator* End the encounter with no health penalty *and* no experience gained.\n"
            elif parsed_string == 'melee':
                response = "**MELEE COMMANDS**\n\n**=getmeleetemplate** *None* Get the new melee attack template.\n**=newmelee** *Admin* Create a new melee attack.\n**=editmelee** *Admin* Edit an existing melee attack.\n**=deletemelee** *Admin* Delete a melee attack.\n**=listmelees** *None* List all melee attacks on the server.\n**=givemelee** *Admin* Give a character a melee attack.\n**=takemelee** *Admin* Take a melee attack from a character.\n"
            elif parsed_string == 'spells':
                response = "**SPELL COMMANDS**\n\n**=getspelltemplate** *None* Get the new spell template.\n**=newspell** *Admin* Create a new spell.\n**=editspell** *Admin* Edit an existing spell.\n**=deletespell** Delete a spell.\n**=listspells** *Admin* List all server spells.\n**=givespell** *Admin* Give a character a spell.\n**=takespell** *Admin* Take a spell away from a character.\n"
            elif parsed_string == 'sparring':
                response = "**SPARRING COMMANDS**\n\nUNDER CONSTRUCTION\n"
            elif parsed_string == 'inventory':
                response = "**INVENTORY COMMANDS**\n\n**=myitems <character name>** List your character's items.\n"
            elif parsed_string == 'economy':
                response == "**ECONOMY COMMANDS**\n\n**=givecurrency** *Game Moderator* Give a character money!\nUNDER CONSTRUCTION\n"
            elif parsed_string == 'fun':
                response = "**FUN FUN FUN COMMANDS**\n\n**=lurk** *None* Post a random lurk command.\n**=ooc** Post as the bot with OOC brackets.\n**=randomooc @user** Do something random to another user.\n**=roll x**d**y *None* Roll x number of y-sided dice.\n"
            elif parsed_string == 'general':
                response = "**GENERAL INFO**\n\nThis bot supports character profiles, leveling/experience, sparring, random encounters, monsters, equipment/inventory/economy, and spells/melee attacks. Most commands take the form of =command followed by fields on a single line, starting with the field name, followed by a colon (:), then a space, then the value. For example, **=newchar Name: Evil Terror\nRace: Big Bad**\n\nSome commands only require the name of the character or spell, like **=castmonster Magic Missile**\n\n**ROLES**\n\nThere are four roles required to use the bot.\n**Admin:** The admin can run all commands of the bot, such as adding and deleting spells or items. The server owner must set the admin role.\n**Game Moderator:** The game moderator is able to start random encounters, add or delete monsters, give money, and give items.\n**NPC Manager:** The NPC manager is able to create, edit and delete NPCs.\n**Player:** A player is able to add, edit, and delete their character profile, and play as their character, and post as NPCs if allowed, and buy and sell items, and trade with other players. It is up to server staff to manage character approval. The bot plays no moderator role on Discord.\n\n**LEVELING**\n\nLeveling is granted by gaining experience. Experience is gained by random encounters, sparring, or granted by a game moderator. A new level is achieved when experience totals twenty times the current level.\n\n"

            await send_message(message, response)
        if "AdminRole" not in guild_settings[message.guild.id].keys():
            await send_message(message, "Admin role not set! Please set an admin role using the command =setadminrole @Role")
            return
        if command == 'initialize':
            if not await admin_check(message.author.id):
                await send_message(message, "This command is admin only!")
                return
            
            create_profile_table = """CREATE TABLE CharacterProfiles (Id int auto_increment, ServerId varchar(40), UserId varchar(40), FirstName varchar(50), LastName varchar(100), Age Int, Race varchar(30), Gender varchar(20), Height varchar(10), Weight varchar(10), PlayedBy varchar(40), Origin varchar(100), Occupation varchar(100), Personality TEXT, Biography TEXT, Description TEXT, Strengths TEXT, Weaknesses TEXT, Powers TEXT, Skills TEXT, Attack Int, Defense Int, MagicAttack Int, Health Int, Mana Int, Level Int, Experience Int, Stamina Int, Agility Int, Intellect Int, Charisma Int, Currency DECIMAL(12,2), PictureLink varchar(1024), PRIMARY KEY (Id));"""
            create_npc_table = """CREATE TABLE NonPlayerCharacters (Id int auto_increment, ServerId varchar(40), UserId varchar(40), UsersAllowed varchar(1500), CharName varchar(100), PictureLink varchar(1024), Shortcut varchar(20), PRIMARY KEY (Id));"""
            create_spell_table = """CREATE TABLE Spells (Id int auto_increment, ServerId varchar(40), UserId varchar(40), SpellName varchar(100), Element varchar(50), ManaCost Int, MinimumLevel int, DamageMultiplier Int, Description TEXT, PRIMARY KEY (Id));"""
            create_melee_table = """CREATE TABLE Melee (Id int auto_increment, ServerId varchar(40), UserId varchar(40), AttackName varchar(100), StaminaCost Int, MinimumLevel Int,DamageMultiplier Int, Description TEXT, PRIMARY KEY (Id));"""
            create_melee_char_table = """CREATE TABLE MeleeSkills (Id int auto_increment, ServerId varchar(40), UserId varchar(40), CharacterId int, MeleeId int, PRIMARY KEY (Id));"""
            create_magic_char_table = """CREATE TABLE MagicSkills (Id int auto_increment, ServerId varchar(40), UserId varchar(40), CharacterId int, SpellId int, PRIMARY KEY (Id));"""
            create_equipment_table = """CREATE TABLE Equipment (Id int auto_increment, ServerId varchar(40), UserId varchar(40), EquipmentName varchar(100), EquipmentDescription TEXT, EquipmentCost DECIMAL(7,2), MinimumLevel Int, StatMod varchar(30), Modifier Int, PRIMARY KEY (Id));"""
            create_inventory_table = """CREATE TABLE Inventory (Id int auto_increment, ServerId varchar(40), UserId varchar(40), CharacterId int, EquipmentId int, PRIMARY KEY (Id));"""
            create_monster_table = """CREATE TABLE Monsters (Id int auto_increment, Serverid varchar(40), UserId varchar(40), MonsterName varchar(100), Description TEXT, Health Int, Level Int, Attack Int, Defense Int, Element varchar(50), MagicAttack Int, PictureLink varchar(1024), PRIMARY KEY(Id));"""
            
            create_guild_settings_table = """CREATE TABLE GuildSettings (Id int auto_increment, ServerId VARCHAR(40),  GuildName VarChar(100), GuildBankBalance DECIMAL(12,2), AdminRole VARCHAR(40), GameModeratorRole VARCHAR(40), PlayerRole VARCHAR(40), NPCRole VARCHAR(40), PRIMARY KEY(Id));"""
            
            result = await execute_sql(create_profile_table)
            if not result:
                await send_message(message, "Database error with profile!")
                return
                
            result = await execute_sql(create_npc_table)
            if not result:
                await send_message(message, "Database error with NPCs!")
                return  
                
            result = await execute_sql(create_spell_table)
                    
            if not result:
                await send_message(message, "Database error with spells!")
                return
                
            result = await execute_sql(create_melee_table)
            if not result:
                await send_message(message, "Database error with melee!")
                return
                
            result = await execute_sql(create_melee_char_table)
            if not result:
                await send_message(message, "Database error with melee character!")
                return    
                
            result = await execute_sql(create_magic_char_table)
            if not result:
                await send_message(message, "Database error with magic character!")
                return
                
            result = await execute_sql(create_equipment_table)
            if not result:
                await send_message(message, "Database error with equipment!")
                return
                
            result = await execute_sql(create_inventory_table)
            if not result:
                await send_message(message, "Database error with inventory!")
                return
            result = await execute_sql(create_monster_table)
            if not result:
                await send_message(message, "Database error with monsters!")
                return
            result = await execute_sql(create_guild_settings_table)
            if not result:
                await send_message(message, "Database error with guild settings!")
                return
            await send_message(message, "Databases initialized!")
        elif command == 'deleteall':
            if not await admin_check(message.author.id):
                await send_message(message, "This command is admin only!")
                return
            drop_all_tables = """DROP TABLE IF EXISTS CharacterProfiles; DROP TABLE IF EXISTS Inventory; DROP TABLE IF EXISTS Equipment; DROP TABLE IF EXISTS NonPlayerCharacters; DROP TABLE IF EXISTS Spells; DROP TABLE IF EXISTS Melee; DROP TABLE IF EXISTS MagicSkills; DROP TABLE IF EXISTS MeleeSkills; DROP TABLE IF EXISTS Monsters;"""
            result = await execute_sql(drop_all_tables)
            if result:
                await send_message(message, "All tables dropped.")
            else:
                await send_message(message, "Database error!")
                
        elif command == 'roll':
            dice_re = re.compile(r"(\d+)d(\d+)")
            m = dice_re.match(parsed_string)
            if not m:
                await send_message(message, "Invalid dice command!")
                return
            number_of_dice = m.group(1)
            dice_sides = m.group(2)
            response = "**Dice roll:**\n\n"
            for x in range(0,int(number_of_dice)):
                response = response + str(random.randint(1,int(dice_sides))) + " "
            await send_message(message, response)
        elif command == 'listallchars':
            records = await select_sql("""SELECT FirstName,LastName,Level,UserId FROM CharacterProfiles WHERE ServerId=%s;""", (str(message.guild.id),))
            if not records:
                await send_message(message, "No characters found for this server!")
                return
            response = "**SERVER CHARACTER LIST**\n\n"
            for row in records:
                response = response + row[0] + " " + row[1] + ", level " + str(row[2]) + ", mun: " + str(message.guild.get_member(int(row[3]))) + "\n"
            await send_message(message, response)
        elif command == 'listuserchars':
            if not message.mentions:
                await send_message(message, "You didn't specify a user!")
                return
            user = message.mentions[0]
            user_id = user.id
            records = await select_sql("""SELECT FirstName,LastName,Level FROM CharacterProfiles WHERE ServerId=%s AND UserId=%s;""",(str(message.guild.id),str(user_id)))
            if not records:
                await send_message(message, "No records found for that user!")
                return
            response = "**USER CHARACTER LIST**\n\n"
            for row in records:
                response = response + row[0] + " " + row[1] + ", level " + int(row[2]) + "\n"
            await send_message(message,response)                
        elif command == 'newchar':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await send_message(message, "You must have the player role to create a new character.")
                return
            name_re = re.compile(r"Name: (?P<firstname>.+?) (?P<lastname>.+)")
            age_re = re.compile(r"Age: (?P<age>.+)")
            race_re = re.compile(r"Race: (?P<race>.+)")
            gender_re = re.compile(r"Gender: (?P<gender>.+)")
            height_re = re.compile(r"Height: (?P<height>.+)")
            weight_re = re.compile(r"Weight: (?P<weight>.+)")
            pb_re = re.compile(r"Played by: (?P<playedby>.+)")
            origin_re = re.compile(r"Origin: (?P<origin>.+)")
            occupation_re = re.compile(r"Occupation: (?P<occupation>.+)")
            picture_re = re.compile(r"Picture Link: (?P<picturelink>.+)")
            
            create_char_entry = "INSERT INTO CharacterProfiles (ServerId, UserId, FirstName, LastName, "
            create_values = "VALUES (%s, %s, %s, %s, "
            char_tuple = (str(message.guild.id), str(message.author.id))
            for line in parsed_string.split('\n'):
                await log_message ("Line: " + line)
                m = name_re.search(line)
                if m:
                    first_name = m.group('firstname')
                    last_name = m.group('lastname')
                    char_tuple = char_tuple + (first_name, last_name)
                m = age_re.search(line)
                if m:
                    age = m.group('age')
                    create_char_entry = create_char_entry + "Age, "
                    create_values = create_values + "%s, "
                    char_tuple = char_tuple + (age,)
                m = race_re.search(line)
                if m:
                    race = m.group('race')
                    create_char_entry = create_char_entry + "Race, "
                    create_values = create_values + "%s, "
                    char_tuple = char_tuple + (race,)
                m = gender_re.search(line)
                if m:
                    gender = m.group('gender')
                    create_char_entry = create_char_entry + "Gender, "
                    create_values = create_values + "%s, "
                    char_tuple = char_tuple + (gender,)
                m = height_re.search(line)
                if m:
                    height = m.group('height')
                    create_char_entry = create_char_entry + "Height, "
                    create_values = create_values + "%s, "
                    char_tuple = char_tuple + (height,)
                m = weight_re.search(line)
                if m:
                    weight = m.group('weight')
                    create_char_entry = create_char_entry + "Weight, "
                    create_values = create_values + "%s, "
                    char_tuple = char_tuple + (weight,)
                m = pb_re.search(line)
                if m:
                    playedby = m.group('playedby')
                    create_char_entry = create_char_entry + "PlayedBy, "
                    create_values = create_values + "%s, "
                    char_tuple = char_tuple + (playedby,)  
                m = origin_re.search(line)
                if m:
                    origin = m.group('origin')
                    create_char_entry = create_char_entry + "Origin, "
                    create_values = create_values + "%s, "
                    char_tuple = char_tuple + (origin,)
                m = occupation_re.search(line)
                if m:
                    occupation = m.group('occupation')
                    create_char_entry = create_char_entry + "Occupation, "
                    create_values = create_values + "%s, "
                    char_tuple = char_tuple + (occupation,)
                m = picture_re.search(line)
                if m:
                    picture_link = m.group('picturelink')
                    create_char_entry = create_char_entry + "PictureLink, "
                    create_values = create_values + "%s, "
                    char_tuple = char_tuple + (picture_link,)
                    
            create_char_entry = re.sub(r", $","", create_char_entry)
            create_char_entry = create_char_entry + ", Attack, Defense, MagicAttack, Health, Mana, Level, Experience, Stamina, Agility, Intellect, Charisma) " + re.sub(r", $","",create_values) + ", 10, 10, 10, 100, 100, 1, 0, 10, 10, 10, 10);"
            # setcharstats Name: \nAttack: \nDefense: \nMagicAttack: \nHealth: \nMana: \nLevel: \nExperience: \nStamina: \nAgility: \nIntellect: \nCharisma: \n"
            await log_message("SQL: " + create_char_entry)
            result = await commit_sql(create_char_entry, char_tuple)
            if result:
                await send_message(message, "Character " + first_name + " " + last_name + " successfully created.")
            else:
                await send_message(message, "Database error!")
        elif (command == 'newchartemplate'):
            await send_message(message,"**NEW CHARACTER TEMPLATE**\n\n=newchar Name: \nAge: \nRace: \nGender: \nHeight: \nWeight: \nPlayed by: \nOrigin: \nOccupation: \n")
        elif (command == 'getcharprofile'):
            m = re.search(r"(?P<firstname>.+) (?P<lastname>.+)", parsed_string)
            if not m:
                await send_message(message, "No character name specified!")
                return
            first_name = m.group('firstname')
            last_name = m.group('lastname')
            
            get_character_profile = """SELECT FirstName,LastName,IFNULL(Age,' '),IFNULL(Race,' '), IFNULL(Gender,' '), IFNULL(Height,' '), IFNULL(Weight,' '), IFNULL(PlayedBy,' '), IFNULL(Origin,' '), IFNULL(Occupation,' '), UserId,Attack,Defense,MagicAttack,Health,Mana,Level,Experience,Stamina,Agility,Intellect,Charisma, IFNULL(Biography,' '), IFNULL(Currency,' '), IFNULL(Description,' '), IFNULL(Personality,' '), IFNULL(Powers,' '), IFNULL(Strengths,' '), IFNULL(Weaknesses,' '), IFNULL(Skills,' '), IFNULL(PictureLink,' ') FROM CharacterProfiles WHERE FirstName=%s AND LastName=%s AND ServerId=%s;"""
            char_tuple = (first_name, last_name, str(message.guild.id))
            
            records = await select_sql(get_character_profile, char_tuple)
            if len(records) < 1:
                await send_message(message, "No character found by that name!")
                return
            for row in records:
                response = "***CHARACTER PROFILE***\n\n**Mun:** <@" + str(row[10]) + ">\n**Name:** " + row[0] + " " + row[1] +"\n**Age:** " + str(row[2]) + "\n**Race:** "+ row[3] + "\n**Gender:** " +row[4] + "\n**Height:** " + row[5] +  "\n**Weight:** " + row[6] +  "\n**Played by:** " + row[7] + "\n**Origin:** " + row[8] + "\n**Occupation:** " + row[9] + "\n\n**STATS**\n\n**Health:** " + str(row[14]) + "\n**Mana:** " + str(row[15]) + "\n**Attack:** " + str(row[11]) + "\n**Defense:** " + str(row[12]) + "\n**Magic Attack Power:** " + str(row[13]) + "\n**Level:** " + str(row[16]) + "\n**Experience:** " + str(row[17]) + "\n**Stamina:** " + str(row[18]) + "\n**Agility:** " + str(row[19]) + "\n**Intellect:** " + str(row[20]) + "\n**Charisma:** " + str(row[21]) + "\n**Currency:** " + str(row[23])+  "\n\n**ADDITIONAL INFORMATION**\n\n**Biography:** " + row[22] + "\n**Description:**" + row[24] + "\n**Personality:** " + row[25] + "\n**Powers:** " + row[26] + "\n**Strengths:** " + row[27] + "\n**Weaknesses:** " + row[28] + "\n**Skills:** " + row[29] + "\n\n**PICTURE**\n\n" + row[30] + "\n"
            await send_message(message, response)
        elif command == 'editchar':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await send_message(message, "You must have the player role to edit a character.")
                return
            name_re = re.compile(r"Name: (?P<firstname>.+?) (?P<lastname>.+)")
            age_re = re.compile(r"Age: (?P<age>.+)")
            race_re = re.compile(r"Race: (?P<race>.+)")
            gender_re = re.compile(r"Gender: (?P<gender>.+)")
            height_re = re.compile(r"Height: (?P<height>.+)")
            weight_re = re.compile(r"Weight: (?P<weight>.+)")
            pb_re = re.compile(r"Played by: (?P<playedby>.+)")
            origin_re = re.compile(r"Origin: (?P<origin>.+)")
            occupation_re = re.compile(r"Occupation: (?P<occupation>.+)")
            picture_re = re.compile(r"Picture Link: (?P<picturelink>.+)")
            
            create_char_entry = "UPDATE CharacterProfiles SET FirstName=%s, LastName=%s, "
            char_tuple = (str(message.guild.id), str(message.author.id))
            for line in parsed_string.split('\n'):
                await log_message ("Line: " + line)
                m = name_re.search(line)
                if m:
                    first_name = m.group('firstname')
                    last_name = m.group('lastname')
                    char_tuple = char_tuple + (first_name, last_name)
                m = age_re.search(line)
                if m:
                    age = m.group('age')
                    create_char_entry = create_char_entry + "Age=%s, "
                    char_tuple = char_tuple + (age,)
                m = race_re.search(line)
                if m:
                    race = m.group('race')
                    create_char_entry = create_char_entry + "Race=%s, "
                    char_tuple = char_tuple + (race,)
                m = gender_re.search(line)
                if m:
                    gender = m.group('gender')
                    create_char_entry = create_char_entry + "Gender=%s, "
                    char_tuple = char_tuple + (gender,)
                m = height_re.search(line)
                if m:
                    height = m.group('height')
                    create_char_entry = create_char_entry + "Height=%s, "
                    char_tuple = char_tuple + (height,)
                m = weight_re.search(line)
                if m:
                    weight = m.group('weight')
                    create_char_entry = create_char_entry + "Weight=%s, "
                    char_tuple = char_tuple + (weight,)
                m = pb_re.search(line)
                if m:
                    playedby = m.group('playedby')
                    create_char_entry = create_char_entry + "PlayedBy=%s, "
                    char_tuple = char_tuple + (playedby,)  
                m = origin_re.search(line)
                if m:
                    origin = m.group('origin')
                    create_char_entry = create_char_entry + "Origin=%s, "
                    char_tuple = char_tuple + (origin,)
                m = occupation_re.search(line)
                if m:
                    occupation = m.group('occupation')
                    create_char_entry = create_char_entry + "Occupation=%s, "
                    char_tuple = char_tuple + (occupation,)
                m = picture_re.search(line)
                if m:
                    picture_link = m.group('picturelink')
                    create_char_entry = create_char_entry + "PictureLink=%s, "
                    char_tuple = char_tuple + (picture_link,)
            records = await select_sql("""SELECT UserId FROM CharacterProfiles WHERE ServerId=%s AND FirstName=%s AND LastName=%s""",(str(message.guild.id), first_name, last_name))
            if not records:
                await send_message(message, "This character doesn't exist! Check the name.")
                return
            for row in records:
                char_user_id = int(row[0])
            if user_id != message.author.id:
                await send_message(message, "This isn't your character!")
                return
            create_char_entry = re.sub(r", $","", create_char_entry)
            create_char_entry = create_char_entry + "WHERE ServerId=%s;"
            char_tuple = char_tuple + (str(message.guild.id),)
            # setcharstats Name: \nAttack: \nDefense: \nMagicAttack: \nHealth: \nMana: \nLevel: \nExperience: \nStamina: \nAgility: \nIntellect: \nCharisma: \n"
            await log_message("SQL: " + create_char_entry)
            result = await commit_sql(create_char_entry, char_tuple)
            if result:
                await send_message(message, "Character " + first_name + " " + last_name + " successfully edited.")
            else:
                await send_message(message, "Database error!")
        elif command == 'listmychars':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await send_message(message, "You must have the player role to list characters.")
                return
            records = await select_sql("""SELECT FirstName,LastName,Level FROM CharacterProfiles WHERE ServerId=%s AND UserId=%s;""", (str(message.guild.id),str(message.author.id)))
            if not records:
                await send_message(message, "You don't have any characters! Use =newchar to create a character!")
                return
            response = "**Characters for " + message.author.name + ":**\n\n" 
            for row in records:
                response = response + row[0] + " " + row[1] + " Level: " + str(row[2]) + "\n"
            await send_message(message, response)
        elif command == 'getcharskills':
            m = re.search(r"(?P<firstname>.+) (?P<lastname>.+)", parsed_string)
            if not m:
                await send_message(message, "No character name specified!")
                return
            first_name = m.group('firstname')
            last_name = m.group('lastname')
            response = "***CHARACTER SKILLS***\n\n**Character Name:** " + first_name + " " + last_name + "\n\n**MAGIC SKILLS**\n\n"
            records = await select_sql("""SELECT Id FROM CharacterProfiles WHERE ServerId=%s AND FirstName=%s AND LastName=%s;""",(str(message.guild.id), first_name, last_name))
            if len(records) == 0:
                await send_message(message, "No character found with that name!")
                return
            for row in records:
                char_id = row[0]
            
            records = await select_sql("""SELECT SpellId FROM MagicSkills WHERE CharacterId=%s;""", (char_id,))
            for row in records:
                spell_records = await select_sql("""SELECT SpellName FROM Spells WHERE Id=%s;""",(row[0],))
                for spell_row in spell_records:
                    response = response + spell_row[0] + "\n"
            response = response + "\n**MELEE SKILLS**\n\n"
            records = await select_sql("""Select MeleeId FROM MeleeSkills WHERE CharacterId=%s""", (char_id,))
            for row in records:
                attack_records = await select_sql("""SELECT AttackName FROM Melee WHERE Id=%s""",(row[0],))
                for attack_row in attack_records:
                    response = response + attack_row[0] + "\n"
            await send_message(message, response)
            
        elif (command == 'setstattemplate'): 
            response = "***CHARACTER STATISTIC TEMPLATE:***\n\n=setcharstats Name: \nAttack: \nDefense: \nMagicAttack: \nHealth: \nMana: \nLevel: \nExperience: \nStamina: \nAgility: \nIntellect: \nCharisma: \n"
            await send_message(message, response)
        elif (command == 'setcharstats'):
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message("You must be a member of the bot admin role to modify character statistics!")
                return
            name_re = re.compile(r"Name: (?P<firstname>.+?) (?P<lastname>.+)")
            attack_re = re.compile(r"^Attack: (?P<attack>.+)")
            defense_re = re.compile(r"Defense: (?P<defense>.+)")
            magicattack_re = re.compile(r"Magic Attack: (?P<magicattack>.+)")
            health_re = re.compile(r"Health: (?P<health>.+)")
            mana_re = re.compile(r"Mana: (?P<mana>.+)")
            level_re = re.compile(r"Level: (?P<level>.+)")
            experience_re = re.compile(r"Experience: (?P<experience>.+)")
            stamina_re = re.compile(r"Stamina: (?P<stamina>.+)")
            agility_re = re.compile(r"Agility: (?P<agility>.+)")
            intellect_re = re.compile(r"Intellect: (?P<intellect>.+)")
            charisma_re = re.compile(r"Charisma: (?P<charisma>.+)")
            
            create_char_entry = "UPDATE CharacterProfiles SET "
            create_values = " "
            char_tuple = ()
            for line in parsed_string.split('\n'):
                await log_message ("Line: " + line)
                m = name_re.search(line)
                if m:
                    first_name = m.group('firstname')
                    last_name = m.group('lastname')
             
                m = attack_re.search(line)
                if m:
                    attack = m.group('attack')
                    create_char_entry = create_char_entry + "Attack=%s, "
                    char_tuple = char_tuple + (attack,)
                m = defense_re.search(line)
                if m:
                    defense = m.group('defense')
                    create_char_entry = create_char_entry + "Defense=%s, "

                    char_tuple = char_tuple + (defense,)
                m = magicattack_re.search(line)
                if m:
                    magicattack = m.group('magicattack')
                    create_char_entry = create_char_entry + "MagicAttack=%s, "

                    char_tuple = char_tuple + (magicattack,)
                m = health_re.search(line)
                if m:
                    health = m.group('health')
                    create_char_entry = create_char_entry + "Health=%s, "

                    char_tuple = char_tuple + (health,)
                m = mana_re.search(line)
                if m:
                    mana = m.group('mana')
                    create_char_entry = create_char_entry + "Mana=%s, "

                    char_tuple = char_tuple + (mana,)
                m = level_re.search(line)
                if m:
                    level = m.group('level')
                    create_char_entry = create_char_entry + "Level=%s, "
                    char_tuple = char_tuple + (level,)  
                m = experience_re.search(line)
                if m:
                    experience = m.group('experience')
                    create_char_entry = create_char_entry + "Experience=%s, "
                    char_tuple = char_tuple + (experience,)
                m = stamina_re.search(line)
                if m:
                    stamina = m.group('stamina')
                    create_char_entry = create_char_entry + "Stamina=%s, "

                    char_tuple = char_tuple + (stamina,)
                m = agility_re.search(line)
                if m:
                    agility = m.group('agility')
                    create_char_entry = create_char_entry + "Agility=%s, "

                    char_tuple = char_tuple + (agility,)
                m = intellect_re.search(line)
                if m:
                    intellect = m.group('intellect')
                    create_char_entry = create_char_entry + "Intellect=%s, "

                    char_tuple = char_tuple + (intellect,)
                    
                m = charisma_re.search(line)
                if m:
                    agility = m.group('charisma')
                    create_char_entry = create_char_entry + "Charisma=%s, "

                    char_tuple = char_tuple + (charisma,)
            create_char_entry = re.sub(r", $","", create_char_entry)
            create_char_entry = create_char_entry + " WHERE ServerId=%s AND FirstName=%s AND LastName=%s;"
            char_tuple = char_tuple + (str(message.guild.id), first_name, last_name)
            await log_message("SQL: " + create_char_entry)
            result = await commit_sql(create_char_entry, char_tuple)
            if result:
                await send_message(message, "Character " + first_name + " " + last_name + " successfully updated.")
            else:
                await send_message(message, "Database error!")
        elif command == 'setcharbio':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await send_message(message, "You must be member of the player role to add a biography!")
                return

            name_re = re.compile(r"Name: (?P<firstname>.+?) (?P<lastname>.+)")
            bio_re = re.compile(r"Biography: (?P<bio>.+)", re.S | re.MULTILINE)
            m = name_re.search(parsed_string)
            if m:
                first_name = m.group('firstname')
                last_name = m.group('lastname')
            m = bio_re.search(parsed_string)
            if m:
                bio = m.group('bio')
            records = await select_sql("""SELECT UserId FROM CharacterProfiles WHERE ServerId=%s AND FirstName=%s AND LastName=%s;""",(str(message.guild.id), first_name, last_name))
            for row in records:
                user_id = row[0]
            if int(user_id) != message.author.id or not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message("This is not your character! Please only add a biography to your character!")
                return
            update_bio = """UPDATE CharacterProfiles SET Biography=%s WHERE ServerId=%s AND FirstName=%s AND LastName=%s;"""
            update_bio_tuple = (bio, str(message.guild.id), first_name, last_name)
            result = await commit_sql(update_bio, update_bio_tuple)
            if result:
                await send_message(message, "Biography of character " + first_name + " " + last_name + " updated successfully.")
            else:
                await send_message(message, "Database error!")
        elif command == 'setcharstrengths':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await send_message(message, "You must be member of the player role to add a biography!")
                return        
            name_re = re.compile(r"Name: (?P<firstname>.+?) (?P<lastname>.+)")
            strengths_re = re.compile(r"Strengths: (?P<strengths>.+)", re.S | re.MULTILINE)
            m = name_re.search(parsed_string)
            if m:
                first_name = m.group('firstname')
                last_name = m.group('lastname')
            m = strengths_re.search(parsed_string)
            if m:
                strengths = m.group('strengths')
            records = await select_sql("""SELECT UserId FROM CharacterProfiles WHERE ServerId=%s AND FirstName=%s AND LastName=%s;""",(str(message.guild.id), first_name, last_name))
            for row in records:
                user_id = row[0]
            if int(user_id) != message.author.id or not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message("This is not your character! Please only add strengths to your character!")
                return                
            update_strengths = """UPDATE CharacterProfiles SET Strengths=%s WHERE ServerId=%s AND FirstName=%s AND LastName=%s;"""
            update_strengths_tuple = (strengths, str(message.guild.id), first_name, last_name)
            result = await commit_sql(update_strengths, update_strengths_tuple)
            if result:
                await send_message(message, "Strengths of character " + first_name + " " + last_name + " updated successfully.")
            else:
                await send_message(message, "Database error!")
        elif command == 'setcharweaknesses':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await send_message(message, "You must be member of the player role to add a biography!")
                return        
            name_re = re.compile(r"Name: (?P<firstname>.+?) (?P<lastname>.+)")
            weaknesses_re = re.compile(r"Weaknesses: (?P<weaknesses>.+)", re.S | re.MULTILINE)
            m = name_re.search(parsed_string)
            if m:
                first_name = m.group('firstname')
                last_name = m.group('lastname')
            m = weaknesses_re.search(parsed_string)
            if m:
                weaknesses = m.group('weaknesses')
            records = await select_sql("""SELECT UserId FROM CharacterProfiles WHERE ServerId=%s AND FirstName=%s AND LastName=%s;""",(str(message.guild.id), first_name, last_name))
            for row in records:
                user_id = row[0]
            if int(user_id) != message.author.id or not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message("This is not your character! Please only add weaknesses to your character!")
                return                 
            update_weaknesses = """UPDATE CharacterProfiles SET Weaknesses=%s WHERE ServerId=%s AND FirstName=%s AND LastName=%s;"""
            update_weaknesses_tuple = (weaknesses, str(message.guild.id), first_name, last_name)
            result = await commit_sql(update_weaknesses, update_weaknesses_tuple)
            if result:
                await send_message(message, "weaknesses of character " + first_name + " " + last_name + " updated successfully.")
            else:
                await send_message(message, "Database error!")
        elif command == 'setcharpowers':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await send_message(message, "You must be member of the player role to add a biography!")
                return        
            name_re = re.compile(r"Name: (?P<firstname>.+?) (?P<lastname>.+)")
            powers_re = re.compile(r"Powers: (?P<powers>.+)", re.S | re.MULTILINE)
            m = name_re.search(parsed_string)
            if m:
                first_name = m.group('firstname')
                last_name = m.group('lastname')
            m = powers_re.search(parsed_string)
            if m:
                powers = m.group('powers')
            records = await select_sql("""SELECT UserId FROM CharacterProfiles WHERE ServerId=%s AND FirstName=%s AND LastName=%s;""",(str(message.guild.id), first_name, last_name))
            for row in records:
                user_id = row[0]
            if int(user_id) != message.author.id or not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message("This is not your character! Please only add powers to your character!")
                return                 
            update_powers = """UPDATE CharacterProfiles SET Powers=%s WHERE ServerId=%s AND FirstName=%s AND LastName=%s;"""
            update_powers_tuple = (powers, str(message.guild.id), first_name, last_name)
            result = await commit_sql(update_powers, update_powers_tuple)
            if result:
                await send_message(message, "powers of character " + first_name + " " + last_name + " updated successfully.")
            else:
                await send_message(message, "Database error!")
        elif command == 'setcharskills':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await send_message(message, "You must be member of the player role to add a biography!")
                return        
            name_re = re.compile(r"Name: (?P<firstname>.+?) (?P<lastname>.+)")
            skills_re = re.compile(r"Skills: (?P<skills>.+)", re.S | re.MULTILINE)
            m = name_re.search(parsed_string)
            if m:
                first_name = m.group('firstname')
                last_name = m.group('lastname')
            m = skills_re.search(parsed_string)
            if m:
                skills = m.group('skills')
            records = await select_sql("""SELECT UserId FROM CharacterProfiles WHERE ServerId=%s AND FirstName=%s AND LastName=%s;""",(str(message.guild.id), first_name, last_name))
            for row in records:
                user_id = row[0]
            if int(user_id) != message.author.id or not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message("This is not your character! Please only add skills to your character!")
                return                 
            update_skills = """UPDATE CharacterProfiles SET Skills=%s WHERE ServerId=%s AND FirstName=%s AND LastName=%s;"""
            update_skills_tuple = (skills, str(message.guild.id), first_name, last_name)
            result = await commit_sql(update_skills, update_skills_tuple)
            if result:
                await send_message(message, "skills of character " + first_name + " " + last_name + " updated successfully.")
            else:
                await send_message(message, "Database error!")
        elif command == 'setcharpersonality':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await send_message(message, "You must be member of the player role to add a biography!")
                return        
            name_re = re.compile(r"Name: (?P<firstname>.+?) (?P<lastname>.+)")
            personality_re = re.compile(r"Personality: (?P<personality>.+)", re.S | re.MULTILINE)
            m = name_re.search(parsed_string)
            if m:
                first_name = m.group('firstname')
                last_name = m.group('lastname')
            m = personality_re.search(parsed_string)
            if m:
                personality = m.group('personality')
            records = await select_sql("""SELECT UserId FROM CharacterProfiles WHERE ServerId=%s AND FirstName=%s AND LastName=%s;""",(str(message.guild.id), first_name, last_name))
            for row in records:
                user_id = row[0]
            if int(user_id) != message.author.id or not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message("This is not your character! Please only add personality to your character!")
                return                 
            update_personality = """UPDATE CharacterProfiles SET Personality=%s WHERE ServerId=%s AND FirstName=%s AND LastName=%s;"""
            update_personality_tuple = (personality, str(message.guild.id), first_name, last_name)
            result = await commit_sql(update_personality, update_personality_tuple)
            if result:
                await send_message(message, "personality of character " + first_name + " " + last_name + " updated successfully.")
            else:
                await send_message(message, "Database error!")
        elif command == 'setchardescription':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await send_message(message, "You must be member of the player role to add a biography!")
                return        
            name_re = re.compile(r"Name: (?P<firstname>.+?) (?P<lastname>.+)")
            description_re = re.compile(r"Description: (?P<description>.+)", re.S | re.MULTILINE)
            m = name_re.search(parsed_string)
            if m:
                first_name = m.group('firstname')
                last_name = m.group('lastname')
            else:
                await send_message(message, "No character name specified!")
                return
            m = description_re.search(parsed_string)
            
            if m:
                description = m.group('description')
            else:
                await send_message(message, "No description specified!")
                return
            records = await select_sql("""SELECT UserId FROM CharacterProfiles WHERE ServerId=%s AND FirstName=%s AND LastName=%s;""",(str(message.guild.id), first_name, last_name))
            for row in records:
                user_id = row[0]
            if int(user_id) != message.author.id or not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message("This is not your character! Please only add strengths to your character!")
                return                 
            update_description = """UPDATE CharacterProfiles SET Description=%s WHERE ServerId=%s AND FirstName=%s AND LastName=%s;"""
            update_description_tuple = (description, str(message.guild.id), first_name, last_name)
            result = await commit_sql(update_description, update_description_tuple)
            if result:
                await send_message(message, "description of character " + first_name + " " + last_name + " updated successfully.")
            else:
                await send_message(message, "Database error!")
        elif command == 'deletechar':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await send_message(message, "You must be member of the player role to delete a character!")
                return
                
            if not parsed_string:
                await send_message("No character specified!")
                return
                
            name_re = re.compile(r"(?P<firstname>.+?) (?P<lastname>.+)")
            m = name_re.search(parsed_string)
            if not m:
                await send_message(message,"The character name was not specified correctly!")
                return
            else:
                first_name = m.group('firstname')
                last_name = m.group('lastname')
            records = await select_sql("""SELECT UserId,Id FROM CharacterProfiles WHERE ServerId=%s AND FirstName=%s AND LastName=%s;""", (str(message.guild.id), first_name, last_name))
            if not records:
                await send_message(message, "That character does not exist!")
                return
            for row in records:
                user_id = int(row[0])
                char_id = row[1]
            if user_id != message.author.id:
                await send_message(message, "You can't delete someone else's character! I'm telling! Hey <@" + str(guild_settings[message.guild.id]["AdminRole"]) + "> !!")
                return
            result = await commit_sql("""DELETE FROM CharacterProfiles WHERE Id=%s;""",(char_id,))
            if result:
                await send_message(message, "Character " + first_name + " " + last_name + " deleted from server!")
            else:
                await send_message(message, "Database error!")
                
        elif command == 'newnpc':
            if not role_check(guild_settings[message.guild.id]["NPCRole"], message.author):
                await send_message(message, "You must be a member of the NPC role to create NPCs!")
                return
            users_allowed = message.mentions
            if not users_allowed:
                await send_message(message, "No users allowed to use the NPC specified!")
                return
            shortcut_re = re.compile(r"Shortcut: (?P<shortcut>.+)")
            name_re = re.compile(r"Name: (?P<firstname>.+?) (?P<lastname>.+)")
            picture_re = re.compile(r"Picture Link: (?P<picturelink>.+)")

            for line in parsed_string.split('\n'):
                m = name_re.search(line)
                if m:

                    char_name = m.group('firstname') + " " + m.group('lastname')

                m = picture_re.search(line)
                if m:
                    picture_link = m.group('picturelink')
                
                m = shortcut_re.search(line)
                if m:
                    shortcut = m.group('shortcut')

            new_npc = """INSERT INTO NonPlayerCharacters (ServerId, UserId, UsersAllowed, CharName, PictureLink, Shortcut) VALUES (%s, %s, %s, %s, %s, %s);"""
            npc_tuple = (str(message.guild.id), str(message.author.id), str(users_allowed), char_name, picture_link, shortcut)
            result = await commit_sql(new_npc, npc_tuple)
            if result:
                await send_message(message, "NPC " + char_name + " created successfully.")
            else:
                await send_message(message, "Database error!")
        elif command == 'postnpc':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await send_message(message, "You must be a member of the player role to post as NPCs!")
                return        
            shortcut = command_string[1]
            parsed_string = message.content.replace("=postnpc ","").replace(shortcut, "")
            
            if not shortcut:
                await send_message (message, "No NPC specified!")
                return
            get_npc = """SELECT UsersAllowed, CharName, PictureLink FROM NonPlayerCharacters WHERE ServerId=%s AND Shortcut=%s;"""
            npc_tuple = (str(message.guild.id), shortcut)
            records = await select_sql(get_npc, npc_tuple)
            for row in records:
                if str(message.author.id) not in row[0]:
                    await send_message(message, "<@" + str(message.author.id) + "> is not allowed to use NPC " + row[1] + "!")
                    return
                response = parsed_string
                current_pfp = await client.user.avatar_url.read()
                

                current_name = message.guild.me.name
#                await message.guild.me.edit(nick=row[1])
                URL = row[2]
                #pfp = requests.get(url = URL)

#                await client.user.edit(avatar=pfp)
 #               await send_message(message, response)
                temp_webhook = await message.channel.create_webhook(name='Chara-Tron')
                await temp_webhook.send(content=response, username=row[1], avatar_url=URL)
                await message.delete()
                await temp_webhook.delete()
#                await client.user.edit(avatar=current_pfp)
#                await message.guild.me.edit(nick=current_name)
                
        elif command == 'deletenpc':
            if not role_check(guild_settings[message.guild.id]["NPCRole"], message.author):
                await send_message(message, "You must be a member of the NPC role to delete NPCs!")
                return        
            if not parsed_string:
                await send_message(message, "No NPC name specified!")
                return
            result = await commit_sql("""DELETE FROM NonPlayerCharacters WHERE ServerId=%s AND CharName=%s""", (str(message.guild.id),parsed_string))
            if result:
                await send_message(message, "NPC " + parsed_string + " deleted.")
            else:
                await send_message(message, "Database error!")
        elif command == 'editnpc':
            if not role_check(guild_settings[message.guild.id]["NPCRole"], message.author):
                await send_message(message, "You must be a member of the NPC role to edit NPCs!")
                return
            users_allowed = message.mentions
            if not users_allowed:
                await send_message(message, "No users allowed to use the NPC specified!")
                return
            shortcut_re = re.compile(r"Shortcut: (?P<shortcut>.+)")
            name_re = re.compile(r"Name: (?P<firstname>.+?) (?P<lastname>.+)")
            picture_re = re.compile(r"Picture Link: (?P<picturelink>.+)")
            new_npc = "UPDATE NonPlayerCharacters SET UsersAllowed=%s, "
            npc_tuple = (str(users_allowed),)
            for line in parsed_string.split('\n'):
                m = name_re.search(line)
                if m:
                    char_name = m.group('firstname') + " " + m.group('lastname')
                m = picture_re.search(line)
                if m:
                    picture_link = m.group('picturelink')
                    npc_tuple = npc_tuple + (picture_link,)
                    new_npc = new_npc + "PictureLink=%s, "
                m = shortcut_re.search(line)
                if m:
                    shortcut = m.group('shortcut')
                    npc_tuple = npc_tuple + (shortcut,)
                    new_npc = new_npc + "Shortcut=%s, "
            if not char_name:
                await send_message(message, "No character name specified!")
                return
                
            new_npc = re.sub(r", $","",new_npc) + " WHERE ServerId=%s AND CharName=%s;"
            npc_tuple = npc_tuple + (str(message.guild.id), char_name)
            result = await commit_sql(new_npc, npc_tuple)
            if result:
                await send_message(message, "NPC " + char_name + " updated successfully.")
            else:
                await send_message(message, "Database error!")
        elif command == 'setupnpc':
            if not role_check(guild_settings[message.guild.id]["NPCRole"], message.author):
                await send_message(message, "You must be a member of the NPC role to create webhooks for NPCs!")
                return        
            webhook[message.channel.id] = await message.channel.create_webhook(name='Chara-Tron')
            if webhook[message.channel.id]:
                await send_message(message, "Webhook for this channel set up successfully!")
            else:
                await send_message(message, "Problem creating webhook!")
        elif command == 'listnpcs':
            response = "***CURRENT NPC LIST***\n\n__NPC Name__ - __Allowed Users__ __Shortcut__\n"
            records = await select_sql("""SELECT CharName,UsersAllowed,Shortcut FROM NonPlayerCharacters WHERE ServerId=%s;""", (str(message.guild.id),))
            name_re = re.compile(r"Member id=.*?name='(.+?)'")

            for row in records:
                m = name_re.findall(row[1])
                if m:
                    names = re.sub(r"[\[\]']","",str(m))
                response = response + row[0] + " - " + str(names) + " - " + row[2] + "\n"
            await send_message(message, response)
        elif command == 'newspell':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message(message, "You must be a member of the admin role to create new spells!")
                return        
            spell_name_re = re.compile(r"Spell Name: (?P<spellname>.+)")
            element_re = re.compile(r"Element: (?P<element>.+)")
            mana_cost_re = re.compile(r"Mana Cost: (?P<manacost>.+)")
            min_level_re = re.compile(r"Minimum Level: (?P<minlevel>.+)")
            damage_re = re.compile(r"Damage Multiplier: (?P<damage>.+)")
            description_re = re.compile(r"Description: (?P<description>.+)")
            
            create_spell_entry = "INSERT INTO Spells (ServerId, UserId, "
            create_values = ") VALUES (%s, %s, "
            spell_tuple = (str(message.guild.id), str(message.author.id))
            for line in parsed_string.split('\n'):
                await log_message ("Line: " + line)
                m = spell_name_re.search(line)
                if m:
                    spell_name = m.group('spellname')
                    create_spell_entry = create_spell_entry + "SpellName, "
                    spell_tuple = spell_tuple + (spell_name,)
                    create_values = create_values + "%s, "
                m = element_re.search(line)
                if m:
                    element = m.group('element')
                    create_spell_entry = create_spell_entry + "Element, "
                    spell_tuple = spell_tuple + (element,)
                    create_values = create_values + "%s, "
                m = mana_cost_re.search(line)
                if m:
                    mana_cost = m.group('manacost')
                    create_spell_entry = create_spell_entry + "ManaCost, "
                    spell_tuple = spell_tuple + (mana_cost,)
                    create_values = create_values + "%s, "
                m = min_level_re.search(line)
                if m:
                    min_level = m.group('minlevel')
                    create_spell_entry = create_spell_entry + "MinimumLevel, "
                    spell_tuple = spell_tuple + (min_level,)
                    create_values = create_values + "%s, "
                m = damage_re.search(line)
                if m:
                    damage = m.group('damage')
                    create_spell_entry = create_spell_entry + "DamageMultiplier, "
                    spell_tuple = spell_tuple + (damage,)
                    create_values = create_values + "%s, "
                m = description_re.search(line)
                if m:
                    description = m.group('description')
                    create_spell_entry = create_spell_entry + "Description, "
                    spell_tuple = spell_tuple + (description,)
                    create_values = create_values + "%s ,"
            create_spell_entry = re.sub(r", $","", create_spell_entry)
            create_spell_entry = create_spell_entry + " " + re.sub(r",\s*?$","",create_values) + ");"
            await log_message("SQL: " + create_spell_entry)
            result = await commit_sql(create_spell_entry, spell_tuple)
            if result:
                await send_message(message, "Spell " + spell_name + " created successfully.")
            else:
                await send_message(message, "Database error!")
        elif command == 'newmelee':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message(message, "You must be a member of the admin role to create new melee attacks!")
                return        
            melee_name_re = re.compile(r"Melee Name: (?P<meleename>.+)")
            stamina_cost_re = re.compile(r"Stamina Cost: (?P<staminacost>.+)")
            min_level_re = re.compile(r"Minimum Level: (?P<minlevel>.+)")
            damage_re = re.compile(r"Damage Multiplier: (?P<damage>.+)")
            description_re = re.compile(r"Description: (?P<description>.+)")
            
            create_melee_entry = "INSERT INTO Melee (ServerId, UserId, "
            create_values = ") VALUES (%s, %s, "
            melee_tuple = (str(message.guild.id), str(message.author.id))
            for line in parsed_string.split('\n'):
                await log_message ("Line: " + line)
                m = melee_name_re.search(line)
                if m:
                    melee_name = m.group('meleename')
                    create_melee_entry = create_melee_entry + "AttackName, "
                    melee_tuple = melee_tuple + (melee_name,)
                    create_values = create_values + "%s, "

                m = stamina_cost_re.search(line)
                if m:
                    stamina_cost = m.group('staminacost')
                    create_melee_entry = create_melee_entry + "StaminaCost, "
                    melee_tuple = melee_tuple + (mana_cost,)
                    create_values = create_values + "%s, "
                m = min_level_re.search(line)
                if m:
                    min_level = m.group('minlevel')
                    create_melee_entry = create_melee_entry + "MinimumLevel, "
                    melee_tuple = melee_tuple + (min_level,)
                    create_values = create_values + "%s, "
                m = damage_re.search(line)
                if m:
                    damage = m.group('damage')
                    create_melee_entry = create_melee_entry + "DamageMultiplier, "
                    melee_tuple = melee_tuple + (damage,)
                    create_values = create_values + "%s, "
                m = description_re.search(line)
                if m:
                    description = m.group('description')
                    create_melee_entry = create_melee_entry + "Description, "
                    melee_tuple = melee_tuple + (description,)
                    create_values = create_values + "%s ,"
            create_melee_entry = re.sub(r", $","", create_melee_entry)
            create_melee_entry = create_melee_entry + " " + re.sub(r",\s*$","",create_values) + ");"
            result = await commit_sql(create_melee_entry, melee_tuple)
            if result:
                await send_message(message, "melee " + melee_name + " created successfully.")
            else:
                await send_message(message, "Database error!")
        elif command == 'newequipment':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message(message, "You must be a member of the admin role to create new equipment!")
                return        
            equip_name_re = re.compile(r"Equipment Name: (?P<equipname>.+)")
            description_re = re.compile(r"Description: (?P>description>.+)")
            cost_re = re.compile(r"Cost: (?P<cost>.+)")
            min_level_re = re.compile(r"Minimum Level: (?P<minlevel>.+)")
            stat_mod_re = re.compile(r"Status Modified: (?P<statmod>.+)")
            mod_re = re.compile(r"Status Change: (?<mod>.+)")
            create_equip_entry = "INSERT INTO Equipment (ServerId, UserId, "
            create_values = ") VALUES (%s, %s, "
            equip_tuple = (str(message.guild.id), str(message.author.id))
            for line in parsed_string.split('\n'):
                await log_message ("Line: " + line)
                m = equip_name_re.search(line)
                if m:
                    equip_name = m.group('equipname')
                    create_equip_entry = create_equip_entry + "EquipmentName, "
                    equip_tuple = equip_tuple + (equip_name,)
                    create_values = create_values + "%s, "

                m = equip_cost_re.search(line)
                if m:
                    equip_cost = m.group('cost')
                    create_equip_entry = create_equip_entry + "EquipmentCost, "
                    equip_tuple = equip_tuple + (mana_cost,)
                    create_values = create_values + "%s, "
                m = min_level_re.search(line)
                if m:
                    min_level = m.group('minlevel')
                    create_equip_entry = create_equip_entry + "MinimumLevel, "
                    equip_tuple = equip_tuple + (min_level,)
                    create_values = create_values + "%s, "
                m = stat_mod_re.search(line)
                if m:
                    stat_mod = m.group('statmod')
                    create_equip_entry = create_equip_entry + "StatMod, "
                    equip_tuple = equip_tuple + (stat_mod,)
                    create_values = create_values + "%s, "
                m = description_re.search(line)
                if m:
                    description = m.group('description')
                    create_equip_entry = create_equip_entry + "Description, "
                    equip_tuple = equip_tuple + (description,)
                    create_values = create_values + "%s ,"
                m = mod_re.search(line)
                if m:
                    description = m.group('mod')
                    create_equip_entry = create_equip_entry + "Modifier, "
                    equip_tuple = equip_tuple + (mod,)
                    create_values = create_values + "%s ,"                    
            create_equip_entry = re.sub(r", $","", create_equip_entry)
            create_equip_entry = create_equip_entry + " " + re.sub(r",\s*$","",create_values) + ");"
            result = await commit_sql(create_equip_entry, equip_tuple)
            if result:
                await send_message(message, "equip " + equip_name + " created successfully.")
            else:
                await send_message(message, "Database error!")
        elif command == 'deletespell':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message(message, "You must be a member of the admin role to delete spells!")
                return        
            if not parsed_string:
                await send_message(message, "No spell specified!")
                return
            result = await commit_sql("""DELETE FROM Spells WHERE ServerId=%s AND SpellName=%s;""", (str(message.guild.id), parsed_string))
            if result:
                await send_message("Spell " + parsed_string + " deleted successfully.")
            else:
                await send_message(message, "Database error!")
        elif command == 'deletemelee':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message(message, "You must be a member of the admin role to delete melee attacks!")
                return        
            if not parsed_string:
                await send_message(message, "No melee attack specified!")
                return
            result = await commit_sql("""DELETE FROM Melee WHERE ServerId=%s AND AttackName=%s;""", (str(message.guild.id), parsed_string))
            if result:
                await send_message("Attack Name " + parsed_string + " deleted successfully.")
            else:
                await send_message(message, "Database error!")            
        elif command == 'listmelees':
            response = "***CURRENT MELEE LIST***\n\n_Attack Name_\n"
            records = await select_sql("""SELECT AttackName FROM Melee WHERE ServerId=%s;""", (str(message.guild.id),))
            for row in records:
                response = response + row[0] + "\n"
            await send_message(message, response)            
        elif command == 'listspells':
            response = "***CURRENT Spell LIST***\n\n_Spell Name_\n"
            records = await select_sql("""SELECT SpellName FROM Spells WHERE ServerId=%s;""", (str(message.guild.id),))
            for row in records:
                response = response + row[0] + "\n"
            await send_message(message, response)
        elif command == 'editmelee':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message(message, "You must be a member of the admin role to edit melee attacks!")
                return        
            pass
        elif command == 'editspell':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message(message, "You must be a member of the admin role to edit spells!")
                return        
            pass
        elif command == 'givemelee':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await send_message(message, "You must be a member of the GM role to give melee attacks!")
                return        
            name_re = re.compile(r"Character Name: (?P<firstname>.+) (?P<lastname>.+)")
            attack_re = re.compile(r"Attack Name: (?P<attackname>.+)")
            
            for line in parsed_string.split('\n'):
                m = name_re.search(line)
                if m:
                    first_name = m.group('firstname')
                    last_name = m.group('lastname')
                m = attack_re.search(line)
                if m:
                    attack_name = m.group('attackname')
            
            records = await select_sql("""SELECT Id FROM CharacterProfiles WHERE ServerId=%s AND FirstName=%s and LastName=%s;""",(str(message.guild.id), first_name, last_name))
            if len(records) == 0:
                await send_message(message, "No character found with that name!")
                return
            for row in records:
                char_id = row[0]
                
            records = await select_sql("""Select Id FROM Melee WHERE ServerId=%s AND AttackName=%s""",(str(message.guild.id), attack_name))
            if len(records) == 0:
                await send_message(message, "No melee attack found with that name!")
                return
            for row in records:
                attack_id = row[0]
                
            result = await commit_sql("""INSERT INTO MeleeSkills (ServerId, UserId, CharacterId, AttackId) VALUES (%s, %s, %s, %s);""", (str(message.guild.id), str(message.author.id), char_id, attack_id))
            if result:
                await send_message(message, first_name + " " + last_name + " can now use the melee attack " + attack_name + "!")
            else:
                await send_message(message, "Database error!")
        elif command == 'givespell':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await send_message(message, "You must be a member of the GM role to give spells!")
                return        
            name_re = re.compile(r"Character Name: (?P<firstname>.+) (?P<lastname>.+)")
            spell_re = re.compile(r"Spell Name: (?P<spellname>.+)")
            
            for line in parsed_string.split('\n'):
                m = name_re.search(line)
                if m:
                    first_name = m.group('firstname')
                    last_name = m.group('lastname')
                m = spell_re.search(line)
                if m:
                    spell_name = m.group('spellname')
            
            records = await select_sql("""SELECT Id FROM CharacterProfiles WHERE ServerId=%s AND FirstName=%s and LastName=%s;""",(str(message.guild.id), first_name, last_name))
            if len(records) == 0:
                await send_message(message, "No character found with that name!")
                return
            for row in records:
                char_id = row[0]
                
            records = await select_sql("""Select Id FROM Spells WHERE ServerId=%s AND SpellName=%s""",(str(message.guild.id), spell_name))
            if len(records) == 0:
                await send_message(message, "No spell found with that name!")
                return
            for row in records:
                spell_id = row[0]
                
            result = await commit_sql("""INSERT INTO MagicSkills (ServerId, UserId, CharacterId, SpellId) VALUES (%s, %s, %s, %s);""", (str(message.guild.id), str(message.author.id), char_id, spell_id))
            if result:
                await send_message(message, first_name + " " + last_name + " can now use the spell " + spell_name + "!")
            else:
                await send_message(message, "Database error!")
            
            
        elif command == 'takemelee':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await send_message(message, "You must be a member of the GM role to take away melee attacks!")
                return        
            pass
        elif command == 'takespell':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await send_message(message, "You must be a member of the GM role to take away spells!")
                return        
            pass
        elif command == 'editequip':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message(message, "You must be a member of the admin role to edit equipment!")
                return        
            pass
        elif command == 'deleteequip':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message(message, "You must be a member of the admin role to delete equipment!")
                return        
            pass
        elif command == 'buy':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await send_message(message, "You must be a member of the player role to buy equipment!")
                return
                
            if not parsed_string:
                await send_message(message, "No item specified!")
                return
            name_re = re.compile(r"Character: (?P<firstname>.+?) (?P<lastname>.+)")
            equip_re = re.compile(r"Item: (?P<itemname>.+)")
            for line in parsed_string.split("\n"):
                m = name_re.search(line)
                if m:
                    first_name = m.group('firstname')
                    last_name = m.group('lastname')
                m = equip_re.search(line)
                if m:
                    equip_name = m.group('itemname')
            if not equip_name:
                await send_message(mesage, "No item name specified!")
                return
            if not first_name or not last_name:
                await send_message(message, "No character name specified!")
                return
                
            records = await select_sql("""SELECT Id,EquipmentCost FROM Equipment WHERE EquipmentName=%s""", (equip_name,))
            
            if not records:
                await send_message(message, "No item found by that name!")
                return
            for row in records:
                item_id = row[0]
                cost = float(row[1])
            records = await select_sql("""SELECT Id,UserId,Currency FROM CharacterProfiles WHERE ServerId=%s AND FirstName=%s AND LastName=%s;""",(str(message.guild.id), first_name, last_name))
            if not records:
                await send_message(message, "No character found by that name!")
                return
            for row in records:
                char_id = row[0]
                user_id = int(row[1])
                currency = float(row[2])
            if user_id != message.author.id:
                await send_message(message, "This isn't your character!")
                return
            if currency < cost:
                await send_message(message, "You don't have enough money to buy this!")
                return
            currency = currency - cost
            result = await commit_sql("""INSERT INTO Inventory (ServerId, UserId, CharacterId, EquipmentId) VALUES (%s, %s, %s, %s);""",(str(message.guild.id), str(user_id), char_id, item_id))
            if result:
                await send_message(message, first_name + " purchased " + equip_name + " for " + str(cost) + " and has " + str(currency) + " left.")
                result_2 = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s WHERE Id=%s""", (str(currency), char_id))
                if not result_2:
                    await send_message(message, "Database error!")
                    return
            else:
                await send_message(message, "Database error!")
        elif command == 'myitems':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await send_message(message, "You must be a member of the player role to check inventory!")
                return
            if not parsed_string:
                await send_message(message, "You didn't specify a character!")
                return
            name_re = re.compile(r"(?P<firstname>.+) (?P<lastname>.+)")
            m = name_re.search(parsed_string)
            if m:
                first_name = m.group('firstname')
                last_name = m.group('lastname')
            else:
                await send_message(message, "No character specified!")
                return
            records = await select_sql("""SELECT Id,UserId FROM CharacterProfiles WHERE ServerId=%s AND FirstName=%s AND LastName=%s;""",(str(message.guild.id), first_name, last_name))
            if not records:
                await send_message(message, "No character by that name found!")
                return
            for row in records:
                char_id = row[0]
                user_id = int(row[1])
            if user_id != message.author.id:
                await send_message(message, "This isn't your character!")
                return
            records = await select_sql("""SELECT EquipmentId FROM Inventory WHERE CharacterId=%s;""",(char_id,))
            if not records:
                await send_message(message, first_name + " doesn't have any items!")
                return
            response = "**INVENTORY**\n\n"
            for row in records:
                item_id = row[0]
                item_records = await select_sql("""SELECT EquipmentName FROM Equipment WHERE Id=%s;""",(item_id,))
                for item in item_records:
                    response = response + item[0] + "\n"
            await send_message(message, response)
        elif command == 'listitems':
            records = await select_sql("""SELECT EquipmentName FROM Equipment WHERE ServerId=%s;""", (str(message.guild.id),))
            if not records:
                await send_message(message, "This server does not have any items yet!")
                return
            response = "**SERVER ITEM LIST**\n\n"
            for row in records:
                response = response + row[0] + "\n"
            await send_message(message, response)        
        elif command == 'sell':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await send_message(message, "You must be a member of the player role to sell equipment!")
                return
                
            if not parsed_string:
                await send_message(message, "No item specified!")
                return
            name_re = re.compile(r"Character: (?P<firstname>.+?) (?P<lastname>.+)")
            equip_re = re.compile(r"Item: (?P<itemname>.+)")
            for line in parsed_string.split("\n"):
                m = name_re.search(line)
                if m:
                    first_name = m.group('firstname')
                    last_name = m.group('lastname')
                m = equip_re.search(line)
                if m:
                    equip_name = m.group('itemname')
            if not equip_name:
                await send_message(mesage, "No item name specified!")
                return
            if not first_name or last_name:
                await send_message(message, "No character name specified!")
                return
                
            records = await select_sql("""SELECT Id,EquipmentCost FROM Equipment WHERE EquipmentName=%s""", (equip_name,))
            
            if not records:
                await send_message(message, "No item found by that name!")
                return
            for row in records:
                item_id = row[0]
                cost = float(row[1])
            records = await select_sql("""SELECT Id,UserId,Currency FROM CharacterProfiles WHERE ServerId=%s AND FirstName=%s AND LastName=%s;""",(str(message.guild.id), first_name, last_name))
            if not records:
                await send_message(message, "No character found by that name!")
                return
            for row in records:
                char_id = row[0]
                user_id = int(row[1])
                currency = float(row[2])
            if user_id != message.author.id:
                await send_message(message, "This isn't your character!")
                return

            currency = currency + cost
            result = await commit_sql("""DELETE FROM Inventory WHERE ServerId=%s AND UserId=%s AND CharacterId=%s AND EquipmentId=%s;""",(str(message.guild.id), str(user_id), char_id, item_id))
            if result:
                await send_message(message, first_name + " sold " + item_name + " for " + str(cost) + " and has " + str(currency) + " left.")
                result_2 = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s WHERE Id=%s""", (str(currency), char_id))
                if not result_2:
                    await send_message(message, "Database error!")
                    return
            else:
                await send_message(message, "You don't own this item!")        
        elif command == 'useitem':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await send_message(message, "You must be a member of the admin role to use items!")
                return
            if not parsed_string:
                await send_message(message, "No item or name given!")
                return
            name_re = re.compile(r"Character: (?P<firstname>.+?) (?P<lastname>.+)")
            item_re = re.compile(r"Item: (?P<itemname>.+)")
            for line in parsed_string.split('\n'):
                m = name_re.search(line)
                if m:
                    first_name = m.group('firstname')
                    last_name = m.group('lastname')
                m = item_re.search(line)
                if m:
                    item = m.group('itemname')
            if not item or not first_name:
                await send_message(message, "Invalid input!")
                return
            records = await select_sql("""SELECT Id,MinimumLevel,StatMod,Modifier FROM Equipment WHERE ServerId=%s AND EquipmentName=%s;""",(str(message.guild.id), item))
            if not records:
                await send_message(message, "No character found by that name.")
                return
            for row in records:
                item_id = row[0]
                min_level = int(row[1])
                stat_mod = row[2]
                mod = int(row[3])
            records = await select_sql("""SELECT Id,UserId,Level,""" + stat_mod + """ FROM CharacterProfiles WHERE ServerId=%s AND FirstName=%s AND LastName=%s;""", (str(message.guild.id), first_name, last_name))
            if not records:
                await send_message(message, "No character found with that name!")
                return
            for row in records:
                char_id = row[0]
                user_id = int(row[1])
                level = int(row[2])
                stat_to_mod = int(row[3])
            if user_id != message.author.id:
                await send_message(message, "This isn't your character!")
                return
            records = await select_sql("""SELECT Id FROM Inventory WHERE ServerId=%s AND CharacterId=%s AND EquipmentId=%s;""",  (str(message.guild.id), char_id, item_id))
            if not records:
                await send_message(message, "That item is not in your inventory!")
                return
            for row in records:
                inventory_id = row[0]
            stat_to_mod = stat_to_mod + mod
            result = await commit_sql("""UPDATE CharacterProfiles SET """ + stat_mod + """=%s WHERE Id=%s""",(str(stat_to_mod), char_id))
            if not result:
                await send_message(message, "Database error!")
                return
            result = await commit_sql("""DELETE FROM Inventory WHERE Id=%s;""", (inventory_id,))
            if not result:
                await send_message(message, "Database error!")
                return
            response = first_name + " consumed item " + item + " and changed " + stat_mod + " by " + str(mod) + " points to " + str(stat_to_mod) + "!"
            await send_message(message, response)
            
        elif command == 'getmeleetemplate':
            respnse = "**NEW MELEE TEMPLATE**\n\n=newmelee Melee Name: \nStamina Cost: \nMinimum Level: (\nDamage Multiplier: \nDescription: \n"
            await send_message(message, response)
        elif command == 'getspelltemplate':
            response = "**NEW SPELL TEMPLATE**\n\n=newspell Spell Name: \nElement: \nMana Cost: \nMinimum Level: \nDamage Multiplier: \nDescription: \n"
            await send_message(message, response)
            
        elif command == 'getequiptemplate':
            response = "**NEW EQUIPMENT TEMPLATE:**\n\n==new equip Equipment Name: \nDescription: \nCost: \nMinimum Level: \nStatus Modified: \nStatus Change: \n"
            await send_command(message, response)
            
        elif command == 'getnpctemplate':
            response = "**NEW NPC TEMPLATE**\n\n=newnpc Name: \nShortcut: \nPicture Link: \n"
            await send_message(message, response)

        elif command == 'lurk':
            if message.author.nick:
                name = message.author.nick
            else:
                name = message.author.name
            responses = ["((*" + name + " lurks in the shadowy rafters with luminous orbs with parted tiers, trailing long digits through their platinum tresses.*))", "**" +name + " :** ((::lurk::))", "((*" + name + " flops on the lurker couch.*))"]
            await send_message(message, random.choice(responses))
            await message.delete()
        elif command == 'ooc':
            if message.author.nick:
                name = message.author.nick
            else:
                name = message.author.name        
            await send_message(message, "**" + name + ":** ((*" + parsed_string + "*))")
            await message.delete()
        elif command == 'randomooc':
            if message.author.nick:
                name = message.author.nick
            else:
                name = message.author.name        
            responses = ["flops on","rolls around","curls on","lurks by","farts near","falls asleep on","throws Skittles at","throws popcorn at","huggles","snugs","hugs","snuggles","tucks in","watches","stabs","slaps","sexes up"]
            usernames = message.guild.members
            user = random.choice(usernames)
            if parsed_string:
                user_id = message.mentions[0].id
            else:
                user_id = user.id
            response = "((*" + name + " " + random.choice(responses) + " <@" + str(user_id) + ">*))"
            await send_message(message, response)
        elif command == 'givecurrency':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await send_message(message, "You must be a member of the GM role to give currency!")
                return        
            name_re = re.compile(r"Name: (?P<firstname>.+) (?P<lastname>.+)")
            money_re = re.compile(r"Amount: (?P<money>.+)")
            for line in parsed_string.split('\n'):
                m = name_re.search(line)
                if m:
                    first_name = m.group('firstname')
                    last_name = m.group('lastname')

                m = money_re.search(line)
                if m:
                    money = m.group('money')

            result = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s WHERE FirstName=%s AND LastName=%s AND ServerId=%s;""",(str(money), first_name, last_name, str(message.guild.id)))
            if result:
                await send_message(message, "Character now has a fatter wallet!")
            else:
                await send_message(message, "Database error!")
        elif command == 'newmonster':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await send_message(message, "You must be a member of the GM role to create monsters!")
                return        
            name_re = re.compile(r"Monster Name: (?P<monstername>.+)")
            description_re = re.compile(r"Description: (?P<description>.+)")
            health_re = re.compile(r"Health: (?P<health>.+)")
            level_re = re.compile(r"Level: (?P<level>.+)")
            attack_re = re.compile(r"Melee Power: (?P<attack>.+)")
            defense_re = re.compile(r"Defense: (?P<defense>.+)")
            element_re = re.compile(r"Element: (?P<element>.+)")
            magic_re = re.compile(r"Magic Power: (?P<magicattack>.+)")
            picture_re = re.compile(r"Picture Link: (?P<picturelink>.+)")
            
            create_monster_entry = "INSERT INTO Monsters (ServerId, UserId, MonsterName, "
            create_values = "VALUES (%s, %s, %s, "
            monster_tuple = (str(message.guild.id), str(message.author.id))
            for line in parsed_string.split('\n'):
                await log_message ("Line: " + line)
                m = name_re.search(line)
                if m:
                    name = m.group('monstername')
                    monster_tuple = monster_tuple + (name,)
                m = description_re.search(line)
                if m:
                    description = m.group('description')
                    create_monster_entry = create_monster_entry + "Description, "
                    create_values = create_values + "%s, "
                    monster_tuple = monster_tuple + (description,)
                m = health_re.search(line)
                if m:
                    health = m.group('health')
                    create_monster_entry = create_monster_entry + "Health, "
                    create_values = create_values + "%s, "
                    monster_tuple = monster_tuple + (health,)
                m = level_re.search(line)
                if m:
                    level = m.group('level')
                    create_monster_entry = create_monster_entry + "Level, "
                    create_values = create_values + "%s, "
                    monster_tuple = monster_tuple + (level,)
                m = attack_re.search(line)
                if m:
                    height = m.group('attack')
                    create_monster_entry = create_monster_entry + "Attack, "
                    create_values = create_values + "%s, "
                    monster_tuple = monster_tuple + (attack,)
                m = defense_re.search(line)
                if m:
                    defense = m.group('defense')
                    create_monster_entry = create_monster_entry + "Defense, "
                    create_values = create_values + "%s, "
                    monster_tuple = monster_tuple + (defense,)
                m = element_re.search(line)
                if m:
                    element = m.group('element')
                    create_monster_entry = create_monster_entry + "Element, "
                    create_values = create_values + "%s, "
                    monster_tuple = monster_tuple + (element,)  
                m = magic_re.search(line)
                if m:
                    magic = m.group('magicattack')
                    create_monster_entry = create_monster_entry + "MagicAttack, "
                    create_values = create_values + "%s, "
                    monster_tuple = monster_tuple + (magic,)
                m = picture_re.search(line)
                if m:
                    picture_link = m.group('picturelink')
                    create_monster_entry = create_monster_entry + "PictureLink, "
                    create_values = create_values + "%s, "
                    monster_tuple = monster_tuple + (picture_link,)
                    
            create_monster_entry = re.sub(r", $","", create_monster_entry)
            create_monster_entry = create_monster_entry + ") " + re.sub(r", $","",create_values) +");"
            # setcharstats Name: \nAttack: \nDefense: \nMagicAttack: \nHealth: \nMana: \nLevel: \nExperience: \nStamina: \nAgility: \nIntellect: \nCharisma: \n"
            await log_message("SQL: " + create_monster_entry)
            result = await commit_sql(create_monster_entry, monster_tuple)
            if result:
                await send_message(message, "Monster " + name + " successfully created.")
            else:
                await send_message(message, "Database error!")
        elif command == 'listmonsters':
            records = await select_sql("""SELECT MonsterName FROM Monsters WHERE ServerId=%s;""", (str(message.guild.id),))
            if not records:
                await send_message(message, "No monsters are on this server yet!")
                return
            response = "**SERVER MONSTER LIST**\n\n"
            for row in records:
                response = response + row[0] + "\n"
            await send_message(message, response)
        elif command == 'getmonster':
            if not parsed_string:
                await send_message(message, "No monster name specified!")
                return
            records = await select_sql("""SELECT Description,Health,Level,Attack,Defense,Element,MagicAttack,IFNULL(PictureLink,' ') FROM Monsters WHERE ServerId=%s AND MonsterName=%s;""", (str(message.guild.id),parsed_string))
            if not records:
                await send_message(message, "No monster found with that name!")
                return
            response = "**MONSTER DATA**\n\n"
            for row in records:
                response = response + "Name: " + parsed_string + "\nDescription: " + row[0] + "\nLevel: " + str(row[1]) + "\nMelee Attack: " + str(row[2]) + "\nDefense: " + str(row[3]) + "\nElement: " + row[4] + "\nPicture Link: " + row[5] + "\n"
            await send_message(message, response)
        elif command == 'getitem':
            if not parsed_string:
                await send_message(message, "No item name specified!")
                return
            records = await select_sql("""SELECT EquipmentDescription, EquipmentCost, MinimumLevel, StatMod, Modifier FROM Equipment WHERE ServerId=%s AND Equipment=%s;""", (str(message.guild.id),parsed_string))
            if not records:
                await send_message(message, "No item found with that name!")
                return
            response = "**ITEM DATA**\n\n"
            for row in records:
                response = response + "Name: " + parsed_string + "\nDescription: " + row[0] + "\nPrice: " + str(row[1]) + "\nMinimum Level: " + str(row[2]) + "\nStat Modified: " + str(row[3]) + "\nModifier Change: " + row[4] + "\n"
            await send_message(message, response)
        elif command == 'getspell':
            if not parsed_string:
                await send_message(message, "No spell name specified!")
                return
            records = await select_sql("""SELECT Element, ManaCost, MinimumLevel, DamageMultiplier, Description FROM Spells WHERE ServerId=%s AND SpellName=%s;""", (str(message.guild.id),parsed_string))
            if not records:
                await send_message(message, "No spell found with that name!")
                return
            response = "**SPELL DATA**\n\n"
            for row in records:
                response = response + "Name: " + parsed_string + "\nElement: " + row[0] + "\nMana Cost: " + str(row[1]) + "\nMinimum Level: " + str(row[2]) + "\nDamage Multiplier: " + str(row[3]) + "\nDescription: " + str(row[4]) +  "\n"
            await send_message(message, response) 
        elif command == 'getmelee':
            if not parsed_string:
                await send_message(message, "No melee attack name specified!")
                return
            records = await select_sql("""SELECT StaminaCost, MinimumLevel,DamageMultiplier, Description FROM Melee WHERE ServerId=%s AND AttackName=%s;""", (str(message.guild.id),parsed_string))
            if not records:
                await send_message(message, "No melee attack found with that name!")
                return
            response = "**MELEE DATA**\n\n"
            for row in records:
                response = response + "Name: " + parsed_string + "\nStamina Cost: " + str(row[0]) + "\nMinimum Level: " + str(row[1]) + "\nDamage Multiplier: " + str(row[2]) + "\nDescription: " + str(row[3]) +  "\n"
            await send_message(message, response)             
        elif command == 'encountermonster':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await send_message(message, "You must be a member of the GM role to start an encounter!")
                return        
            if server_encounters[message.guild.id]:
                await send_message(message, "Monster encounter already in progress! There can only be one encounter active per server!")
                return
                
            monster_name = parsed_string
            if not monster_name:
                await send_message(message, "There's nothing to encounter! Specify a monster!")
                return
            records = await select_sql("""SELECT Description,Health,Level,Attack,Defense,Element,MagicAttack,IFNULL(PictureLink,' ') FROM Monsters WHERE ServerId=%s AND MonsterName=%s""", (str(message.guild.id), monster_name))
            if not records:
                await send_message(message, "No monsters found!")
                return
            server_id = message.guild.id
            for row in records:
                server_monsters[server_id]["MonsterName"] = monster_name
                server_monsters[server_id]["Description"] = row[0]
                server_monsters[server_id]["Health"] = int(row[1])
                server_monsters[server_id]["Level"] = int(row[2])
                server_monsters[server_id]["Attack"] = int(row[3])
                server_monsters[server_id]["Defense"] = int(row[4])
                server_monsters[server_id]["Element"] = row[5]
                server_monsters[server_id]["MagicAttack"] = int(row[6])
                server_monsters[server_id]["PictureLink"] = row[7]
                monster_health[server_id] = int(row[6])
            server_encounters[server_id] = True
            await send_message(message, "The level " + str(server_monsters[server_id]["Level"]) + " **" + monster_name + "** has appeared in " + message.channel.name + "! As described: " + server_monsters[server_id]["Description"] + "\n" + server_monsters[server_id]["PictureLink"] + "\n\nGood luck!")
        
        elif command == 'newparty':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await send_message(message, "You must be a member of the GM role to create a server party!")
                return        
            if not message.mentions:
                await send_message(message, "You didn't mention any party members!")
                return
            if server_party[message.guild.id]:
                await send_message(message, "Server party already exists!")
                return
            server_party[message.guild.id] = message.mentions
            await send_message(message, "Server party created successfully.")
            
        elif command == 'disbandparty':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await send_message(message, "You must be a member of the GM role to disband a party!")
                return        
            if server_encounters[message.guild.id]:
                await send_message(message, "There's a server encounter in progress. Cannot disband!")
                return
            server_party[message.guild.id].clear()
            await send_message(message, "Server party disbanded.")
        elif command == 'listparty':
            if not server_party[message.guild.id]:
                await send_message(message, "No party currently exists!")
                return
            response = "***SERVER PARTY***\n\n"
            for party_member in server_party[message.guild.id]:
                if party_member.nick:
                    name = party_member.nick
                else:
                    name = party_member.name
                    
                response = response + name + "\n"
            await send_message(message, response)
        elif command == 'abortencounter':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await send_message(message, "You must be a member of the GM role to abort an encounter!")
                return        
            server_encounters[message.guild.id] = False
            await send_message(message, "Encounter aborted. No health will be deducted and no XP will be gained.")
        elif command == 'setencounterchar':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await send_message(message, "You must be a member of the player role to set an encounter character!")
                return        
            if str(message.author.id) not in str(server_party[message.guild.id]):
                await send_message(message, "You're not part of the server party!")
                return
            name_re = re.compile(r"(?P<firstname>.+) (?P<lastname>.+)")
            m = name_re.search(parsed_string)
            if m:
                char_first_name = m.group('firstname')
                char_last_name = m.group('lastname')
            else:
                await send_message(message, "No character specified!")
                return
            records = await select_sql("""SELECT UserId,Attack,Defense,MagicAttack,Health,Mana,Level,Experience,Stamina,Agility,Intellect,Charisma,Id FROM CharacterProfiles WHERE ServerId=%s AND FirstName=%s AND LastName=%s;""",(str(message.guild.id), char_first_name, char_last_name))
            if not records:
                await send_message(message, "No character found!")
                return
            server_id = message.guild.id
            user_id = message.author.id
            for row in records:
                char_id = row[0]
                if int(char_id) != message.author.id:
                    await send_message(message, "This character is not yours!")
                    return
                server_party_chars[server_id][user_id] = { }
                server_party_chars[server_id][user_id]["CharName"] = char_first_name
                server_party_chars[server_id][user_id]["Attack"] = int(row[1])
                server_party_chars[server_id][user_id]["Defense"] = int(row[2])
                server_party_chars[server_id][user_id]["MagicAttack"] = int(row[3])
                server_party_chars[server_id][user_id]["Health"] = int(row[4])
                server_party_chars[server_id][user_id]["Mana"] = int(row[5])
                server_party_chars[server_id][user_id]["Level"] = int(row[6])
                server_party_chars[server_id][user_id]["Experience"] = int(row[7])
                server_party_chars[server_id][user_id]["Stamina"] = int(row[8])
                server_party_chars[server_id][user_id]["Agility"] = int(row[9])
                server_party_chars[server_id][user_id]["Intellect"] = int(row[10])
                server_party_chars[server_id][user_id]["Charisma"] = int(row[11])
                server_party_chars[server_id][user_id]["CharId"] = int(row[12])
            await send_message(message, message.author.name + " successfully set party character to " + char_first_name + " " + char_last_name + ".")
        elif command == 'monsterattack':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await send_message(message, "You must be a member of the GM role to attack with the monster!")
                return        
            server_id = message.guild.id
            if not server_encounters[server_id]:
                await send_message(message, "No encounter in progress!")
                return
            target = random.choice(list(server_party_chars[server_id].keys()))
            await send_message(message, " " + str(server_monsters[server_id]["MonsterName"]) + " attacks " + str(server_party_chars[server_id][target]["CharName"]) + "!")
            dodge = await calculate_dodge(server_monsters[server_id]["Level"], server_party_chars[server_id][target]["Agility"])
            if dodge:
                await send_message(message, server_party_chars[server_id][target]["CharName"] + " dodged the attack! No damage taken!")
                return
            else:
                damage = await calculate_damage(server_monsters[server_id]["Attack"], server_party_chars[server_id][target]["Defense"], random.randint(1,5), server_monsters[server_id]["Level"], server_party_chars[server_id][target]["Level"])
                server_party_chars[server_id][target]["Health"] = server_party_chars[server_id][target]["Health"] - damage
                await send_message(message, server_party_chars[server_id][target]["CharName"] + " was hit by " + server_monsters[server_id]["MonsterName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(server_party_chars[server_id][target]["Health"]))
                if server_party_chars[server_id][target]["Health"] < 1:
                    await send_message(message, server_party_chars[server_id][target]["CharName"] + " has no health left and is out of the fight!")
                    del server_party_chars[server_id][target]
                if len(server_party_chars[server_id]) < 1:
                    await send_message(message, "The party has been vanquished! " +server_monsters[server_id]["MonsterName"] + " wins! No experience will be awarded.")
                    server_encounters[server_id] = False
                    
        elif command == 'castmonster':
            server_id = message.guild.id
            user_id = message.author.id
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await send_message(message, "You must be a member of the player role to cast spells!")
                return            
            if not server_encounters[server_id]:
                await send_message(message, "Why are you casting " + parsed_string + "? There's nothing to attack here!")
                return

            in_party = next((item for item in server_party[server_id] if item.id == user_id), None)
            if not in_party:
                await send_message(message, "You are not in the server party!")
                return

            records = await select_sql("""SELECT Id,Element,ManaCost,MinimumLevel,DamageMultiplier FROM Spells WHERE SpellName=%s;""",(parsed_string,))
            if not records:
                await send_message(message, "That's not a valid spell. Try again.")
                return
            else:
                for row in records:
                    spell_id = row[0]
                    element = row[1]
                    mana_cost = int(row[2])
                    min_level = int(row[3])
                    damage_multiplier = int(row[4])
                spell_records = await select_sql("""SELECT CharacterId FROM MagicSkills WHERE CharacterId=%s""", (server_party_chars[server_id][user_id]["CharId"],))
                if not spell_records:
                    await send_message(message, "You do not know this spell. Try something you do know!")
                    return
                if (min_level > server_party_chars[server_id][user_id]["Level"]):
                    await send_message(message, "You're not a high enough level for this spell. How did you even learn it?")
                    return
            if server_party_chars[server_id][user_id]["Mana"] < mana_cost:
                await send_message(message, "You do not have sufficient mana for this spell. Try another spell or restore mana!")
                return
            server_party_chars[server_id][user_id]["Mana"] = server_party_chars[server_id][user_id]["Mana"] - mana_cost
            await send_message(message, " " + str(server_party_chars[server_id][user_id]["CharName"]) + " attacks " + str(server_monsters[server_id]["MonsterName"]) + " with " + parsed_string + "!\nThis drained " + str(mana_cost) + " from " + server_party_chars[server_id][user_id]["CharName"] + ", leaving them with " + str(server_party_chars[server_id][user_id]["Mana"]) + " mana!")
            dodge = await calculate_dodge(server_monsters[server_id]["Level"], server_party_chars[server_id][user_id]["Agility"])
            if dodge:
                await send_message(message, server_monsters[server_id]["MonsterName"] + " dodged the attack! No damage taken!")
                return
            else:
                damage = await calculate_damage(server_party_chars[server_id][user_id]["MagicAttack"], server_monsters[server_id]["Defense"], damage_multiplier, server_party_chars[server_id][user_id]["Level"], server_monsters[server_id]["Level"])
                server_monsters[server_id]["Health"] = server_monsters[server_id]["Health"] - damage
                await send_message(message, server_monsters[server_id]["MonsterName"] + " was hit by " + server_party_chars[server_id][user_id]["CharName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(server_monsters[server_id]["Health"]))
                if server_monsters[server_id]["Health"] < 1:
                    await send_message(message, server_monsters[server_id]["MonsterName"] + " has no health left and is out of the fight!")
                    
                    server_encounters[server_id] = False
                    await send_message(message, "Victory!")
                    response = "**Experience gained:**\n\n"
                    for user in server_party_chars[server_id].keys():
                        char_id = server_party_chars[server_id][user]["CharId"]
                        await log_message("Level " + str(server_party_chars[server_id][user]["Level"]))
                        new_xp = await calculate_xp(server_party_chars[server_id][user]["Level"], server_monsters[server_id]["Level"], monster_health[server_id], len(server_party_chars[server_id]))
                        response = response + "*" + server_party_chars[server_id][user]["CharName"] + "*: " + str(new_xp) + "\n"
                        records = await select_sql("""SELECT Experience FROM CharacterProfiles WHERE Id=%s;""", (str(server_party_chars[server_id][user]["CharId"]),))
                        for row in records:
                            old_xp = int(row[0])
                        total_xp = old_xp + new_xp
                        if total_xp > (20 * server_party_chars[server_id][user]["Level"]):
                            server_party_chars[server_id][user]["Level"] = server_party_chars[server_id][user]["Level"] + 1
                            available_points[server_id][user] = int(level / 2)
                            response = response + "**" + server_party_chars[server_id][user]["CharName"] + "** LEVELED UP TO LEVEL **" + str(server_party_chars[server_id][user]["Level"]) + "!**\nYou have " + str(int(level/2)) + " stat points to spend!"
                            total_xp = 0
                            
                        result = await commit_sql("""UPDATE CharacterProfiles SET Level=%s,Experience=%s WHERE Id=%s;""",(str(server_party_chars[server_id][user]["Level"]),str(total_xp),str(server_party_chars[server_id][user]["CharId"])))
                    await send_message(message, response)
                    server_monsters[server_id] = { }
        elif command == 'meleemonster':
            server_id = message.guild.id
            user_id = message.author.id
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await send_message(message, "You must be a member of the player role to attack the monster!")
                return            
            if not server_encounters[server_id]:
                await send_message(message, "Why are you casting " + parsed_string + "? There's nothing to attack here!")
                return

            in_party = next((item for item in server_party[server_id] if item.id == user_id), None)
            if not in_party:
                await send_message(message, "You are not in the server party!")
                return

            records = await select_sql("""SELECT Id,StaminaCost,MinimumLevel,DamageMultiplier FROM Melee WHERE AttackName=%s;""",(parsed_string,))
            if not records:
                await send_message(message, "That's not a valid attack. Try again.")
                return
            else:
                for row in records:
                    melee_id = row[0]
                    stamina_cost = int(row[2])
                    min_level = int(row[3])
                    damage_multiplier = int(row[4])
                melee_records = await select_sql("""SELECT CharacterId FROM MeleeSkills WHERE CharacterId=%s""", (server_party_chars[server_id][user_id]["CharId"],))
                if not melee_records:
                    await send_message(message, "You do not know this attack. Try something you do know!")
                    return
                if (min_level > server_party_chars[server_id][user_id]["Level"]):
                    await send_message(message, "You're not a high enough level for this attack. How did you even learn it?")
                    return
            server_party_chars[server_id][user_id]["Stamina"] = server_party_chars[server_id][user_id]["Stamina"] - stamina_cost
            await send_message(message, " " + str(server_party_chars[server_id][user_id]["CharName"]) + " attacks " + str(server_monsters[server_id]["MonsterName"]) + " with " + parsed_string + "!\nThis drained " + str(stamina_cost) + " from " + server_party_chars[server_id][user_id]["CharName"] + ", leaving them with " + str(server_party_chars[server_id][user_id]["Stamina"]) + " stamina!")                   
            dodge = await calculate_dodge(server_monsters[server_id]["Level"], server_party_chars[server_id][user_id]["Agility"])
            if dodge:
                await send_message(message, server_monsters[server_id]["MonsterName"] + " dodged the attack! No damage taken!")
                return
            else:
                damage = await calculate_damage(server_party_chars[server_id][user_id]["Attack"], server_monsters[server_id]["Defense"], damage_multiplier, server_party_chars[server_id][user_id]["Level"], server_monsters[server_id]["Level"])
                server_monsters[server_id]["Health"] = server_monsters[server_id]["Health"] - damage
                await send_message(message, server_monsters[server_id]["MonsterName"] + " was hit by " + server_party_chars[server_id][user_id]["CharName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(server_monsters[server_id]["Health"]))
                if server_monsters[server_id]["Health"] < 1:
                    await send_message(message, server_monsters[server_id]["MonsterName"] + " has no health left and is out of the fight!")
                    
                    server_encounters[server_id] = False
                    await send_message(message, "Victory!")
                    response = "**Experience gained:**\n\n"
                    for user in server_party_chars[server_id].keys():
                        char_id = server_party_chars[server_id][user]["CharId"]
                        await log_message("Level " + str(server_party_chars[server_id][user]["Level"]))
                        new_xp = await calculate_xp(server_party_chars[server_id][user]["Level"], server_monsters[server_id]["Level"], monster_health[server_id], len(server_party_chars[server_id]))
                        response = response + "*" + server_party_chars[server_id][user]["CharName"] + "*: " + str(new_xp) + "\n"
                        records = await select_sql("""SELECT Experience FROM CharacterProfiles WHERE Id=%s;""", (str(server_party_chars[server_id][user]["CharId"]),))
                        for row in records:
                            old_xp = int(row[0])
                        total_xp = old_xp + new_xp
                        if total_xp > (20 * server_party_chars[server_id][user]["Level"]):
                            server_party_chars[server_id][user]["Level"] = server_party_chars[server_id][user]["Level"] + 1
                            available_points[server_id][user] = int(level / 2)
                            response = response + "**" + server_party_chars[server_id][user]["CharName"] + "** LEVELED UP TO LEVEL **" + str(server_party_chars[server_id][user]["Level"]) + "!**\nYou have " + str(int(level/2)) + " stat points to spend!"
                            total_xp = 0
                            
                        result = await commit_sql("""UPDATE CharacterProfiles SET Level=%s,Experience=%s WHERE Id=%s;""",(str(server_party_chars[server_id][user]["Level"]),str(total_xp),str(server_party_chars[server_id][user]["CharId"])))
                    await send_message(message, response)
                    server_monsters[server_id] = { }
        elif command == 'getmonstertemplate':
            response = "***NEW MONSTER TEMPLATE***\n\n=newmonster Monster Name: \nDescription: \nHealth: \nLevel: \nAttack: \nDefense: \nElement: \nMagic Power: \nPicture Link: \n"
            await send_message(message, response)

        elif command == 'addstatpoints':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message(message, "You must be a member of the player role to add stat points!")
                return
            if not available_points[message.guild.id][message.author.id]:
                await send_message(message, "You have no available points!")
                return
            name_re = re.compile(r"Name: (?P<firstname>.+?) (?P<lastname>.+)")
            points_re = re.compile(r"Points: (?P<points>.+)")
            stat_re = re.compile(r"Stat: (?P<stat>.+)")
            for line in parsed_string:
                m = name_re.search(line)
                if m:
                    first_name = m.group('firstname')
                    last_name = m.group('lastname')
                m = points_re.search(line)
                if m:
                    points = m.group('points')
                m = stat_re.search(line)
                if m:
                    stat = m.group('stat')
            if not first_name or not last_name or not points or not stat:
                await send_message(message,"Invalid input!")
                return
            records = await select_sql("""SELECT UserId,""" + stat + """,Id FROM CharacterProfiles WHERE ServerId=%s AND FirstName=%s AND LastName=%s;""",(str(message.guild.id), first_name, last_name))
            if not records:
                await send_message(message, "No character by that name!")
                return
            for row in records:
                user_id = int(row[0])
                stat_to_mod = int(row[1])
                char_id = row[2]
            if user_id != message.author.id:
                await send_message(message, "This isn't your character!")
                return
            if not stat_to_mod:
                await send_message(message, "Invalid stat to modify!")
                return
            if int(points) > available_points[message.guild.id][message.author.id]:
                await send_message(message, "You don't have that many stat points!")
                return
            stat_to_mod = stat_to_mod +  int(points)
            available_points[message.guild.id][message.author.id] = available_points[message.guild.id][message.author.id] - int(points)
            result = await commit_sql("""UPDATE CharacterProfiles SET """ + stat + """=%s WHERE Id=%s;""",(str(stat_to_mod), char_id))
            if result:
                await send_message(message, first_name + " increased their " + stat + " points to " + stat_to_mod + " and has " + str(available_points[message.guild.id][message.author.id]) + " points left!")
            else:
                await send_message(message, "Database error!")
        elif command == 'setgmrole':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message(message, "You must be a member of the admin role to set other roles!")
                return
            if len(message.role_mentions) > 1:
                await send_message(message, "Only one role can be defined as the GM role!")
                return
            role_id = message.role_mentions[0].id
            guild_settings[message.guild.id]["GameModeratorRole"] = role_id
            result = await commit_sql("""UPDATE GuildSettings SET GameModeratorRole=%s WHERE ServerId=%s;""", (str(role_id), str(message.guild.id)))
            if result:
                await send_message(message, "GM role successfully set!")
            else:
                await send_message(message, "Database error!")            

        elif command == 'setplayerrole':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message(message, "You must be a member of the admin role to set other roles!")
                return
            if len(message.role_mentions) > 1:
                await send_message(message, "Only one role can be defined as the player role!")
                return
            role_id = message.role_mentions[0].id
            guild_settings[message.guild.id]["PlayerRole"] = role_id
            result = await commit_sql("""UPDATE GuildSettings SET PlayerRole=%s WHERE ServerId=%s;""", (str(role_id),str(message.guild.id)))
            if result:
                await send_message(message, "Player role successfully set!")
            else:
                await send_message(message, "Database error!") 
        elif command == 'setnpcrole':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message(message, "You must be a member of the admin role to set other roles!")
                return        
            if len(message.role_mentions) > 1:
                await send_message(message, "Only one role can be defined as the GM role!")
                return
            role_id = message.role_mentions[0].id
            guild_settings[message.guild.id]["NPCRole"] = role_id
            result = await commit_sql("""UPDATE GuildSettings SET NPCRole=%s WHERE ServerId=%s;""", (str(role_id),str(message.guild.id)))
            if result:
                await send_message(message, "NPC role successfully set!")
            else:
                await send_message(message, "Database error!")
        elif command == 'listroles':
            records = await select_sql("""SELECT IFNULL(AdminRole,'0'),IFNULL(GameModeratorRole,'0'),IFNULL(NPCRole, '0'),IFNULL(PlayerRole,'0') FROM GuildSettings WHERE ServerId=%s;""", (str(message.guild.id),))
            if not records:
                await send_message(message, "Database error!")
                return
            for row in records:
                
                admin_role = message.guild.get_role(int(row[0]))
                gm_role = message.guild.get_role(int(row[1]))
                npc_role = message.guild.get_role(int(row[2]))
                player_role = message.guild.get_role(int(row[3]))
            response = "**Server Roles**\n\n**Admin Role:** " + str(admin_role) + "\n**Game Moderator Role:** " + str(gm_role) + "\n**NPC Role:** " + str(npc_role) + "\n**Player Role:** " + str(player_role) + "\n"
            await send_message(message, response)
        elif  command == 'loaddefault':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await send_message(message, "You must be a member of the admin role to set other roles!")
                return        
            with open('/home/REDACTED/defaultitems.csv', newline='\n') as csvfile:
                equipreader = csv.reader(csvfile, delimiter=',')
                for row in equipreader:
                    result = await commit_sql("INSERT INTO Equipment (ServerId,UserId,EquipmentName,EquipmentDescription,EquipmentCost,MinimumLevel,StatMod,Modifier) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);", (str(message.guild.id), str(message.author.id),row[0], row[1], str(row[2]), str(row[3]), row[4], str(row[5])))

            with open('/home/REDACTED/defaultspells.csv', newline='\n') as csvfile:
                equipreader = csv.reader(csvfile, delimiter=',')
                for row in equipreader:
                    result = await commit_sql("INSERT INTO Spells (ServerId,UserId,SpellName,Element,ManaCost,MinimumLevel,DamageMultiplier,Description) VALUES (%s, %s,%s, %s, %s, %s, %s, %s);", (str(message.guild.id), str(message.author.id), row[0], row[1], str(row[2]), str(row[3]), row[4], row[5]))               
            with open('/home/REDACTED/defaultmelee.csv', newline='\n') as csvfile:
                equipreader = csv.reader(csvfile, delimiter=',')
                for row in equipreader:
                    result = await commit_sql("INSERT INTO Melee (ServerId,UserId,AttackName,StaminaCost,MinimumLevel,DamageMultiplier,Description) VALUES (%s, %s,%s, %s, %s, %s, %s);", (str(message.guild.id), str(message.author.id), row[0], row[1], str(row[2]), str(row[3]), row[4])) 
            with open('/home/REDACTED/defaultmonsters.csv', newline='\n') as csvfile:
                equipreader = csv.reader(csvfile, delimiter=',')
                for row in equipreader:
                    result = await commit_sql("INSERT INTO Monsters (ServerId,UserId,MonsterName,Description,Health, Level,Attack, Defense, Element, MagicAttack) VALUES (%s, %s,%s, %s, %s, %s, %s, %s, %s, %s);", (str(message.guild.id), str(message.author.id), row[0], row[1], str(row[2]), str(row[3]), str(row[4]), str(row[5]), row[6], str(row[7])))
            await send_message(message, "Done!")
        else:
            pass        
client.run('REDACTED')
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
client = discord.Client(heartbeat_timeout=600)
server_monsters = { }
server_encounters = { }
encounter_turn = {} 
server_party = { } 
server_party_chars = {} 
guild_settings = { }
monster_health = { }
available_points = { }
mass_spar = { }
mass_spar_chars = { }
mass_spar_event =  { }
mass_spar_turn = { }
mass_spar_confirm = {} 
alt_aliases = { }
dm_tracker = { }
fallen_chars = { } 
narrator_url = ""
npc_aliases = { }

async def log_message(log_entry):
    current_time_obj = datetime.now()
    current_time_string = current_time_obj.strftime("%b %d, %Y-%H:%M:%S.%f")
    print(current_time_string + " - " + log_entry, flush = True)
    
async def commit_sql(sql_query, params = None):
    await log_message("Commit SQL: " + sql_query + "\n" + "Parameters: " + str(params))
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
    await log_message("Select SQL: " + sql_query + "\n" + "Parameters: " + str(params))
    try:
        connection = mysql.connector.connect(host='localhost', database='CharaTron', user='REDACTED', password='REDACTED')
        cursor = connection.cursor()
        result = cursor.execute(sql_query, params)
        records = cursor.fetchall()
        await log_message("Returned " + str(records))
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
            
async def direct_message(message, response):
    channel = await message.author.create_dm()
    await log_message("replied to user " + message.author.name + " in DM with " + response)
    try:
        await channel.send(response)
    except discord.errors.Forbidden:
        await dm_tracker[message.author.id]["commandchannel"].send(">>> You have DMs off. Please reply with =answer <reply> in the server channel.\n" + response)
        
async def post_webhook(channel, name, response, picture):
    temp_webhook = await channel.create_webhook(name='Chara-Tron')
    await temp_webhook.send(content=response, username=name, avatar_url=picture)
    await temp_webhook.delete() 
    
async def reply_message(message, response):
    if not message.guild:
        channel_name = dm_tracker[message.author.id]["commandchannel"].name
        server_name = str(dm_tracker[message.author.id]["server_id"])
    else:
        channel_name = message.channel.name
        server_name = message.guild.name
        
    await log_message("Message sent back to server " + server_name + " channel " + channel_name + " in response to user " + message.author.name + "\n\n" + response)
    
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
    total_attack_power = attack * random.randint(damage_multiplier - 2, damage_multiplier + 2)
    level_difference = target_level / attacker_level
    effective_attack_power = total_attack_power * level_difference
    total_damage = effective_attack_power - defense
    if total_damage < 0:
        total_damage = 5
    return int(total_damage)
    
async def calculate_dodge(attacker_agility, target_agility):
    dodge_chance = random.randint(0,100)
    if attacker_agility > target_agility:
        dodge = 5
    else:
        dodge = 10
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
        return int(xp)
async def initialize_dm(author_id):
    global dm_tracker
    dm_tracker[author_id] = { }
    dm_tracker[author_id]["currentcommand"] = " "
    dm_tracker[author_id]["currentfield"] = 0
    dm_tracker[author_id]["fieldlist"] = []
    dm_tracker[author_id]["fielddict"] = []
    dm_tracker[author_id]["server_id"] = 0
    dm_tracker[author_id]["commandchannel"] = 0
    dm_tracker[author_id]["parameters"] = " "
    
    
def role_check(role_required, user):
    for role in user.roles:
        if role.id == role_required:
            return True
            
    return False
async def insert_into(message, table_name):
    global dm_tracker
    field_list = dm_tracker[message.author.id]["fieldlist"]
    field_dict = dm_tracker[message.author.id]["fielddict"]
    server_id = dm_tracker[message.author.id]["server_id"]
    create_entry = "INSERT INTO " + table_name + " (ServerId, UserId, "
    create_values = ") VALUES (%s, %s, "
    create_tuple = (str(dm_tracker[message.author.id]["server_id"]), str(message.author.id))
    counter = 0
    for field in field_list:
        create_entry = create_entry + field + ", "
        create_tuple = create_tuple + (field_dict[counter],)
        create_values = create_values + "%s, "
        counter = counter + 1
        if counter > len(field_list) - 1:
            break

    create_entry = re.sub(r", $","", create_entry)
    create_entry = create_entry + " " + re.sub(r",\s*$","",create_values) + ");"
    result = await commit_sql(create_entry, create_tuple)
    return result

async def update_table(message, table_name):
    global dm_tracker
    field_list = dm_tracker[message.author.id]["fieldlist"]
    field_dict = dm_tracker[message.author.id]["fielddict"]
    server_id = dm_tracker[message.author.id]["server_id"]    
    update_entry = "UPDATE " + table_name + " SET UserId=%s, "
    update_tuple = (str(message.author.id),)
    counter = 0
    for field in field_list:
        update_entry = update_entry + field + "=%s, "
        update_tuple = update_tuple + (str(field_dict[counter]),)
        counter = counter + 1 
    try: 
        dm_tracker[message.author.id]["parameters"]
        if dm_tracker[message.author.id]["parameters"].strip():
            field_value = dm_tracker[message.author.id]["parameters"]
        else:
            field_value = field_dict[0]
    except:
        field_value = field_dict[0]
        
    update_entry = re.sub(r", $","", update_entry)
    update_entry = update_entry + " WHERE ServerId=%s AND " + field_list[0] + "=%s;"
    update_tuple = update_tuple + (str(dm_tracker[message.author.id]["server_id"]), field_value)

    result = await commit_sql(update_entry, update_tuple)
    return result
async def make_menu(message, table1, table2, id_field1, id_field2, name_field,id ):
    global dm_tracker
    records = await select_sql("""SELECT """ + id_field1 + """ FROM """ + table1 + """ WHERE ServerId=%s AND """ + id_field2 + """=%s;""",  (str(dm_tracker[message.author.id]["server_id"]), id))
    if not records:
        return "Menu error!"
    response = " "
    for row in records:
        item_record = await select_sql("SELECT " + name_field + " FROM " + table2 + " WHERE Id=%s AND ServerId=%s;", (str(row[0]),str(dm_tracker[message.author.id]["server_id"])))
        for item_row in item_record:
            response = response + "**" + str(row[0]) + "** - " + item_row[0] + "\n"
    return response

async def make_simple_menu(message, table1, name_field):
    global dm_tracker
    records = await select_sql("""SELECT Id,""" + name_field + """ FROM """ + table1 + """ WHERE ServerId=%s;""",  (str(dm_tracker[message.author.id]["server_id"]),))
    if not records:
        return "Menu error!"
    response = " "
    for row in records:
        response = response + "**" + str(row[0]) + "** - " + row[1] + "\n"
    return response
    
async def make_less_simple_menu(message, table1, name_field, id_field, id):
    global dm_tracker
    records = await select_sql("""SELECT Id,""" + name_field + """ FROM """ + table1 + """ WHERE ServerId=%s AND """ + id_field + """=%s;""",  (str(dm_tracker[message.author.id]["server_id"]),id))
    if not records:
        return "Menu error!"
    response = " "
    for row in records:
        response = response + "**" + str(row[0]) + "** - " + row[1] + "\n"
    return response  
    
@client.event
async def on_ready():
    global webhook
    global server_monsters
    global server_encounters
    global server_party
    global server_party_chars
    global guild_settings
    global available_points
    global mass_spar
    global mass_spar_chars
    global mass_spar_event
    global mass_spar_turn
    global mass_spar_confirm
    global alt_aliases
    global dm_tracker
    global fallen_chars
    global encounter_turn
    global narrator_url
    global npc_aliases
    
    await log_message("Logged in!")
    
    for guild in client.guilds:
            
        try: alt_aliases[guiild.id]
        except: alt_aliases[guild.id] = {}
        try: npc_aliases[guiild.id]
        except: npc_aliases[guild.id] = {}
        available_points[guild.id] = {}
        server_encounters[guild.id] = False
        server_monsters[guild.id] = {} 
        server_party[guild.id] = {}
        server_party_chars[guild.id] = {}
        guild_settings[guild.id]  =  {}
        mass_spar[guild.id] = { }
        mass_spar_event[guild.id] = False
        mass_spar_chars[guild.id] = { }
        mass_spar_turn[guild.id] = 0
        mass_spar_confirm[guild.id] = { }

        fallen_chars[guild.id] = { }
        encounter_turn[guild.id] = 0
        for user in guild.members:
            try: alt_aliases[guiild.id][user.id]
            except: alt_aliases[guild.id][user.id] = {}
            try: npc_aliases[guiild.id][user.id]
            except: npc_aliases[guild.id][user.id] = {}
            for channel in guild.text_channels:
                try: alt_aliases[guild.id][user.id][channel.id]
                except: alt_aliases[guild.id][user.id][channel.id] = ""
                try: npc_aliases[guild.id][user.id][channel.id]
                except: npc_aliases[guild.id][user.id][channel.id] = ""                
    # GMRole,NPCRole,PlayerRole,GuildBankBalance,StartingHealth,StartingMana,StartingStamina,StartingAttack,StartingDefense,StartingMagicAttack,StartingAgility,StartingIntellect,StartingCharisma,HealthLevelRatio,ManaLevelRatio,StaminaLevelRatio,XPLevelRatio,HealthAutoHeal,ManaAutoHeal,StaminaAutoHeal
    # ALTER TABLE GuildSettings ADD COLUMN StartingHealth Int, StartingMana Int, StartingStamina Int, StartingAttack Int, StartingDefense Int, StartingMagicAttack Int, StartingAgility Int, StartingIntellect Int, StartingCharisma Int, HealthLevelRatio Int, ManaLevelRatio Int, StaminaLevelRatio Int, XPLevelRatio Int, HealthAutoHeal DECIMAL(1,2), ManaAutoHeal DECIMAL (1,2), StaminaAutoHeal DECIMAL(1,2);
    records = await select_sql("""SELECT ServerId,IFNULL(AdminRole,'0'),IFNULL(GameModeratorRole,'0'),IFNULL(NPCRole,'0'),IFNULL(PlayerRole,'0'),IFNULL(StartingHealth,'0'),IFNULL(StartingMana,'0'),IFNULL(StartingStamina,'0'),IFNULL(StartingAttack,'0'),IFNULL(StartingDefense,'0'),IFNULL(StartingMagicAttack,'0'),IFNULL(StartingAgility,'0'),IFNULL(StartingIntellect,'0'),IFNULL(StartingCharisma,'0'),IFNULL(HealthLevelRatio,'0'),IFNULL(ManaLevelRatio,'0'),IFNULL(StaminaLevelRatio,'0'),IFNULL(XPLevelRatio,'0'),IFNULL(HealthAutoHeal,'0'),IFNULL(ManaAutoHeal,'0'),IFNULL(StaminaAutoHeal,'0') FROM GuildSettings;""")
    if records:
        for row in records:
            server_id = int(row[0])
            guild_settings[server_id] = {} 
            if row[1] is not None:        
                guild_settings[server_id]["AdminRole"] = int(row[1])    
            if row[2] is not None:   
                guild_settings[server_id]["GameModeratorRole"] = int(row[2])
            if row[3] is not None:   
                guild_settings[server_id]["NPCRole"] = int(row[3])
            if row[4] is not None:   
                guild_settings[server_id]["PlayerRole"] = int(row[4])
            if row[5] is not None:   
                guild_settings[server_id]["StartingHealth"] = int(row[5])
            if row[6] is not None:   
                guild_settings[server_id]["StartingMana"] = int(row[6])
            if row[7] is not None:   
                guild_settings[server_id]["StartingStamina"] = int(row[7])
            if row[8] is not None:   
                guild_settings[server_id]["StartingAttack"] = int(row[8])
            if row[9] is not None:   
                guild_settings[server_id]["StartingDefense"] = int(row[9])
            if row[10] is not None:   
                guild_settings[server_id]["StartingMagicAttack"] = int(row[10])
            if row[11] is not None:   
                guild_settings[server_id]["StartingAgility"] = int(row[11])
            if row[12] is not None:   
                guild_settings[server_id]["StartingIntellect"] = int(row[12])
            if row[13] is not None:       
                guild_settings[server_id]["StartingCharisma"] = int(row[13])
            if row[14] is not None:   
                guild_settings[server_id]["HealthLevelRatio"] = int(row[14])
            if row[15] is not None:   
                guild_settings[server_id]["ManaLevelRatio"] = int(row[15])
            if row[16] is not None:   
                guild_settings[server_id]["StaminaLevelRatio"] = int(row[16])
            if row[17] is not None:   
                guild_settings[server_id]["XPLevelRatio"] = int(row[17])
            if row[18] is not None:   
                guild_settings[server_id]["HealthAutoHeal"] = float(row[18])
            if row[19] is not None:   
                guild_settings[server_id]["ManaAutoHeal"] = float(row[19])
            if row[20] is not None:   
                guild_settings[server_id]["StaminaAutoHeal"] = float(row[20])
    await log_message("All SQL loaded for guilds.")
            
            
@client.event
async def on_guild_join(guild):
    global available_points
    global server_monsters
    global server_encounters
    global server_party
    global server_party_chars
    global guild_settings
    global monster_health
    global mass_spar
    global mass_spar_chars
    global mass_spar_event
    global mass_spar_turn
    global mass_spar_confirm
    global alt_aliases
    global fallen_chars
    global encounter_turn
    global npc_aliases

    
    await log_message("Joined guild " + guild.name)
    server_encounters[guild.id] = False
    server_monsters[guild.id] = {}     
    server_party[guild.id] = { }
    server_party_chars[guild.id] = { }
    guild_settings[guild.id] = {}
    available_points[guild.id] = { }
    mass_spar[guild.id] = { }
    mass_spar_event[guild.id] = False
    mass_spar_confirm[guild.id] = { }
    mass_spar_turn = 0
    alt_aliases[guild.id] = { }
    npc_aliases[guild.id] = { }
    fallen_chars[guild.id] = { }
    encounter_turn[guild.id] = 0
    for user in guild.members:
        npc_aliases[guild.id][user.id] = { }
        alt_aliases[guild.id][user.id] = { }
        available_points[guild.id][user.id] = 0
        for channel in guild.text_channels:
            npc_aliases[guild.id][user.id][channel.id] = ""
            alt_aliases[guild.id][user.id][channel.id] = ""
    
    
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
    global available_points
    global mass_spar
    global mass_spar_chars
    global mass_spar_event
    global mass_spar_turn
    global mass_spar_confirm
    global alt_aliases
    global dm_tracker
    global fallen_chars
    global encounter_turn
    global narrator_url
    global npc_aliases
    
    if message.author.bot:
        return
    if message.author == client.user:
        return
    
    das_server = message.guild
    
    if message.content.startswith('=answer'):
        das_server = None
        message.content = message.content.replace('=answer ','')
       
    if not das_server:
        await log_message("Received DM from user " + message.author.name + " with content " + message.content)

        current_command = dm_tracker[message.author.id]["currentcommand"]
        current_field = dm_tracker[message.author.id]["currentfield"]
        field_list = dm_tracker[message.author.id]["fieldlist"]
        field_dict = dm_tracker[message.author.id]["fielddict"]
        server_id = dm_tracker[message.author.id]["server_id"]
        await log_message("Command : " + current_command + " Field: " + str(current_field) + " Field list: " +str(field_list) + " Field dict: " + str(field_dict))
            
        if message.content == 'stop' or message.content == 'Stop':
            dm_tracker[message.author.id] = {}
            await direct_message(message, "Command stopped!")
            return
        elif (message.content == 'skip' or message.content == 'Skip') and current_field < len(field_list):
            dm_tracker[message.author.id]["currentfield"] = dm_tracker[message.author.id]["currentfield"] + 1
            if current_field < len(field_list) - 1:
                await direct_message(message, "Skipping field **"  + field_list[current_field] + "** and not changing its value. The next field is **" + dm_tracker[message.author.id]["fieldlist"][current_field + 1] + "** and its value is **" + str(dm_tracker[message.author.id]["fielddict"][current_field + 1]) + "**. Reply with the new value or *skip* to leave the current value.")
                
                return
            else:
                await direct_message(message, "Setting field **"  + dm_tracker[message.author.id]["fieldlist"][current_field] + "** to **" + message.content.strip() + "**. That was the last field. Reply *end* to commit to the database.")            
            

        elif current_command.startswith('edit') and current_field < len(field_list):
            dm_tracker[message.author.id]["fielddict"][current_field] = message.content.strip()
            dm_tracker[message.author.id]["currentfield"] = current_field + 1
            if current_field < len(field_list) - 1:
           
                if message.attachments:
                    dm_tracker[message.author.id]["fielddict"][current_field] = message.attachments[0].url            
                await direct_message(message, "Setting field **"  + dm_tracker[message.author.id]["fieldlist"][current_field] + "** to **" + message.content.strip() + "**. The next field is **" + dm_tracker[message.author.id]["fieldlist"][current_field + 1] + "** and its value is **" + str(dm_tracker[message.author.id]["fielddict"][current_field + 1]) + "**. Reply with the new value or *skip* to leave the current value.")
            else:
                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url                
                await direct_message(message, "Setting field **"  + dm_tracker[message.author.id]["fieldlist"][current_field] + "** to **" + message.content.strip() + "**. That was the last field. Reply *end* to commit to the database.")            
            
            return
        elif current_command == 'newvendor' and message.content != 'end' and not message.attachments  and not message.content.startswith("http"):
            if current_field == 0:
                menu = await make_simple_menu(message, "Equipment", "EquipmentName")
                await direct_message(message, "Vendor now named " + message.content + ". Please enter the ID of each item as a single reply until you have added all items the vendor should sell, then type **end** to commit.\n\n" + menu)
                dm_tracker[message.author.id]["currentfield"] = 1
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                dm_tracker[message.author.id]["fielddict"].append(" ")
                return
            else:
                dm_tracker[message.author.id]["fielddict"][1] = str(dm_tracker[message.author.id]["fielddict"][1]) + message.content + ", "
                menu = await make_simple_menu(message, "Equipment", "EquipmentName")
                response = "Please reply with the ID of the item to add, or **end** to commit the item list.\n\n" + menu
                await direct_message(message, response)
                return
                
        elif current_command == 'addvendoritem' and message.content != 'end':
            if current_field == 0:
                menu = await make_simple_menu(message, "Equipment", "EquipmentName")
                await direct_message(message, "Please enter the ID of each item as a single reply until you have added all items the vendor should sell, then type **end** to commit.\n\n" + menu)
                dm_tracker[message.author.id]["currentfield"] = 1
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                dm_tracker[message.author.id]["fielddict"].append(" ")
                return
            else:
                dm_tracker[message.author.id]["fielddict"][1] = str(dm_tracker[message.author.id]["fielddict"][1]) + message.content + ", "
                menu = await make_simple_menu(message, "Equipment", "EquipmentName")
                response = "Please reply with the ID of the item to add, or **end** to commit the item list.\n\n" + menu
                await direct_message(message, response)
                return
        elif current_command == 'newarmory' and message.content != 'end' and not message.attachments and not message.content.startswith("http"):
            if current_field == 0:
                menu = await make_simple_menu(message, "Armaments", "ArmamentName")
                await direct_message(message, "Armory now named " + message.content + ". Please enter the ID of each item as a single reply until you have added all items the armory should sell, then type **end** to commit.\n\n" + menu)
                dm_tracker[message.author.id]["currentfield"] = 1
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                dm_tracker[message.author.id]["fielddict"].append(" ")
                return
            elif current_field == 1:
                dm_tracker[message.author.id]["fielddict"][1] = str(dm_tracker[message.author.id]["fielddict"][1]) + message.content + ", "
                menu = await make_simple_menu(message, "Armaments", "ArmamentName")
                response = "Please reply with the ID of the item to add, or **end** to commit the item list.\n\n" + menu
                await direct_message(message, response)
                return
                
        elif current_command == 'addarmoryitem' and message.content != 'end':
            if current_field == 0:
                menu = await make_simple_menu(message, "Armaments", "ArmamentName")
                await direct_message(message, "Please enter the ID of each item as a single reply until you have added all items the armory should sell, then type **end** to commit.\n\n" + menu)
                dm_tracker[message.author.id]["currentfield"] = 1
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                dm_tracker[message.author.id]["fielddict"].append(" ")
                return
            else:
                dm_tracker[message.author.id]["fielddict"][1] = str(dm_tracker[message.author.id]["fielddict"][1]) + message.content + ", "
                menu = await make_simple_menu(message, "Armaments", "ArmamentName")
                response = "Please reply with the ID of the item to add, or **end** to commit the item list.\n\n" + menu
                await direct_message(message, response)
                return                
        elif current_command == 'resetserver':
            if message.content != 'CONFIRM':
                await direct_message(message, "Server reset canceled.")
                await dm_tracker[message.author.id]["commandchannel"].send(">>> Server reset canceled.")
                return
            else:
                await dm_tracker[message.author.id]["commandchannel"].send(">>> Server reset commencing...")
                delete_tuple = ()
                for x in range(1,10):
                    delete_tuple = delete_tuple + (str(dm_tracker[message.author.id]["server_id"]),)
                result = await commit_sql("""DELETE FROM CharacterProfiles WHERE ServerId=%s; DELETE FROM Vendors WHERE ServerId=%s; DELETE FROM Spells WHERE ServerId=%s; DELETE FROM Melee WHERE ServerId-%s; DELETE FROM Inventory WHERE ServerId-%s; DELETE FROM Equipment WHERE ServerId=%s; DELETE FROM MagicSkills WHERE ServerId=%s; DELETE FROM MeleeSkills WHERE ServerId=%s; DELETE FROM Monsters WHERE ServerId=%s; DELETE FROM GuildSettings WHERE ServerId=%s;""", delete_tuple)
                await dm_tracker[message.author.id]["commandchannel"].send(">>> Server reset complete! Please run =setadminrole @adminrole followed by =newsetup to create a new setup for this server!")
                return

        elif current_command == 'deletevendoritem':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                records = await select_sql("""SELECT ItemList,VendorName FROM Vendors WHERE Id=%s;""", (message.content,))
                if not records:
                    await reply_message(message, "No vendor found by that ID!")
                    return
                for row in records:
                    items = row[0]
                    vendor_name = row[1]
                response = "**ITEMS FOR VENDOR " + message.content + "**\n\n"   
                item_list = items.split(',')
                for item in item_list:
                    item_record = await select_sql("""SELECT EquipmentName FROM Equipment WHERE Id=%s""",(item,))
                    for item_name in item_record:
                        response = response + item_name[0] + "\n"
                menu = "Type the ID of the item you'd like to delete from this vendor in a reply below.\n\n"
                await direct_message(message, menu + response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            elif current_field == 1:
                records = await select_sql("""SELECT ItemList,VendorName FROM Vendors WHERE Id=%s;""", (field_dict[0],))
                if not records:
                    await reply_message(message, "No vendor found by that ID!")
                    return
                for row in records:
                    items = row[0]
                    vendor_name = row[1]    
                items = items.replace(message.content + ",","")
                result = await commit_sql("UPDATE Vendors SET ItemList=%s WHERE Id=%s",(items, field_dict[0]))
                if result:
                    await direct_message(message, "Item deleted from vendor successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Item deleted from vendor successfully.")
                return
        elif current_command == 'newrandomchar':
            if message.content == 'YES':
                result = await insert_into(message, "UnapprovedCharacterProfiles")
                if result:
                    await direct_message(message, "Character application for " + field_dict[0] + " created successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Character application for  " + field_dict[0] + " successfully created.\n\nAfter approval, you may edit any character fields with =editchar.\n\n<@&" + str(guild_settings[dm_tracker[message.author.id]["server_id"]]["AdminRole"]) + ">, please approve or decline the character with =approvechar or =denychar.")
                else:
                    await direct_message(message, "Database error!")
            else:
                await direct_message(message, "Character discarded.")
            return
        elif current_command == 'deletearmoryitem':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                records = await select_sql("""SELECT ItemList,ArmamentName FROM Armory WHERE Id=%s;""", (message.content,))
                if not records:
                    await reply_message(message, "No armory found by that ID!")
                    return
                for row in records:
                    items = row[0]
                    armory_name = row[1]
                response = "**ITEMS FOR VENDOR " + message.content + "**\n\n"   
                item_list = items.split(',')
                for item in item_list:
                    item_record = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s""",(item,))
                    for item_name in item_record:
                        response = response + item_name[0] + "\n"
                menu = "Type the ID of the item you'd like to delete from this armory in a reply below.\n\n"
                await direct_message(message, menu + response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            elif current_field == 1:
                records = await select_sql("""SELECT ItemList,ArmamentName FROM Armory WHERE Id=%s;""", (field_dict[0],))
                if not records:
                    await reply_message(message, "No armory found by that ID!")
                    return
                for row in records:
                    items = row[0]
                    armory_name = row[1]    
                items = items.replace(message.content + ",","")
                result = await commit_sql("UPDATE Armory SET ItemList=%s WHERE Id=%s",(items, field_dict[0]))
                if result:
                    await direct_message(message, "Item deleted from armory successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Item deleted from armory successfully.")                
        elif current_command == 'approvechar':
            unapproved_char_id = message.content
            records = await select_sql("""SELECT CharacterName,UserId FROM UnapprovedCharacterProfiles WHERE Id=%s""", (message.content,))
            for row in records:
                char_name = row[0]
                char_user_id = row[1]
            # Copy to Character profiles
            records = await select_sql("""SELECT ServerId,UserId,CharacterName,Age,Race,Gender,Height,Weight,Playedby,Origin,Occupation,PictureLink,Attack,Defense,MagicAttack,Health,Mana,Level,Experience,Stamina,Agility,Intellect,Charisma,Currency FROM UnapprovedCharacterProfiles WHERE Id=%s;""", (message.content,))
            insert_statement = """INSERT INTO CharacterProfiles (ServerId,UserId,CharacterName,Age,Race,Gender,Height,Weight,Playedby,Origin,Occupation,PictureLink,Attack,Defense,MagicAttack,Health,Mana,Level,Experience,Stamina,Agility,Intellect,Charisma,Currency) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
            insert_tuple = ()
            for row in records:
                for item in row:
                    insert_tuple = insert_tuple + (item,)
            result = await commit_sql(insert_statement, insert_tuple)        
#            result = await commit_sql("""INSERT INTO CharacterProfiles (SELECT * FROM UnapprovedCharacterProfiles WHERE Id=%s);""", (message.content,))
            if result:
                await dm_tracker[message.author.id]["commandchannel"].send(">>> <@" + char_user_id + ">, your character is approved! You may now play as " + char_name + ".")
            else:
                await direct_message(message, "Database error!")
                return
            result = await commit_sql("""DELETE FROM UnapprovedCharacterProfiles WHERE Id=%s;""", (message.content,))
            if result:
                await direct_message(message, "Character confirmed deletion and moved to approved characters list. User will be notiified of the approval.")
                deleted = True
            else:
                await direct_message(message, "Database error!")
              
            return
        elif current_command == 'denychar':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                await direct_message(message, "Enter a reason why this character is declined. Please specify what needs to be changed to approve it, and if nothing can be changed, why it was deleted.")
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                await direct_message(message, "Please type **DELETE** in reply to this message if the character profile will be deleted from the unapproved character list.")
                dm_tracker[message.author.id]["currentfield"] = 2
                return
            if current_field == 2:
                records = await select_sql("""SELECT UserId,CharacterName FROM UnapprovedCharacterProfiles WHERE Id=%s;""",(dm_tracker[message.author.id]["fielddict"][0],))
                for row in records:
                    user_id = row[0]
                    char_name = row[1]
                    
                if message.content == 'DELETE':
                    result = await commit_sql("""DELETE FROM UnapprovedCharacterProfiles WHERE Id=%s;""", (dm_tracker[message.author.id]["fielddict"][0],))
                    if result:
                        await direct_message(message, "Character confirmed deletion and not moved to approved characters list. User will be notiified of the decline and reason.")
                        deleted = True
                    else:
                        await direct_message(message, "Database error!")
                        return
                else:
                    deleted = False
                response = "Your character was declined. The reason given was:\n```" + dm_tracker[message.author.id]["fielddict"][1] + "```"
                if deleted:
                    response = response + "\n\nThe character was also deleted from unapproved profiles for the above reason. Please create a new application that fits the server rules.\n"
                user_obj = client.get_user(int(user_id))
                channel = await user_obj.create_dm()
                await channel.send(">>> " + response)
                await dm_tracker[message.author.id]["commandchannel"].send(">>> " + char_name + " was declined. <@" + str(user_id) + ">, please check your DMs for the reason.")
                return
                    
        elif current_command == 'setencounterchar':
            records = await select_sql("""SELECT UserId,Attack,Defense,MagicAttack,Health,Mana,Level,Experience,Stamina,Agility,Intellect,Charisma,Id,CharacterName,Currency,PictureLink FROM CharacterProfiles WHERE Id=%s;""",(message.content,))
            if not records:
                await reply_message(message, "No character found!")
                return
            server_id = dm_tracker[message.author.id]["server_id"]
            user_id = message.author.id
            for row in records:
                char_id = row[0]
                if int(char_id) != message.author.id:
                    await reply_message(message, "This character is not yours!")
                    return
                server_party_chars[server_id][user_id] = { }
                server_party_chars[server_id][user_id]["CharName"] = row[13]
                server_party_chars[server_id][user_id]["Attack"] = int(row[1])
                server_party_chars[server_id][user_id]["Defense"] = int(row[2])
                server_party_chars[server_id][user_id]["MagicAttack"] = int(row[3])
                server_party_chars[server_id][user_id]["Health"] = int(row[4])
                server_party_chars[server_id][user_id]["MaxHealth"] = int(row[4])
                server_party_chars[server_id][user_id]["Mana"] = int(row[5])
                server_party_chars[server_id][user_id]["MaxMana"] = int(row[5])
                server_party_chars[server_id][user_id]["Level"] = int(row[6])
                server_party_chars[server_id][user_id]["Experience"] = int(row[7])
                server_party_chars[server_id][user_id]["Stamina"] = int(row[8])
                server_party_chars[server_id][user_id]["MaxStamina"] = int(row[8])
                server_party_chars[server_id][user_id]["Agility"] = int(row[9])
                server_party_chars[server_id][user_id]["Intellect"] = int(row[10])
                server_party_chars[server_id][user_id]["Charisma"] = int(row[11])
                server_party_chars[server_id][user_id]["CharId"] = int(row[12])
                server_party_chars[server_id][user_id]["Currency"] = float(row[14])
                server_party_chars[server_id][user_id]["PictureLink"] = row[15]
                char_name = row[13]
            records = await select_sql("""SELECT IFNULL(HeadId,'None'),IFNULL(ChestId,'None'),IFNULL(LeftHandId,'None'),IFNULL(RightHandId,'None'),IFNULL(FeetId,'None') FROM CharacterArmaments WHERE CharacterId=%s;""",(str(server_party_chars[server_id][user_id]["CharId"]),))
            if records:
                for row in records:
                    for x in range(0,len(row)):
                        item = row[x]
                        if item != 'None':
                            arm_records = await select_sql("""SELECT MinimumLevel,Defense,StatMod,Modifier FROM Armaments WHERE Id=%s;""", (str(item),))
                            for arm_row in arm_records:
                                if int(arm_row[0]) < server_party_chars[server_id][user_id]["Level"]:
                                    if int(arm_row[1]) > 0:
                                        server_party_chars[server_id][user_id]["Defense"] = server_party_chars[server_id][user_id]["Defense"] + int(arm_row[1])
                                        await log_message("applying defense!")
                                    if re.search(r"Attack|MagicAttack|Agility",arm_row[2]):
                                        server_party_chars[server_id][user_id][arm_row[2]] = server_party_chars[server_id][user_id][arm_row[2]] + int(arm_row[3])
                                        await log_message("applying " + str(arm_row[3]) + " to " + str(arm_row[2]))

                                  
                    
            await dm_tracker[message.author.id]["commandchannel"].send(">>> " + message.author.name + " successfully set party character to " + char_name + ".")        
            await direct_message(message,"You successfully set your party character to " + char_name + ".")
            return
        elif current_command == 'encountermonster':
            records = await select_sql("""SELECT IFNULL(Description,'None'),Health,Level,Attack,Defense,Element,MagicAttack,IFNULL(PictureLink,' '),MaxCurrencyDrop,MonsterName FROM Monsters WHERE Id=%s""", (message.content,))
            if not records:
                await reply_message(message, "No monsters found!")
                return
            server_id = dm_tracker[message.author.id]["server_id"]
            for row in records:
                server_monsters[server_id]["MonsterName"] = row[9]
                monster_name = row[9]
                server_monsters[server_id]["Description"] = row[0]
                server_monsters[server_id]["Health"] = int(row[1])
                server_monsters[server_id]["Level"] = int(row[2])
                server_monsters[server_id]["Attack"] = int(row[3])
                server_monsters[server_id]["Defense"] = int(row[4])
                server_monsters[server_id]["Element"] = row[5]
                server_monsters[server_id]["MagicAttack"] = int(row[6])
                server_monsters[server_id]["PictureLink"] = row[7]
                server_monsters[server_id]["MaxCurrencyDrop"] = int(row[8])
                monster_health[server_id] = int(row[6])
            server_encounters[server_id] = True
            await direct_message(message, "Beginning monster encounter with " + monster_name + ".")
            await dm_tracker[message.author.id]["commandchannel"].send(">>> The level " + str(server_monsters[server_id]["Level"]) + " **" + monster_name + "** has appeared in " + str(dm_tracker[message.author.id]["commandchannel"].name) + "! As described: " + server_monsters[server_id]["Description"] + "\n" + server_monsters[server_id]["PictureLink"] + "\n\nGood luck!\n\n<@" + str(list(server_party[server_id])[encounter_turn[server_id]].id) + "> gets first blood!")
            return
        elif current_command == 'givebuff':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_simple_menu(message, "Buffs", "BuffName")
                response = "Please select a spell to give to the character.\n\n" + menu
                
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                spell_id = message.content
                char_id = dm_tracker[message.author.id]["fielddict"][0]
                result = await commit_sql("""INSERT INTO BuffSkills (ServerId, UserId, CharId, BuffId) VALUES (%s, %s, %s, %s);""", (str(dm_tracker[message.author.id]["server_id"]), str(message.author.id), char_id, spell_id))
                char_record = await select_sql("""SELECT CharacterName FROM CharacterProfiles WHERE Id=%s;""",(str(char_id),))
                
                for row in char_record:
                    char_name = row[0]
                spell_record = await select_sql("""SELECT BuffName FROM Buffs WHERE Id=%s;""",(str(spell_id),))
                for row in spell_record:
                    spell_name = row[0]
                    
                if result:
                    await direct_message(message, char_name + " can now use the buff " + spell_name + "!")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + char_name + " can now use the buff " + spell_name + "!")
                    await initialize_dm(message.author.id)
                else:
                    await direct_message(message, "Database error!")
                return
        elif current_command == 'givestatpoints':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                await direct_message(message, "Enter the number of stat points to grant.")
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                records = await select_sql("""SELECT UserId,CharacterName FROM CharacterProfiles WHERE Id=%s""",(dm_tracker[message.author.id]["fielddict"][0],))
                for row in records:
                    char_user = int(row[0])
                    char_name = row[1]
                available_points[server_id][char_user] = int(message.content)
                await direct_message(message, "You have granted " + char_name + " " + message.content + " points to spend.")
                await dm_tracker[message.author.id]["commandchannel"].send(">>> " + char_name + ", played by <@" + str(char_user) + ">, has been granted " + message.content + " stat points to spend!\n\n")
                return
        elif current_command == 'equiparmament':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_menu(message, "ArmamentInventory","Armaments","ArmamentId","CharacterId","ArmamentName",message.content)
                response = "Select an armament from your inventory to equip by replying with the ID below:\n\n" + menu
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                response = "Please select a slot for this item (Head, Left Hand, Right Hand, Chest, Feet):\n\n"
                await direct_message(message,response)
                dm_tracker[message.author.id]["currentfield"] = 2
                return
            if current_field == 2:
                dm_tracker[message.author.id]["fielddict"].append(message.content.replace(' ',''))
                target_slot = message.content.replace(' ','') + "Id"
                records = await select_sql("""SELECT ArmamentName,Slot,MinimumLevel FROM Armaments WHERE Id=%s""",(field_dict[1],))
                for row in records:
                        arm_name = row[0]
                        slot = row[1]
                        minimumlevel = row[2]
                records = await select_sql("""SELECT CharacterName,Level FROM CharacterProfiles WHERE Id=%s""", (field_dict[0],))
                for row in records:
                        char_name = row[0]
                        level = row[1]
                records = await select_sql("""SELECT IFNULL(""" + target_slot + """,'None') FROM CharacterArmaments WHERE CharacterId=%s;""", (field_dict[0],))
                for row in records:
                    char_slot = row[0]
                try: char_slot
                except: 
                    char_slot = 'None'
                    result = await commit_sql("""INSERT INTO CharacterArmaments (ServerId,UserId,CharacterId, HeadId, LeftHandId, RightHandId, ChestId, FeetId) VALUES (%s, %s, %s, NULL, NULL, NULL, NULL, NULL);""",(str(dm_tracker[message.author.id]["server_id"]), str(message.author.id), field_dict[0]))
                    if not result:
                        await direct_message(message, "Database error!")
                        return
                if int(level) < int(minimumlevel):
                    await direct_message(message, char_name + " isn't a high enough level to equip this armament!")
                    return
                if char_slot != 'None' and int(char_slot) != 0:
                    await direct_message(message, "You already have an armament equipped in this slot!")
                    return
                if (slot == 'Hand' and 'Hand' not in target_slot) and (slot != target_slot):
                    await direct_message(message, "This armament does not go in this slot!")
                    return

 
                result = await commit_sql("""UPDATE CharacterArmaments SET """ + target_slot + """=%s WHERE CharacterId=%s""",(field_dict[1],field_dict[0]))
                if result:
                    await direct_message(message, char_name + " now has equipped " + arm_name +" in the " + message.content)
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + char_name + " now has equipped " + arm_name +" in the " + message.content)
                else:
                    await direct_message(mesage, "Database error!")
                return
        elif current_command == 'unequiparmament':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                records = await select_sql("""SELECT IFNULL(HeadId,'0'), IFNULL(LeftHandId,'0'), IFNULL(RightHandId,'0'), IFNULL(ChestId,'0'), IFNULL(FeetId,'0') FROM CharacterArmaments WHERE CharacterId=%s;""",(message.content,))
                for row in records:
                    head_id = row[0]
                    left_id = row[1]
                    right_id = row[2]
                    chest_id = row[3]
                    feet_id = row[4]
                if not records:
                    await direct_message(message, "This character has nothing equipped!")
                    return
                records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (head_id,))
                for row in records:
                    head_name = row[0]
                try: head_name
                except: head_name = "None"
                records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (left_id,))
                for row in records:
                    left_name = row[0]
                try: left_name
                except: left_name = "None"
                records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (right_id,))
                for row in records:
                    right_name = row[0]
                try: right_name
                except: right_name = "None"
                records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (chest_id,))
                for row in records:
                    chest_name = row[0]
                try: chest_name
                except: chest_name = "None"
                records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (feet_id,))
                for row in records:
                    feet_name = row[0]
                try: feet_name
                except: feet_name = "None"

                menu = "Current Armaments Equipped\n\nHead: **" +head_id + "** - " + head_name + "\nLeftHand: **" + left_id + "** - " + left_name + "\nRightHand: **" + right_id +  "** - " + right_name + "\nChest: **" + chest_id + "** - " + chest_name + "\nFeet: **" + feet_id + "** - " + feet_name +"\n"

                response = "Select an armament from your inventory to unequip by replying with the slot below:\n\n" + menu
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                if not re.search(r"Hand|Feet|Chest|Head",message.content):
                    await direct_message(message, "Invalid slot for armaments! Please try again.")
                    return

                result = await commit_sql("""UPDATE CharacterArmaments SET """ + message.content + "Id=%s WHERE CharacterId=%s;",('0',field_dict[0]))
                if result:
                    await direct_message(message, "Unequipped the " + message.content + " slot.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Unequipped " + message.content + " slot.")
                else:
                    await direct_message(message, "Database error!")
                return
                      
        elif current_command == 'trade':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_menu(message, "Inventory", "Equipment","EquipmentId", "CharacterId", "EquipmentName", dm_tracker[message.author.id]["fielddict"][0])
                if not menu:
                    await direct_message(message, "You don't have any items for this character!")
                    return
                    
                response = "**YOUR INVENTORY**\n\n" + menu
                await direct_message(message, "Select an item to trade:\n\n" + response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            elif dm_tracker[message.author.id]["currentfield"] == 1:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
                response = "Please select a chraacter to trade the item to.\n\n" + menu
                
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 2
                return            
            elif dm_tracker[message.author.id]["currentfield"] == 2:
            
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                item_id = message.content
                records = await select_sql("""SELECT EquipmentName,EquipmentCost FROM Equipment WHERE Id=%s""", (dm_tracker[message.author.id]["fielddict"][1],))
                
                if not records:
                    await reply_message(message, "No item found by that ID!")
                    return
                for row in records:
                    equip_name = row[0]
                    cost = float(row[1])
                records = await select_sql("""SELECT CharacterName,UserId,Currency FROM CharacterProfiles WHERE Id=%s;""",( dm_tracker[message.author.id]["fielddict"][0],))
                if not records:
                    await reply_message(message, "No character found by that name!")
                    return
                for row in records:
                    char_name = row[0]
                    user_id = int(row[1])
                    currency = float(row[2])
                if user_id != message.author.id:
                    await reply_message(message, "This isn't your character!")
                    return
                records = await select_sql("""SELECT CharacterName,UserId FROM CharacterProfiles WHERE Id=%s;""", (dm_tracker[message.author.id]["fielddict"][2],))
                if not records:
                    await direct_message(message, "No character exists by that target ID!")
                    return
                for row in records:
                    target_name = row[0]
                    target_user = row[1]
                    
                result = await commit_sql("""DELETE FROM Inventory WHERE ServerId=%s AND UserId=%s AND CharacterId=%s AND EquipmentId=%s;""",(str(dm_tracker[message.author.id]["server_id"]), str(message.author.id), dm_tracker[message.author.id]["fielddict"][0], item_id))
                if result:

                    result_2 = await commit_sql("""INSERT INTO Inventory (ServerId,UserId,CharacterId ,EquipmentId) VALUES (%s, %s, %s, %s);""", (str(dm_tracker[message.author.id]["server_id"]), str(target_user), str(dm_tracker[message.author.id]["fielddict"][2]), dm_tracker[message.author.id]["fielddict"][1]))
                    if not result_2:
                        await direct_message(message, "Database error!")
                        return
                    await direct_message(message, char_name + " traded to " + target_name + " with mun of <@" + str(target_user) + ">.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + char_name + " traded to " + target_name + " with mun of <@" + str(target_user) + ">.")                        
                else:
                    await reply_message(message, "You don't own this item!")
                await initialize_dm(message.author.id)    
                return            
        elif current_command == 'tradearms':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_menu(message, "ArmamentInventory", "Armaments","ArmamentId", "CharacterId", "ArmamentName", dm_tracker[message.author.id]["fielddict"][0])
                if not menu:
                    await direct_message(message, "You don't have any items for this character!")
                    return
                    
                response = "**YOUR INVENTORY**\n\n" + menu
                await direct_message(message, "Select an armament to trade:\n\n" + response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            elif dm_tracker[message.author.id]["currentfield"] == 1:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
                response = "Please select a chraacter to trade the item to.\n\n" + menu
                
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 2
                return            
            elif dm_tracker[message.author.id]["currentfield"] == 2:
            
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                item_id = message.content
                records = await select_sql("""SELECT ArmamentName,ArmamentCost FROM Armaments WHERE Id=%s""", (dm_tracker[message.author.id]["fielddict"][1],))
                
                if not records:
                    await reply_message(message, "No item found by that ID!")
                    return
                for row in records:
                    equip_name = row[0]
                    cost = float(row[1])
                records = await select_sql("""SELECT CharacterName,UserId,Currency FROM CharacterProfiles WHERE Id=%s;""",( dm_tracker[message.author.id]["fielddict"][0],))
                if not records:
                    await reply_message(message, "No character found by that name!")
                    return
                for row in records:
                    char_name = row[0]
                    user_id = int(row[1])
                    currency = float(row[2])
                if user_id != message.author.id:
                    await reply_message(message, "This isn't your character!")
                    return
                records = await select_sql("""SELECT CharacterName,UserId FROM CharacterProfiles WHERE Id=%s;""", (dm_tracker[message.author.id]["fielddict"][2],))
                if not records:
                    await direct_message(message, "No character exists by that target ID!")
                    return
                for row in records:
                    target_name = row[0]
                    target_user = row[1]
                    
                result = await commit_sql("""DELETE FROM ArmamentInventory WHERE ServerId=%s AND UserId=%s AND CharacterId=%s AND ArmamentId=%s;""",(str(dm_tracker[message.author.id]["server_id"]), str(message.author.id), dm_tracker[message.author.id]["fielddict"][0], item_id))
                if result:

                    result_2 = await commit_sql("""INSERT INTO ArmamentInventory (ServerId,UserId,CharacterId ,ArmamentId) VALUES (%s, %s, %s, %s);""", (str(dm_tracker[message.author.id]["server_id"]), str(target_user), str(dm_tracker[message.author.id]["fielddict"][2]), dm_tracker[message.author.id]["fielddict"][1]))
                    if not result_2:
                        await direct_message(message, "Database error!")
                        return
                    await direct_message(message, char_name + " traded to " + target_name + " with mun of <@" + str(target_user) + ">.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + char_name + " traded to " + target_name + " with mun of <@" + str(target_user) + ">.")                        
                else:
                    await reply_message(message, "You don't own this item!")
                await initialize_dm(message.author.id)    
                return            
        elif current_command == 'giveitem':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_simple_menu(message, "Equipment", "EquipmentName")
                response = "Select an item to give to the character by replying to the DM with the ID of the item:\n\n"
                await direct_message(message, response + menu)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                records = await select_sql("""SELECT CharacterName FROM CharacterProfiles WHERE Id=%s""",(str(dm_tracker[message.author.id]["fielddict"][0]),))
                for row in records:
                    char_name = row[0]  
                records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s""",(str(message.content),))
                for row in records:
                    item_name = row[0]
                result = await commit_sql("""INSERT INTO Inventory (ServerId, UserId, CharacterId, EquipmentId) VALUES (%s, %s, %s, %s);""", (str(dm_tracker[message.author.id]["server_id"]), str(message.author.id), dm_tracker[message.author.id]["fielddict"][0], message.content))
                if result:
                    await reply_message(message, char_name + " can now use the item " + item_name + "!")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + char_name + " can now use the item " + item_name + "!")
                else:
                    await reply_message(message, "Database error!") 
        elif current_command == 'givearmament':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_simple_menu(message, "Armaments", "ArmamentName")
                response = "Select an armament to give to the character by replying to the DM with the ID of the armament:\n\n"
                await direct_message(message, response + menu)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                records = await select_sql("""SELECT CharacterName FROM CharacterProfiles WHERE Id=%s""",(str(dm_tracker[message.author.id]["fielddict"][0]),))
                for row in records:
                    char_name = row[0]
                records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s""",(str(message.content),))
                for row in records:
                    item_name = row[0]
                result = await commit_sql("""INSERT INTO ArmamentInventory (ServerId, UserId, CharacterId, ArmamentId) VALUES (%s, %s, %s, %s);""", (str(dm_tracker[message.author.id]["server_id"]), str(message.author.id), dm_tracker[message.author.id]["fielddict"][0], message.content))
                if result:
                    await reply_message(message, char_name + " can now use the armament " + item_name + "!")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + char_name + " can now use the armament " + item_name + "!")
                else:
                    await reply_message(message, "Database error!") 
        elif current_command == 'givespell':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_simple_menu(message, "Spells", "SpellName")
                response = "Please select a spell to give to the character.\n\n" + menu
                
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                spell_id = message.content
                char_id = dm_tracker[message.author.id]["fielddict"][0]
                result = await commit_sql("""INSERT INTO MagicSkills (ServerId, UserId, CharacterId, SpellId) VALUES (%s, %s, %s, %s);""", (str(dm_tracker[message.author.id]["server_id"]), str(message.author.id), char_id, spell_id))
                char_record = await select_sql("""SELECT CharacterName FROM CharacterProfiles WHERE Id=%s;""",(str(char_id),))
                
                for row in char_record:
                    char_name = row[0]
                spell_record = await select_sql("""SELECT SpellName FROM Spells WHERE Id=%s;""",(str(spell_id),))
                for row in spell_record:
                    spell_name = row[0]
                    
                if result:
                    await direct_message(message, char_name + " can now use the spell " + spell_name + "!")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + char_name + " can now use the spell " + spell_name + "!")
                    
                else:
                    await direct_message(message, "Database error!")
                await initialize_dm(message.author.id)
                return
        elif current_command == 'takespell':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_menu(message, "MagicSkills","Spells","SpellId","UserId","SpellName",str(message.author.id))
                if not menu:
                    await direct_message(message, "This character has no spells!")
                    return
                response = "Please select a spell to take from the character.\n\n" + menu
                
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                spell_id = message.content
                char_id = dm_tracker[message.author.id]["fielddict"][0]
                result = await commit_sql("""DELETE FROM MagicSkills WHERE ServerId=%s AND CharacterId=%s AND SpellId=%s;""", (str(dm_tracker[message.author.id]["server_id"]), char_id, spell_id))
                char_record = await select_sql("""SELECT CharacterName FROM CharacterProfiles WHERE Id=%s;""",(str(char_id),))
                
                for row in char_record:
                    char_name = row[0]
                spell_record = await select_sql("""SELECT SpellName FROM Spells WHERE Id=%s;""",(str(spell_id),))
                for row in spell_record:
                    spell_name = row[0]
                    
                if result:
                    await direct_message(message, char_name + " can no longer use the spell " + spell_name + "!")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + char_name + " can no longer uae the spell " + spell_name + "!")
                else:
                    await direct_message(message, "Database error!")
                await initialize_dm(message.author.id)
                return            
        elif current_command == 'givemelee':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_simple_menu(message, "Melee", "AttackName")
                response = "Please select a melee to give to the character.\n\n" + menu
                
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
                
            if current_field == 1:
                melee_id = message.content
                char_id = dm_tracker[message.author.id]["fielddict"][0]
                result = await commit_sql("""INSERT INTO MeleeSkills (ServerId, UserId, CharacterId, MeleeId) VALUES (%s, %s, %s, %s);""", (str(dm_tracker[message.author.id]["server_id"]), str(message.author.id), char_id, melee_id))
                char_record = await select_sql("""SELECT CharacterName FROM CharacterProfiles WHERE Id=%s;""",(str(char_id),))
                
                for row in char_record:
                    char_name = row[0]
                melee_record = await select_sql("""SELECT AttackName FROM Melee WHERE Id=%s;""",(str(melee_id),))
                for row in melee_record:
                    melee_name = row[0]
                    
                if result:
                    await direct_message(message, char_name + " can now use the melee " + melee_name + "!")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + char_name + " can now use the melee " + melee_name + "!")
                else:
                    await direct_message(message, "Database error!")
                await initialize_dm(message.author.id)
                return
        elif current_command == 'changecharowner':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                players = dm_tracker[message.author.id]["commandchannel"].guild.members
                menu = "**LIST OF PLAYERS**\n\n"
                for player in players:
                    for role in player.roles:
                        if role.id == guild_settings[dm_tracker[message.author.id]["server_id"]]["PlayerRole"]:
                            menu = menu + "**" + str(player.id) + "** - " + player.name + "\n"
                await direct_message(message, "Please select a player to change the owner to below:\n\n" + menu)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                result = await commit_sql("""UPDATE CharacterProfiles SET UserId=%s WHERE Id=%s;""",(message.content, field_dict[0]))
                if result:
                    await direct_message(message, "Character owner updated.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Character ID " + field_dict[0] + " updated to be owned by <@" + message.content + ">")
                else:
                    await direct_message("Database error!")
            
        elif current_command == 'addstatpoints':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                await direct_message(message, "Please enter a statistic to modify (Attack, MagicAttack, Defense, Agility, Intellect, Charisma):")
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                if not re.search(r"Attack|MagicAttack|Defense|Agility|Intellect|Charisma", message.content):
                    await direct_message(message, "Invalid field! Please try again.")
                    return
                await direct_message(message, "Please enter the number of points to add (current number of points **" + str(available_points[dm_tracker[message.author.id]["server_id"]][message.author.id]) + "**):")
                dm_tracker[message.author.id]["currentfield"] = 2  
                return
            if current_field == 2:
                points = int(message.content)
                
                if points > available_points[dm_tracker[message.author.id]["server_id"]][message.author.id]:
                    await direct_message(message, "You don't have that many points! Please enter a number less than " + str(available_points[dm_tracker[message.author.id]["server_id"]][message.author.id]))
                    return
                records = await select_sql("SELECT " + field_dict[1] + " FROM CharacterProfiles WHERE Id=%s;", (str(field_dict[0]),))
                for row in records:
                    current_stat = int(row[0])
                result = await commit_sql("UPDATE CharacterProfiles SET " + field_dict[1] + "=%s WHERE Id=%s;", (str(points + current_stat), str(field_dict[0])))
                if result:
                    response = "Character successfully added " + str(points) + " to " + field_dict[1] + "."
                    available_points[dm_tracker[message.author.id]["server_id"]][message.author.id] = available_points[dm_tracker[message.author.id]["server_id"]][message.author.id] - points
                    await direct_message(message, response)
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
                else:
                    await direct_message(message, "Database error!")
                return
               
        elif current_command == 'takecurrency':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                records = await select_sql("""SELECT Currency FROM CharacterProfiles WHERE ServerId=%s;""", (str(dm_tracker[message.author.id]["server_id"]),))
                for row in records:
                    balance = int(row[0])
                dm_tracker[message.author.id]["parameters"] = str(balance)    
                await direct_message(message, "Current character balance: " + str(balance) + "\nPlease enter the amount to take from the character:")
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                amount = int(message.content)
                if amount > int(dm_tracker[message.author.id]["parameters"]):
                    await direct_message(message, "There isn't that much in their wallet! Please choose an amount lower than that!")
                    return
                records = await select_sql("""SELECT Currency FROM CharacterProfiles WHERE Id=%s;""", (str(dm_tracker[message.author.id]["fielddict"][0]),))
                for row in records:
                    current_currency = int(row[0])
                new_total = current_currency - amount
                balance = int(dm_tracker[message.author.id]["parameters"])
                new_bank = balance - amount
                result = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s WHERE Id=%s;""",(str(new_total), str(dm_tracker[message.author.id]["fielddict"][0])))
                if result:
                    result2 = await commit_sql("""UPDATE GuildSettings SET GuildBankBalance=%s WHERE ServerId=%s;""",(str(new_bank),str(dm_tracker[message.author.id]["server_id"])))
                    if result2:
                        await direct_message(message, "Character now has a thinner wallet!")
                        await dm_tracker[message.author.id]["commandchannel"].send(">>> Character now has a fatter wallet!")
                    else:
                        await direct_message(message, "Database error!")
                else:
                    await direct_message(message, "Database error!")                
        elif current_command == 'givecurrency':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                records = await select_sql("""SELECT GuildBankBalance FROM GuildSettings WHERE ServerId=%s;""", (str(dm_tracker[message.author.id]["server_id"]),))
                for row in records:
                    balance = int(row[0])
                dm_tracker[message.author.id]["parameters"] = str(balance)    
                await direct_message(message, "Current bank balance: " + str(balance) + "\nPlease enter the amount to grant the character:")
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                amount = int(message.content)
                if amount > int(dm_tracker[message.author.id]["parameters"]):
                    await direct_message(message, "There isn't that much in the bank! Please choose an amount lower than the bank balance!")
                    return
                records = await select_sql("""SELECT Currency FROM CharacterProfiles WHERE Id=%s;""", (str(dm_tracker[message.author.id]["fielddict"][0]),))
                for row in records:
                    current_currency = int(row[0])
                new_total = current_currency + amount
                balance = int(dm_tracker[message.author.id]["parameters"])
                new_bank = balance - amount
                result = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s WHERE Id=%s;""",(str(new_total), str(dm_tracker[message.author.id]["fielddict"][0])))
                if result:
                    result2 = await commit_sql("""UPDATE GuildSettings SET GuildBankBalance=%s WHERE ServerId=%s;""",(str(new_bank),str(dm_tracker[message.author.id]["server_id"])))
                    if result2:
                        await direct_message(message, "Character now has a fatter wallet!")
                        await dm_tracker[message.author.id]["commandchannel"].send(">>> Character now has a fatter wallet!")
                    else:
                        await direct_message(message, "Database error!")
                else:
                    await direct_message(message, "Database error!")
        elif current_command == 'takemelee':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_menu(message, "MeleeSkills","Melee","MeleeId","CharacterId","AttackName",message.content)
                if not menu:
                    await direct_message(message, "This character has no attacks!")
                    return
                response = "Please select a melee attack to take from the character.\n\n" + menu
                
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                melee_id = message.content
                char_id = dm_tracker[message.author.id]["fielddict"][0]
                result = await commit_sql("""DELETE FROM MeleeSkills WHERE ServerId=%s AND CharacterId=%s AND MeleeId=%s;""", (str(dm_tracker[message.author.id]["server_id"]), char_id, melee_id))
                char_record = await select_sql("""SELECT CharacterName FROM CharacterProfiles WHERE Id=%s;""",(str(char_id),))
                
                for row in char_record:
                    char_name = row[0]
                melee_record = await select_sql("""SELECT AttackName FROM Melee WHERE Id=%s;""",(str(melee_id),))
                for row in melee_record:
                    melee_name = row[0]
                    
                if result:
                    await direct_message(message, char_name + " can no longer use the melee " + melee_name + "!")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + char_name + " can no longer uae the melee " + melee_name + "!")
                else:
                    await direct_message(message, "Database error!")
                await initialize_dm(message.author.id)    
                return           
            pass
        elif current_command == 'setsparchar':
            records = await select_sql("""SELECT UserId,Attack,Defense,MagicAttack,Health,Mana,Level,Experience,Stamina,Agility,Intellect,Charisma,Id,CharacterName,PictureLink FROM CharacterProfiles WHERE Id=%s;""",(message.content,))
            if not records:
                await reply_message(message, "No character found!")
                return
            server_id = dm_tracker[message.author.id]["server_id"]
            user_id = message.author.id
            for row in records:
                char_id = row[0]
                if int(char_id) != message.author.id:
                    await reply_message(message, "This character is not yours!")
                    return
                mass_spar_chars[server_id][user_id] = { }
                mass_spar_chars[server_id][user_id]["CharName"] = row[13]
                mass_spar_chars[server_id][user_id]["Attack"] = int(row[1])
                mass_spar_chars[server_id][user_id]["Defense"] = int(row[2])
                mass_spar_chars[server_id][user_id]["MagicAttack"] = int(row[3])
                mass_spar_chars[server_id][user_id]["Health"] = int(row[4])
                mass_spar_chars[server_id][user_id]["MaxHealth"] = int(row[4])
                mass_spar_chars[server_id][user_id]["Mana"] = int(row[5])
                mass_spar_chars[server_id][user_id]["MaxMana"] = int(row[5])
                mass_spar_chars[server_id][user_id]["Level"] = int(row[6])
                mass_spar_chars[server_id][user_id]["Experience"] = int(row[7])
                mass_spar_chars[server_id][user_id]["MaxStamina"] = int(row[8])
                mass_spar_chars[server_id][user_id]["Stamina"] = int(row[8])
                mass_spar_chars[server_id][user_id]["Agility"] = int(row[9])
                mass_spar_chars[server_id][user_id]["Intellect"] = int(row[10])
                mass_spar_chars[server_id][user_id]["Charisma"] = int(row[11])
                mass_spar_chars[server_id][user_id]["CharId"] = int(row[12])
                mass_spar_chars[server_id][user_id]["PictureLink"] = row[14]
                mass_spar_chars[server_id][user_id]["TotalDamage"] = 0
                char_name = row[13]
            records = await select_sql("""SELECT IFNULL(HeadId,'None'),IFNULL(ChestId,'None'),IFNULL(LeftHandId,'None'),IFNULL(RightHandId,'None'),IFNULL(FeetId,'None') FROM CharacterArmaments WHERE CharacterId=%s;""",(str(mass_spar_chars[server_id][user_id]["CharId"]),))
            if records:
                for row in records:
                    for x in range(0,len(row)):
                        item = row[x]
                        if item != 'None':
                            arm_records = await select_sql("""SELECT MinimumLevel,Defense,StatMod,Modifier FROM Armaments WHERE Id=%s;""", (str(item),))
                            for arm_row in arm_records:
                                if int(arm_row[0]) < mass_spar_chars[server_id][user_id]["Level"]:
                                    if int(arm_row[1]) > 0:
                                        mass_spar_chars[server_id][user_id]["Defense"] = mass_spar_chars[server_id][user_id]["Defense"] + int(arm_row[1])
                                        await log_message("applying defense!")
                                    if re.search(r"Attack|MagicAttack|Agility",arm_row[2]):
                                        mass_spar_chars[server_id][user_id][arm_row[2]] = mass_spar_chars[server_id][user_id][arm_row[2]] + int(arm_row[3])
                                        await log_message("applying " + str(arm_row[3]) + " to " + str(arm_row[2]))
            await dm_tracker[message.author.id]["commandchannel"].send(">>> " + message.author.name + " successfully set party character to " + char_name + ".")
            await direct_message(message, "You successfully set your spar character to " + char_name)
            await initialize_dm(message.author.id)
            return
        elif current_command == 'weaponspar':
            if dm_tracker[message.author.id]["currentfield"] == 0:
                char_map = {} 
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                response = "Select a target:\n\n"
                for character in mass_spar_chars[server_id]:
                    char_name = mass_spar_chars[server_id][character]["CharName"]
                    char_id = mass_spar_chars[server_id][character]["CharId"]
                    char_map[char_id] = character
                    response = response + "**" + str(char_id) + "** - " + char_name + "\n"
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 1
                dm_tracker[message.author.id]["parameters"] =  char_map               
                return            
            elif dm_tracker[message.author.id]["currentfield"] == 1:
                user_id = message.author.id
                target_id = dm_tracker[message.author.id]["parameters"][int(message.content)]
            records = await select_sql("""SELECT Id,ArmamentName,MinimumLevel,DamageMin,DamageMax,PictureLink FROM Armaments WHERE Id=%s;""",(field_dict[0],))
            if not records:
                await reply_message(message, "That's not a armament. Try again.")
                return
            else:
                for row in records:
                    arm_id = row[0]
                    arm_name = row[1]
                    min_level = int(row[2])
                    damage_min = int(row[3])
                    damage_max = int(row[4])
                    picture_link = row[5]
                if (min_level > mass_spar_chars[server_id][user_id]["Level"]):
                    await direct_message(message, "You're not a high enough level for this armament. How did you even get it?")
                    return
                await direct_message(message, "Attacking with " + arm_name)
                attack_text = ">>> " + str(mass_spar_chars[server_id][user_id]["CharName"]) + " attacks " + str(mass_spar_chars[server_id][target_id]["CharName"]) + " with " + arm_name + "!\n" + picture_link
                await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][user_id]["CharName"], attack_text, mass_spar_chars[server_id][user_id]["PictureLink"])
#                await dm_tracker[message.author.id]["commandchannel"].send(">>> " + str(mass_spar_chars[server_id][user_id]["CharName"]) + " attacks " + str(mass_spar_chars[server_id][target_id]["CharName"]) + " with " + arm_name + "!\n")
                dodge = await calculate_dodge(mass_spar_chars[server_id][user_id]["Level"], mass_spar_chars[server_id][user_id]["Agility"])
                if dodge:
                    dodge_text = mass_spar_chars[server_id][target_id]["CharName"] + " dodged the attack! No damage taken!"
                    await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][target_id]["CharName"], dodge_text, mass_spar_chars[server_id][target_id]["PictureLink"])
#                    await reply_message(message, mass_spar_chars[server_id][target_id]["CharName"] + " dodged the attack! No damage taken!")
                else:
                    damage = await calculate_damage(random.randint(damage_min, damage_max), mass_spar_chars[server_id][target_id]["Defense"], 1, mass_spar_chars[server_id][user_id]["Level"], mass_spar_chars[server_id][target_id]["Level"])
                    mass_spar_chars[server_id][target_id]["Health"] = mass_spar_chars[server_id][target_id]["Health"] - damage
                    mass_spar_chars[server_id][user_id]["TotalDamage"] = mass_spar_chars[server_id][user_id]["TotalDamage"] + damage
                    hit_text = ">>> " + mass_spar_chars[server_id][target_id]["CharName"] + " was hit by " + mass_spar_chars[server_id][user_id]["CharName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(mass_spar_chars[server_id][target_id]["Health"]) + "!"
                    
                    await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][target_id]["CharName"], hit_text, mass_spar_chars[server_id][target_id]["PictureLink"])
#                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + mass_spar_chars[server_id][target_id]["CharName"] + " was hit by " + mass_spar_chars[server_id][user_id]["CharName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(mass_spar_chars[server_id][target_id]["Health"]))
                    if mass_spar_chars[server_id][target_id]["Health"] < 1:
                        fallen_text = mass_spar_chars[server_id][target_id]["CharName"] + " has no health left and is out of the fight!"
                        await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][target_id]["CharName"], fallen_text, mass_spar_chars[server_id][target_id]["PictureLink"])
                       # await reply_message(message, mass_spar_chars[server_id][target_id]["CharName"] + " has no health left and is out of the fight!")
                        

                        fallen_chars[dm_tracker[message.author.id]["server_id"]][target_id] = {} 
                        fallen_chars[dm_tracker[message.author.id]["server_id"]][target_id] = mass_spar_chars[server_id][target_id]
                        del mass_spar_chars[server_id][target_id]

                if len(mass_spar_chars[server_id]) < 2:
                    response = "<@" + str(message.author.id) + "> is the last one standing and is the spar winner!\n\n**Experience gained:**\n\n"
                    fallen_chars[dm_tracker[message.author.id]["server_id"]][message.author.id] = {} 
                    fallen_chars[dm_tracker[message.author.id]["server_id"]][message.author.id] = mass_spar_chars[server_id][message.author.id]
                    for char in fallen_chars[dm_tracker[message.author.id]["server_id"]].keys():
                    
                        char_id = fallen_chars[server_id][char]["CharId"]
                        await log_message("Level " + str(fallen_chars[server_id][char]["Level"]))
                        new_xp = await calculate_xp(fallen_chars[server_id][char]["Level"], fallen_chars[server_id][char]["Level"], fallen_chars[server_id][char]["TotalDamage"], 1) * 2
                        response = response + "*" + fallen_chars[server_id][char]["CharName"] + "*: " + str(new_xp) + "\n"
                        records = await select_sql("""SELECT Experience FROM CharacterProfiles WHERE Id=%s;""", (str(fallen_chars[server_id][char]["CharId"]),))
                        for row in records:
                            old_xp = int(row[0])
                        total_xp = old_xp + new_xp
                        if total_xp > (guild_settings[server_id]["XPLevelRatio"] * fallen_chars[server_id][char]["Level"]):
                            fallen_chars[server_id][char]["Level"] = fallen_chars[server_id][char]["Level"] + 1
                            available_points[server_id][char] = int(fallen_chars[server_id][char]["Level"] / 2)
                            response = response + "**" + fallen_chars[server_id][char]["CharName"] + "** LEVELED UP TO LEVEL **" + str(fallen_chars[server_id][char]["Level"]) + "!**\nYou have " + str(int(fallen_chars[server_id][char]["Level"]/2)) + " stat points to spend!\n\n"
                            total_xp = 0
                            health = fallen_chars[server_id][user_id]["Level"] * guild_settings[server_id]["HealthLevelRatio"]
                            stamina = fallen_chars[server_id][user_id]["Level"] * guild_settings[server_id]["StaminaLevelRatio"]
                            mana = fallen_chars[server_id][user_id]["Level"] * guild_settings[server_id]["ManaLevelRatio"]
                        result = await commit_sql("""UPDATE CharacterProfiles SET Level=%s,Experience=%s,Health=%s,Stamina=%s,Mana=%s WHERE Id=%s;""",(str(fallen_chars[server_id][target_id]["Level"]),str(total_xp),str(health), str(stamina), str(mana), str(fallen_chars[server_id][target_id]["CharId"])))
                    mass_spar_event[server_id] = False
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
                    return
                            
                if mass_spar_turn[server_id] > len(mass_spar_chars[server_id]) - 2:
                    mass_spar_turn[server_id] = 0
                else:
                    mass_spar_turn[server_id] = mass_spar_turn[server_id] + 1
                await dm_tracker[message.author.id]["commandchannel"].send(">>> <@" + str(list(mass_spar[server_id])[mass_spar_turn[server_id]].id) + ">, it is your turn!")
            await initialize_dm(message.author.id)    
            return
        elif current_command == 'weaponmonster':
            user_id = message.author.id
            server_id = dm_tracker[message.author.id]["server_id"]        
            records = await select_sql("""SELECT Id,ArmamentName,MinimumLevel,DamageMin,DamageMax,PictureLink FROM Armaments WHERE Id=%s;""",(message.content,))
            if not records:
                await reply_message(message, "That's not a armament. Try again.")
                return
            else:
                for row in records:
                    arm_id = row[0]
                    arm_name = row[1]
                    min_level = int(row[2])
                    damage_min = int(row[3])
                    damage_max = int(row[4])
                    picture_link = row[5]
                if (min_level > server_party_chars[server_id][user_id]["Level"]):
                    await direct_message(message, "You're not a high enough level for this armament. How did you even get it?")
                    return
            await direct_message(message, "Attacking the monster with " + arm_name + ".")
            attack_text = ">>> " + str(server_party_chars[server_id][user_id]["CharName"]) + " attacks " + str(server_monsters[server_id]["MonsterName"]) + " with " + arm_name + "!\n\n" + picture_link
            await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_party_chars[server_id][user_id]["CharName"], attack_text, server_party_chars[server_id][user_id]["PictureLink"])
#            await dm_tracker[message.author.id]["commandchannel"].send(">>> " + str(server_party_chars[server_id][user_id]["CharName"]) + " attacks " + str(server_monsters[server_id]["MonsterName"]) + " with " + arm_name + "!")
                  
            dodge = await calculate_dodge(server_monsters[server_id]["Level"], server_party_chars[server_id][user_id]["Agility"])
            if dodge:
                dodge_text = ">>> " + server_monsters[server_id]["MonsterName"] + " dodged the attack! No damage taken!"
                await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_monsters[server_id]["MonsterName"], dodge_text, server_monsters[server_id]["PictureLink"])
               #  await dm_tracker[message.author.id]["commandchannel"].send(">>> " + server_monsters[server_id]["MonsterName"] + " dodged the attack! No damage taken!")
            else:
                damage = await calculate_damage(random.randint(damage_min, damage_max), server_monsters[server_id]["Defense"], 1, server_party_chars[server_id][user_id]["Level"], server_monsters[server_id]["Level"])
                server_monsters[server_id]["Health"] = int(server_monsters[server_id]["Health"] - damage)
                # await dm_tracker[message.author.id]["commandchannel"].send(">>> " + server_monsters[server_id]["MonsterName"] + " was hit by " + server_party_chars[server_id][user_id]["CharName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(server_monsters[server_id]["Health"]))
                hit_text = ">>> " + server_monsters[server_id]["MonsterName"] + " was hit by " + server_party_chars[server_id][user_id]["CharName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(server_monsters[server_id]["Health"]) + "!"
                await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_monsters[server_id]["MonsterName"], hit_text, server_monsters[server_id]["PictureLink"])
                if server_monsters[server_id]["Health"] < 1:
                    fallen_text = ">>> " + server_monsters[server_id]["MonsterName"] + " has no health left and is out of the fight!"
                    await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_monsters[server_id]["MonsterName"], hit_text, server_monsters[server_id]["PictureLink"])
                   # await dm_tracker[message.author.id]["commandchannel"].send(">>> " + server_monsters[server_id]["MonsterName"] + " has no health left and is out of the fight!")
                    currency_earned = random.randint(1, server_monsters[dm_tracker[message.author.id]["server_id"]]["MaxCurrencyDrop"]) / len(server_party)
                    server_encounters[server_id] = False
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Victory!")
                    response = "**Experience gained:**\n\n"
                    for user in server_party_chars[server_id].keys():
                        char_id = server_party_chars[server_id][user]["CharId"]
                        await log_message("Level " + str(server_party_chars[server_id][user]["Level"]))
                        new_xp = await calculate_xp(server_party_chars[server_id][user]["Level"], server_monsters[server_id]["Level"], monster_health[server_id], len(server_party_chars[server_id]))
                        response = response + "*" + server_party_chars[server_id][user]["CharName"] + "*: " + str(new_xp) + "\n"
                        records = await select_sql("""SELECT Experience FROM CharacterProfiles WHERE Id=%s;""", (str(server_party_chars[server_id][user]["CharId"]),))
                        for row in records:
                            old_xp = int(row[0])
                        total_xp = int(old_xp + new_xp)
                        response = response + "Currency earned: " + str(currency_earned) + "\n"
                        if total_xp > (guild_settings[server_id]["XPLevelRatio"] * server_party_chars[server_id][user]["Level"]):
                            server_party_chars[server_id][user]["Level"] = server_party_chars[server_id][user]["Level"] + 1
                            available_points[server_id][user] = int(server_party_chars[server_id][user]["Level"] / 2)
                            response = response + "**" + server_party_chars[server_id][user]["CharName"] + "** LEVELED UP TO LEVEL **" + str(server_party_chars[server_id][user]["Level"]) + "!**\nYou have " + str(int(server_party_chars[server_id][user]["Level"]/2)) + " stat points to spend!\n\n"
                            total_xp = 0
                            health = server_party_chars[server_id][user_id]["Level"] * guild_settings[server_id]["HealthLevelRatio"]
                            stamina = server_party_chars[server_id][user_id]["Level"] * guild_settings[server_id]["StaminaLevelRatio"]
                            mana = server_party_chars[server_id][user_id]["Level"] * guild_settings[server_id]["ManaLevelRatio"]
                            result = await commit_sql("""UPDATE CharacterProfiles SET Level=%s,Experience=%s,Health=%s,Stamina=%s,Mana=%s WHERE Id=%s;""",(str(server_party_chars[server_id][user]["Level"]),str(total_xp),str(health), str(stamina), str(mana), str(server_party_chars[server_id][user]["CharId"])))
                        else:
                            result = await commit_sql("""UPDATE CharacterProfiles SET Level=%s,Experience=%s WHERE Id=%s;""",(str(server_party_chars[server_id][user]["Level"]),str(total_xp), str(server_party_chars[server_id][user]["CharId"])))
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
                    return
            if encounter_turn[server_id] > len(server_party[server_id]) - 2:
                encounter_turn[server_id] = 0
            else:
                encounter_turn[server_id] = encounter_turn[server_id] + 1
            await dm_tracker[message.author.id]["commandchannel"].send(">>> <@" + str(list(server_party[server_id])[encounter_turn[server_id]].id) + ">, it is your turn!")
            return
        elif current_command == 'meleemonster':
            user_id = message.author.id
            server_id = dm_tracker[message.author.id]["server_id"]        
            records = await select_sql("""SELECT Id,StaminaCost,MinimumLevel,DamageMultiplier,AttackName,PictureLink FROM Melee WHERE Id=%s;""",(message.content,))
            if not records:
                await reply_message(message, "That's not a valid attack. Try again.")
                return
            else:
                for row in records:
                    melee_id = row[0]
                    stamina_cost = int(row[1])
                    min_level = int(row[2])
                    damage_multiplier = int(row[3])
                    attack_name = row[4]
                    picture_link = row[5]
                melee_records = await select_sql("""SELECT CharacterId FROM MeleeSkills WHERE CharacterId=%s""", (server_party_chars[server_id][user_id]["CharId"],))
                if not melee_records:
                    await reply_message(message, "You do not know this attack. Try something you do know!")
                    return
                if (min_level > server_party_chars[server_id][user_id]["Level"]):
                    await direct_message(message, "You're not a high enough level for this attack. How did you even learn it?")
                    return
            if server_party_chars[server_id][user_id]["Stamina"] < stamina_cost:
                await direct_message(message, "You do not have sufficient stamina for this melee. Try another melee or restore stamina!")
                return 
            await direct_message(message, "Attacking the monster with " + attack_name + ".")
            server_party_chars[server_id][user_id]["Stamina"] = server_party_chars[server_id][user_id]["Stamina"] - stamina_cost
            
            # await dm_tracker[message.author.id]["commandchannel"].send(">>> " + str(server_party_chars[server_id][user_id]["CharName"]) + " attacks " + str(server_monsters[server_id]["MonsterName"]) + " with " + attack_name + "!\nThis drained " + str(stamina_cost) + " from " + server_party_chars[server_id][user_id]["CharName"] + ", leaving them with " + str(server_party_chars[server_id][user_id]["Stamina"]) + " stamina!")
            attack_text = ">>> " + str(server_party_chars[server_id][user_id]["CharName"]) + " attacks " + str(server_monsters[server_id]["MonsterName"]) + " with " + attack_name + "!\nThis drained " + str(stamina_cost) + " from " + server_party_chars[server_id][user_id]["CharName"] + ", leaving them with " + str(server_party_chars[server_id][user_id]["Stamina"]) + " stamina!\n" + picture_link
            await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_party_chars[server_id][user_id]["CharName"], attack_text, server_party_chars[server_id][user_id]["PictureLink"])            
            dodge = await calculate_dodge(server_monsters[server_id]["Level"], server_party_chars[server_id][user_id]["Agility"])
            if dodge:
                dodge_text = ">>> " + server_monsters[server_id]["MonsterName"] + " dodged the attack! No damage taken!"
                await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_monsters[server_id]["MonsterName"], dodge_text, server_monsters[server_id]["PictureLink"])
               # await dm_tracker[message.author.id]["commandchannel"].send(">>> " + server_monsters[server_id]["MonsterName"] + " dodged the attack! No damage taken!")
            else:
                damage = await calculate_damage(server_party_chars[server_id][user_id]["Attack"], server_monsters[server_id]["Defense"], damage_multiplier, server_party_chars[server_id][user_id]["Level"], server_monsters[server_id]["Level"])
                server_monsters[server_id]["Health"] = int(server_monsters[server_id]["Health"] - damage)
                #await dm_tracker[message.author.id]["commandchannel"].send(">>> " + server_monsters[server_id]["MonsterName"] + " was hit by " + server_party_chars[server_id][user_id]["CharName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(server_monsters[server_id]["Health"]))
                hit_text = ">>> " + server_monsters[server_id]["MonsterName"] + " was hit by " + server_party_chars[server_id][user_id]["CharName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(server_monsters[server_id]["Health"])
                await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_monsters[server_id]["MonsterName"], hit_text, server_monsters[server_id]["PictureLink"])
                if server_monsters[server_id]["Health"] < 1:
                    fallen_text = ">>> " + server_monsters[server_id]["MonsterName"] + " has no health left and is out of the fight!"
                    await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_monsters[server_id]["MonsterName"], fallen_text, server_monsters[server_id]["PictureLink"])
                   # await dm_tracker[message.author.id]["commandchannel"].send(">>> " + server_monsters[server_id]["MonsterName"] + " has no health left and is out of the fight!")
                    currency_earned = random.randint(1, server_monsters[server_id]["MaxCurrencyDrop"]) / len(server_party)
                    server_encounters[server_id] = False
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Victory!")
                    response = "**Experience gained:**\n\n"
                    for user in server_party_chars[server_id].keys():
                        char_id = server_party_chars[server_id][user]["CharId"]
                        await log_message("Level " + str(server_party_chars[server_id][user]["Level"]))
                        new_xp = await calculate_xp(server_party_chars[server_id][user]["Level"], server_monsters[server_id]["Level"], monster_health[server_id], len(server_party_chars[server_id]))
                        response = response + "*" + server_party_chars[server_id][user]["CharName"] + "*: " + str(new_xp) + "\n"
                        records = await select_sql("""SELECT Experience FROM CharacterProfiles WHERE Id=%s;""", (str(server_party_chars[server_id][user]["CharId"]),))
                        for row in records:
                            old_xp = int(row[0])
                        total_xp = int(old_xp + new_xp)
                        response = response + "Currency earned: " + str(currency_earned) + "\n"
                        if total_xp > (guild_settings[server_id]["XPLevelRatio"] * server_party_chars[server_id][user]["Level"]):
                            server_party_chars[server_id][user]["Level"] = server_party_chars[server_id][user]["Level"] + 1
                            available_points[server_id][user] = int(server_party_chars[server_id][user]["Level"] / 2)
                            response = response + "**" + server_party_chars[server_id][user]["CharName"] + "** LEVELED UP TO LEVEL **" + str(server_party_chars[server_id][user]["Level"]) + "!**\nYou have " + str(int(server_party_chars[server_id][user]["Level"]/2)) + " stat points to spend!\n\n"
                            total_xp = 0
                            health = server_party_chars[server_id][user_id]["Level"] * guild_settings[server_id]["HealthLevelRatio"]
                            stamina = server_party_chars[server_id][user_id]["Level"] * guild_settings[server_id]["StaminaLevelRatio"]
                            mana = server_party_chars[server_id][user_id]["Level"] * guild_settings[server_id]["ManaLevelRatio"]
                            result = await commit_sql("""UPDATE CharacterProfiles SET Level=%s,Experience=%s,Health=%s,Stamina=%s,Mana=%s WHERE Id=%s;""",(str(server_party_chars[server_id][user]["Level"]),str(total_xp),str(health), str(stamina), str(mana), str(server_party_chars[server_id][user]["CharId"])))
                        else:
                            result = await commit_sql("""UPDATE CharacterProfiles SET Level=%s,Experience=%s WHERE Id=%s;""",(str(server_party_chars[server_id][user]["Level"]),str(total_xp), str(server_party_chars[server_id][user]["CharId"])))
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
                    return
            if encounter_turn[server_id] > len(server_party[server_id]) - 2:
                encounter_turn[server_id] = 0
            else:
                encounter_turn[server_id] = encounter_turn[server_id] + 1
            await dm_tracker[message.author.id]["commandchannel"].send(">>> <@" + str(list(server_party[server_id])[encounter_turn[server_id]].id) + ">, it is your turn!")
            return
        elif current_command == 'castmonster':
            user_id = message.author.id
            
            server_id = dm_tracker[message.author.id]["server_id"]
            records = await select_sql("""SELECT Id,Element,ManaCost,MinimumLevel,DamageMultiplier,SpellName,PictureLink FROM Spells WHERE Id=%s;""",(message.content,))
            if not records:
                await direct_message(message, "That's not a valid spell. Try again.")
                return
            else:
                for row in records:
                    spell_id = row[0]
                    element = row[1]
                    mana_cost = int(row[2])
                    min_level = int(row[3])
                    damage_multiplier = int(row[4])
                    spell_name = row[5]
                    picture_link = row[6]
                spell_records = await select_sql("""SELECT CharacterId FROM MagicSkills WHERE CharacterId=%s""", (server_party_chars[server_id][user_id]["CharId"],))
                if not spell_records:
                    await direct_message(message, "You do not know this spell. Try something you do know!")
                    return
                if (min_level > server_party_chars[server_id][user_id]["Level"]):
                    await direct_message(message, "You're not a high enough level for this spell. How did you even learn it?")
                    return
            if server_party_chars[server_id][user_id]["Mana"] < mana_cost:
                await direct_message(message, "You do not have sufficient mana for this spell. Try another spell or restore mana!")
                return
            await direct_message(message, "Attacking monster with " + spell_name + ".")
            server_party_chars[server_id][user_id]["Mana"] = int(server_party_chars[server_id][user_id]["Mana"] - mana_cost)
            attack_text = ">>> " + str(server_party_chars[server_id][user_id]["CharName"]) + " attacks " + str(server_monsters[server_id]["MonsterName"]) + " with " + spell_name + "!\nThis drained " + str(mana_cost) + " from " + server_party_chars[server_id][user_id]["CharName"] + ", leaving them with " + str(server_party_chars[server_id][user_id]["Mana"]) + " mana!\n\n" +  picture_link
            await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_party_chars[server_id][user_id]["CharName"], attack_text, server_party_chars[server_id][user_id]["PictureLink"])
#            await dm_tracker[user_id]["commandchannel"].send(">>> " + str(server_party_chars[server_id][user_id]["CharName"]) + " attacks " + str(server_monsters[server_id]["MonsterName"]) + " with " + spell_name + "!\nThis drained " + str(mana_cost) + " from " + server_party_chars[server_id][user_id]["CharName"] + ", leaving them with " + str(server_party_chars[server_id][user_id]["Mana"]) + " mana!")
            dodge = await calculate_dodge(server_monsters[server_id]["Level"], server_party_chars[server_id][user_id]["Agility"])
            if dodge:
                dodge_text = ">>> " + server_monsters[server_id]["MonsterName"] + " dodged the attack! No damage taken!"
                await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_monsters[server_id]["MonsterName"], dodge_text, server_monsters[server_id]["PictureLink"])
               # await dm_tracker[user_id]["commandchannel"].send(">>> " + server_monsters[server_id]["MonsterName"] + " dodged the attack! No damage taken!")
            else:
                damage = await calculate_damage(server_party_chars[server_id][user_id]["MagicAttack"], server_monsters[server_id]["Defense"], damage_multiplier, server_party_chars[server_id][user_id]["Level"], server_monsters[server_id]["Level"])
                server_monsters[server_id]["Health"] = int(server_monsters[server_id]["Health"] - damage)
                hit_text = ">>> " + server_monsters[server_id]["MonsterName"] + " was hit by " + server_party_chars[server_id][user_id]["CharName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(server_monsters[server_id]["Health"])
                await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_monsters[server_id]["MonsterName"], hit_text, server_monsters[server_id]["PictureLink"])
#                await dm_tracker[user_id]["commandchannel"].send(">>> " + server_monsters[server_id]["MonsterName"] + " was hit by " + server_party_chars[server_id][user_id]["CharName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(server_monsters[server_id]["Health"]))
                if server_monsters[server_id]["Health"] < 1:
                    fallen_text = ">>> " + server_monsters[server_id]["MonsterName"] + " has no health left and is out of the fight!"
                    await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_monsters[server_id]["MonsterName"], hit_text, server_monsters[server_id]["PictureLink"])
#                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + server_monsters[server_id]["MonsterName"] + " has no health left and is out of the fight!")
                    
                    server_encounters[server_id] = False
                    currency_earned = random.randint(1, server_monsters[server_id]["MaxCurrencyDrop"]) / len(server_party)
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Victory!")
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
                        response = response + "Currency earned: " + str(currency_earned) + "\n"
                        if total_xp > (guild_settings[server_id]["XPLevelRatio"] * server_party_chars[server_id][user]["Level"]):
                            server_party_chars[server_id][user]["Level"] = server_party_chars[server_id][user]["Level"] + 1
                            available_points[server_id][user] = int(server_party_chars[server_id][user]["Level"] / 2)
                            response = response + "**" + server_party_chars[server_id][user]["CharName"] + "** LEVELED UP TO LEVEL **" + str(server_party_chars[server_id][user]["Level"]) + "!**\nYou have " + str(int(server_party_chars[server_id][user]["Level"]/2)) + " stat points to spend!\n\n"
                            health = server_party_chars[server_id][user_id]["Level"] * guild_settings[server_id]["HealthLevelRatio"]
                            stamina = server_party_chars[server_id][user_id]["Level"] * guild_settings[server_id]["StaminaLevelRatio"]
                            mana = server_party_chars[server_id][user_id]["Level"] * guild_settings[server_id]["ManaLevelRatio"]
                            result = await commit_sql("""UPDATE CharacterProfiles SET Level=%s,Experience=%s,Health=%s,Stamina=%s,Mana=%s WHERE Id=%s;""",(str(server_party_chars[server_id][user]["Level"]),str(total_xp),str(health), str(stamina), str(mana), str(server_party_chars[server_id][user]["CharId"])))
                        else:
                            result = await commit_sql("""UPDATE CharacterProfiles SET Level=%s,Experience=%s WHERE Id=%s;""",(str(server_party_chars[server_id][user]["Level"]),str(total_xp), str(server_party_chars[server_id][user]["CharId"])))
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
                    server_monsters[server_id] = { }
                    return
            if encounter_turn[server_id] > len(server_party[server_id]) - 2:
                encounter_turn[server_id] = 0
            else:
                encounter_turn[server_id] = encounter_turn[server_id] + 1
            await dm_tracker[message.author.id]["commandchannel"].send(">>> <@" + str(list(server_party[server_id])[encounter_turn[server_id]].id) + ">, it is your turn!")  
            return
        elif current_command == 'meleespar':
            if dm_tracker[message.author.id]["currentfield"] == 0:
                char_map = {} 
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                response = "Select a target:\n\n"
                for character in mass_spar_chars[server_id]:
                    char_name = mass_spar_chars[server_id][character]["CharName"]
                    char_id = mass_spar_chars[server_id][character]["CharId"]
                    char_map[char_id] = character
                    response = response + "**" + str(char_id) + "** - " + char_name + "\n"
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 1
                dm_tracker[message.author.id]["parameters"] =  char_map               
                return            
            elif dm_tracker[message.author.id]["currentfield"] == 1:
                user_id = message.author.id
                target_id = dm_tracker[message.author.id]["parameters"][int(message.content)]
                records = await select_sql("""SELECT Id,StaminaCost,MinimumLevel,DamageMultiplier,AttackName,PictureLink FROM Melee WHERE Id=%s;""",(dm_tracker[message.author.id]["fielddict"][0],))
                if not records:
                    await reply_message(message, "That's not a valid melee. Try again.")
                    return
                else:
                    for row in records:
                        melee_id = row[0]
                        stamina_cost = int(row[1])
                        min_level = int(row[2])
                        damage_multiplier = int(row[3])
                        parsed_string = row[4]
                        picture_link = row[5]
                    melee_records = await select_sql("""SELECT CharacterId FROM MeleeSkills WHERE CharacterId=%s""", (mass_spar_chars[server_id][user_id]["CharId"],))
                    if not melee_records:
                        await reply_message(message, "You do not know this melee. Try something you do know!")
                        return
                    if (min_level > mass_spar_chars[server_id][user_id]["Level"]):
                        await direct_message(message, "You're not a high enough level for this melee. How did you even learn it?")
                        return
                if mass_spar_chars[server_id][user_id]["Stamina"] < stamina_cost:
                    await direct_message(message, "You do not have sufficient stamina for this melee. Try another melee or restore stamina!")
                    return
                mass_spar_chars[server_id][user_id]["Stamina"] = mass_spar_chars[server_id][user_id]["Stamina"] - stamina_cost
                await direct_message(message, "Attacking with " + parsed_string)
 #               await dm_tracker[message.author.id]["commandchannel"].send(">>> " + str(mass_spar_chars[server_id][user_id]["CharName"]) + " attacks " + str(mass_spar_chars[server_id][target_id]["CharName"]) + " with " + parsed_string + "!\nThis drained " + str(stamina_cost) + " from " + mass_spar_chars[server_id][user_id]["CharName"] + ", leaving them with " + str(mass_spar_chars[server_id][user_id]["Stamina"]) + " stamina!")
                attack_text = ">>> " + str(mass_spar_chars[server_id][user_id]["CharName"]) + " attacks " + str(mass_spar_chars[server_id][target_id]["CharName"]) + " with " + parsed_string + "!\nThis drained " + str(stamina_cost) + " from " + mass_spar_chars[server_id][user_id]["CharName"] + ", leaving them with " + str(mass_spar_chars[server_id][user_id]["Stamina"]) + " stamina!\n\n" + picture_link
                await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][user_id]["CharName"], attack_text, mass_spar_chars[server_id][user_id]["PictureLink"])
                dodge = await calculate_dodge(mass_spar_chars[server_id][user_id]["Level"], mass_spar_chars[server_id][user_id]["Agility"])
                if dodge:
                    dodge_text = mass_spar_chars[server_id][target_id]["CharName"] + " dodged the attack! No damage taken!"
                    await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][target_id]["CharName"], dodge_text, mass_spar_chars[server_id][target_id]["PictureLink"])
 #                   await reply_message(message, mass_spar_chars[server_id][target_id]["CharName"] + " dodged the attack! No damage taken!")
                else:
                    damage = await calculate_damage(mass_spar_chars[server_id][user_id]["Attack"], mass_spar_chars[server_id][target_id]["Defense"], damage_multiplier, mass_spar_chars[server_id][user_id]["Level"], mass_spar_chars[server_id][target_id]["Level"])
                    mass_spar_chars[server_id][target_id]["Health"] = mass_spar_chars[server_id][target_id]["Health"] - damage
                    mass_spar_chars[server_id][user_id]["TotalDamage"] = mass_spar_chars[server_id][user_id]["TotalDamage"] + damage
                    hit_text = ">>> " + mass_spar_chars[server_id][target_id]["CharName"] + " was hit by " + mass_spar_chars[server_id][user_id]["CharName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(mass_spar_chars[server_id][target_id]["Health"]) + "!"
                    await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][target_id]["CharName"], hit_text, mass_spar_chars[server_id][target_id]["PictureLink"])
                    #await dm_tracker[message.author.id]["commandchannel"].send(">>> " + mass_spar_chars[server_id][target_id]["CharName"] + " was hit by " + mass_spar_chars[server_id][user_id]["CharName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(mass_spar_chars[server_id][target_id]["Health"]))
                    if mass_spar_chars[server_id][target_id]["Health"] < 1:
                        fallen_text = mass_spar_chars[server_id][target_id]["CharName"] + " has no health left and is out of the fight!"
                        await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][target_id]["CharName"], fallen_text, mass_spar_chars[server_id][target_id]["PictureLink"])
                        #await reply_message(message, mass_spar_chars[server_id][target_id]["CharName"] + " has no health left and is out of the fight!")
                        

                        fallen_chars[dm_tracker[message.author.id]["server_id"]][target_id] = {} 
                        fallen_chars[dm_tracker[message.author.id]["server_id"]][target_id] = mass_spar_chars[server_id][target_id]
                        del mass_spar_chars[server_id][target_id]

                if len(mass_spar_chars[server_id]) < 2:
                    response = "<@" + str(message.author.id) + "> is the last one standing and is the spar winner!\n\n**Experience gained:**\n\n"
                    fallen_chars[dm_tracker[message.author.id]["server_id"]][message.author.id] = {} 
                    fallen_chars[dm_tracker[message.author.id]["server_id"]][message.author.id] = mass_spar_chars[server_id][message.author.id]
                    for char in fallen_chars[dm_tracker[message.author.id]["server_id"]].keys():
                    
                        char_id = fallen_chars[server_id][char]["CharId"]
                        await log_message("Level " + str(fallen_chars[server_id][char]["Level"]))
                        new_xp = await calculate_xp(fallen_chars[server_id][char]["Level"], fallen_chars[server_id][char]["Level"], fallen_chars[server_id][char]["TotalDamage"], 1) * 2
                        response = response + "*" + fallen_chars[server_id][char]["CharName"] + "*: " + str(new_xp) + "\n"
                        records = await select_sql("""SELECT Experience FROM CharacterProfiles WHERE Id=%s;""", (str(fallen_chars[server_id][char]["CharId"]),))
                        for row in records:
                            old_xp = int(row[0])
                        total_xp = old_xp + new_xp
                        if total_xp > (guild_settings[server_id]["XPLevelRatio"] * fallen_chars[server_id][char]["Level"]):
                            fallen_chars[server_id][char]["Level"] = fallen_chars[server_id][char]["Level"] + 1
                            available_points[server_id][char] = int(fallen_chars[server_id][char]["Level"] / 2)
                            response = response + "**" + fallen_chars[server_id][char]["CharName"] + "** LEVELED UP TO LEVEL **" + str(fallen_chars[server_id][char]["Level"]) + "!**\nYou have " + str(int(fallen_chars[server_id][char]["Level"]/2)) + " stat points to spend!\n\n"
                            total_xp = 0
                            health = fallen_chars[server_id][user_id]["Level"] * guild_settings[server_id]["HealthLevelRatio"]
                            stamina = fallen_chars[server_id][user_id]["Level"] * guild_settings[server_id]["StaminaLevelRatio"]
                            mana = fallen_chars[server_id][user_id]["Level"] * guild_settings[server_id]["ManaLevelRatio"]
                        result = await commit_sql("""UPDATE CharacterProfiles SET Level=%s,Experience=%s,Health=%s,Stamina=%s,Mana=%s WHERE Id=%s;""",(str(fallen_chars[server_id][target_id]["Level"]),str(total_xp),str(health), str(stamina), str(mana), str(fallen_chars[server_id][target_id]["CharId"])))
                    mass_spar_event[server_id] = False
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
                    return
                            
                if mass_spar_turn[server_id] > len(mass_spar_chars[server_id]) - 2:
                    mass_spar_turn[server_id] = 0
                else:
                    mass_spar_turn[server_id] = mass_spar_turn[server_id] + 1
                await dm_tracker[message.author.id]["commandchannel"].send(">>> <@" + str(list(mass_spar[server_id])[mass_spar_turn[server_id]].id) + ">, it is your turn!")
            await initialize_dm(message.author.id)    
            return
        elif current_command == 'castspar':
            if dm_tracker[message.author.id]["currentfield"] == 0:
                char_map = {} 
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                response = "Select a target:\n\n"
                for character in mass_spar_chars[server_id]:
                    char_name = mass_spar_chars[server_id][character]["CharName"]
                    char_id = mass_spar_chars[server_id][character]["CharId"]
                    char_map[char_id] = character
                    response = response + "**" + str(char_id) + "** - " + char_name + "\n"
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 1
                dm_tracker[message.author.id]["parameters"] =  char_map              
                return
            elif dm_tracker[message.author.id]["currentfield"] == 1:
                user_id = message.author.id
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                target_id = dm_tracker[message.author.id]["parameters"][int(message.content)]
                records = await select_sql("""SELECT Id,Element,ManaCost,MinimumLevel,DamageMultiplier,SpellName,PictureLink FROM Spells WHERE Id=%s;""",(dm_tracker[message.author.id]["fielddict"][0],))
                if not records:
                    await direct_message(message, "That's not a valid spell. Try again.")
                    return
                else:
                    for row in records:
                        spell_id = row[0]
                        element = row[1]
                        mana_cost = int(row[2])
                        min_level = int(row[3])
                        damage_multiplier = int(row[4])
                        parsed_string = row[5]
                        picture_link = row[6]
                    spell_records = await select_sql("""SELECT CharacterId FROM MagicSkills WHERE CharacterId=%s""", (mass_spar_chars[server_id][user_id]["CharId"],))
                    if not spell_records:
                        await direct_message(message, "You do not know this spell. Try something you do know!")
                        return
                    if (min_level > mass_spar_chars[server_id][user_id]["Level"]):
                        await direct_message(message, "You're not a high enough level for this spell. How did you even learn it?")
                        return
                if mass_spar_chars[server_id][user_id]["Mana"] < mana_cost:
                    await direct_message(message, "You do not have sufficient mana for this spell. Try another spell or restore mana!")
                    return
                await direct_message(message, "Attacking with " + parsed_string)
                mass_spar_chars[server_id][user_id]["Mana"] = mass_spar_chars[server_id][user_id]["Mana"] - mana_cost
                attack_text = ">>> " + str(mass_spar_chars[server_id][user_id]["CharName"]) + " attacks " + str(mass_spar_chars[server_id][target_id]["CharName"]) + " with " + parsed_string + "!\nThis drained " + str(mana_cost) + " from " + mass_spar_chars[server_id][user_id]["CharName"] + ", leaving them with " + str(mass_spar_chars[server_id][user_id]["Mana"]) + " mana!\n\n" + picture_link
                await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][user_id]["CharName"], attack_text, mass_spar_chars[server_id][user_id]["PictureLink"])
#                await dm_tracker[message.author.id]["commandchannel"].send(">>> " + str(mass_spar_chars[server_id][user_id]["CharName"]) + " attacks " + str(mass_spar_chars[server_id][target_id]["CharName"]) + " with " + parsed_string + "!\nThis drained " + str(mana_cost) + " from " + mass_spar_chars[server_id][user_id]["CharName"] + ", leaving them with " + str(mass_spar_chars[server_id][user_id]["Mana"]) + " mana!")
                dodge = await calculate_dodge(mass_spar_chars[server_id][user_id]["Level"], mass_spar_chars[server_id][user_id]["Agility"])
                if dodge:
                  #  await dm_tracker[message.author.id]["commandchannel"].send(">>> " + mass_spar_chars[server_id][target_id]["CharName"] + " dodged the attack! No damage taken!")
                    dodge_text = ">>> " + mass_spar_chars[server_id][target_id]["CharName"] + " dodged the attack! No damage taken!"
                    await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][target_id]["CharName"], dodge_text, mass_spar_chars[server_id][target_id]["PictureLink"])
                else:
                    damage = await calculate_damage(mass_spar_chars[server_id][user_id]["MagicAttack"], mass_spar_chars[server_id][target_id]["Defense"], damage_multiplier, mass_spar_chars[server_id][user_id]["Level"], mass_spar_chars[server_id][target_id]["Level"])
                    mass_spar_chars[server_id][target_id]["Health"] = mass_spar_chars[server_id][target_id]["Health"] - damage
                    mass_spar_chars[server_id][user_id]["TotalDamage"] = mass_spar_chars[server_id][user_id]["TotalDamage"] + damage
                    hit_text = ">>> " + mass_spar_chars[server_id][target_id]["CharName"] + " was hit by " + mass_spar_chars[server_id][user_id]["CharName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(mass_spar_chars[server_id][target_id]["Health"]) + "!"
                    await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][target_id]["CharName"], hit_text, mass_spar_chars[server_id][target_id]["PictureLink"])
                  #  await dm_tracker[message.author.id]["commandchannel"].send(">>> " + mass_spar_chars[server_id][target_id]["CharName"] + " was hit by " + mass_spar_chars[server_id][user_id]["CharName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(mass_spar_chars[server_id][target_id]["Health"]))
                    if mass_spar_chars[server_id][target_id]["Health"] < 1:
                        
                        await dm_tracker[message.author.id]["commandchannel"].send(">>> " + mass_spar_chars[server_id][target_id]["CharName"] + " has no health left and is out of the fight!")
                        out_text = ">>> " + mass_spar_chars[server_id][target_id]["CharName"] + " has no health left and is out of the fight!"
                        await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][target_id]["CharName"], out_text, mass_spar_chars[server_id][target_id]["PictureLink"])

                        fallen_chars[dm_tracker[message.author.id]["server_id"]][target_id] = {} 
                        fallen_chars[dm_tracker[message.author.id]["server_id"]][target_id] = mass_spar_chars[server_id][target_id]
                        del mass_spar_chars[server_id][target_id]
                        

                if len(mass_spar_chars[server_id]) < 2:
                    fallen_chars[dm_tracker[message.author.id]["server_id"]][message.author.id] = {} 
                    fallen_chars[dm_tracker[message.author.id]["server_id"]][message.author.id] = mass_spar_chars[server_id][message.author.id]
                    response = "<@" + str(message.author.id) + "> is the last one standing and is the spar winner!\n\n**Experience gained:**\n\n"
                    for char in fallen_chars[dm_tracker[message.author.id]["server_id"]].keys():
                    
                        char_id = fallen_chars[server_id][char]["CharId"]
                        await log_message("Level " + str(fallen_chars[server_id][char]["Level"]))
                        new_xp = await calculate_xp(fallen_chars[server_id][char]["Level"], fallen_chars[server_id][char]["Level"], fallen_chars[server_id][char]["TotalDamage"], 1) * 2
                        response = response + "*" + fallen_chars[server_id][char]["CharName"] + "*: " + str(new_xp) + "\n"
                        records = await select_sql("""SELECT Experience FROM CharacterProfiles WHERE Id=%s;""", (str(fallen_chars[server_id][char]["CharId"]),))
                        for row in records:
                            old_xp = int(row[0])
                        total_xp = old_xp + new_xp
                        if total_xp > (guild_settings[server_id]["XPLevelRatio"] * fallen_chars[server_id][char]["Level"]):
                            fallen_chars[server_id][char]["Level"] = fallen_chars[server_id][char]["Level"] + 1
                            available_points[server_id][char] = int(fallen_chars[server_id][char]["Level"] / 2)
                            response = response + "**" + fallen_chars[server_id][char]["CharName"] + "** LEVELED UP TO LEVEL **" + str(fallen_chars[server_id][char]["Level"]) + "!**\nYou have " + str(int(fallen_chars[server_id][char]["Level"]/2)) + " stat points to spend!\n\n"
                            total_xp = 0
                            health = fallen_chars[server_id][user_id]["Level"] * guild_settings[server_id]["HealthLevelRatio"]
                            stamina = fallen_chars[server_id][user_id]["Level"] * guild_settings[server_id]["StaminaLevelRatio"]
                            mana = fallen_chars[server_id][user_id]["Level"] * guild_settings[server_id]["ManaLevelRatio"]
                        result = await commit_sql("""UPDATE CharacterProfiles SET Level=%s,Experience=%s,Health=%s,Stamina=%s,Mana=%s WHERE Id=%s;""",(str(fallen_chars[server_id][target_id]["Level"]),str(total_xp),str(health), str(stamina), str(mana), str(fallen_chars[server_id][target_id]["CharId"])))
                    mass_spar_event[server_id] = False
                    
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
                    return

                            
                if mass_spar_turn[server_id] > len(mass_spar_chars[server_id]) - 2:
                    mass_spar_turn[server_id] = 0
                else:
                    mass_spar_turn[server_id] = mass_spar_turn[server_id] + 1
                await dm_tracker[message.author.id]["commandchannel"].send(">>> <@" + str(list(mass_spar[server_id])[mass_spar_turn[server_id]].id) + ">, it is your turn!")  
                await initialize_dm(message.author.id)
                return
        elif current_command == 'buy':
            if dm_tracker[message.author.id]["currentfield"] == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_simple_menu(message, "Vendors","VendorName")
                response = "Please select from the list of available vendors by replying with the ID in bold.\n\n**VENDOR LIST**\n\n" + menu
                dm_tracker[message.author.id]["currentfield"] = 1
                await direct_message(message, response)
                return
            elif dm_tracker[message.author.id]["currentfield"] == 1:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                records = await select_sql("""SELECT ItemList FROM Vendors WHERE Id=%s;""",(message.content,))
                response  = "Select an item from the vendor by using the ID in bold in your reply.\n\n**VENDOR ITEMS**\n\n"
                for row in records:
                    item_list = row[0].split(',')
                for item in item_list:
                    item_record = await select_sql("SELECT EquipmentName,EquipmentCost FROM Equipment WHERE Id=%s;", (item,))
                    for item_obj in item_record:
                        response = response + "**" + item + "** - " + item_obj[0] + " - *" + str(item_obj[1]) + "*\n"
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 2
                return
                        
            
            elif dm_tracker[message.author.id]["currentfield"] == 2:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                records = await select_sql("""SELECT EquipmentName,EquipmentCost FROM Equipment WHERE Id=%s;""", (dm_tracker[message.author.id]["fielddict"][2],))
                
                if not records:
                    await direct_message(message, "No item found by that Id")
                    return
                for row in records:
                    item_name = row[0]
                    cost = float(row[1])
                records = await select_sql("""SELECT UserId,Currency,CharacterName FROM CharacterProfiles WHERE Id=%s;""",(dm_tracker[message.author.id]["fielddict"][0],))
                if not records:
                    await direct_message(message, "No character found by that ID")
                    return
                for row in records:
                    user_id = row[0]
                    currency = float(row[1])
                    char_name = row[2]
                if int(user_id) != message.author.id:
                    await direct_message(message, "This isn't your character!")
                    return
                if currency < cost:
                    await direct_message(message, "You don't have enough money to buy this!")
                    return
                currency = currency - cost
                records = await select_sql("""SELECT GuildBankBalance FROM GuildSettings WHERE ServerId=%s;""", (str(dm_tracker[message.author.id]["server_id"]),))
                for row in records:
                    balance = int(row[0])
                new_bank = balance + cost
                result2 = await commit_sql("""UPDATE GuildSettings SET GuildBankBalance=%s WHERE ServerId=%s;""",(str(new_bank),str(dm_tracker[message.author.id]["server_id"])))
                if result2:
                    pass
                else:
                    await direct_message(message, "Database error!")
                result = await commit_sql("""INSERT INTO Inventory (ServerId, UserId, CharacterId, EquipmentId) VALUES (%s, %s, %s, %s);""",(str(dm_tracker[message.author.id]["server_id"]), str(message.author.id), dm_tracker[message.author.id]["fielddict"][0], dm_tracker[message.author.id]["fielddict"][2]))
                if result:
                    await direct_message(message, char_name + " purchased " + item_name + " for " + str(cost) + " and has " + str(currency) + " left.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> "+ char_name + " purchased " + item_name + " for " + str(cost) + " and has " + str(currency) + " left.")
                    result_2 = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s WHERE Id=%s""", (str(currency), dm_tracker[message.author.id]["fielddict"][0]))
                    if not result_2:
                        await reply_message(message, "Database error!")
                        return
                else:
                    await reply_message(message, "Database error!")            
                await initialize_dm(message.author.id)
                return
        elif current_command == 'buyarms':
            if dm_tracker[message.author.id]["currentfield"] == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_simple_menu(message, "Armory","ArmoryName")
                response = "Please select from the list of available armories by replying with the ID in bold.\n\n**VENDOR LIST**\n\n" + menu
                dm_tracker[message.author.id]["currentfield"] = 1
                await direct_message(message, response)
                return
            elif dm_tracker[message.author.id]["currentfield"] == 1:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                records = await select_sql("""SELECT ArmamentList FROM Armory WHERE Id=%s;""",(message.content,))
                response  = "Select an armament from the armory by using the ID in bold in your reply.\n\n**ARMORY ITEMS**\n\n"
                for row in records:
                    item_list = row[0].split(',')
                for item in item_list:
                    item_record = await select_sql("SELECT ArmamentName,ArmamentCost FROM Armaments WHERE Id=%s;", (item,))
                    for item_obj in item_record:
                        response = response + "**" + item + "** - " + item_obj[0] + " - *" + str(item_obj[1]) + "*\n"
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 2
                return
                        
            
            elif dm_tracker[message.author.id]["currentfield"] == 2:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                records = await select_sql("""SELECT ArmamentName,ArmamentCost FROM Armaments WHERE Id=%s;""", (dm_tracker[message.author.id]["fielddict"][2],))
                
                if not records:
                    await direct_message(message, "No item found by that Id")
                    return
                for row in records:
                    item_name = row[0]
                    cost = float(row[1])
                records = await select_sql("""SELECT UserId,Currency,CharacterName FROM CharacterProfiles WHERE Id=%s;""",(dm_tracker[message.author.id]["fielddict"][0],))
                if not records:
                    await direct_message(message, "No character found by that ID")
                    return
                for row in records:
                    user_id = row[0]
                    currency = float(row[1])
                    char_name = row[2]
                if int(user_id) != message.author.id:
                    await direct_message(message, "This isn't your character!")
                    return
                if currency < cost:
                    await direct_message(message, "You don't have enough money to buy this!")
                    return
                currency = currency - cost
                records = await select_sql("""SELECT GuildBankBalance FROM GuildSettings WHERE ServerId=%s;""", (str(dm_tracker[message.author.id]["server_id"]),))
                for row in records:
                    balance = int(row[0])
                new_bank = balance + cost
                result2 = await commit_sql("""UPDATE GuildSettings SET GuildBankBalance=%s WHERE ServerId=%s;""",(str(new_bank),str(dm_tracker[message.author.id]["server_id"])))
                if result2:
                    pass
                else:
                    await direct_message(message, "Database error!")
                result = await commit_sql("""INSERT INTO ArmamentInventory (ServerId, UserId, CharacterId, ArmamentId) VALUES (%s, %s, %s, %s);""",(str(dm_tracker[message.author.id]["server_id"]), str(message.author.id), dm_tracker[message.author.id]["fielddict"][0], dm_tracker[message.author.id]["fielddict"][2]))
                if result:
                    await direct_message(message, char_name + " purchased " + item_name + " for " + str(cost) + " and has " + str(currency) + " left.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> "+ char_name + " purchased " + item_name + " for " + str(cost) + " and has " + str(currency) + " left.")
                    result_2 = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s WHERE Id=%s""", (str(currency), dm_tracker[message.author.id]["fielddict"][0]))
                    if not result_2:
                        await reply_message(message, "Database error!")
                        return
                else:
                    await reply_message(message, "Database error!")            
                await initialize_dm(message.author.id)                
        elif current_command == 'sell':
            if dm_tracker[message.author.id]["currentfield"] == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_menu(message, "Inventory", "Equipment","EquipmentId", "CharacterId", "EquipmentName", dm_tracker[message.author.id]["fielddict"][0])
                if not menu:
                    await direct_message(message, "You don't have any items for this character!")
                    return
                    
                response = "**YOUR INVENTORY**\n\n" + menu
                await direct_message(message, "Select an item to sell:\n\n" + response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            elif dm_tracker[message.author.id]["currentfield"] == 1:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                item_id = message.content
                records = await select_sql("""SELECT EquipmentName,EquipmentCost FROM Equipment WHERE Id=%s""", (dm_tracker[message.author.id]["fielddict"][1],))
                
                if not records:
                    await reply_message(message, "No item found by that ID!")
                    return
                for row in records:
                    equip_name = row[0]
                    cost = float(row[1])
                records = await select_sql("""SELECT CharacterName,UserId,Currency FROM CharacterProfiles WHERE Id=%s;""",( dm_tracker[message.author.id]["fielddict"][0],))
                if not records:
                    await reply_message(message, "No character found by that name!")
                    return
                for row in records:
                    char_name = row[0]
                    user_id = int(row[1])
                    currency = float(row[2])
                if user_id != message.author.id:
                    await reply_message(message, "This isn't your character!")
                    return
                records = await select_sql("""SELECT GuildBankBalance FROM GuildSettings WHERE ServerId=%s;""", (str(dm_tracker[message.author.id]["server_id"]),))
                for row in records:
                    balance = int(row[0])
                if cost > balance:
                    await direct_message(message, "The guild bank doesn't have enough to buy your item! Contact an admin or GM to update the bank balance!")
                    return
                new_bank = balance - cost
                result2 = await commit_sql("""UPDATE GuildSettings SET GuildBankBalance=%s WHERE ServerId=%s;""",(str(new_bank),str(dm_tracker[message.author.id]["server_id"])))
                if result2:
                    pass
                else:
                    await direct_message(message, "Database error!")
                currency = currency + cost
                result = await commit_sql("""DELETE FROM Inventory WHERE ServerId=%s AND UserId=%s AND CharacterId=%s AND EquipmentId=%s;""",(str(dm_tracker[message.author.id]["server_id"]), str(message.author.id), dm_tracker[message.author.id]["fielddict"][0], item_id))
                if result:
                    await direct_message(message, char_name + " sold for " + str(cost) + " and has " + str(currency) + " left.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + char_name + " sold for " + str(cost) + " and has " + str(currency) + " left.")
                    result_2 = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s WHERE Id=%s""", (str(currency), dm_tracker[message.author.id]["fielddict"][0]))
                    if not result_2:
                        await direct_message(message, "Database error!")
                        return
                else:
                    await reply_message(message, "You don't own this item!")
                await initialize_dm(message.author.id)    
                return
        elif current_command == 'sellarms':
            if dm_tracker[message.author.id]["currentfield"] == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_menu(message, "ArmamentInventory", "Armaments","ArmamentId", "CharacterId", "ArmamentName", dm_tracker[message.author.id]["fielddict"][0])
                if not menu:
                    await direct_message(message, "You don't have any items for this character!")
                    return
                    
                response = "**YOUR ARMAMENTS**\n\n" + menu
                await direct_message(message, "Select an item to sell:\n\n" + response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            elif dm_tracker[message.author.id]["currentfield"] == 1:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                item_id = message.content
                records = await select_sql("""SELECT ArmamentName,ArmamentCost FROM Armaments WHERE Id=%s""", (dm_tracker[message.author.id]["fielddict"][1],))
                
                if not records:
                    await reply_message(message, "No item found by that ID!")
                    return
                for row in records:
                    equip_name = row[0]
                    cost = float(row[1])
                records = await select_sql("""SELECT CharacterName,UserId,Currency FROM CharacterProfiles WHERE Id=%s;""",( dm_tracker[message.author.id]["fielddict"][0],))
                if not records:
                    await reply_message(message, "No character found by that name!")
                    return
                for row in records:
                    char_name = row[0]
                    user_id = int(row[1])
                    currency = float(row[2])
                if user_id != message.author.id:
                    await reply_message(message, "This isn't your character!")
                    return
                records = await select_sql("""SELECT GuildBankBalance FROM GuildSettings WHERE ServerId=%s;""", (str(dm_tracker[message.author.id]["server_id"]),))
                for row in records:
                    balance = int(row[0])
                if cost > balance:
                    await direct_message(message, "The guild bank doesn't have enough to buy your item! Contact an admin or GM to update the bank balance!")
                    return
                new_bank = balance - cost
                result2 = await commit_sql("""UPDATE GuildSettings SET GuildBankBalance=%s WHERE ServerId=%s;""",(str(new_bank),str(dm_tracker[message.author.id]["server_id"])))
                if result2:
                    pass
                else:
                    await direct_message(message, "Database error!")
                currency = currency + cost
                result = await commit_sql("""DELETE FROM ArmamentInventory WHERE ServerId=%s AND UserId=%s AND CharacterId=%s AND ArmamentId=%s;""",(str(dm_tracker[message.author.id]["server_id"]), str(message.author.id), dm_tracker[message.author.id]["fielddict"][0], item_id))
                if result:
                    await direct_message(message, char_name + " sold for " + str(cost) + " and has " + str(currency) + " left.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + char_name + " sold for " + str(cost) + " and has " + str(currency) + " left.")
                    result_2 = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s WHERE Id=%s""", (str(currency), dm_tracker[message.author.id]["fielddict"][0]))
                    if not result_2:
                        await direct_message(message, "Database error!")
                        return
                else:
                    await reply_message(message, "You don't own this armament!")
                await initialize_dm(message.author.id)    
                return

                    
        elif current_command == 'sendcurrency':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_simple_menu(message, "CharacterProfiles","CharacterName")
                response = "Please choose a character to send currency to on the list below by replying with the character ID:\n\n"
                await direct_message(message, response + menu)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                response = "Please enter an amount of currency below to send to the character."
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 2
                return
      
            if current_field == 2:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                sent_amount = float(message.content)
                records = await select_sql("""SELECT CharacterName,Currency FROM CharacterProfiles WHERE Id=%s;""",(dm_tracker[message.author.id]["fielddict"][0],))
                for row in records:
                    user_name = row[0]
                    user_currency = float(row[1])
                records = await select_sql("""SELECT CharacterName,Currency,UserId FROM CharacterProfiles WHERE Id=%s;""",(dm_tracker[message.author.id]["fielddict"][1],))
                for row in records:
                    target_name = row[0]
                    target_currency = float(row[1])
                    target_id = row[2]
                if sent_amount > user_currency:
                    await direct_message(message, "You don't have enough currency! Send an amount less than " + str(user_currency) + "!")
                    return
                result = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s WHERE Id=%s;""", (str(user_currency - sent_amount),dm_tracker[message.author.id]["fielddict"][0]))
                if result:
                    result_2 = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s WHERE Id=%s;""", (str(target_currency + sent_amount),dm_tracker[message.author.id]["fielddict"][1]))
                    if result_2:
                        await direct_message(message, user_name + " has given " + target_name + " " + str(sent_amount) + " of currency!")
                        await dm_tracker[message.author.id]["commandchannel"].send(">>> " + user_name + " has sent " + target_name + " " + str(sent_amount) + " of currency, a character played by <@" + target_id + "> .")
                return
        elif current_command == 'buff':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_menu(message, "BuffSkills","Buffs","BuffId","CharId","BuffName",message.content)
                response = "Please choose a buff from your character by replying with the ID below.\n\n"
                response = response + menu
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_simple_menu(message, "CharacterProfiles","CharacterName")
                response = "Please choose a character to target with your buff by replying with the ID below.\n\n"
                response = response + menu
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 2
                return
            if current_field == 2:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                buff_id = dm_tracker[message.author.id]["fielddict"][1]
                char_id = dm_tracker[message.author.id]["fielddict"][0]
                target_id = message.content
                records = await select_sql("""SELECT Id,MinimumLevel,StatMod,Modifier,BuffName,ManaCost FROM Buffs WHERE ServerId=%s AND Id=%s;""",(str(dm_tracker[message.author.id]["server_id"]), buff_id))
                if not records:
                    await reply_message(message, "No buff found by that ID")
                    return
                for row in records:
                    min_level = int(row[1])
                    stat_mod = row[2]
                    mod = int(row[3])
                    buff = row[4]
                    mana_cost = int(row[5])
                    

                records = await select_sql("""SELECT Id FROM BuffSkills WHERE ServerId=%s AND CharId=%s AND BuffId=%s;""",  (str(dm_tracker[message.author.id]["server_id"]), char_id, buff_id))
                if not records:
                    await reply_message(message, "That buff is not in your skillset!")
                    return
                for row in records:
                    inventory_id = row[0]
                records = await select_sql("SELECT CharacterName,Level FROM CharacterProfiles WHERE Id=%s", (str(char_id),))
                for row in records:
                    char_name = row[0]
                    level = int(row[1])
                if level < min_level:
                    await direct_message(message, "You aren't a high enough level to use this buff! Level up!")
                    return
                records = await select_sql("""SELECT CharacterName,""" + stat_mod + """,UserId FROM CharacterProfiles WHERE Id=%s;""", (str(target_id),))
                if not records:
                    await direct_message(message, "Invalid target!")
                    return
                for row in records:
                    target_name = row[0]
                    stat_to_mod = int(row[1])
                    target_user = int(row[2])
                    
                stat_to_mod = stat_to_mod + mod
                if mass_spar_event[dm_tracker[message.author.id]["server_id"]]:
                    if mass_spar_chars[dm_tracker[message.author.id]["server_id"]][target_user]:
                        mass_spar_chars[dm_tracker[message.author.id]["server_id"]][target_user][stat_mod] = mass_spar_chars[dm_tracker[message.author.id]["server_id"]][target_user][stat_mod] + mod
                        mass_spar_chars[dm_tracker[message.author.id]["server_id"]][message.author.id]["Mana"] = mass_spar_chars[dm_tracker[message.author.id]["server_id"]][message.author.id]["Mana"] - mana_cost
                        mana_left = mass_spar_chars[dm_tracker[message.author.id]["server_id"]][message.author.id]["Mana"]
                elif server_party[dm_tracker[message.author.id]["server_id"]]:
                    if server_party_chars[dm_tracker[message.author.id]["server_id"]][message.author.id]:
                        server_party_chars[dm_tracker[message.author.id]["server_id"]][target_user][stat_mod] = server_party_chars[dm_tracker[message.author.id]["server_id"]][target_user][stat_mod] + mod   
                        server_party_chars[dm_tracker[message.author.id]["server_id"]][message.author.id]["Mana"] = server_party_chars[dm_tracker[message.author.id]["server_id"]][message.author.id]["Mana"] - mana_cost
                        mana_left = server_party_chars[dm_tracker[message.author.id]["server_id"]][message.author.id]["Mana"]
                response = char_name + " used buff " + buff + " and changed " + stat_mod + " by " + str(mod) + " points to " + str(stat_to_mod) + " on " + target_name + " and has " + str(mana_left) + " remaining!"
                await direct_message(message, response)
                await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
                await initialize_dm(message.author.id)
                return                
        elif current_command == 'useitem1':
            char_id = message.content
            

            response = "**YOUR INVENTORY**\n\n"
            menu = await make_menu(message, "Inventory", "Equipment", "EquipmentId", "CharacterId", "EquipmentName", char_id)
            if not menu:
                await direct_message(message, "You don't have any items for this character!")
                return
            dm_tracker[message.author.id]["currentcommand"] = "useitem2"
            dm_tracker[message.author.id]["parameters"] = char_id
            response = response + menu
            await direct_message(message, "Select an item to use:\n\n" + response)
            return
        elif current_command == 'useitem2':
            item_id = message.content
            char_id = dm_tracker[message.author.id]["parameters"]
            records = await select_sql("""SELECT Id,MinimumLevel,StatMod,Modifier,EquipmentName FROM Equipment WHERE ServerId=%s AND Id=%s;""",(str(dm_tracker[message.author.id]["server_id"]), item_id))
            if not records:
                await reply_message(message, "No item found by that ID")
                return
            for row in records:
                min_level = int(row[1])
                stat_mod = row[2]
                mod = int(row[3])
                item = row[4]

            records = await select_sql("""SELECT Id FROM Inventory WHERE ServerId=%s AND CharacterId=%s AND EquipmentId=%s;""",  (str(dm_tracker[message.author.id]["server_id"]), char_id, item_id))
            if not records:
                await reply_message(message, "That item is not in your inventory!")
                return
            for row in records:
                inventory_id = row[0]
            records = await select_sql("SELECT CharacterName,Level," + stat_mod + " FROM CharacterProfiles WHERE Id=%s", (str(char_id),))
            for row in records:
                char_name = row[0]
                level = int(row[1])
                stat_to_mod = int(row[2])
            if level < min_level:
                await direct_message(message, "You aren't a high enough level to use this item! Level up or sell it for cash!")
                return                
            stat_to_mod = stat_to_mod + mod
            if mass_spar_event[dm_tracker[message.author.id]["server_id"]]:
                if mass_spar_chars[dm_tracker[message.author.id]["server_id"]][message.author.id]:
                    mass_spar_chars[dm_tracker[message.author.id]["server_id"]][message.author.id][stat_mod] = mass_spar_chars[dm_tracker[message.author.id]["server_id"]][message.author.id][stat_mod] + mod
            if server_party[dm_tracker[message.author.id]["server_id"]]:
                if server_party_chars[dm_tracker[message.author.id]["server_id"]][message.author.id]:
                    server_party_chars[dm_tracker[message.author.id]["server_id"]][message.author.id][stat_mod] = server_party_chars[dm_tracker[message.author.id]["server_id"]][message.author.id][stat_mod] + mod                    
            result = await commit_sql("""UPDATE CharacterProfiles SET """ + stat_mod + """=%s WHERE Id=%s""",(str(stat_to_mod), char_id))
            if not result:
                await reply_message(message, "Database error!")
                return
            result = await commit_sql("""DELETE FROM Inventory WHERE Id=%s;""", (inventory_id,))
            if not result:
                await reply_message(message, "Database error!")
                return
            response = char_name + " consumed item " + item + " and changed " + stat_mod + " by " + str(mod) + " points to " + str(stat_to_mod) + "!"
            await direct_message(message, response)
            await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
            await initialize_dm(message.author.id)
            return
            
        dm_tracker[message.author.id]["fielddict"].append(message.content.strip())
        dm_tracker[message.author.id]["currentfield"] = dm_tracker[message.author.id]["currentfield"] + 1
        if dm_tracker[message.author.id]["currentfield"] < len(field_list):
            await direct_message(message, "Reply received. Next field is " + "**" + dm_tracker[message.author.id]["fieldlist"][dm_tracker[message.author.id]["currentfield"]] + "**.")
        if current_field > len(field_list) - 2 and current_command !='newrandomchar':
            if current_command == 'newcustomchar':
                new_custom_profile = """INSERT INTO Server""" + str(dm_tracker[message.author.id]["server_id"]) + """ (UserId, Name, """
                create_values = """ VALUES (%s, """
                create_tuple = (str(message.author.id))
                for key in field_list:
                    new_custom_profile = new_custom_profile + key + """, """
                    create_values = create_values + """%s, """
                    create_tuple = create_tuple + (field_dict[key],)
                new_custom_profile = re.sub(r", , $", "", new_custom_profile) + ")" + re.sub(r", %s, $", "", create_values) + """);"""
                create_tuple = create_tuple[ : len(create_tuple) - 1 ]
                await log_message("SQL: " + new_custom_profile)
                result = await commit_sql(new_custom_profile, create_tuple)
                if result:
                    await direct_message(message, "Custom character created successfully!")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Custom character successfully created.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'newdefaultchar':
                char_name = field_dict[0]
                if message.attachments:
                    field_dict[len(field_dict) -1] = message.attachments[0].url
                
                create_char_entry = "INSERT INTO UnapprovedCharacterProfiles (ServerId, UserId, "
                create_value = "VALUES (%s, %s, "
                char_tuple = (str(server_id), str(message.author.id),)
                counter = 0
                for field in field_list:
                    create_char_entry = create_char_entry + field + ", "
                    char_tuple = char_tuple + (field_dict[counter],)
                    create_value = create_value + "%s, "
                    counter = counter + 1
                    if counter > len(dm_tracker[message.author.id]["fieldlist"]) - 1:
                        break
                        
                create_char_entry = re.sub(r", $","", create_char_entry)
                create_char_entry = create_char_entry + ", Attack, Defense, MagicAttack, Health, Mana, Level, Experience, Stamina, Agility, Intellect, Charisma,Currency) " + re.sub(r", $","",create_value) + ", %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1000);"

                await log_message("SQL: " + create_char_entry)
                char_tuple = char_tuple + (str(guild_settings[server_id]["StartingAttack"]), str(guild_settings[server_id]["StartingDefense"]), str(guild_settings[server_id]["StartingMagicAttack"]), str(guild_settings[server_id]["StartingHealth"]), str(guild_settings[server_id]["StartingMana"]), '1', '0', str(guild_settings[server_id]["StartingStamina"]), str(guild_settings[server_id]["StartingAgility"]), str(guild_settings[server_id]["StartingIntellect"]), str(guild_settings[server_id]["StartingCharisma"]))
                
                result = await commit_sql(create_char_entry, char_tuple)
                if result:
                    await direct_message(message, "Character " + char_name + " successfully created.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Character " + char_name + " successfully created.\n\n<@&" + str(guild_settings[dm_tracker[message.author.id]["server_id"]]["AdminRole"]) + ">, please approve or decline the character with =approvechar or =denychar.")
                else:
                    await direct_message(message, "Database error!")

            elif current_command == 'newspell':
                if message.attachments:
                    field_dict[len(field_dict) -1] = message.attachments[0].url               
                result = await insert_into(message, "Spells")
                if result:
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Spell " + field_dict[0] + " successfully created.")
                else:
                    await direct_message(message, "Database error!")            
            elif current_command == 'newmelee':
                if message.attachments:
                    field_dict[len(field_dict) -1] = message.attachments[0].url               
                result = await insert_into(message, "Melee")
                if result:
                    await direct_message(message, "melee " + field_dict[0] + " created successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Melee attack " + field_dict[0] +  " successfully created.")
                else:
                    await direct_message(message, "Database error!") 
            elif current_command == 'newarmament':
                if message.attachments:
                    field_dict[len(field_dict) -1] = message.attachments[0].url                
                result = await insert_into(message, "Armaments")
                if result:
                    await direct_message(message, "equip " + field_dict[0] + " created successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Item " + field_dict[0] + " successfully created.")
                else:
                    await direct_message(message, "Database error!")                    
            elif current_command == 'newitem':
                if message.attachments:
                    field_dict[len(field_dict) -1] = message.attachments[0].url                
                result = await insert_into(message, "Equipment")
                if result:
                    await direct_message(message, "equip " + field_dict[0] + " created successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Item " + field_dict[0] + " successfully created.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'newbuff':
                if message.attachments:
                    field_dict[len(field_dict) -1] = message.attachments[0].url                
                result = await insert_into(message, "Buffs")
                if result:
                    await direct_message(message, "Buff " + field_dict[0] + " created successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Buff " + field_dict[0] + " successfully created.")
                else:
                    await direct_message(message, "Database error!")                     
            elif current_command == 'newmonster':
                if message.attachments:
                    field_dict[len(field_dict) -1] = message.attachments[0].url
                result = await insert_into(message, "Monsters")
                if result:
                    await direct_message(message, "Monster " + field_dict[0] + " successfully created.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Monster " + field_dict[0] + " successfully created.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'newalt':
                if message.attachments:
                    field_dict[len(field_dict) -1] = message.attachments[0].url 
                field_dict.append(str(dm_tracker[message.author.id]["parameters"]))
                field_list.append("UsersAllowed")
                result = await insert_into(message, "Alts")
                if result:
                    await direct_message(message, "Alt " + field_dict[0] + " successfully created.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Alt " + field_dict[0] + " successfully created.")
                else:
                    await direct_message(message, "Database error!")   
            elif current_command == 'editalt':
                if message.attachments:
                    field_dict[len(field_dict) -1] = message.attachments[0].url
                field_dict.append(str(dm_tracker[message.author.id]["parameters"]))
                field_list.append("UsersAllowed")                    
                result = await update_table(message, "Alts")
                if result:
                    await direct_message(message, "Alt " + field_dict[0] + " successfully edited.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Alt " + field_dict[0] + " successfully edited.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'newnpc':
                if message.attachments:
                    field_dict[len(field_dict) -1] = message.attachments[0].url 
                field_dict.append(str(dm_tracker[message.author.id]["parameters"]))
                result = await insert_into(message, "NonPlayerCharacters")
                if result:
                    await direct_message(message, "NPC " + field_dict[0] + " successfully created.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> NPC " + field_dict[0] + " successfully created.")
                else:
                    await direct_message(message, "Database error!")   
            elif current_command == 'editnpc':
                if message.attachments:
                    field_dict[len(field_dict) -1] = message.attachments[0].url
                field_dict.append(str(dm_tracker[message.author.id]["parameters"]))
          
                result = await update_table(message, "NonPlayerCharacters")
                if result:
                    await direct_message(message, "NPC " + field_dict[0] + " successfully edited.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> NPC " + field_dict[0] + " successfully edited.")
                else:
                    await direct_message(message, "Database error!")                    
            elif current_command == 'editsetup':
                records = await select_sql("""SELECT ServerId FROM GuildSettings WHERE ServerId=%s;""",(str(dm_tracker[message.author.id]["server_id"]),))
                if not records:
                    result = await commit_sql("""INSERT INTO GuildSettings (ServerId) VALUES (%s);""",(str(dm_tracker[message.author.id]["server_id"]),))
                    if not result:
                        await direct_message(message, "Database error!")
                        return
                result = await update_table(message, "GuildSettings")
                if result:
                    await direct_message(message, "Guild settings successfully edited.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Guild settings successfully edited.")
                else:
                    await direct_message(message, "Database error!")
                return               
            elif current_command == 'editchar':
                if message.attachments:
                    field_dict[len(field_dict)] = message.attachments[0].url
                result = await update_table(message, "CharacterProfiles")
                if result:
                    await direct_message(message, "Character " + field_dict[0] + " successfully edited.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Character " + field_dict[0] + " successfully edited.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'editcharinfo':
                result = await update_table(message, "CharacterProfiles")
                if result:
                    await direct_message(message, "Character " + field_dict[0] + " successfully edited.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Character " + field_dict[0] + " successfully edited.")
                else:
                    await direct_message(message, "Database error!")                    
            elif current_command == 'editmonster':
                dm_tracker[message.author.id]["fielddict"].remove('end')
       
                if message.attachments:
                    field_dict[len(field_dict) -1] = message.attachments[0].url
                result = await update_table(message, "Monsters")
                if result:
                    await direct_message(message, "Monster " + dm_tracker[message.author.id]["parameters"] + " successfully edited.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Monster " + dm_tracker[message.author.id]["parameters"] + " successfully edited.")   
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'edititem':
                dm_tracker[message.author.id]["fielddict"].remove('end')
                if message.attachments:
                    field_dict[len(field_dict) -1] = message.attachments[0].url           
                result = await update_table(message, "Equipment")
                if result:
                    await direct_message(message, "Item edited successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Item edited successfully.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'editarmament':
                dm_tracker[message.author.id]["fielddict"].remove('end')
                dm_tracker[message.author.id]["fielddict"].remove('')            
                if message.attachments:
                    field_dict[len(field_dict) -1] = message.attachments[0].url
                result = await update_table(message, "Armaments")
                if result:
                    await direct_message(message, "Armamentedited successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Item edited successfully.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'editbuff':
                dm_tracker[message.author.id]["fielddict"].remove('end')
                result = await update_table(message, "Buffs")
                if result:
                    await direct_message(message, "Buff edited successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Buff edited successfully.")
                else:
                    await direct_message(message, "Database error!")                    
            elif current_command == 'editmelee':
                dm_tracker[message.author.id]["fielddict"].remove('end')
           
                if message.attachments:
                    field_dict[len(field_dict) -1] = message.attachments[0].url            
                result = await update_table(message, "Melee")
                if result:
                    await direct_message(message, "Melee attack " + dm_tracker[message.author.id]["parameters"] + " edited successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Melee attack " + dm_tracker[message.author.id]["parameters"]+ " edited successfully.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'editspell':
                dm_tracker[message.author.id]["fielddict"].remove('end')
       
                if message.attachments:
                    field_dict[len(field_dict) -1] = message.attachments[0].url            
                result = await update_table(message, "Spells")
                if result:
                    await direct_message(message, "Spell " + dm_tracker[message.author.id]["parameters"] + " edited successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Spell attack " + dm_tracker[message.author.id]["parameters"]+ " edited successfully.")
                else:
                    await direct_message(message, "Database error!")           
            elif current_command == 'editstats':
                char_name = dm_tracker[message.author.id]["parameters"]
            
                create_char_entry = "UPDATE CharacterProfiles SET "
                create_values = " "
                char_tuple = ()
                counter = 0 
                for field in field_list:
                    create_char_entry = create_char_entry + field + "=%s, "
                    char_tuple = char_tuple + (field_dict[counter],)
                    counter = counter + 1 
                create_char_entry = re.sub(r", $","", create_char_entry)
                create_char_entry = create_char_entry + " WHERE ServerId=%s AND CharacterName=%s ;"
                char_tuple = char_tuple + (str(dm_tracker[message.author.id]["server_id"]), char_name)
                await log_message("SQL: " + create_char_entry)
                result = await commit_sql(create_char_entry, char_tuple)
                if result:
                    await direct_message(message, "Character " + char_name + " successfully updated.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Character " + char_name + " successfully updated.")
                else:
                    await reply_message(message, "Database error!")
            elif current_command == 'newvendor':
                dm_tracker[message.author.id]["fielddict"].remove('end')
                dm_tracker[message.author.id]["fielddict"].remove('')
                if message.attachments:
                    dm_tracker[message.author.id]["fielddict"].append(message.attachments[0].url)            
                result = await insert_into(message, "Vendors")
                if result:
                    await direct_message(message, "Vendor " + field_dict[0] + " updated successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Vendor " + field_dict[0] + " createed successfully.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'addvendoritem':
                records = await select_sql("SELECT ItemList FROM Vendors WHERE Id=%s;",(str(dm_tracker[message.author.id]["fielddict"][0]),))
                for row in records:
                    item_list = row[0]
                item_list = item_list + str(dm_tracker[message.author.id]["fielddict"][1])
                result = await commit_sql("UPDATE Vendors SET UserId=%s,ItemList=%s WHERE Id=%s;",(str(message.author.id), item_list, field_dict[0]))
                if result:
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Vendor updated successfully.")
                    await direct_message(message, "Vendor updated successfully.")
            elif current_command == 'newarmory':
                dm_tracker[message.author.id]["fielddict"].remove('end')
                dm_tracker[message.author.id]["fielddict"].remove('')
                if message.attachments:
                    dm_tracker[message.author.id]["fielddict"].append(message.attachments[0].url)
                result = await insert_into(message, "Armory")
                if result:
                    await direct_message(message, "Armory " + field_dict[0] + " updated successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Armory " + field_dict[0] + " createed successfully.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'addarmoryitem':
                records = await select_sql("SELECT ArmamentList FROM Armory WHERE Id=%s;",(str(dm_tracker[message.author.id]["fielddict"][0]),))
                for row in records:
                    item_list = row[0]
                item_list = item_list + str(dm_tracker[message.author.id]["fielddict"][1])
                result = await commit_sql("UPDATE Armory SET UserId=%s,ArmamentList=%s WHERE Id=%s;",(str(message.author.id), item_list, field_dict[0]))
                if result:
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Armory updated successfully.")
                    await direct_message(message, "Armory updated successfully.")
                return                    
            await initialize_dm(message.author.id)        
        else:
            pass
        return
        
    elif not message.content.startswith('='):
        try:
            alt_aliases[message.guild.id][message.author.id][message.channel.id]
            get_alt = """SELECT UsersAllowed, CharName, PictureLink FROM Alts WHERE ServerId=%s AND Shortcut=%s;"""
            alt_tuple = (str(message.guild.id), alt_aliases[message.guild.id][message.author.id][message.channel.id])
            records = await select_sql(get_alt, alt_tuple)
            for row in records:
                if str(message.author.id) not in row[0]:
                    await reply_message(message, "<@" + str(message.author.id) + "> is not allowed to use Alt " + row[1] + "!")
                    return
                response = message.content
                current_pfp = await client.user.avatar_url.read()
                

                current_name = message.guild.me.name
                URL = row[2]
                temp_webhook = await message.channel.create_webhook(name='Chara-Tron')
                await temp_webhook.send(content=response, username=row[1], avatar_url=URL)
                await message.delete()
                await temp_webhook.delete()
        except:
            pass
    elif message.content.startswith('='):

            
        command_string = message.content.split(' ')
        command = command_string[0].replace('=','')
        parsed_string = message.content.replace("=" + command + " ","")
        await log_message("Command " + message.content + " called by " + message.author.name + " from server " + message.guild.name + " in channel " + message.channel.name)
        await log_message("Parsed string: " + parsed_string)
        
        
        if command == 'setadminrole':
            if message.author != message.guild.owner:
                await reply_message(message, "Only the server owner can set the admin role!")
                return
            if len(message.role_mentions) > 1:
                await reply_message(message, "Only one role can be defined as the admin role!")
                return
            role_id = message.role_mentions[0].id
            guild_settings[message.guild.id]["AdminRole"] = role_id
            result = await commit_sql("""INSERT INTO GuildSettings (ServerId,AdminRole) Values (%s,%s);""",  (str(message.guild.id), str(role_id)))
            if result:
                await reply_message(message, "Admin role successfully set!")
            else:
                await reply_message(message, "Database error!")
        if command == 'help' or command == 'info':
            fields = " "
            if parsed_string == '=help' or parsed_string == '=info':
            
                response = "`Welcome to RP Mastermind, the Discord RP Bot Master!`\n\n\n\n*Using Help:*\n\n\n\nType =info or =help followed by one of these categories:\n\n\n\n`general`: Not commands, but information on how the bot works.\n\n`setup`: Commands for getting the bot running.\n\n`characters`: Commands for managing characters.\n\n`alts`: Commands for managing Alts.\n\n`monsters` Commands for managing monsters.\n\n`items`: Commands for managing equipment.\n\n`encounters`: Commands for managing encounters.\n\n`melee` Commands for managing melee attacks.\n\n`spells` Commands for managing spells.\n\n`sparring`: Commands for managing sparring.\n\n`inventory`: Commands for managing inventory.\n\n`economy`: Commands for buying, selling and the guild bank.\n\n`vendors`: Commands for creating, editing and deleting vendors and adding items to them.\n\n`buffs`: Commands for adding, editing, deleting, and giving and taking away buffs.\n\n`armaments`: Commands for managing armaments\n\n`armories`: Commands for managing armories.\n\n`fun`: Commands for old time RP fun.\n\nMore advanced documentation can be found on the wiki: https://github.com/themidnight12am/rpmastermind/wiki\n\n"
            elif parsed_string == 'setup':
                response = "**SETUP COMMANDS**\n\n\n\n`=setadminrole @Role`: *Owner* Set the admin role. This must be done before any other setup. This can only be done by a server owner. See general for role descriptions.\n\n`=newsetup` *Admin* Set up the initial server parameters. See the fields below for descriptions.\n\n`=editsetup` Modify the existing server setup parameters.\n\n`=setplayerrole @Role` *Admin* Set the player role.\n\n`=setgmrole @Role` *Admin* Set the Game Moderator role.\n\n`=setaltrole @Role` *Admin* Set the Alt manager role.\n\n`=listroles` *None* List the server roles.\n\n`=addadmin @user1 @user2` Add users to the admin role. Only the server owner can do this.\n\n`=addaltuser @user1 @user2` Add users to the NPC role.\n\n`=addplayer @user1 @user2` Add users to the player role.\n\n`=addgm @user1 @user2` Add users to the GM role.\n\n`=deleteadmin @user1 @user2` Delete users from the admin role. Only the server owner can do this.\n\n`=deletealt @user1 @user2` Delete users from the NPC role.\n\n`=deleteplayer @user1 @user2` Delete users from the player role.\n\n`=deletegm @user1 @user2` Delete users from the GM role.\n\n`=resetserver` Wipe all data from the bot for this server. Only the server owner may perform this action.\n\n`=invite` Get an invite link for the bot.\n\n"
#                fields = "**SERVER SETTINGS FIELDS**\n\n\n\n`GuildBankBalance:` The total currency in the guild bank. Used for determining how much can be sold back to the guild or how much currency can be given by GMs.\n\n`StartingHealth:` The amount of health new characters start with.\n\n`StartingMana:` The amount of stamina new characters start with.\n\n`StartingAttack:` The amount of attack power new characters start with for melee.\n\n`StartingDefense:` The amount of defense against total damage a character starts with.\n\n`StartingMagicAttack:` The amount of spell power a new character starts with.\n\n`StartingAgility:` The amount of agility a new character starts with.\n\n`StartingIntellect:` The amount of intellect a new character starts with (unused).\n\n  `StartingCharisma:` The amount of charisma a new character starts with (unused).\n\n`HealthLevelRatio:` How many times the level a character's health is set to.\n\n`ManaLevelRatio:` How many times the level a character's mana is set to.\n\n`StaminaLevelRatio:` How many times the level a character's stamina is set to.\n\n`XPLevelRatio:` How many times a level XP must total to before a new level is granted.\n\n`HealthAutoHeal:` How much health is restored per turn during spars and encounters for characters as a multiplier of health. Set to zero for no restores, or less than 1 for partial autoheal (such as 0.1 for 10% per turn).\n\n`ManaAutoHeal:` How much mana restores per turn.\n\n`StaminaAutoHeal:` How much stamina restores per turn.\n\n"
                fields = "For server settings fields, see: https://github.com/themidnight12am/rpmastermind/wiki#server-settings-fields\n\n"
            elif parsed_string == 'characters':
                response = "**CHARACTER COMMANDS**\n\n\n\n`=newchar` *Player* Set up a new character. The bot will DM you for all new fields. An admin must approve a character to become active.\n\n`=editstats` *Admin* Modify character statistics. Specify the name of the character, the bot will DM you for new stats.\n\n`=editchar <charname>` *Player* Edit an existing character's profile. The bot will DM you for the fields.\n\n`=editcharinfo` *Player* Edit a character's addtional information fields.\n\n`=deletechar <charname>` *Player* Delete a character.\n\n`=getcharskills` *None* Get the current list of character spells and melee attacks.\n\n`=getcharprofile` *None* Get a character's complete profile.\n\n`=listmychars` *Player* List the current user's characters.\n\n`=listallchars` *None* List all server characters and their owners.\n\n`=listuserchars @User` *None* List a user's characters.\n\n`=addstatpoints` *Player* Spend earned stat points on character stats.\n\n`=givestatpoints` *Game Moderator* Grant stat points to a character.\n\n`=approvechar` *Admin* Approve a character for play.\n\n`=denychar` *Admin* Decline a character for play. A reason should be provided, and the admin has the option to delete the application entirely if it cannot be fixed.\n\n`=listunapprovedchars` *None* List the characters waiting to be approved or denied.\n`=getchararms name` Get a list of the named character's armaments.\n\n`=getcharequipped name` See what the character currently has equipped in which slots.\n\n"
#                fields = "**CHARACTER FIELDS**\n\n\n\n`CharacterName:` The given full name of the character.\n\n`Age:` The age of the character.\n\n`Race:` The race of the character (human, vampire, etc)\n\n`Gender:` The gender, if known of the character (male, female, trans, etc).\n\n`Height:` The usual height of the character, if known (5'5'', 10 cubits, etc).\n\n`Weight:` The mass on the current world of the character (180 lbs, five tons, etc).\n\n`PlayedBy:` The name of the artist, human representation, actor, etc who is used to show what the character looks like (Angelina Jolie, Brad Pitt, etc).\n\n`Origin:` The hometown or homeworld of the character (Texas, Earth, Antares, etc).\n\n`Occupation:` What the character does for a living, if applicable (blacksmith, mercenary, prince, etc).\n\n`PictureLink:` A direct upload or http link to a publicly accessible picture on the Internet. Google referral links don't always work.\n\n\n\n**ADDITIONAL CHARACTER INFO**\n\n\n\n`Personality:` Free text description of the character's personality (aloof, angry, intelligent)\n\n`Biography:` Any information about the character's history (tragic past, family story, etc).\n\n`Description:` Free text physical description of the character, especially if no play by or picture link is provided, or a description of alternate forms (such as wolf form, final form, etc).\n\n`Strengths:` Free text description of what the character is good at (drawing, melee combat, science, magic.\n\n`Weaknesses:` Free text description of what weaknesses the character has (silver, light, Kryptonite, etc).\n\n`Powers:` The supernatural abilities the character has (such as magic, fire, telepathy.\n\n`Skills:` Any speciality skills the character has (ace sniper, expert in arcane arts, engineer PhD, etc).\n\n\n\n**CHARACTER STATISTICS**\n\n\n\n`Attack:` The base number for melee combat damage. Multiplied by the melee damage multiplier.\n\n`Defense:` The total defense against all damage the character has. Subtracted from damage.\n\n`MagicAttack:` The base number for spell damage. Multiplied by the spell damage multiplier.\n\n`Health:` The amount of health a character has. When this reaches zero during sparring or monster encounters, the player is out of the group. Can be restored by buffs or items. Base is 20 times the level, and restores by 10% each turn.\n\n`Level:` The character's current level, which determines health, mana and stamina. Also determines the experience gained by combat with characters or monsters of different levels.\n\n`Experience:` The amount of experience a character has. To level up, a character must earn 20 times their current level in experience points.\n\n`Stamina:` The amount of stamina a character has for melee combat. When this reaches zero, a chracter must pass or use a spell or item. Heals by 20% every turn.\n\n`Mana:` The amount of mana for spells. When this reaches zero, a character must pass, use melee attacks or an item. Heals for 20% every turn.\n\n`Agility:` How likely a character is to dodge an attack. Higher agility means greater speed.\n\n`Intellect:` Currently unused.\n\n`Charisma:` Currently unused.\n\n`Currency:` How much money a character has for purchasing items.\n\n"
                fields = "For character fields, see: https://github.com/themidnight12am/rpmastermind/wiki#character-profile-fields\n\nFor character status fields, see: https://github.com/themidnight12am/rpmastermind/wiki#character-statistic-fields\n\nFor character additional info fields, see: https://github.com/themidnight12am/rpmastermind/wiki#character-additional-information-fields\n\n"
            elif parsed_string == 'alts':
                response = "**Alt COMMANDS**\n\n\n\n`=alttemplate` *None* Get the template for Alts.\n\n`=newpc` *Alt* Create a new Alt.\n\n`=postalt` *Player* Post as an Alt if you are in the allowed user list.\n\n`=editalt` *Alt* Edit an Alt.\n\n`=deletealt` *Alt* Delete an Alt.\n\n`=listalts`: *None* List all server Alts.\n\n"
            elif parsed_string == 'monsters':
                response = "**MONSTER COMMANDS**\n\n\n\n`=newmonster` *Game Moderator* Add a new monster to the game.\n\n`=editmonster monster name` *Game Moderator* Edit an existing monster. The bot will DM you for the fields.\n\n`=deletemonster monster name` *Game Moderator* Delete a monster from the game.\n\n"
                fields = "For monster fields, see: https://github.com/themidnight12am/rpmastermind/wiki#monster-fields\n\n"
#                fields = "**MONSTER FIELDS**\n\n\n\n`MonsterName:` The name of the monster as appearing in encounters.\n\n`Description:` A brief description of the monster physically, its temperament, and powers.\n\n`Health:` The total health of the monster. When this reaches zero, the encounter ends. It does not restore.\n\n`Level:` The level of the monster, used for calculating experience.\n\n`Attack:` The attack power of the monster. The monster's damage multiplier will be a random number between one and five.\n\n`Defense:` The defense against player damage the monster has.\n\n`Element:` The magic element of the monster, currently unused.\n\n`MagicAttack:` The spell power of the monster, currently unused.\n\n`MaxCurrencyDrop:` The maximum amount of money the monster drops when the encounter ends. The drop will vary between 1 and this maximum and is evenly split among the server party.\n\n`PictureLink:` A picture of the monster, either Internet link or direct Discord upload.\n\n"
            elif parsed_string == 'items':
                response = "**ITEM COMMANDS**\n\n\n\n`=newitem` *Admin* Add a new item to the game.\n\n`=edititem` Edit an existing item. The bot will DM you for the fields.\n\n`=deleteitem item name` Remove an item from the game.\n\n`=listitems` List all equipment on the server.\n\n`=giveitem` *Game Moderator* Give a character an item.\n\n`=takeitem` *Game Moderator.* Take an item away from a character."
                fields = "For item fields, see: https://github.com/themidnight12am/rpmastermind/wiki#item-fields\n\n"
#                fields = "**ITEM FIELDS**\n\n\n\n`EquipmentName:` The name of the item as it will appear in the inventory and vendor lists.\n\n`EquipmentDescription:` A description of the item.\n\n`EquipmentCost:` How much currency a player must have to purchase the item.\n\n`MinimumLevel:` The minimum level a character must be to use an item. A player may purchase a higher-level item but will not be able to use it until their level is the minimum or higher.\n\n`StatMod:` Which character statistic this item modifies (Health, Stamina, Mana, Attack, Defense, MagicAttack, Agility).\n\n`Modifier:` The value this item modifies the statistic by. A positive value increases the stat, a negative one decreases it. So a healing potion could be 100, and a cursed item -500.\n\n"
            elif parsed_string == 'encounters':
                response = "**ENCOUNTER COMMANDS**\n\n\n\n`=newparty @user1 @user2` *Game Moderator* Set a new party with the specified users.\n\n`=disbandparty` *Game Moderator* Disband the current server party.\n\n`=setencounterchar` *Player* Set the player's character for the encounter.\n\n`=encountermonster` *Game Moderator* Begin the monster encounter.\n\n`=monsterattack` *Game Moderator* Have the monster attack a random party member.\n\n`=castmonster` *Player* Attack the monster with the specified spell.\n\n`meleemonster` *Player* Attack the monster with the specified melee attack.\n\n`=weaponmonster` Attack the monster with an equipped armament.\n\n`=abortencounter` *Game Moderator* End the encounter with no health penalty *and* no experience gained.\n\n`=pass` Pass on your turn.\n\n\n\n"
                fields = "For encounter comamnd sequences, see: https://github.com/themidnight12am/rpmastermind/wiki#running-an-encounter\n\n"
#                fields = "**ENCOUNTER COMMAND SEQUENCE**\n\n\n\nA game moderator can begin a monster encounter by using the command `=newparty` followed by mentions (@) of the players in the encounter. Each player must then enter `=setencounterchar` to set a character for the encounter by using the DM system. The game moderator then use the command `=encountermonster` and selects a server monster from the list by replying to the DM. This initiates the encounter. Each character will be told it is their turn and can use `=meleemonster` to select a melee attack to strike the monster or `=castmonster` to strike the monster with a spell. The game moderator may use `=monsterattack` on anyone's turn to randomly strike any party member with the monster's attack. The game moderator may also end the encounter early with the `=abortencounter` command, which resets all stats but does not restore items, and returns no experience or currency. Players may also `=pass` on their turn but may not leave the encounter. The encounter ends when the monster's health reaches zero, and then everyone gets an even split of the currency drop and experience based on the damage they did to the monster. The party will not disband automatically, in case there are multiple monsters to encounter. A party may disband with the `=disbandparty` command."
            elif parsed_string == 'melee':
                response = "**MELEE COMMANDS**\n\n\n\n`=newmelee` *Admin* Create a new melee attack.\n\n`=editmelee` *Admin* Edit an existing melee attack. The bot will DM you for the fields.\n\n`=deletemelee attack name` *Admin* Delete a melee attack.\n\n`=listmelees` *None* List all melee attacks on the server.\n\n`=givemelee` *Admin* Give a character a melee attack.\n\n`=takemelee` *Admin* Take a melee attack from a character.\n\n"
#                fields = "**MELEE FIELDS**\n\n\n\n`AttackName:` The name of the melee attack as it appears in combat (punch, kick, body slam).\n\n`StaminaCost:` How much stamina will be used to perform the attack.\n\n`MinimumLevel:` The minimum level required for this attack. A character may know a technique at a lower level but cannot use it in combat.\n\n`DamageMultiplier:` How much to multiply the character's base attack power by for total damage.\n\n`Description:` A description of the attack (free text).\n\n"
                fields = "For meelee attack fields, see: https://github.com/themidnight12am/rpmastermind/wiki#melee-attack-fields\n\n"
            elif parsed_string == 'spells':
                response = "**SPELL COMMANDS**\n\n\n\n`=newspell` *Admin* Create a new spell.\n\n`=editspell` *Admin* Edit an existing spell.\n\n`=deletespell spell name` Delete a spell.\n\n`=listspells` *Admin* List all server spells.\n\n`=givespell` *Admin* Give a character a spell.\n\n`=takespell` *Admin* Take a spell away from a character.\n\n"
#                fields = "`SPELL FIELDS`\n\n\n\n`SpellName:` The name of the spell as it appears in combat or skill lists.\n\n`Element:` The magic element of this spell (currently unused).\n\n`ManaCost:` The amount of mana drained to perform the spell.\n\n`MinimumLevel:` The mininum level required to use the spell. A character may know higher-level spells but cannot use them in combat.\n\n`DamageMultiplier:` The value by which MagicAttack is multiplied for total spell damage.\n\n`Description:` A free text description of the spell, such as what it looks like or its effects.\n\n"
                fields = "For spell fields, see: https://github.com/themidnight12am/rpmastermind/wiki#spell-fields\n\n"
            elif parsed_string == 'sparring':
                response = "**SPARRING COMMANDS**\n\n\n\n*All spar commands only require player role.*\n\n\n\n`=newspargroup @User1 @User2...` Initiate a spar with two or more players.\n\n`=sparconfirm` Confirm you wish to spar if included in a spar group.`=spardeny` Decline the spar group invitation. If only player is left, the spar group disbands.\n\n`=setsparchar` Set the character to use for the spar.\n\n`=beginspar` Begin the spar. The bot will keep track of turns.\n\n`=meleespar` Target a *user's* character with a melee attack.\n\n`=castspar` Target a *user's* character with a spell.\n\n`=weaponspar` Attack a player with an armament.\n\n`=leavespar` Leave a spar group. You gain no experience and your health returns to normal, but the other spar members do gain experience.\n\n"
                fields = "For how to run a mass spar, see: https://github.com/themidnight12am/rpmastermind/wiki#running-a-mass-spar\n\n"
               # fields = "**SPARRING COMMAND SEQUENCE**\n\n\n\nAny player may initiate a spar with any number of players. The first command is `=newspargroup` followed by Discord mentions (@) of players wished to be in the spar group. Next, all mentioned players must reply `=sparconfirm` or `=spardeny` to join or not join the spar. If at least two people confirm the spar, then all players must select a character by entering `=setsparchar` and replying to the DM which character to use. `=beginspar` will initiate the spar. During combat, `=meleespar` will allow a character to select a melee attack and any target, and `=castspar` will allow a character to select a spell and any target. `=useitem` can be used out of turn to restore any statistic. A player may enter `=pass` if they have no mana or stamina, or do not wish to attack, and `=leavespar` will remove a character from the spar, gaining no experience but having no penalty on health.\n\n"
            elif parsed_string == 'inventory':
                response = "**INVENTORY COMMANDS**\n\n\n\n`=myitems <character name>` List your character's items.\n\n`=useitem`\n\nUse an item in your inventory.\n\n"
            elif parsed_string == 'economy':
                response = "**ECONOMY COMMANDS**\n\n\n\n`=givecurrency` *Game Moderator* Give a character money!\n\n`=buy` Buy an item from a vendor.\n\n`=sell` Sell an item back to the game for money.\n\n`=trade` Give an item to another character. Be careful with trades, as there's no way to guarantee the other party will trade back!\n\n`=sendcurrency` Send currency to another character, including your own.\n\n`=buyarms` Buy an armament from an armory.\n\n`=sellarms` Sell an armament back to the bank.\n\n`=tradearms` Trade an armament to another character. Again, no fairness is enforced.\n\n`=setbankbalance` *Admin* Update the bank guild balance.\n\n\n\n"
                fields = "For buying and selling, see: https://github.com/themidnight12am/rpmastermind/wiki#buying-and-selling\n\n"
            elif parsed_string == 'vendors':
                response = "**VENDOR COMMANDS**\n\n\n\n`=newvendor` Create a new vendor with items.\n\n`=addvendoritem` Add items to an existing vendor.\n\n`=deletevendor` Remove a vendor from the game.\n\n`=deletevendoritem` Delete an item for a particular vendor.\n\n`=listvendors` List all vendors in the game.\n\n`=listvendor <name>` List all items of a particular vendor."
                fields = "For vendor fields, see: https://github.com/themidnight12am/rpmastermind/wiki#vendor-fields\n\n "
 #               fields = "**VENDOR FIELDS**\n\n\n\n`VendorName:` The name of the vendor as it appears in buying items.\n\n`ItemList:` A comma delimited list of item IDs available for purchase.\n\n"
            elif parsed_string == 'fun':                
                response = "**FUN FUN FUN COMMANDS**\n\n\n\n`=lurk` *None* Post a random lurk command.\n\n`=ooc` Post as the bot with OOC brackets.\n\n`=randomooc @user` Do something random to another user.\n\n`=roll` x`d`y *None* Roll x number of y-sided dice.\n\n"
            elif parsed_string == 'general':
                response = "**GENERAL INFO**\n\n\n\nThis bot supports character profiles, leveling/experience, sparring, random encounters, monsters, equipment/inventory/economy, and spells/melee attacks.\n\n\n\nSome commands only require the name of the character or spell, like `=editmonster Evil Dead`. Other commands will initiate a DM that has menus that you can reply to for setting up or modifying game parameters. If the user has DMs disabled, the bot will reply in the same channel as the user's command.\n\n\n\n**ROLES**\n\n\n\nThere are four roles required to use the bot.\n\n`Admin:` The admin can run all commands of the bot, such as adding and deleting spells or items. The server owner must set the admin role.\n\n`Game Moderator:` The game moderator is able to start random encounters, add or delete monsters, give money, and give items.\n\n`Alt Manager:` The Alt manager is able to create, edit and delete Alts.\n\n`Player:` A player is able to add, edit, and delete their character profile, and play as their character, and post as Alts if allowed, and buy and sell items, and trade with other players. An admin role user must approve new characters.\n\n\n\n**LEVELING**\n\n\n\nLeveling is granted by gaining experience. Experience is gained by random encounters, sparring, or granted by a game moderator. A new level is achieved when experience totals twenty times the current level (default).\n\nFor more information, see the wiki: https://github.com/themidnight12am/rpmastermind/wiki#general-information\n\n"
            elif parsed_string == 'buffs':
                response = "**BUFF COMMANDS**\n\n\n\n=`=newbuff` *Admin* Create a new buff.\n\n`=editbuff` Edit an existing buff.\n\n`=deletebuff` Delete a buff from the server.\n\n`=givebuff` Give a buff to a character.\n\n`=takebuff` Take a buff from a character.\n\n`=buff` Use a buff on a character during a spar or encounter.\n\n"
#                fields = "**BUFF FIELDS**\n\n\n\n`BuffName:` The name of the buff spell.\n\n`ManaCost:` The amount of mana drained to use the buff.\n\n`MinimumLevel:` The minimum level required to use the buff.\n\n`StatMod:` The status modified by the buff.\n\n`Modifier:` The amount, positive or negative, of the buff's modification to the status.\n\n`Description:` A free text desciption of the buff.\n\n"
                fields = "For buff fields, see: https://github.com/themidnight12am/rpmastermind/wiki#buff-fields\n\n"
            elif parsed_string == 'armaments':
                response = "**ARMAMENTS COMMANDS**\n\n\n\n`=newarmament` Create a new armament.\n\n`=editarmament` Edit an existing armament.\n\n`=deletearmament` Delete an armament from the game.\n\n`=givearmament` Give an armament to a character.\n\n`=takearmament` Take an armament from a character.\n\n`=equiparmament` Equip a character with an armament from their inventory in an available, matching slot.\n\n`=unequiparmament` Remove an armamemnt from an equipped slot on a character.\n\n"
                fields = "For armament fields, see: https://github.com/themidnight12am/rpmastermind/wiki#armament-fields\n\n"
#                fields = "**ARMAMENT FIELDS**\n\n\n\n`ArmamentName`: The display name of the armament.\n\n`Description`: The free text description of the armament.\n\n`ArmamentCost`: How much currency the armament will sell for.\n\n`MinimumLevel`: The minimum level required to use the armament.\n\n`StatMod`: The status field modified by the armament (Attack, MagicAttack or Agility)\n\n`Modifier`: The amount a statistic is modified by the armament.\n\n`Slot`: The slot the armament can be equipped in (Head, Hand, Chest, or Feet)\n\n`MinimumDamage`: The minimum damage the armament can do (zero for status only items).\n\n`MaximumDamage`: The maximum amount of damage the armament can do (zero for status only items).\n\n`Defense`: The amount of defense added by the armament (zero for non-defensive armaments).\n\n"
            elif parsed_string == 'armories':
                response = "**ARMORY COMMANDS**\n\n\n\n`=newarmory` Create a new armory.\n\n`=editarmory` Edit an existing armory.\n\n`=deletearmory` Delete an armory from the game.\n\n`=addarmoryitem` Add items to an armory.\n\n`=deletearmoryitem` Delete an item from the armory.\n"
                fields = "**ARMORY FIELDS**\n\n\n\n`ArmoryName:` The display name of the armory.\n\n`ArmamentList:` The list of armaments for sale at this armory.\n"
                fields = "For armory fields, see: https://github.com/themidnight12am/rpmastermind/wiki#armory-fields\n\n"
            if fields:
                await reply_message(message, response + fields)
            else: 
                await reply_message(message, response)
        if "AdminRole" not in guild_settings[message.guild.id].keys():
            await reply_message(message, "Admin role not set! Please set an admin role using the command =setadminrole @Role")
            return
        if message.guild and re.search(r"cast|melee|weapon", message.content):
            if mass_spar_event[message.guild.id] and message.author.id in list(mass_spar_chars[message.guild.id].keys()):
                server_id = message.guild.id
                user_id = message.author.id
                if mass_spar_chars[server_id][user_id]["Health"] < mass_spar_chars[server_id][user_id]["MaxHealth"]:
                    health_gained = int(guild_settings[server_id]["HealthAutoHeal"] * mass_spar_chars[server_id][user_id]["MaxHealth"])
                    mass_spar_chars[server_id][user_id]["Health"] = mass_spar_chars[server_id][user_id]["Health"] + health_gained
                else:
                    health_gained = "0 (at max)"
                if mass_spar_chars[server_id][user_id]["Mana"] < mass_spar_chars[server_id][user_id]["MaxMana"]:
                    mana_gained = int(guild_settings[server_id]["ManaAutoHeal"] * mass_spar_chars[server_id][user_id]["Mana"])
                    mass_spar_chars[server_id][user_id]["Mana"] = mass_spar_chars[server_id][user_id]["Mana"] + mana_gained
                else:
                    mana_gained = "0 (at max)"
                    
                if mass_spar_chars[server_id][user_id]["Stamina"] < mass_spar_chars[server_id][user_id]["MaxStamina"]:
                    stamina_gained = int(guild_settings[server_id]["StaminaAutoHeal"] * mass_spar_chars[server_id][user_id]["Stamina"])
                    mass_spar_chars[server_id][user_id]["Stamina"] = mass_spar_chars[server_id][user_id]["Stamina"] + stamina_gained
                else:
                    stamina_gained = "0 (at max)"
                    
                await reply_message(message, mass_spar_chars[server_id][user_id]["CharName"] + " automatically gained **" + str(health_gained) + "** health, **"     + str(mana_gained) + "** mana and **" + str(stamina_gained) + "** stamina this turn!")
            if server_encounters[message.guild.id] and message.author.id in list(server_party_chars[message.guild.id].keys()):
                server_id = message.guild.id
                user_id = message.author.id
                if server_party_chars[server_id][user_id]["Health"] < server_party_chars[server_id][user_id]["MaxHealth"]:
                    health_gained = int(guild_settings[server_id]["HealthAutoHeal"] * server_party_chars[server_id][user_id]["MaxHealth"])
                    server_party_chars[server_id][user_id]["Health"] = server_party_chars[server_id][user_id]["Health"] + health_gained
                else:
                    health_gained = "0 (at max)"
                if server_party_chars[server_id][user_id]["Mana"] < server_party_chars[server_id][user_id]["MaxMana"]:
                    mana_gained = int(guild_settings[server_id]["ManaAutoHeal"] * server_party_chars[server_id][user_id]["Mana"])
                    server_party_chars[server_id][user_id]["Mana"] = server_party_chars[server_id][user_id]["Mana"] + mana_gained
                else:
                    mana_gained = "0 (at max)"
                    
                if server_party_chars[server_id][user_id]["Stamina"] < server_party_chars[server_id][user_id]["MaxStamina"]:
                    stamina_gained = int(guild_settings[server_id]["StaminaAutoHeal"] * server_party_chars[server_id][user_id]["Stamina"])
                    server_party_chars[server_id][user_id]["Stamina"] = server_party_chars[server_id][user_id]["Stamina"] + stamina_gained
                else:
                    stamina_gained = "0 (at max)"
                    
                await reply_message(message, server_party_chars[server_id][user_id]["CharName"] + " automatically gained **" + str(health_gained) + "** health, **"     + str(mana_gained) + "** mana and **" + str(stamina_gained) + "** stamina this turn!")
                
        if command == 'initialize':
            if not await admin_check(message.author.id):
                await reply_message(message, "This command is admin only!")
                return
            
            create_profile_table = """CREATE TABLE CharacterProfiles (Id int auto_increment, ServerId varchar(40), UserId varchar(40), CharacterName varchar(50), LastName varchar(100), Age Int, Race varchar(30), Gender varchar(20), Height varchar(10), Weight varchar(10), PlayedBy varchar(40), Origin varchar(100), Occupation varchar(100), Personality TEXT, Biography TEXT, Description TEXT, Strengths TEXT, Weaknesses TEXT, Powers TEXT, Skills TEXT, Attack Int, Defense Int, MagicAttack Int, Health Int, Mana Int, Level Int, Experience Int, Stamina Int, Agility Int, Intellect Int, Charisma Int, Currency DECIMAL(12,2), PictureLink varchar(1024), PRIMARY KEY (Id));"""
            create_alt_table = """CREATE TABLE Alts (Id int auto_increment, ServerId varchar(40), UserId varchar(40), UsersAllowed varchar(1500), CharName varchar(100), PictureLink varchar(1024), Shortcut varchar(20), PRIMARY KEY (Id));"""
            create_spell_table = """CREATE TABLE Spells (Id int auto_increment, ServerId varchar(40), UserId varchar(40), SpellName varchar(100), Element varchar(50), ManaCost Int, MinimumLevel int, DamageMultiplier Int, Description TEXT, PRIMARY KEY (Id));"""
            create_melee_table = """CREATE TABLE Melee (Id int auto_increment, ServerId varchar(40), UserId varchar(40), AttackName varchar(100), StaminaCost Int, MinimumLevel Int,DamageMultiplier Int, Description TEXT, PRIMARY KEY (Id));"""
            create_melee_char_table = """CREATE TABLE MeleeSkills (Id int auto_increment, ServerId varchar(40), UserId varchar(40), CharacterId int, MeleeId int, PRIMARY KEY (Id));"""
            create_magic_char_table = """CREATE TABLE MagicSkills (Id int auto_increment, ServerId varchar(40), UserId varchar(40), CharacterId int, SpellId int, PRIMARY KEY (Id));"""
            create_equipment_table = """CREATE TABLE Equipment (Id int auto_increment, ServerId varchar(40), UserId varchar(40), EquipmentName varchar(100), EquipmentDescription TEXT, EquipmentCost DECIMAL(7,2), MinimumLevel Int, StatMod varchar(30), Modifier Int, PictureLink TEXT, PRIMARY KEY (Id));"""
            create_inventory_table = """CREATE TABLE Inventory (Id int auto_increment, ServerId varchar(40), UserId varchar(40), CharacterId int, EquipmentId int, PRIMARY KEY (Id));"""
            create_monster_table = """CREATE TABLE Monsters (Id int auto_increment, Serverid varchar(40), UserId varchar(40), MonsterName varchar(100), Description TEXT, Health Int, Level Int, Attack Int, Defense Int, Element varchar(50), MagicAttack Int, MaxCurrencyDrop Int, PictureLink varchar(1024), PRIMARY KEY(Id));"""
            # "GMRole","NPCRole","PlayerRole","GuildBankBalance","StartingHealth","StartingMana","StartingStamina","StartingAttack","StartingDefense","StartingMagicAttack","StartingAgility","StartingIntellect","StartingCharisma","HealthLevelRatio","ManaLevelRatio","StaminaLevelRatio","XPLevelRatio","HealthAutoHeal","ManaAutoHeal","StaminaAutoHeal"
            create_guild_settings_table = """CREATE TABLE GuildSettings (Id int auto_increment, ServerId VARCHAR(40),  GuildName VarChar(100), GuildBankBalance DECIMAL(12,2), AdminRole VARCHAR(40), GameModeratorRole VARCHAR(40), PlayerRole VARCHAR(40), NPCRole VARCHAR(40), PRIMARY KEY(Id));"""
            
            create_custom_profile_table = """CREATE TABLE CustomProfiles (Id int auto_increment, ServerId VARCHAR(40), Fields BIGTEXT, PRIMARY KEY(Id));"""
            
            create_vendor_table = """CREATE TABLE Vendors (Id int auto_increment, ServerId VARCHAR(40), UserId VARCHAR(40), VendorName VARCHAR(100), ItemList TEXT, PRIMARY KEY(Id));"""
            create_healing_table = """CREATE TABLE Buffs (Id int auto_increment, ServerId VARCHAR(40), UserId VARCHAR(40), BuffName VARCHAR(100), ManaCost Int, MinimumLevel Int, StatMod VARCHAR(30), Modifier Int, Description TEXT, PRIMARY KEY(Id));"""
            create_buff_char_table = """CREATE TABLE BuffSkills (Id int auto_increment, ServerId VARCHAR(40), UserId VARCHAR(40), CharId Int, BuffId Int, PRIMARY KEY(Id));"""
            create_unapproved_char_table = """CREATE TABLE UnapprovedCharacterProfiles (Id int auto_increment, ServerId varchar(40), UserId varchar(40), CharacterName varchar(50), LastName varchar(100), Age Int, Race varchar(30), Gender varchar(20), Height varchar(10), Weight varchar(10), PlayedBy varchar(40), Origin varchar(100), Occupation varchar(100), Personality TEXT, Biography TEXT, Description TEXT, Strengths TEXT, Weaknesses TEXT, Powers TEXT, Skills TEXT, Attack Int, Defense Int, MagicAttack Int, Health Int, Mana Int, Level Int, Experience Int, Stamina Int, Agility Int, Intellect Int, Charisma Int, Currency DECIMAL(12,2), PictureLink varchar(1024), PRIMARY KEY (Id));"""
            create_armaments_table = """CREATE TABLE Armaments (Id int auto_increment, ServerId VARCHAR(40), UserId VARCHAR(40),ArmamentName VARCHAR(100), Description TEXT, ArmamentCost DECIMAL(7,2), Slot VARCHAR(20), MinimumLevel Int, DamageMin Int, DamageMax Int, Defense Int, StatMod VARCHAR(30), Modifier Int, PictureLink TEXT, PRIMARY KEY(Id));"""
            create_char_armaments_table = """CREATE TABLE CharacterArmaments (Id int auto_increment, ServerId VARCHAR(40), UserId VARCHAR(40), CharacterId Int, HeadSlotId Int, LeftHandId Int, RightHandId Int, ChestId Int, FeetId int, PRIMARY KEY(Id));"""
            create_char_armaments_inventory_table = """CREATE TABLE ArmamentInventory (Id int auto_increment, ServerId VARCHAR(40), UserId VARCHAR(40), CharacterId Int, ArmamentId Int, PRIMARY KEY(Id));"""
            create_armory_table = """CREATE TABLE Armory (Id Int auto_increment, ServerId VARCHAR(40), UserId VARCHAR(40), ArmoryName VARCHAR(100), ArmamentList TEXT, PRIMARY KEY(Id));"""
            
            result = await execute_sql(create_profile_table)
            if not result:
                await reply_message(message, "Database error with profile!")
                return
                
            result = await execute_sql(create_alt_table)
            if not result:
                await reply_message(message, "Database error with Alts!")
                return  
                
            result = await execute_sql(create_spell_table)
                    
            if not result:
                await reply_message(message, "Database error with spells!")
                return
                
            result = await execute_sql(create_melee_table)
            if not result:
                await reply_message(message, "Database error with melee!")
                return
                
            result = await execute_sql(create_melee_char_table)
            if not result:
                await reply_message(message, "Database error with melee character!")
                return    
                
            result = await execute_sql(create_magic_char_table)
            if not result:
                await reply_message(message, "Database error with magic character!")
                return
                
            result = await execute_sql(create_equipment_table)
            if not result:
                await reply_message(message, "Database error with equipment!")
                return
                
            result = await execute_sql(create_inventory_table)
            if not result:
                await reply_message(message, "Database error with inventory!")
                return
            result = await execute_sql(create_monster_table)
            if not result:
                await reply_message(message, "Database error with monsters!")
                return
            result = await execute_sql(create_guild_settings_table)
            if not result:
                await reply_message(message, "Database error with guild settings!")
                return
            result = await execute_sql(create_custom_profile_table)
            if not result:
                await reply_message(message, "Database error with custom profiles!")
                return  
            result = await execute_sql(create_vendor_table)
            if not result:
                await reply_message(message, "Database error with Vendors!")
                
            result = await execute_sql(create_healing_table)
            if not result:
                await reply_message(message, "Database error with buffs!")
                return 
            result = await execute_sql(create_buff_char_table)
            if not result:
                await reply_message(message, "Database error with buff skills!")
                return
            result = await execute_sql(create_unapproved_char_table)
            if not result:
                await reply_message(message, "Database error with unapproved char table!")
                return
            result = await execute_sql(create_armaments_table)
            if not result:
                await reply_message(message, "Database error with armaments table!")
                return                                       
            result = await execute_sql(create_char_armaments_table)
            if not result:
                await reply_message(message, "Database error with character armaments table!")
                return
            result = await execute_sql(create_char_armaments_inventory_table)
            if not result:
                await reply_message(message, "Database error with character armaments inventory table!")
                return 
            result = await execute_sql(create_char_armory_table)
            if not result:
                await reply_message(message, "Database error with armory table!")
                return                    
            await reply_message(message, "Databases initialized!")
        elif command == 'deleteall':
            if not await admin_check(message.author.id):
                await reply_message(message, "This command is admin only!")
                return
            drop_all_tables = """DROP TABLE IF EXISTS CharacterProfiles; DROP TABLE IF EXISTS Inventory; DROP TABLE IF EXISTS Equipment; DROP TABLE IF EXISTS Alts; DROP TABLE IF EXISTS Spells; DROP TABLE IF EXISTS Melee; DROP TABLE IF EXISTS MagicSkills; DROP TABLE IF EXISTS MeleeSkills; DROP TABLE IF EXISTS Monsters; DROP TABLE IF Exists CustomProfiles; DROP TABLE IF Exists Vendors; DROP TABLE IF EXISTS Buffs; DROP TABLE IF EXISTS BuffSkills;"""
            result = await execute_sql(drop_all_tables)
            if result:
                await reply_message(message, "All tables dropped.")
            else:
                await reply_message(message, "Database error!")
        elif command == 'listunapprovedchars':
            dm_tracker[message.author.id] = {}
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            response = "**UNAPPROVED CHARACTERS**\n\n"
            menu = await make_simple_menu(message, "UnapprovedCharacterProfiles", "CharacterName")
            await reply_message(message, response + menu)                
        elif command == 'pass':
            server_id = message.guild.id
            user_id = message.author.id
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to cast spells!")
                return            
            if not mass_spar_event[server_id]:
                await reply_message(message, "Why are you casting Magic Missile? There's nothing to attack here!")
                return

            in_party = next((item for item in mass_spar[server_id] if item.id == user_id), None)
            if not in_party:
                await reply_message(message, "You are not in the spar group!")
                return
            if message.author != list(mass_spar[server_id])[mass_spar_turn[server_id]]:
                await reply_message(message, "It's not your turn!")
                return        
            if mass_spar_turn[server_id] > len(mass_spar[server_id]) - 2:
                mass_spar_turn[server_id] = 0
            else:
                mass_spar_turn[server_id] = mass_spar_turn[server_id] + 1
            await reply_message(message, "<@" + str(mass_spar[server_id][mass_spar_turn[server_id]].id) + ">, it is your turn!")             
        elif command == 'roll':
            dice_re = re.compile(r"(\d+)d(\d+)")
            m = dice_re.match(parsed_string)
            if not m:
                await reply_message(message, "Invalid dice command!")
                return
            number_of_dice = m.group(1)
            dice_sides = m.group(2)
            response = "**Dice roll:**\n\n"
            sum = 0
            for x in range(0,int(number_of_dice)):
                die_roll = random.randint(1,int(dice_sides))
                sum = sum + die_roll
                response = response + "`" + str(die_roll) + "` "
            response = response + "\nSum of rolled dice: `" + str(sum) + "`"
            await reply_message(message, response)
        elif command == 'leavespar':
            server_id = message.guild.id
            user_id = message.author.id
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to leave a spar!")
                return            
            if not mass_spar_event[message.guild.id]:
                await reply_message(message, "Why are you trying to leave a spar? There's nothing going on!")
                return

            in_party = next((item for item in mass_spar[server_id] if item.id == user_id), None)
            if not in_party:
                await reply_message(message, "You are not in the spar group!")
                return
            if message.author == list(mass_spar[server_id])[mass_spar_turn[server_id]]:
                await reply_message(message, "It's your turn! Please pass then try again")
                return
            del mass_spar_chars[message.guild.id][message.author.id]
            await reply_message(message, "<@" + str(message.author.id) + "> has left the spar!")
        elif command == 'listallchars':
            records = await select_sql("""SELECT CharacterName,Level,UserId FROM CharacterProfiles WHERE ServerId=%s;""", (str(message.guild.id),))
            if not records:
                await reply_message(message, "No characters found for this server!")
                return
            response = "**SERVER CHARACTER LIST**\n\n"
            for row in records:
                response = response + row[0] + ", level " + str(row[1]) + ", mun: `" + str(message.guild.get_member(int(row[2]))) + "`\n"
            await reply_message(message, response)
        elif command == 'listuserchars':
            if not message.mentions:
                await reply_message(message, "You didn't specify a user!")
                return
            user = message.mentions[0]
            user_id = user.id
            records = await select_sql("""SELECT CharacterName,Level FROM CharacterProfiles WHERE ServerId=%s AND UserId=%s;""",(str(message.guild.id),str(user_id)))
            if not records:
                await reply_message(message, "No records found for that user!")
                return
            response = "**USER CHARACTER LIST**\n\n"
            for row in records:
                response = response + row[0] + " " + row[1] + ", level " + int(row[2]) + "\n"
            await reply_message(message,response)
        elif command == 'approvechar':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must have the admin role to approve a new character.")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'approvechar'
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterName","Approval"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "UnapprovedCharacterProfiles", "CharacterName")
            
            response = "Please select a new character to approve by replying to this message with the ID below:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to approve a character, <@" + str(message.author.id) + ">.")
        elif command == 'denychar':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must have the admin role to deny a new character.")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'denychar'
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterName","Deny","DenyReason","Deletion"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "UnapprovedCharacterProfiles", "CharacterName")
            
            response = "Please select a new character to deny by replying to this message with the ID below:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to deny a character, <@" + str(message.author.id) + ">.")        
        elif command == 'newchar':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must have the player role to create a new character.")
                return
            records = await select_sql("""SELECT Fields FROM CustomProfiles WHERE ServerId=%s;""",(str(message.guild.id),))
            if records:
                field_dict = { }
                for row in records:
                    fields = row[0].split(',')
                if message.author.id not in dm_tracker.keys():
                    await initialize_dm(message.author.id)
                dm_tracker[message.author.id]["currentcommand"] = 'newcustomchar'
                dm_tracker[message.author.id]["fieldlist"] = fields
                dm_tracker[message.author.id]["server_id"] = message.guild.id
                dm_tracker[message.author.id]["currentfield"] = 0
                dm_tracker[message.author.id]["commandchannel"] = message.channel
                await reply_message(message, "Please check your DMs for instructions on how to create a new character, <@" + str(message.author.id) + ">.")
                await direct_message(message, "Hello, you have requested to create a new character! Please start with the **name** of the character below in your reply!")
                return

            else:        
                if message.author.id not in dm_tracker.keys():
                    await initialize_dm(message.author.id)
                dm_tracker[message.author.id]["currentcommand"] = 'newdefaultchar'
                dm_tracker[message.author.id]["fieldlist"] = ["CharacterName","Age","Race","Gender","Height","Weight","Playedby","Origin","Occupation","PictureLink"]                                                   
                dm_tracker[message.author.id]["currentfield"] = 0
                dm_tracker[message.author.id]["fielddict"] = [] 
                dm_tracker[message.author.id]["server_id"] = message.guild.id
                dm_tracker[message.author.id]["commandchannel"] = message.channel
                
                await reply_message(message, "Please check your DMs for instructions on how to create a new character, <@" + str(message.author.id) + ">.")
                
                await direct_message(message, "You have requested a new default character! Please type in the response the **first and last names of the character**, and then enter each field as a reply to the DMs. When you have filled out all fields, the character will be created!")
        elif command == 'newrandomchar':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must have the player role to create a new character.")
                return

            male_first_name_list = ["Ferris", "Redmond", "Raphael", "Orion", "Caspian", "Aramis", "Lucian", "Storm", "Percival", "Gawain", "Perseus", "Cormac", "Leon", "Patrick", "Robert", "Morgan", "Brandon", "Sven", "Roland", "Ronan", "Edmund", "Adam", "Edric", "Martin", "Odin", "Bayard", "Laurent", "Faramond", "Finn", "Edward", "Tristan", "Emil", "Zephyr", "Soren", "Arthur", "Robin", "Marcel", "Roman", "Beowulf"", ""Seth", "Tristan", "Arthur", "Edmund", "Percival", "Ronan", "Thor", "Leon", "Roman", "Adam", "Ferris", "Zephyr", "Gawain", "Perseus", "Cormac", "Lydan", "Syrin", "Ptorik", "Joz", "Varog", "Gethrod", "Hezra", "Feron", "Ophni", "Colborn", "Fintis", "Gatlin", "Jinto", "Hagalbar", "Krinn", "Lenox", "Revvyn", "Hodus", "Dimian", "Paskel", "Kontas", "Weston", "Azamarr ", "Jather ", "Tekren ", "Jareth", "Adon", "Zaden", "Eune ", "Graff", "Tez", "Jessop", "Gunnar", "Pike", "Domnhar", "Baske", "Jerrick", "Mavrek", "Riordan", "Wulfe", "Straus", "Tyvrik ", "Henndar", "Favroe", "Whit", "Jaris", "Renham", "Kagran", "Lassrin ", "Vadim", "Arlo", "Quintis", "Vale", "Caelan", "Yorjan", "Khron", "Ishmael", "Jakrin", "Fangar", "Roux", "Baxar", "Hawke", "Gatlen", "Barak", "Nazim", "Kadric", "Paquin", " ", "", "Kent", "Moki", "Rankar", "Lothe", "Ryven", "Clawsen", "Pakker", "Embre", "Cassian", "Verssek", "Dagfinn", "Ebraheim", "Nesso", "Eldermar", "Rivik", "Rourke", "Barton", "Hemm", "Sarkin", "Blaiz ", "Talon", "Agro", "Zagaroth", "Turrek", "Esdel", " ", "", "Lustros", "Zenner", "Baashar ", "Dagrod ", "Gentar", "Feston"]
            female_first_name_list = ["Ayrana", "Resha", "Varin", "Wren", "Yuni", "Talis", "Kessa", "Magaltie", "Aeris", "Desmina", "Krynna", "Asralyn ", "Herra", "Pret", "Kory", "Afia", "Tessel", "Rhiannon", "Zara", "Jesi", "Belen", "Rei", "Ciscra", "Temy", "Renalee ", "Estyn", "Maarika", "Lynorr", "Tiv", "Annihya", "Semet", "Tamrin", "Antia", "Reslyn", "Basak", "Vixra", "Pekka ", "Xavia", "Beatha ", "Yarri", "Liris", "Sonali", "Razra ", "Soko", "Maeve", "Everen", "Yelina", "Morwena", "Hagar", "Palra", "Elysa", "Sage", "Ketra", "Lynx", "Agama", "Thesra ", "Tezani", "Ralia", "Esmee", "Heron", "Naima", "Rydna ", "Sparrow", "Baakshi ", "Ibera", "Phlox", "Dessa", "Braithe", "Taewen", "Larke", "Silene", "Phressa", "Esther", "Anika", "Rasy ", "Harper", "Indie", "Vita", "Drusila", "Minha", "Surane", "Lassona", "Merula", "Kye", "Jonna", "Lyla", "Zet", "Orett", "Naphtalia", "Turi", "Rhays", "Shike", "Hartie", "Beela", "Leska", "Vemery ", "Lunex", "Fidess", "Tisette", "Partha"]
            unisex_first_name_list = []
            last_name_list = ["Starbringer","Leafgreen","Smith","Thundershaw","Dreamweaver","McAle","Hale","Zendor","Zoaraster","Horserider","Stormwalker","Abawi", "Allard", "Adara", "Abbott", "Acampora", "Ackerman", "Ackroyd", "Abbington", "Axworthy", "Ainge", "Abernathy", "Atkinson", "Abner", "Abella", "Agholor", "Allred", "Asola", "Abrams", "Acker", "Abrell", "Acuff", "Archer", "Asterio", "Adair", "Albright", "Adelson", "Atwood", "Aguillar", "Adler", "Arrowood", "Agnew", "Akuna", "Alcott", "Alstott", "Austin", "Algarotti", "Alvarez", "Armani", "Anderson", "Amherst", "Adkins", "Ayesa", "Argento", "Arrowood", "Andruzzi", "Abraham", "Angle", "Armstrong", "Attard", "Annenberg", "Arrhenius", "Acosta", "Antrican", "Adderley", "Atwater", "Agassi", "Apatow", "Archeletta", "Averescu", "Arrington", "Agrippa", "Aiken", "Albertson", "Alexander", "Amado", "Anders", "Armas", "Akkad", "Aoki", "Aldrich", "Almond", "Alinsky", "Agnello", "Alterio", "Atchley",  "Bynes", "Bray", "Budreau", "Byrne", "Bragg", "Banner", "Bishop", "Burris", "Boggs", "Brembilla", "Booth", "Bullard", "Booker", "Buckner", "Borden", "Breslin", "Bryant", "BIles", "Brunt", "Brager", "Brandt", "Bosa", "Bradshaw", "Brubaker", "Berry", "Brooks", "Bandini", "Bristow", "Barrick", "Biddle", "Brennan", "Brinkmann", "Benz", "Braddock", "Bright", "Berman", "Bracco", "Bartley", "Briggs", "Bonanno", "Boyle", "Beeks", "Bernthal", "Boldon", "Bowser", "Benwikere", "Bowman", "Bamberger", "Bowden", "Batch", "Blaustein", "Blow", "Boulware", "Bezos", "Boulder", "Bauer", "Ballard", "Benton", "Bixby", "Bostwick", "Biles", "Bobusic", "Belinski", "Blood", "Bisley", "Bettis", "Bensen", "Binion", "Bloch", "Blixt", "Bellisario", "Botkin", "Benoit", "BInda", "Baldwin", "Bennett", "Bourland", "Bester", "Bender", "Best", "Bald", "Bersa", "Belt", "Bourne", "Barks", "Beebe", "Banu", "Bozzelli", "Bogaerts",  "Cyrus", "Craggs", "Crisper", "Cotheran", "Curry", "Conard", "Cutler", "Coggins", "Cates", "Crisp", "Curio ", "Creed", "Costner", "Cortse", "Cunningham", "Cooper", "Cullen", "Castle", "Cugat", "Click", "Cassidy", "Crespo", "Crusher", "Cooper", "Coates", "Crowley", "Creel", "Crassus", "Cogdill", "Cross", "Crabtree", "Cranham", "Carver", "Cox", "Coltrane", "Chatwin", "Conklin", "Colt", "Coulter", "Cleveland", "Coppens", "Coolidge", "Copeland", "Celino", "Coffin", "Cena", "Conti ", "Coin", "Connelly", "Cents", "Carney", "Carmichael", "Coffey", "Carling", "Christie", "Chadwick", "Cobo", "Clay", "Capra", "Candy", "Clancy", "Chalk", "Chambers", "Callahan", "Cirque", "Cabrera-Bello", "Cherry", "Cannon", "Chung", "Cave", "Challenger", "Cobb", "Calaway", "Chalut", "Cayce", "Cahill", "Cruz", "Cohen", "Caylor", "Cagle", "Cline", "Crawford", "Cleary", "Cain", "Champ", "Cauley", "Claxton"    "Dubois", "Darby", "Draper", "Dwyer", "Dixon", "Danton", "Devereaux", "Ditka", "Dominguez", "Decker", "Dobermann", "Dunlop", "Dumont", "Dandridge", "Diamond", "Dobra ", "Dukas", "Dyer", "Decarlo", "Delpy", "Dufner", "Driver", "Dalton", "Dark", "Dawkins", "Driskel", "Derbyshire", "Davenport", "Dabney", "Dooley", "Dickerson", "Donovan", "Dallesandro", "Devlin", "Donnelly", "Day", "Daddario", "Donahue", "Denver", "Denton", "Dodge", "Dempsey", "Dahl", "Drewitt",  "Earp", "Eberstark ", "Egan", "Elder", "Eldridge", "Ellenburg", "Eslinger", "England", "Epps", "Eubanks", "Everhart", "Evert", "Eastwood", "Elway", "Eslinger", "Ellerbrock", "Edge", "Endo", "Etter", "Ebersol", "Everson", "Earwood", "Ekker", "Escobar", "Edgeworth",  "Future", "Fitzpatrick", "Fontana", "Fenner", "Furyk", "Finch", "Fullbright", "Fassbinder", "Flood", "Fong", "Fleetwood", "Fugger", "Frost", "Fsik", "Fawcett", "Fishman", "Freeze", "Fissolo", "Foley", "Fairchild", "Freeman", "Flanagan", "Freed", "Fogerty", "Foster", "Finn", "Fletcher", "Floris", "Flynn", "Fairbanks", "Fawzi ", "Finau", "Floquet ", "Fleiss", "Ferguson", "Froning", "Fitzgerald", "Fingermann", "Flagg", "Finchum", "Flair", "Ferber", "Fuller", "Farrell", "Fenton", "Fangio", "Faddis", "Ferenz", "Farley",  "Gundlach", "Gannon", "Goulding", "Greenway", "Guest", "Gillis", "Gellar", "Gaither", "Griffith", "Grubbs", "Glass", "Gotti", "Goodwin", "Grizzly", "Glover", "Grimes", "Gleason", "Gardner", "Geske", "Griffo", "Glunt", "Golden", "Gardel", "Gribble", "Grell", "Gearey", "Grooms", "Glaser", "Greer", "Geel", "Gallagher", "Glick", "Graber ", "Gore", "Gabbard", "Gelpi", "Gilardi", "Goddard", "Gabel", "Hyde", "Hood", "Hull", "Hogan", "Hitchens", "Higgins", "Hodder", "Huxx", "Hester", "Huxley", "Hess", "Hutton", "Hobgood", "Husher", "Hitchcock", "Huffman", "Herrera", "Humber", "Hobbs", "Hostetler", "Henn", "Horry", "Hightower", "Hindley", "Hitchens", "Holiday", "Holland", "Hitchcock", "Hoagland", "Hilliard", "Harvick", "Hardison", "Hickey", "Heller", "Hartman", "Halliwell", "Hughes", "Hart", "Healy", "Head", "Harper", "Hibben", "Harker", "Hatton", "Hawk", "Hardy", "Hadwin", "Hemmings", "Hembree", "Helbig", "Hardin", "Hammer", "Hammond", "Haystack", "Howell", "Hatcher", "Hamilton", "Halleck", "Hooper", "Hartsell", "Henderson", "Hale", "Hokoda", "Heers", "Homa", "Hanifin", "Most Common Last Names Around the World" ,    "Inch", "Inoki", "Ingram", "Idelson", "Irvin", "Ives", "Ishikawa", "Irons", "Irwin", "Ibach", "Ivanenko", "Ibara"    "Jurado", "Jammer", "Jagger", "Jackman", "Jishu", "Jingle", "Jessup", "Jameson", "Jett", "Jackson",  "Kulikov ", "Kellett", "Koo", "Kitt", "Keys", "Kaufman", "Kersey", "Keating", "Kotek ", "Kuchar", "Katts", "Kilmer", "King", "Kubiak", "Koker", "Kerrigan", "Kumara", "Knox", "Koufax", "Keagan", "Kestrel", "Kinder", "Koch", "Keats", "Keller", "Kessler", "Kobayashi", "Klecko", "Kicklighter", "Kincaid", "Kershaw", "Kaminsky", "Kirby", "Keene", "Kenny", "Keogh", "Kipps",   "Salvador Dali", "Salvador Dali"    "Litvak", "Lawler", "London", "Lynch", "Lacroix", "Ledford", "LeMay", "Lovejoy", "Lombardo", "Lovecraft", "Laudermilk", "Locke", "Leishman", "Leary", "Lott", "Ledger", "Lords", "Lacer", "Longwood", "Lattimore", "Laker", "Lecter", "Liston", "Londos", "Lomax", "Leaves ", "Lipman", "Lambert", "Lesnar", "Lazenby", "Lichter", "Lafferty", "Lovin", "Lucchesi", "Landis", "Lopez", "Lentz", "Murray", "Morrison", "McKay", "Merchant", "Murillo", "Mooney", "Murdock", "Matisse", "Massey", "McGee", "Minter", "Munson", "Mullard", "Mallory", "Meer ", "Mercer", "Mulder", "Malik", "Moreau ", "Metz", "Mudd", "Meilyr", "Motter", "McNamara", "Malfoy", "Moses", "Moody", "Morozov", "Mason", "Metcalf", "McGillicutty", "Montero", "Molinari", "Marsh", "Moffett", "McCabe", "Manus", "Malenko", "Mullinax", "Morrissey", "Mantooth", "Mintz", "Messi", "Mattingly", "Mannix", "Maker", "Montoya", "Marley", "McKnight", "Magnusson ", "Marino", "Maddox", "Macklin", "Mackey", "Morikowa", "Mahan", "Necessary", "Nicely", "Nejem", "Nunn", "Neiderman", "Naillon", "Nyland", "Novak", "Nygard", "Norwood", "Norris", "Namath", "Nabor", "Nash", "Noonan", "Nolan ", "Nystrom", "Niles", "Napier", "Nunley", "Nighy", "Overholt", "Ogletree", "Opilio ", "October", "Ozu", "O'Rourke", "Owusu", "Oduya", "Oaks", "Odenkirk", "Ottinger", "O'Donnell", "Orton", "Oakley", "Oswald", "Ortega", "Ogle", "Orr", "Ogden", "Onassis", "Olson", "Ollenrenshaw", "O'Leary", "O'Brien", "Oldman", "O'Bannon", "Oberman", "O'Malley", "Otto", "Oshima",    "Prado", "Prunk", "Piper", "Putnam", "Pittman", "Post", "Price", "Plunkett", "Pitcher", "Pinzer", "Punch", "Paxton", "Powers", "Previn", "Pulman", "Puller", "Peck", "Pepin", "Platt", "Powell", "Pawar", "Pinder", "Pickering", "Pollock", "Perrin", "Pell", "Pavlov", "Patterson", "Perabo", "Patnick", "Panera", "Prescott", "Portis", "Perkins", "Palmer", "Paisley", "Pladino", "Pope", "Posada", "Pointer", "Poston", "Porter", "Quinn", "Quan", "Quaice", "Quaid", "Quirico", "Quarters", "Quimby", "Qua", "Quivers", "Quall", "Quick", "Qugg", "Quint", "Quintero",  "Leonardo da Vinci", "Leonardo da Vinci"    "Rudd", "Ripperton", "Renfro", "Rifkin", "Rand", "Root", "Rhodes", "Rowland", "Ramos", "Ryan", "Rafus", "Radiguet", "Ripley", "Ruster", "Rush", "Race", "Rooney", "Russo", "Rude", "Roland", "Reader", "Renshaw", "Rossi", "Riddle", "Ripa", "Richter", "Rosenberg", "Romo", "Ramirez", "Reagan", "Rainwater", "Romirez", "Riker", "Riggs", "Redman", "Reinhart", "Redgrave", "Rafferty", "Rigby", "Roman", "Reece",  "Sutton", "Swift", "Sorrow", "Spinks", "Suggs", "Seagate", "Story", "Soo", "Sullivan", "Sykes", "Skirth", "Silver", "Small", "Stoneking", "Sweeney", "Surrett", "Swiatek", "Sloane", "Stapleton", "Seibert", "Stroud", "Strode", "Stockton", "Scardino", "Spacek", "Spieth", "Stitchen", "Stiner", "Soria", "Saxon", "Shields", "Stelly", "Steele", "Standifer", "Shock", "Simerly", "Swafford", "Stamper", "Sotelo", "Smoker", "Skinner", "Shaver", "Shivers", "Savoy", "Small", "Skills", "Sinclair", "Savage", "Sereno", "Sasai", "Silverman", "Silva", "Shippen", "Sasaki", "Sands", "Shute", "Sabanthia", "Sheehan", "Sarkis", "Shea", "Santos", "Snedeker", "Stubbings", "Streelman", "Skaggs", "Spears", "Dave Chappelle", "Dave Chappelle"    "Twigg", "Tracy", "Truth", "Tillerson", "Thorisdottir ", "Tooms", "Tripper", "Tway", "Taymor", "Tamlin", "Toller", "Tussac", "Turpin", "Tippett", "Tabrizi", "Tanner", "Tuco", "Trumbo", "Tucker", "Theo", "Thain", "Trapp", "Trumbald ", "Trench", "Terrella", "Tait", "Tanaka", "Tapp", "Tepper", "Trainor", "Turner", "Teague", "Templeton", "Temple", "Teach", "Tam"    "Udder", "Uso", "Uceda", "Umoh", "Underhill", "Uplinger", "Ulett", "Urtz", "Unger", "Vroman", "Vess", "Voight", "Vegas", "Vasher", "Vandal", "Vader", "Volek", "Vega", "Vestine", "Vaccaro", "Vickers",  "Witt", "Wolownik", "Winding", "Wooten ", "Whitner", "Winslow", "Winchell", "Winters", "Walsh", "Whalen", "Watson", "Wooster", "Woodson", "Winthrop", "Wall", "Wight", "Webb", "Woodard", "Wixx", "Wong", "Whesker", "Wolfenstein", "Winchester", "Wire", "Wolf", "Wheeler", "Warrick", "Walcott", "Wilde", "Wexler", "Wells", "Weeks", "Wainright", "Wallace", "Weaver", "Wagner", "Wadd", "Withers", "Whitby", "Woodland", "Woody", "Xavier", "Xanders", "Xang", "Ximinez", "Xie", "Xenakis", "Xu", "Xiang", "Xuxa",  "Yearwood", "Yellen", "Yaeger", "Yankovich", "Yamaguchi", "Yarborough", "Youngblood", "Yanetta", "Yadao", "Yale", "Yasumoto", "Yates", "Younger", "Yoakum", "York", "Yount",  "Zuckerberg", "Zeck", "Zavaroni", "Zeller", "Zipser", "Zedillo", "Zook", "Zeigler", "Zimmerman", "Zeagler", "Zale", "Zasso", "Zant", "Zappa", "Zapf", "Zahn", "Zabinski", "Zade", "Zabik", "Zader", "Zukoff", "Zullo", "Zmich", "Zoller"]
            race_list = ["Human","Elf","Dwarf","Gnome","Troll","Elemental","Orc","Angel","Demon","Vampire","Shadow walker","Deity","Xendorian","Archangel","Archdemon","Undead","Drow","Ghost","Dragon","Werewolf","Fairy","Dark Fairy","Pixie","Shifter","Merperson","Sentient animal","Goblin","Halfling","Kitsune","Centaur","Satyr","Dryad","Nightmare","Incarnate","Death walker","Yeti","Wendigo","Monster","High Elf","Wood Elf","Dark Elf","Manticore","Gryphon","Phoenix","Ent"]
            height_min_feet = 1
            height_max_feet = 8
            height_inches_max = 11
            weight_min = 50
            weight_max = 400
            age_min = 18
            age_max = 2000
            occupation_list = []
            occupation_list = ["Warrior","Knight","Hunter","Blacksmith","Noble","Royalty","Slave","Mercenary","Caster","Mage","Wizard","Warlock","Protector","Healer","Medium","Psychic","Assassin","Swordsman","Thief","Cobbler","Potion maker","Preacher","Priest","Paladin","Witch","Warlock","Sorcerer","Servant","Escort","Prostitute","Solider","Bartender","Merchant","Sailor","Pirate","Archer","Guard","Slayer","Alchemist","Apothecary","Shopkeeper","Trader","Wizard","Fighter","Teacher","Physician","Philosopher","Farmer","Shepherd","Harbinger","Messenger","Horserider","Chef","Night watch","None","Beggar","Researcher","Advisor","Judge","Executioner","Commander","Captain","Fisher","Ranchhand","Druid"]
            gender_list = ["Male","Female","Non-binary","Genderfluid"]
            origin_list = ["Unknown","Earth","Rhydin","Offworld"]
            powers_list = ["Psychic","Lightning","Light","Healing","Destruction","Darkness","Telepathy","Psychokinesis","Flight","Storms","Water","Air","Wind","Earth","Fire","Talking to the dead","Plane-walking","Illusion","Glamor","Holy","White Magic","Black Magic","Seduction","Speed","Superhuman strength","Immortality","Energy manipulation","Reality warping","Spaceflight","Cloaking","Shadow"]
            strengths_list = ["Melee combat","Magic","Physical strength","Physical speed","Highly intelligent","Expert swordfighter","Martial arts","Strategic","Charismatic","Highly perceptive","Expert with firearms","Expert archer","Resistant to magic"]
            weaknesses_list = ["Black magic","Light","Holy power","Evil power","Easily seduced","Gullible","Socially mnanipulatable","Low intelligence","Fire","Water","Lightning","Darkness","Shadow","Astral attacks","Weak physically","Lost immortality","Reduced powers","Trauma in past","Phobias","Anxiety","Poor training","Little magical capacity"]
            personality_list = ["Warm","Cold","Aloof","Caring","Gregarious","Affable","Talkative","Strong, silent type","Brash","Boisterous","Lazy","Shy","Fearful","Happy-go-lucky","Perky","Perverted","Sociopathic","Formal","Casual","Creative","Nice","Mean","Rude","Kind","Gentle","Harsh","Asexual","Wild in bed","Stoic","Charismatic","Charming","Romantic","Detached","Depressed","Worrywart","Troubled by their past","Carries a grudge","Loving","Hateful","Spiteful","Angry","Short fuse","Patient","Passionate","Empty"]
            skills_list = ["Archery","Swordplay","Reading","Writing","Science","Technology","Music","Telling jokes","Lying when needed","Magic","Alchemy","Healing","Medicine","Potions","Elixirs","Chemistry","Knowledge of the beyond","Master illusionist","Computers","Mixing drinks","Telling stories","Inspiring others","Leading","Fighting","Organizing","Art","Scuplting","Crafts","Metalworking","Buidling structures","Tinkering"]
            
            gender = random.choice(gender_list)
            if gender == 'Male':
                first_name = random.choice(male_first_name_list)
            elif gender == 'Female':
                first_name = random.choice(female_first_name_list)
            else:
                first_name = random.choice(male_first_name_list + female_first_name_list)
            last_name = random.choice(last_name_list)
            
            race = random.choice(race_list)
            
            occupation = random.choice(occupation_list)
            
            if race == 'Human':
                age = random.randint(18,100)
            else:
                age = random.randint(age_min, age_max)
            
            origin = random.choice(origin_list)
            height_feet = random.randint(height_min_feet, height_max_feet)
            height_inches = random.randint(0,11)
            weight = random.randint(weight_min, weight_max)
            
            number_of_strengths = random.randint(1,5)
            strengths = ""
            for x in range(0,number_of_strengths):
                strengths = strengths + random.choice(strengths_list) + ", "
            number_of_weaknesses = random.randint(1,5)
            weaknesses = ""
            for x in range(0,number_of_weaknesses):
                weaknesses = weaknesses  + random.choice(weaknesses_list) + ", " 
            powers = ""
            
            number_of_powers = random.randint(1,3)
            for x in range(0,number_of_powers):
                powers = powers  + random.choice(powers_list) + ", " 
            number_of_skills = random.randint(1,5)
            skills = ""
            for x in range(0,number_of_skills):
                skills = skills  + random.choice(skills_list) + ", "     
            personality = ""
            number_of_personality = random.randint(2,6)
            for x in range(0,number_of_personality):
                personality = personality  + random.choice(personality_list) + ", "                     
                
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newrandomchar'
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterName","Age","Race","Gender","Height","Weight","Playedby","Origin","Occupation","PictureLink","Strengths","Weaknesses","Powers","Skills","Personality"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [first_name + " " + last_name, str(age), race, gender, str(height_feet) + "'" + str(height_inches) + r"\"", str(weight) + " lbs", "None", origin, occupation, "None", strengths, weaknesses, powers, skills, personality] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            
            counter = 0
            response = "**RANDOM CHARACTER INFORMATION**\n\n"
            for field in dm_tracker[message.author.id]["fieldlist"]:
                response = response + "**" + field + ":** " + dm_tracker[message.author.id]["fielddict"][counter] + "\n"
                counter = counter + 1
            await reply_message(message, response)
            
            await direct_message(message, "Would you like to add this character to the applicant characters list? Respond **YES** to apply, anything else to discard.")
                
        elif command == 'givestatpoints':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must have the GM role to give stat points.")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'givestatpoints'
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterId","Points"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "CharacterProfiles","CharacterName")
            response = "Please choose a character from the below to give available points to:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please see your DMs for instructions on how to give stat points, <@" + str(message.author.id) + ">.")
            
        elif (command == 'getcharprofile'):
            records = await select_sql("""SELECT Fields FROM CustomProfiles WHERE ServerId=%s;""",(str(message.guild.id),))
            if records:
                field_dict = { }
                for row in records:
                    fields = row[0].split(',')
                create_custom_profile = "SELECT " 
                get_display_name = "SELECT "
                create_tuple = ()
                for key in fields:
                    if key:
                        get_display_name = get_display_name + key + ", "
                        create_custom_profile = create_custom_profile + "IFNULL(" + key + ",'None'), "
                create_custom_profile = re.sub(r", $", "", create_custom_profile) + " FROM " + re.sub(r"[^A-Za-z0-9]","",message.guild.name) + str(message.guild.id) + " WHERE Name=%s;"
                get_display_name = re.sub(r", $", "", get_display_name) + " FROM " + re.sub(r"[^A-Za-z0-9]","",message.guild.name) + str(message.guild.id) + " WHERE Id=1;"
                await log_message("SQL: " + create_custom_profile)
                create_tuple = create_tuple + (parsed_string,)
                
                records1 = await select_sql(create_custom_profile, create_tuple)
                records2 = await select_sql(get_display_name)
                if not records1:
                    await reply_message(message, "Character not found!")
                    return
                response = "**CHARACTER PROFILE**\n\n**Name:** " + parsed_string + "\n"
                counter = 0
                for row in records1:
                    for field in fields:
                        if counter > len(records2[0]) - 1:
                            break;
                        response = response + "**" + records2[0][counter] + ":** " + row[counter] + "\n"
                        counter = counter + 1
                await reply_message(message, response)
            else:    
                char_name = parsed_string
                
                get_character_profile = """SELECT CharacterName,IFNULL(Age,' '),IFNULL(Race,' '), IFNULL(Gender,' '), IFNULL(Height,' '), IFNULL(Weight,' '), IFNULL(PlayedBy,' '), IFNULL(Origin,' '), IFNULL(Occupation,' '), UserId,Attack,Defense,MagicAttack,Health,Mana,Level,Experience,Stamina,Agility,Intellect,Charisma, IFNULL(Biography,' '), IFNULL(Currency,' '), IFNULL(Description,' '), IFNULL(Personality,' '), IFNULL(Powers,' '), IFNULL(Strengths,' '), IFNULL(Weaknesses,' '), IFNULL(Skills,' '), IFNULL(PictureLink,' ') FROM CharacterProfiles WHERE CharacterName=%s  AND ServerId=%s;"""
                char_tuple = (char_name, str(message.guild.id))
                
                records = await select_sql(get_character_profile, char_tuple)
                if len(records) < 1:
                    await reply_message(message, "No character found by that name!")
                    return
                for row in records:
                    response = "***CHARACTER PROFILE***\n\n**Mun:** <@" + str(row[9]) + ">\n**Name:** " + row[0] + "\n**Age:** " + str(row[1]) + "\n**Race:** "+ row[2] + "\n**Gender:** " +row[3] + "\n**Height:** " + row[4] +  "\n**Weight:** " + row[5] +  "\n**Played by:** " + row[6] + "\n**Origin:** " + row[7] + "\n**Occupation:** " + row[8] + "\n\n**STATS**\n\n**Health:** " + str(row[13]) + "\n**Mana:** " + str(row[14]) + "\n**Attack:** " + str(row[10]) + "\n**Defense:** " + str(row[11]) + "\n**Magic Attack Power:** " + str(row[12]) + "\n**Level:** " + str(row[15]) + "\n**Experience:** " + str(row[16]) + "\n**Stamina:** " + str(row[17]) + "\n**Agility:** " + str(row[18]) + "\n**Intellect:** " + str(row[19]) + "\n**Charisma:** " + str(row[20]) + "\n**Currency:** " + str(row[22])+  "\n\n**ADDITIONAL INFORMATION**\n\n**Biography:** " + row[21] + "\n**Description:**" + row[23] + "\n**Personality:** " + row[24] + "\n**Powers:** " + row[25] + "\n**Strengths:** " + row[26] + "\n**Weaknesses:** " + row[27] + "\n**Skills:** " + row[28] + "\n\n**PICTURE**\n\n" + row[29] + "\n"
                await reply_message(message, response)
        elif command == 'editchar':
            user_id = message.author.id
            server_id = message.guild.id
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must have the player role to edit a character.")
                return
                
            char_name = parsed_string
            current_fields = await select_sql("""SELECT Age,Race,Gender,Height,Weight,Playedby,Origin,Occupation,PictureLink FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""", (str(message.guild.id), char_name))
            if not current_fields:
                await reply_message(message, "No character found by that name!")
                return
            records = await select_sql("""SELECT UserId FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s """,(str(message.guild.id), char_name))
            for row in records:
                char_user_id = int(row[0])
            if char_user_id != message.author.id:
                await reply_message(message, "This isn't your character!")
                return   
            for row in current_fields:
                fields = row
             
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterName","Age","Race","Gender","Height","Weight","Playedby","Origin","Occupation","PictureLink"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["fielddict"].append(parsed_string)
            dm_tracker[message.author.id]["currentcommand"] = 'editchar'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(fields[counter])
                counter = counter + 1
                if counter > len(dm_tracker[message.author.id]["fieldlist"]) - 2:
                    break
            
            await reply_message(message, "Please check your DMs for instructions on how to edit a character, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested to edit the character **" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the character will be updated!\nThe first field is **" + dm_tracker[message.author.id]["fieldlist"][0] + "** and its current value is **" + dm_tracker[message.author.id]["fielddict"][0] + "**.")
            

        elif command == 'listmychars':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must have the player role to list characters.")
                return
            records = await select_sql("""SELECT CharacterName,Level FROM CharacterProfiles WHERE ServerId=%s AND UserId=%s;""", (str(message.guild.id),str(message.author.id)))
            if not records:
                await reply_message(message, "You don't have any characters! Use =newchar to create a character!")
                return
            response = "**Characters for " + message.author.name + ":**\n\n" 
            for row in records:
                response = response + row[0] + " Level: " + str(row[1]) + "\n"
            await reply_message(message, response)
        elif command == 'getcharskills':
            m = re.search(r"(?P<name>.+) (?P<lastname>.+)", parsed_string)
            if not m:
                await reply_message(message, "No character name specified!")
                return
            char_name = parsed_string

            response = "***CHARACTER SKILLS***\n\n**Character Name:** " + char_name + "\n\n**MAGIC SKILLS**\n\n"
            records = await select_sql("""SELECT Id FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""",(str(message.guild.id), char_name))
            if not records:
                await reply_message(message, "No character found with that name!")
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
            await reply_message(message, response)
        elif (command == 'editstats'):
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to modify character statistics!")
                return
            user_id = message.author.id
            server_id = message.guild.id

                
            char_name = parsed_string
            current_fields = await select_sql("""SELECT Attack,Defense,MagicAttack,Health,Mana,Level,Experience,Stamina,Agility,Intellect,Charisma FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""", (str(message.guild.id), char_name))
            if not current_fields:
                await reply_message(message, "No character found by that name!")
                return
            records = await select_sql("""SELECT UserId FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s """,(str(message.guild.id), char_name))
            for row in records:
                char_user_id = int(row[0])
             
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Attack","Defense","MagicAttack","Health","Mana","Level","Experience","Stamina","Agility","Intellect","Charisma"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'editstats'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(current_fields[0][counter])
                counter = counter + 1
            
            await reply_message(message, "Please check your DMs for instructions on how to edit character stats, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested to edit the character statistics of **" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the character will be updated!\nThe first field is **" + dm_tracker[message.author.id]["fieldlist"][0] + "** and its current value is **" + str(dm_tracker[message.author.id]["fielddict"][0]) + "**.")                

            
        elif command == 'setcharbio':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be member of the player role to add a biography!")
                return

            name_re = re.compile(r"Name: (?P<name>.+)")
            bio_re = re.compile(r"Biography: (?P<bio>.+)", re.S | re.MULTILINE)
            m = name_re.search(parsed_string)
            if m:
                char_name = m.group('name')

            m = bio_re.search(parsed_string)
            if m:
                bio = m.group('bio')
            records = await select_sql("""SELECT UserId FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""",(str(message.guild.id), char_name))
            for row in records:
                user_id = row[0]
            if int(user_id) != message.author.id or not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "This is not your character! Please only add a biography to your character!")
                return
            update_bio = """UPDATE CharacterProfiles SET Biography=%s WHERE ServerId=%s AND CharacterName=%s ;"""
            update_bio_tuple = (bio, str(message.guild.id), char_name)
            result = await commit_sql(update_bio, update_bio_tuple)
            if result:
                await reply_message(message, "Biography of character " + char_name + " updated successfully.")
            else:
                await reply_message(message, "Database error!")
        elif command == 'setcharstrengths':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be member of the player role to add a biography!")
                return        
            name_re = re.compile(r"Name: (?P<name>.+)")
            strengths_re = re.compile(r"Strengths: (?P<strengths>.+)", re.S | re.MULTILINE)
            m = name_re.search(parsed_string)
            if m:
                char_name = m.group('name')
            m = strengths_re.search(parsed_string)            
            if m:
                strengths = m.group('strengths')
            records = await select_sql("""SELECT UserId FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""",(str(message.guild.id), char_name))
            for row in records:
                user_id = row[0]
            if int(user_id) != message.author.id or not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "This is not your character! Please only add strengths to your character!")
                return                
            update_strengths = """UPDATE CharacterProfiles SET Strengths=%s WHERE ServerId=%s AND CharacterName=%s ;"""
            update_strengths_tuple = (strengths, str(message.guild.id), char_name)
            result = await commit_sql(update_strengths, update_strengths_tuple)
            if result:
                await reply_message(message, "Strengths of character " + char_name + " updated successfully.")
            else:
                await reply_message(message, "Database error!")
        elif command == 'setcharweaknesses':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be member of the player role to add a biography!")
                return        
            name_re = re.compile(r"Name: (?P<name>.+)")
            weaknesses_re = re.compile(r"Weaknesses: (?P<weaknesses>.+)", re.S | re.MULTILINE)
            m = name_re.search(parsed_string)
            if m:
                char_name = m.group('name')
                
            m = weaknesses_re.search(parsed_string)
            if m:
                weaknesses = m.group('weaknesses')
            records = await select_sql("""SELECT UserId FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""",(str(message.guild.id), char_name))
            for row in records:
                user_id = row[0]
            if int(user_id) != message.author.id or not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "This is not your character! Please only add weaknesses to your character!")
                return                 
            update_weaknesses = """UPDATE CharacterProfiles SET Weaknesses=%s WHERE ServerId=%s AND CharacterName=%s ;"""
            update_weaknesses_tuple = (weaknesses, str(message.guild.id), char_name)
            result = await commit_sql(update_weaknesses, update_weaknesses_tuple)
            if result:
                await reply_message(message, "weaknesses of character " + char_name + " updated successfully.")
            else:
                await reply_message(message, "Database error!")
        elif command == 'setcharpowers':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be member of the player role to add a biography!")
                return        
            name_re = re.compile(r"Name: (?P<name>.+)")
            powers_re = re.compile(r"Powers: (?P<powers>.+)", re.S | re.MULTILINE)
            m = name_re.search(parsed_string)
            if m:
                char_name = m.group('name')
                
            m = powers_re.search(parsed_string)
            if m:
                powers = m.group('powers')
            records = await select_sql("""SELECT UserId FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""",(str(message.guild.id), char_name))
            for row in records:
                user_id = row[0]
            if int(user_id) != message.author.id or not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "This is not your character! Please only add powers to your character!")
                return                 
            update_powers = """UPDATE CharacterProfiles SET Powers=%s WHERE ServerId=%s AND CharacterName=%s ;"""
            update_powers_tuple = (powers, str(message.guild.id), char_name)
            result = await commit_sql(update_powers, update_powers_tuple)
            if result:
                await reply_message(message, "powers of character " + char_name + " updated successfully.")
            else:
                await reply_message(message, "Database error!")
        elif command == 'setcharskills':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be member of the player role to add a biography!")
                return        
            name_re = re.compile(r"Name: (?P<name>.+)")
            skills_re = re.compile(r"Skills: (?P<skills>.+)", re.S | re.MULTILINE)
            m = name_re.search(parsed_string)
            if m:
                char_name = m.group('name')
                
            m = skills_re.search(parsed_string)
            if m:
                skills = m.group('skills')
            records = await select_sql("""SELECT UserId FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""",(str(message.guild.id), char_name))
            for row in records:
                user_id = row[0]
            if int(user_id) != message.author.id or not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "This is not your character! Please only add skills to your character!")
                return                 
            update_skills = """UPDATE CharacterProfiles SET Skills=%s WHERE ServerId=%s AND CharacterName=%s ;"""
            update_skills_tuple = (skills, str(message.guild.id), char_name)
            result = await commit_sql(update_skills, update_skills_tuple)
            if result:
                await reply_message(message, "skills of character " + char_name + " updated successfully.")
            else:
                await reply_message(message, "Database error!")
        elif command == 'setcharpersonality':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be member of the player role to add a biography!")
                return        
            name_re = re.compile(r"Name: (?P<name>.+)")
            personality_re = re.compile(r"Personality: (?P<personality>.+)", re.S | re.MULTILINE)
            m = name_re.search(parsed_string)
            if m:
                char_name = m.group('name')
                
            m = personality_re.search(parsed_string)
            if m:
                personality = m.group('personality')
            records = await select_sql("""SELECT UserId FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""",(str(message.guild.id), char_name))
            for row in records:
                user_id = row[0]
            if int(user_id) != message.author.id or not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "This is not your character! Please only add personality to your character!")
                return                 
            update_personality = """UPDATE CharacterProfiles SET Personality=%s WHERE ServerId=%s AND CharacterName=%s ;"""
            update_personality_tuple = (personality, str(message.guild.id), char_name)
            result = await commit_sql(update_personality, update_personality_tuple)
            if result:
                await reply_message(message, "personality of character " + char_name + " updated successfully.")
            else:
                await reply_message(message, "Database error!")
        elif command == 'setchardescription':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be member of the player role to add a biography!")
                return        
            name_re = re.compile(r"Name: (?P<name>.+)")
            description_re = re.compile(r"Description: (?P<description>.+)", re.S | re.MULTILINE)
            m = name_re.search(parsed_string)
            if m:
                char_name = m.group('name')
                
            else:
                await reply_message(message, "No character name specified!")
                return
            m = description_re.search(parsed_string)
            
            if m:
                description = m.group('description')
            else:
                await reply_message(message, "No description specified!")
                return
            records = await select_sql("""SELECT UserId FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""",(str(message.guild.id), char_name))
            for row in records:
                user_id = row[0]
            if int(user_id) != message.author.id or not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "This is not your character! Please only add strengths to your character!")
                return                 
            update_description = """UPDATE CharacterProfiles SET Description=%s WHERE ServerId=%s AND CharacterName=%s ;"""
            update_description_tuple = (description, str(message.guild.id), char_name)
            result = await commit_sql(update_description, update_description_tuple)
            if result:
                await reply_message(message, "description of character " + char_name + " updated successfully.")
            else:
                await reply_message(message, "Database error!")
        elif command == 'deletechar':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be member of the player role to delete a character!")
                return
                
            if not parsed_string:
                await reply_message(message, "No character specified!")
                return
                
            char_name = parsed_string
                
            records = await select_sql("""SELECT UserId,Id FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""", (str(message.guild.id), char_name))
            if not records:
                await reply_message(message, "That character does not exist!")
                return
            for row in records:
                user_id = int(row[0])
                char_id = row[1]
            if user_id != message.author.id:
                await reply_message(message, "You can't delete someone else's character! I'm telling! Hey <@" + str(guild_settings[message.guild.id]["AdminRole"]) + "> !!")
                return
            result = await commit_sql("""DELETE FROM CharacterProfiles WHERE Id=%s;""",(char_id,))
            if result:
                await reply_message(message, "Character " + char_name + " deleted from server!")
            else:
                await reply_message(message, "Database error!")
        
        elif command == 'setalt':
            if not role_check(guild_settings[message.guild.id]["NPCRole"], message.author):
                await reply_message(message, "You must be a member of the NPC role to create Alts!")
                return
            if not parsed_string:
                await reply_message(message, "No Alt shortcut specified!")
                return
            alt_aliases[message.guild.id][message.author.id][message.channel.id] = parsed_string
            await reply_message(message, "User <@" + str(message.author.id) + "> set alias to " + parsed_string + " in channel " + message.channel.name + ".")
        elif command == 'unsetalt':
            if not role_check(guild_settings[message.guild.id]["NPCRole"], message.author):
                await reply_message(message, "You must be a member of the NPC role to create Alts!")
                return
            alt_aliases[message.guild.id][message.author.id][message.channel.id] = ""
            await reply_message(message, "User <@" + str(message.author.id) + "> cleared alias in channel " + message.channel.name + ".")            
        elif command == 'newalt':
            if not role_check(guild_settings[message.guild.id]["NPCRole"], message.author):
                await reply_message(message, "You must be a member of the NPC role to create Alts!")
                return
            users_allowed = message.mentions
            if not users_allowed:
                await reply_message(message, "No users allowed to use the Alt specified!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newalt'
            dm_tracker[message.author.id]["fieldlist"] = ["CharName","Shortcut","PictureLink"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = message.mentions
            
            await reply_message(message, "Please check your DMs for instructions on how to create a new Alt, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested a new Alt! Please type in the response the **name of the character**, and then enter each field as a reply to the DMs. When you have filled out all fields, the character will be created!")
        elif command == 'newnpc':
            if not role_check(guild_settings[message.guild.id]["NPCRole"], message.author):
                await reply_message(message, "You must be a member of the NPC role to create NPCs!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newnpc'
            dm_tracker[message.author.id]["fieldlist"] = ["CharName","Shortcut","PictureLink"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            
            await reply_message(message, "Please check your DMs for instructions on how to create a new NPC, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested a new NPC! Please type in the response the **name of the character**, and then enter each field as a reply to the DMs. When you have filled out all fields, the character will be created!")
        elif command == 'pause':
            await post_webhook(message.channel, "Narrator", "--scene paused--", narrator_url)
            await message.delete()
        elif command == 'unpause':
            await post_webhook(message.channel, "Narrator", "--scene resumed--", narrator_url)
            await message.delete()
        elif command == 'newscene':
            await post_webhook(message.channel, "Narrator", "--new scene--", narrator_url)
            await message.delete()
        elif command == 'endscene':
            await post_webhook(message.channel, "Narrator", "--end scene--", narrator_url)
            await message.delete()
        elif command =='postnarr':
            await post_webhook(message.channel, "Narrator", parsed_string, narrator_url)    
            await message.delete()            
        elif command == 'setnarratorurl':
            narrator_url = message.attachments[0].url
            await reply_message(message, "Set narrator to " + narrator_url)
        elif command == 'postnpc':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to post as NonPlayerCharacters!")
                return        
            shortcut = command_string[1]
            parsed_string = message.content.replace("=postnpc ","").replace(shortcut, "")
            
            if not shortcut:
                await reply_message (message, "No NPC specified!")
                return
            get_npc = """SELECT CharName, PictureLink FROM NonPlayerCharacters WHERE ServerId=%s AND Shortcut=%s;"""
            npc_tuple = (str(message.guild.id), shortcut)
            records = await select_sql(get_npc, npc_tuple)
            for row in records:
                response = parsed_string
                current_pfp = await client.user.avatar_url.read()
                

                current_name = message.guild.me.name
#                await message.guild.me.edit(nick=row[1])
                URL = row[1]
                #pfp = requests.get(url = URL)

#                await client.user.edit(avatar=pfp)
 #               await reply_message(message, response)
                temp_webhook = await message.channel.create_webhook(name='Chara-Tron')
                await temp_webhook.send(content=response, username=row[0], avatar_url=URL)
                await message.delete()
                await temp_webhook.delete()
#                await client.user.edit(avatar=current_pfp)
#                await message.guild.me.edit(nick=current_name)
                
        elif command == 'deletenpc':
            if not role_check(guild_settings[message.guild.id]["NPCRole"], message.author):
                await reply_message(message, "You must be a member of the NPC role to delete NonPlayerCharacters!")
                return        
            if not parsed_string:
                await reply_message(message, "No NPC name specified!")
                return
            result = await commit_sql("""DELETE FROM NonPlayerCharacters WHERE ServerId=%s AND CharName=%s""", (str(message.guild.id),parsed_string))
            if result:
                await reply_message(message, "NPC " + parsed_string + " deleted.")
            else:
                await reply_message(message, "Database error!")
        elif command == 'editnpc':
            if not role_check(guild_settings[message.guild.id]["NPCRole"], message.author):
                await reply_message(message, "You must be a member of the NPC role to edit NonPlayerCharacters!")
                return
            users_allowed = message.mentions
            if not users_allowed:
                await reply_message(message, "No users allowed to use the NPC specified!")
                return
            records = await select_sql("""SELECT CharName,PictureLink,Shortcut FROM NonPlayerCharacters WHERE ServerId=%s AND CharName=%s;""",(str(message.guild.id),parsed_string))
            if not records:
                await reply_message(message, "No NPC found with that name!")
                return
            for row in records:
                fields = row
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'editnpc'
            dm_tracker[message.author.id]["fieldlist"] = ["CharName","PictureLink","Shortcut"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 1
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = message.mentions
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(fields[counter])
                counter = counter + 1
                if counter > len(dm_tracker[message.author.id]["fieldlist"]) - 2:
                    break           
            await reply_message(message, "Please check your DMs for instructions on how to edit a NPC, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested to edit NPC! Please type in the response the ID of the character, and then enter each field as a reply to the DMs. When you have filled out all fields, the NPC will be updated!")        
        elif command == 'postalt':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to post as Alts!")
                return        
            shortcut = command_string[1]
            parsed_string = message.content.replace("=postalt ","").replace(shortcut, "")
            
            if not shortcut:
                await reply_message (message, "No Alt specified!")
                return
            get_alt = """SELECT UsersAllowed, CharName, PictureLink FROM Alts WHERE ServerId=%s AND Shortcut=%s;"""
            alt_tuple = (str(message.guild.id), shortcut)
            records = await select_sql(get_alt, alt_tuple)
            for row in records:
                if str(message.author.id) not in row[0]:
                    await reply_message(message, "<@" + str(message.author.id) + "> is not allowed to use Alt " + row[1] + "!")
                    return
                response = parsed_string
                current_pfp = await client.user.avatar_url.read()
                

                current_name = message.guild.me.name
#                await message.guild.me.edit(nick=row[1])
                URL = row[2]
                #pfp = requests.get(url = URL)

#                await client.user.edit(avatar=pfp)
 #               await reply_message(message, response)
                temp_webhook = await message.channel.create_webhook(name='Chara-Tron')
                await temp_webhook.send(content=response, username=row[1], avatar_url=URL)
                await message.delete()
                await temp_webhook.delete()
#                await client.user.edit(avatar=current_pfp)
#                await message.guild.me.edit(nick=current_name)
                
        elif command == 'deletealt':
            if not role_check(guild_settings[message.guild.id]["NPCRole"], message.author):
                await reply_message(message, "You must be a member of the NPC role to delete Alts!")
                return        
            if not parsed_string:
                await reply_message(message, "No Alt name specified!")
                return
            result = await commit_sql("""DELETE FROM Alts WHERE ServerId=%s AND CharName=%s""", (str(message.guild.id),parsed_string))
            if result:
                await reply_message(message, "Alt " + parsed_string + " deleted.")
            else:
                await reply_message(message, "Database error!")
        elif command == 'editalt':
            if not role_check(guild_settings[message.guild.id]["NPCRole"], message.author):
                await reply_message(message, "You must be a member of the NPC role to edit Alts!")
                return
            users_allowed = message.mentions
            if not users_allowed:
                await reply_message(message, "No users allowed to use the Alt specified!")
                return
            records = await select_sql("""SELECT CharName,PictureLink,Shortcut FROM Alts WHERE ServerId=%s AND CharName=%s;""",(str(message.guild.id),parsed_string))
            if not records:
                await reply_message(message, "No Alt found with that name!")
                return
            for row in records:
                fields = row
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'editalt'
            dm_tracker[message.author.id]["fieldlist"] = ["CharName","PictureLink","Shortcut"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 1
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = message.mentions
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(fields[counter])
                counter = counter + 1
                if counter > len(dm_tracker[message.author.id]["fieldlist"]) - 2:
                    break           
            await reply_message(message, "Please check your DMs for instructions on how to edit a Alt, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested to edit Alt! Please type in the response the ID of the character, and then enter each field as a reply to the DMs. When you have filled out all fields, the Alt will be updated!")
                

        elif command == 'setupalt':
            if not role_check(guild_settings[message.guild.id]["NPCRole"], message.author):
                await reply_message(message, "You must be a member of the NPC role to create webhooks for Alts!")
                return        
            webhook[message.channel.id] = await message.channel.create_webhook(name='Chara-Tron')
            if webhook[message.channel.id]:
                await reply_message(message, "Webhook for this channel set up successfully!")
            else:
                await reply_message(message, "Problem creating webhook!")
        elif command == 'listalts':
            response = "***CURRENT Alt LIST***\n\n__Alt Name__ - __Allowed Users__ __Shortcut__\n"
            records = await select_sql("""SELECT CharName,UsersAllowed,Shortcut FROM Alts WHERE ServerId=%s;""", (str(message.guild.id),))
            name_re = re.compile(r"Member id=.*?name='(.+?)'")

            for row in records:
                m = name_re.findall(row[1])
                if m:
                    names = re.sub(r"[\[\]']","",str(m))
                response = response + row[0] + " - " + str(names) + " - " + row[2] + "\n"
            await reply_message(message, response)
        elif command == 'listnpcs':
            response = "***CURRENT Alt LIST***\n\n__Alt Name__  __Shortcut__\n"
            records = await select_sql("""SELECT CharName,Shortcut FROM NonPlayerCharacters WHERE ServerId=%s;""", (str(message.guild.id),))
            name_re = re.compile(r"Member id=.*?name='(.+?)'")

            for row in records:
                response = response + row[0] + " - " + row[1] + "\n"
            await reply_message(message, response)            
        elif command == 'newspell':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to create new spells!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newspell'
            dm_tracker[message.author.id]["fieldlist"] = ["SpellName","Element","ManaCost","MinimumLevel","DamageMultiplier","Description","PictureLink"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            
            await reply_message(message, "Please check your DMs for instructions on how to create a new spell, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested a new spell! Please type in the response the **spell name**, and then enter each field as a reply to the DMs. When you have filled out all fields, the spell will be created!")

            

        elif command == 'newmelee':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to create new melee attacks!")
                return
                
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newmelee'
            dm_tracker[message.author.id]["fieldlist"] = ["AttackName","StaminaCost","MinimumLevel","DamageMultiplier","Description","PictureLink"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            
            await reply_message(message, "Please check your DMs for instructions on how to create a new melee attack, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested a new melee attack! Please type in the response the **attack name**, and then enter each field as a reply to the DMs. When you have filled out all fields, the melee attack will be created!")            
        elif command == 'newvendor':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to create new vendors!")
                return
                
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newvendor'
            dm_tracker[message.author.id]["fieldlist"] = ["VendorName","ItemList","PictureLink"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            
            await reply_message(message, "Please check your DMs for instructions on how to create a new vendor, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested a new vendor! Please type in the response the **vendor name**, and then enter each field as a reply to the DMs. When you have filled out all fields, the vendor will be created!")
        elif command == 'addvendoritem':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to edit vendors!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'addvendoritem'
            dm_tracker[message.author.id]["fieldlist"] = ["VendorName","ItemList"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "Vendors", "VendorName")
            response = "Please select a vendor from the below list to edit:\n\n" + menu
            await reply_message(message, "Please check your DMs for instructions on how to add items to a vendor, <@" + str(message.author.id) + ">.")
            await direct_message(message, response)
        elif command == 'deletevendor':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to delete vendors!")
                return
            if not parsed_string:
                await reply_message(message, "No vendor name specified!")
                return
            result = await commit_sql("""DELETE FROM Vendors WHERE ServerId=%s and VendorName=%s;""",(str(message.author.id),parsed_string))
            if result:
                await reply_message(message, "Vendor " + parsed_string + " deleted!")
            else:
                await reply_message(message, "Database error!")
        elif command == 'deletearmory':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to delete armories!")
                return
            if not parsed_string:
                await reply_message(message, "No armory name specified!")
                return                
            result = commit_sql("""DELETE FROM Armory WHERE ServerId=%s and ArmoryName=%s;""",(str(message.author.id),parsed_string))
            if result:
                await reply_message(message, "Armory " + parsed_string + " deleted!")
            else:
                await reply_message(message, "Database error!")                
            
        elif command == 'deletevendoritem':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to edit vendors!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'deletevendoritem'
            dm_tracker[message.author.id]["fieldlist"] = ["VendorName","ItemList"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "Vendors", "VendorName")
            response = "Please select a vendor from the below list to edit:\n\n" + menu
            await reply_message(message, "Please check your DMs for instructions on how to delete items from a vendor, <@" + str(message.author.id) + ">.")
            await direct_message(message, response)
            
        elif command == 'listvendor':
            vendor_name = parsed_string
            records = await select_sql("""SELECT ItemList,PictureLink FROM Vendors WHERE VendorName=%s;""", (vendor_name,))
            if not records:
                await reply_message(message, "No vendor found by that name!")
                return
            for row in records:
                items = row[0]
            response = "**ITEMS FOR VENDOR " + parsed_string + "**\n\n"   
            item_list = items.split(',')
            for item in item_list:
                item_record = await select_sql("""SELECT EquipmentName FROM Equipment WHERE Id=%s""",(item,))
                for item_name in item_record:
                    response = response + item_name[0] + "\n"
            await reply_message(message, response + "\nPicture Link: " + row[1] + "\n")
        elif command == 'listvendors':
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)           
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            response = "**VENDORS**\n\n"
            menu = await make_simple_menu(message, "Vendors", "VendorName")
            await reply_message(message, response + menu)
        elif command == 'newarmory':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to create new armories!")
                return
                
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newarmory'
            dm_tracker[message.author.id]["fieldlist"] = ["ArmoryName","ArmamentList","PictureLink"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            
            await reply_message(message, "Please check your DMs for instructions on how to create a new armory, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested a new armory! Please type in the response the **armory name**, and then enter each field as a reply to the DMs. When you have filled out all fields, the armory will be created!")
        elif command == 'addarmoryitem':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to edit armories!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'addarmoryitem'
            dm_tracker[message.author.id]["fieldlist"] = ["ArmoryName","ItemList"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "Armory", "ArmoryName")
            response = "Please select a armory from the below list to edit:\n\n" + menu
            await reply_message(message, "Please check your DMs for instructions on how to add items to a armory, <@" + str(message.author.id) + ">.")
            await direct_message(message, response)
        elif command == 'deletearmoryitem':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to delete armories!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'deletearmoryitem'
            dm_tracker[message.author.id]["fieldlist"] = ["ArmoryName","ItemList"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "Armory", "ArmoryName")
            response = "Please select a armory from the below list to edit:\n\n" + menu
            await reply_message(message, "Please check your DMs for instructions on how to delete items from a armory, <@" + str(message.author.id) + ">.")
            await direct_message(message, response)
            
        elif command == 'listarmory':
            armory_name = parsed_string
            records = await select_sql("""SELECT ArmamentList,PictureLink FROM Armory WHERE ArmoryName=%s;""", (armory_name,))
            if not records:
                await reply_message(message, "No armory found by that name!")
                return
            for row in records:
                items = row[0]
            response = "**ARMAMENTS FOR ARMORY " + parsed_string + "**\n\n"   
            item_list = items.split(',')
            for item in item_list:
                item_record = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s""",(item,))
                for item_name in item_record:
                    response = response + item_name[0] + "\n"
            await reply_message(message, response + "\nPicture Link: " + row[1] + "\n")
        elif command == 'listarmories':
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)           
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            response = "**ARMORIES**\n\n"
            menu = await make_simple_menu(message, "Armory", "ArmoryName")
            await reply_message(message, response + menu)            
        elif command == 'listspell':
            if not parsed_string:
                await reply_message(message, "No spell name specified!")
                return
            records = await select_sql("""SELECT Element,ManaCost,MinimumLevel,DamageMultiplier,Description,PictureLink FROM Spells WHERE ServerId=%s AND SpellName=%s;""", (str(message.guild.id), parsed_string))
            if not records:
                await reply_message(message, "No spell found by that name!")
                return
            response = "**SPELL DETAILS**\n\nSpell Name: " + parsed_string + "\n"
            for row in records:
                response = response + "Element: " + row[0] + "\nMana Cost: " + str(row[1]) + "\nMinimum Level: " + str(row[2]) + "\nDamage Multiplier: " + str(row[3]) + "\nDescription: " + row[4] + "\nPicture Link: " + row[5] + "\n"
            await reply_message(message, response)
        elif command == 'listmelee':
            if not parsed_string:
                await reply_message(message, "No melee name specified!")
                return
            records = await select_sql("""SELECT StaminaCost,MinimumLevel,DamageMultiplier,Description,PictureLink FROM Melee WHERE ServerId=%s AND AttackName=%s;""", (str(message.guild.id), parsed_string))
            if not records:
                await reply_message(message, "No spell found by that name!")
                return
            response = "**MELEE DETAILS**\n\nAttack Name: " + parsed_string + "\n"
            for row in records:
                response = response + "Stamina Cost: " + str(row[0]) + "\nMinimum Level: " + str(row[1]) + "\nDamage Multiplier: " + str(row[2]) + "\nDescription: " + row[3] + "\nPicture Link: " + row[4] + "\n"
            await reply_message(message, response)            
        elif command == 'newitem':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to create new equipment!")
                return
            
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newitem'
            dm_tracker[message.author.id]["fieldlist"] = ["EquipmentName","EquipmentDescription","EquipmentCost","MinimumLevel","StatMod","Modifier","PictureLink"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            
            await reply_message(message, "Please check your DMs for instructions on how to create a new item, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested a new item! Please type in the response the **name of the item**, and then enter each field as a reply to the DMs. When you have filled out all fields, the item will be created!")

        elif command == 'newarmament':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to create new armaments!")
                return
            
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            # CREATE TABLE Armaments (Id int auto_increment, ArmamentName VARCHAR(100), ServerId VARCHAR(40), UserId VARCHAR(40), Description TEXT, Slot VARCHAR(20) MinimumLevel Int, DamageMin Int, DamageMax Int, Defense Int, StatMod VARCHAR(30), PRIMARY KEY(Id))
            dm_tracker[message.author.id]["currentcommand"] = 'newarmament'
            dm_tracker[message.author.id]["fieldlist"] = ["ArmamentName","Description","ArmamentCost","Slot","MinimumLevel","DamageMin","DamageMax","Defense","StatMod","Modifier","PictureLink"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            
            await reply_message(message, "Please check your DMs for instructions on how to create a new armament, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested a new item! Please type in the response the **name of the armament**, and then enter each field as a reply to the DMs. When you have filled out all fields, the armamement will be created!")

        elif command == 'deletespell':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to delete spells!")
                return        
            if not parsed_string:
                await reply_message(message, "No spell specified!")
                return
            result = await commit_sql("""DELETE FROM Spells WHERE ServerId=%s AND SpellName=%s;""", (str(message.guild.id), parsed_string))
            if result:
                await reply_message(message, "Spell " + parsed_string + " deleted successfully.")
            else:
                await reply_message(message, "Database error!")
        elif command == 'deletemelee':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to delete melee attacks!")
                return        
            if not parsed_string:
                await reply_message(message, "No melee attack specified!")
                return
            result = await commit_sql("""DELETE FROM Melee WHERE ServerId=%s AND AttackName=%s;""", (str(message.guild.id), parsed_string))
            if result:
                await reply_message(message, "Attack Name " + parsed_string + " deleted successfully.")
            else:
                await reply_message(message, "Database error!")            
        elif command == 'listmelees':
            response = "***CURRENT MELEE LIST***\n\n_Attack Name_\n"
            records = await select_sql("""SELECT AttackName FROM Melee WHERE ServerId=%s;""", (str(message.guild.id),))
            for row in records:
                response = response + row[0] + "\n"
            await reply_message(message, response)            
        elif command == 'listspells':
            response = "***CURRENT Spell LIST***\n\n_Spell Name_\n"
            records = await select_sql("""SELECT SpellName FROM Spells WHERE ServerId=%s;""", (str(message.guild.id),))
            for row in records:
                response = response + row[0] + "\n"
            await reply_message(message, response)
        elif command == 'editmelee':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to edit melee attacks!")
                return        
            user_id = message.author.id
            server_id = message.guild.id

            current_fields = await select_sql("""SELECT AttackName,Description,StaminaCost,MinimumLevel,DamageMultiplier,PictureLink FROM Melee WHERE ServerId=%s AND AttackName=%s;""", (str(message.guild.id), parsed_string))
            if not current_fields:
                await reply_message(message, "No melee attack found by that name!")
                return
          
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["AttackName","Description","StaminaCost","MinimumLevel","DamageMultiplier","PictureLink"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'editmelee'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(current_fields[0][counter])
                counter = counter + 1
            
            await reply_message(message, "Please check your DMs for instructions on how to edit an item, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested to edit the item **" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the item will be updated!\nThe first field is **" + dm_tracker[message.author.id]["fieldlist"][0] + "** and its current value is **" + dm_tracker[message.author.id]["fielddict"][0] + "**.")
        elif command == 'editspell':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to edit spells!")
                return        
            user_id = message.author.id
            server_id = message.guild.id

            current_fields = await select_sql("""SELECT SpellName,Description,ManaCost,MinimumLevel,DamageMultiplier,Element,PictureLink FROM Spells WHERE ServerId=%s AND SpellName=%s;""", (str(message.guild.id), parsed_string))
            if not current_fields:
                await reply_message(message, "No spell found by that name!")
                return
          
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["SpellName","Description","ManaCost","MinimumLevel","DamageMultiplier","Element","PictureLink"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'editspell'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(current_fields[0][counter])
                counter = counter + 1
            
            await reply_message(message, "Please check your DMs for instructions on how to edit a spell, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested to edit the spell **" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the spell will be updated!\nThe first field is **" + dm_tracker[message.author.id]["fieldlist"][0] + "** and its current value is **" + dm_tracker[message.author.id]["fielddict"][0] + "**.")
        elif command == 'givemelee':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to give melee attacks!")
                return 
  
             

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Character","Spell"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'givemelee'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Pick a character to add a melee attack to:\n\nPlease choose a character by selecting the IDs.\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to give a melee attack, <@" + str(message.author.id) + ">.")                
            
        elif command == 'givearmament':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to give melee attacks!")
                return 
  
             

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Character","Armament"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'givearmament'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Pick a character to add a melee attack to:\n\nPlease choose a character by selecting the IDs.\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to give an armament, <@" + str(message.author.id) + ">.")              

        elif command == 'giveitem':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to give melee attacks!")
                return 
  
             

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Character","Item"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'giveitem'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Pick a character to add a melee attack to:\n\nPlease choose a character by selecting the IDs.\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to give an item, <@" + str(message.author.id) + ">.")  

                    
        elif command == 'givespell':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to give spells!")
                return        
             

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Character","Spell"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'givespell'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Pick a character to add a spell to:\n\nPlease choose a character by selecting the IDs.\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to give a spell, <@" + str(message.author.id) + ">.")

            
                

            
            
        elif command == 'takemelee':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to take melee attacks!")
                return
     
             

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Character","Spell"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'takemelee'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Pick a character to add a spell to:\n\nPlease choose a character by selecting the IDs.\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to take a melee attack, <@" + str(message.author.id) + ">.")

        elif command == 'takespell':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to take spells!")
                return
 
             

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Character","Spell"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'takespell'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Pick a character to add a spell to:\n\nPlease choose a character by selecting the IDs.\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to take a spell, <@" + str(message.author.id) + ">.")
        elif command == 'editarmament':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to edit armaments!")
                return
            user_id = message.author.id
            server_id = message.guild.id
                
            current_fields = await select_sql("""SELECT ArmamentName,Description,ArmamentCost,Slot,MinimumLevel,DamageMin,DamageMax,Defense,StatMod,Modifier,PictureLink FROM Armaments WHERE ServerId=%s AND ArmamentName=%s;""", (str(message.guild.id), parsed_string))
            if not current_fields:
                await reply_message(message, "No armament found by that name!")
                return
          
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["ArmamentName","Description","ArmamentCost","Slot","MinimumLevel","DamageMin","DamageMax","Defense","StatMod","Modifier","PictureLink"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'editarmament'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(current_fields[0][counter])
                counter = counter + 1
            
            await reply_message(message, "Please check your DMs for instructions on how to edit an armament, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested to edit the armament **" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the armament will be updated!\nThe first field is **" + dm_tracker[message.author.id]["fieldlist"][0] + "** and its current value is **" + dm_tracker[message.author.id]["fielddict"][0] + "**.")            
        elif command == 'edititem':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to edit equipment!")
                return
            user_id = message.author.id
            server_id = message.guild.id
                
            current_fields = await select_sql("""SELECT EquipmentDescription,EquipmentCost,MinimumLevel,StatMod,Modifier,PictureLink FROM Equipment WHERE ServerId=%s AND EquipmentName=%s;""", (str(message.guild.id), parsed_string))
            if not current_fields:
                await reply_message(message, "No item found by that name!")
                return
          
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["EquipmentDescription","EquipmentCost","MinimumLevel","StatMod","Modifier","PictureLink"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'edititem'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(current_fields[0][counter])
                counter = counter + 1
            
            await reply_message(message, "Please check your DMs for instructions on how to edit an item, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested to edit the item **" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the item will be updated!\nThe first field is **" + dm_tracker[message.author.id]["fieldlist"][0] + "** and its current value is **" + dm_tracker[message.author.id]["fielddict"][0] + "**.")                

                
        elif command == 'deletearmament':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to delete equipment!")
                return        
            if not parsed_string:
                await reply_message(message, "You didn't specify an equipment name!")
                return
            records = await select_sql("""SELECT Id FROM Armaments WHERE ArmamentName=%s AND ServerId=%s;""", (parsed_string,str(message.guild.id)))
            
            if not records:
                await reply_message(message, "No item found by that name!")
                return 
            for row in records:
                item_id = row[0]
                
            result = await commit_sql("""DELETE FROM Armaments WHERE Id=%s;""", (item_id,))
            if result:
                result_remove = await commit_sql("""DELETE FROM ArmamentInventory WHERE ServerId=%s AND ArmamentId=%s;""",(str(message.guild.id),item_id))
                if result_remove:
                    await reply_message(message, "Armament removed from game and inventory successfully.")
                else:
                    await reply_message(message, "Database error!")
            else:
                await reply_message(message, "Database error!")
        elif command == 'deleteitem':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to delete equipment!")
                return        
            if not parsed_string:
                await reply_message(message, "You didn't specify an equipment name!")
                return
            records = await select_sql("""SELECT Id FROM Equipment WHERE EquipmentName=%s AND ServerId=%s;""", (parsed_string,str(message.guild.id)))
            
            if not records:
                await reply_message(message, "No item found by that name!")
                return 
            for row in records:
                item_id = row[0]
                
            result = await commit_sql("""DELETE FROM Equipment WHERE Id=%s;""", (item_id,))
            if result:
                result_remove = await commit_sql("""DELETE FROM Inventory WHERE ServerId=%s AND EquipmentId=%s;""",(str(message.guild.id),item_id))
                if result_remove:
                    await reply_message(message, "Item removed from game and inventory successfully.")
                else:
                    await reply_message(message, "Database error!")
            else:
                await reply_message(message, "Database error!")
        elif command == 'buy':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to buy equipment!")
                return
            name_re = re.compile(r"Character: (?P<name>.+?) (?P<lastname>.+)")
            equip_re = re.compile(r"Item: (?P<itemname>.+)")
            
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'buy'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = ""
            dm_tracker[message.author.id]["fieldlist"] = ["CharId","VendorId","ItemId"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            response = "**YOUR CHARACTERS**\n\n"
            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId", str(message.author.id))
            response = response + menu
            await direct_message(message, "Please select a character to purchase the item for by replying with the ID in bold.\n\n" + response)
            await reply_message(message, "Please check your DMs for instructions on how to buy an item, <@" + str(message.author.id) + ">.")
        elif command == 'buyarms':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to buy armaments!")
                return
            
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'buyarms'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = ""
            dm_tracker[message.author.id]["fieldlist"] = ["CharId","VendorId","ItemId"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            response = "**YOUR CHARACTERS**\n\n"
            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId", str(message.author.id))
            response = response + menu
            await direct_message(message, "Please select a character to purchase the item for by replying with the ID in bold.\n\n" + response)
            await reply_message(message, "Please check your DMs for instructions on how to buy armaments, <@" + str(message.author.id) + ">.")            
            

        elif command == 'myitems':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to check inventory!")
                return
            if not parsed_string:
                await reply_message(message, "You didn't specify a character!")
                return
            name_re = re.compile(r"(?P<name>.+) (?P<lastname>.+)")
            m = name_re.search(parsed_string)
            if m:
                char_name = m.group('name')
                
            else:
                await reply_message(message, "No character specified!")
                return
            records = await select_sql("""SELECT Id,UserId FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""",(str(message.guild.id), char_name))
            if not records:
                await reply_message(message, "No character by that name found!")
                return
            for row in records:
                char_id = row[0]
                user_id = int(row[1])
            if user_id != message.author.id:
                await reply_message(message, "This isn't your character!")
                return
            records = await select_sql("""SELECT EquipmentId FROM Inventory WHERE CharacterId=%s;""",(char_id,))
            if not records:
                await reply_message(message, char_name + " doesn't have any items!")
                return
            response = "**INVENTORY**\n\n"
            for row in records:
                item_id = row[0]
                item_records = await select_sql("""SELECT EquipmentName FROM Equipment WHERE Id=%s;""",(item_id,))
                for item in item_records:
                    response = response + item[0] + "\n"
            await reply_message(message, response)
        elif command == 'inventory':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to check inventory!")
                return
            if not parsed_string:
                await reply_message(message, "You didn't specify a character!")
                return
            records = await select_sql("""SELECT Id,UserId FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""",(str(message.guild.id), parsed_string))
            if not records:
                await reply_message(message, "No character by that name found!")
                return
            for row in records:
                char_id = row[0]
                user_id = int(row[1])
            records = await select_sql("""SELECT EquipmentId FROM Inventory WHERE CharacterId=%s;""",(char_id,))
            if not records:
                await reply_message(message, char_name + " doesn't have any items!")
                return
            response = "**INVENTORY**\n\n"
            for row in records:
                item_id = row[0]
                item_records = await select_sql("""SELECT EquipmentName FROM Equipment WHERE Id=%s;""",(item_id,))
                for item in item_records:
                    response = response + item[0] + "\n"
            await reply_message(message, response)
        elif command == 'trade':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to check inventory!")
                return  

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'trade'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = ""
            dm_tracker[message.author.id]["fieldlist"] = ["CharId","ItemId","TargetId"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId", str(message.author.id))

            await direct_message(message, "Please select a character to trade the item from by replying with the ID in bold.\n\n" + menu)
            await reply_message(message, "Please check your DMs for instructions on how to trade an item, <@" + str(message.author.id) + ">.")  
        elif command == 'tradearms':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to check inventory!")
                return  

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'tradearms'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = ""
            dm_tracker[message.author.id]["fieldlist"] = ["CharId","ItemId","TargetId"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId", str(message.author.id))

            await direct_message(message, "Please select a character to trade the item from by replying with the ID in bold.\n\n" + menu)
            await reply_message(message, "Please check your DMs for instructions on how to trade an item, <@" + str(message.author.id) + ">.")              
        elif command == 'listitems':
            records = await select_sql("""SELECT EquipmentName FROM Equipment WHERE ServerId=%s;""", (str(message.guild.id),))
            if not records:
                await reply_message(message, "This server does not have any items yet!")
                return
            response = "**SERVER ITEM LIST**\n\n"
            for row in records:
                response = response + row[0] + "\n"
            await reply_message(message, response)
        elif command == 'listarmaments':
            records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE ServerId=%s;""", (str(message.guild.id),))
            if not records:
                await reply_message(message, "This server does not have any armaments yet!")
                return
            response = "**SERVER ARMAMENT LIST**\n\n"
            for row in records:
                response = response + row[0] + "\n"
            await reply_message(message, response)             
        elif command == 'sell':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to sell equipment!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'sell'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = ""
            dm_tracker[message.author.id]["fieldlist"] = ["CharId","VendorId","ItemId"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            response = "**YOUR CHARACTERS**\n\n"
            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId", str(message.author.id))
            response = response + menu
            await direct_message(message, "Please select a character to sell the item for by replying with the ID in bold.\n\n" + response)
            await reply_message(message, "Please check your DMs for instructions on how to sell an item, <@" + str(message.author.id) + ">.")  
        elif command == 'sellarms':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to sell armaments!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'sellarms'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = ""
            dm_tracker[message.author.id]["fieldlist"] = ["CharId","VendorId","ItemId"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            response = "**YOUR CHARACTERS**\n\n"
            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId", str(message.author.id))
            response = response + menu
            await direct_message(message, "Please select a character to sell the armament for by replying with the ID in bold.\n\n" + response)
            await reply_message(message, "Please check your DMs for instructions on how to sell an armament, <@" + str(message.author.id) + ">.")                
        elif command == 'buff':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to use buffs!")
                return
            if not mass_spar_event[message.guild.id] and not server_encounters[message.guild.id]:
                await reply_message(message, "No encounter or spar in progress to use buffs for!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = []
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'buff'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = "" 
            characters = {} 
            if mass_spar_event[message.guild.id]:
                characters[mass_spar_chars[message.guild.id][message.author.id]["CharId"]] = mass_spar_chars[message.guild.id][message.author.id]["CharName"]
            if server_encounters[message.guild.id]:
                characters[server_party_chars[message.guild.id][message.author.id]["CharId"]] = server_party_chars[message.guild.id][message.author.id]["CharName"]
            menu = "**CURRENT EVENT CHARACTERS**\n\n"
            for char in characters:
                menu = menu + "**" + str(char) + "** - " + characters[char] + "\n"
                
               
            await direct_message(message, "Select a character's buff to use by replying with their ID (the number in bold):\n" + menu)
            await reply_message(message, "<@" + str(message.author.id) + "> , check your DMs for how to use the buff.")
        elif command == 'newbuff':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to create new buffs!")
                return
            
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newbuff'
            # BuffName VARCHAR(100), ManaCost Int, MinimumLevel Int, StatMod VARCHAR(30), Modifier Int, Description TEXT,
            dm_tracker[message.author.id]["fieldlist"] = ["BuffName","ManaCost","MinimumLevel","StatMod","Modifier","Description","PictureLink"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            
            await reply_message(message, "Please check your DMs for instructions on how to create a new buff, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested a new buff! Please type in the response the **name of the buff**, and then enter each field as a reply to the DMs. When you have filled out all fields, the buff will be created!")
        elif command == 'editbuff':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to edit buffs!")
                return
            current_fields = await select_sql("""SELECT BuffName,ManaCost,MinimumLevel,StatMod,Modifier,Description,PictureLink FROM Buffs WHERE ServerId=%s AND BuffName=%s;""", (str(message.guild.id), parsed_string))
            if not current_fields:
                await reply_message(message, "No buff found by that name!")
                return                
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
                
            dm_tracker[message.author.id]["currentcommand"] = 'editbuff'
            # BuffName VARCHAR(100), ManaCost Int, MinimumLevel Int, StatMod VARCHAR(30), Modifier Int, Description TEXT,
            dm_tracker[message.author.id]["fieldlist"] = ["BuffName","ManaCost","MinimumLevel","StatMod","Modifier","Description","PictureLink"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(current_fields[0][counter])
                counter = counter + 1
                
            await reply_message(message, "Please check your DMs for instructions on how to edit a buff, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested a buff edit! The first field is **" + dm_tracker[message.author.id]["fieldlist"][0] + "** and its value is **" + dm_tracker[message.author.id]["fielddict"][0] + "**!")
        elif command == 'deletebuff':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to delete buffs!")
                return        
            if not parsed_string:
                await reply_message(message, "You didn't specify a buff name!")
                return
            records = await select_sql("""SELECT Id FROM EBuffs WHERE BuffName=%s AND ServerId=%s;""", (parsed_string,str(message.guild.id)))
            
            if not records:
                await reply_message(message, "No buff found by that name!")
                return 
            for row in records:
                item_id = row[0]
                
            result = await commit_sql("""DELETE FROM Buffs WHERE Id=%s;""", (item_id,))
            if result:
                result_remove = await commit_sql("""DELETE FROM BuffSkills WHERE ServerId=%s AND BuffId=%s;""",(str(message.guild.id),item_id))
                if result_remove:
                    await reply_message(message, "Buff removed from game successfully.")
                else:
                    await reply_message(message, "Database error!")
            else:
                await reply_message(message, "Database error!")
        elif command == 'changecharowner':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to change character owners!")
                return
                
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
               
            dm_tracker[message.author.id]["currentcommand"] = 'changecharowner'
            # BuffName VARCHAR(100), ManaCost Int, MinimumLevel Int, StatMod VARCHAR(30), Modifier Int, Description TEXT,
            dm_tracker[message.author.id]["fieldlist"] = ["Id","UserId"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "CharacterProfiles","CharacterName")
            await reply_message(message, "Please check your DMs for instructions on how to change a character owner, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested a character owner change! Please type in the response the **ID of the character**, and then enter each field as a reply to the DMs. When you have filled out all fields, the owner will be updated!\n\n" + menu)                
        elif command == 'listbuffs':
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            menu = await make_simple_menu(message, "Buffs","BuffName")
            response = "**SERVER LIST OF BUFFS**\n\n"
            response = response + menu
            await reply_message(message, response)
        elif command == 'givebuff':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to give buffs!")
                return        
             

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Character","Buff"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'givebuff'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Pick a character to add a buff to:\n\nPlease choose a character by selecting the IDs.\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to give a buff, <@" + str(message.author.id) + ">.")
        elif command == 'takebuff':
            pass
        elif command == 'listbuff':
            if not parsed_string:
                await reply_message(message, "You did not specify a buff!")
                return
            records = await select_sql("""SELECT BuffName,ManaCost,MinimumLevel,StatMod,Modifier,Description,PictureLink FROM Buffs WHERE ServerId=%s AND BuffName=%s;""",(str(message.guild.id),str(parsed_string)))
            if not records:
                await reply_message(message, "No buff found with that name!")
                return
            for row in records:
                buff_name = row[0]
                mana_cost = str(row[1])
                min_level = str(row[2])
                stat_mod = row[3]
                modifier = str(row[4])
                description = row[5]
                picture_link = row[6]
            response = "**BUFF DETAILS**\n\nName: " + buff_name + "\nMana Cost: " + mana_cost + "\nMinimum Level: " + min_level + "\nStatus Modified: " + stat_mod + "\nModified By: " + modifier + "\nDescription: " + description + "\nPicture Link: " + picture_link
            await reply_message(message, response)
         
        elif command == 'useitem':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to use items!")
                return
                
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = []
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'useitem1'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = "" 

            records = await select_sql("""SELECT Id,CharacterName FROM CharacterProfiles WHERE ServerId=%s AND UserId=%s;""", (str(message.guild.id), str(message.author.id)))
            if not records:
                await reply_message(message, "No characters found for you!")
                return
            character_list = "**YOUR CHARACTERS**\n\n"    
            for row in records:
                char_id = row[0]
                char_name = row[1]
                character_list = character_list + "**" + str(char_id) + "** " + char_name + "\n"
                
            await direct_message(message, "Select a character to use an item on by replying with their ID (the number in bold):\n" + character_list)
            await reply_message(message, "<@" + str(message.author.id) + "> , check your DMs for how to use the item.")

 
        elif command == 'getcharequipped':
            char_name = parsed_string
            if not parsed_string:
                await reply_message(message, "No character name specified!")
                return
            records = await select_sql("""SELECT Id FROM CharacterProfiles WHERE CharacterName=%s AND ServerId=%s;""",(char_name,str(message.guild.id)))
            if not records:
                await reply_message(message, "No character found by that name!")
            for row in records:
                char_id = str(row[0])
            records = await select_sql("""SELECT IFNULL(HeadId,'0'), IFNULL(LeftHandId,'0'), IFNULL(RightHandId,'0'), IFNULL(ChestId,'0'), IFNULL(FeetId,'0') FROM CharacterArmaments WHERE CharacterId=%s;""",(char_id,))
            for row in records:
                head_id = row[0]
                left_id = row[1]
                right_id = row[2]
                chest_id = row[3]
                feet_id = row[4]
            if not records:
                await direct_message(message, "This character has nothing equipped!")
                return
            records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (head_id,))
            for row in records:
                head_name = row[0]
            try: head_name
            except: head_name = "None"
            records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (left_id,))
            for row in records:
                left_name = row[0]
            try: left_name
            except: left_name = "None"
            records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (right_id,))
            for row in records:
                right_name = row[0]
            try: right_name
            except: right_name = "None"
            records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (chest_id,))
            for row in records:
                chest_name = row[0]
            try: chest_name
            except: chest_name = "None"
            records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (feet_id,))
            for row in records:
                feet_name = row[0]
            try: feet_name
            except: feet_name = "None"

            menu = "Current Armaments Equipped\n\nHead: **" +head_id + "** - " + head_name + "\nLeftHand: **" + left_id + "** - " + left_name + "\nRightHand: **" + right_id +  "** - " + right_name + "\nChest: **" + chest_id + "** - " + chest_name + "\nFeet: **" + feet_id + "** - " + feet_name +"\n"
            await reply_message(message, menu)
        elif command == 'getalttemplate':
            response = "**NEW Alt TEMPLATE**\n\n=newalt Name: \nShortcut: \nPicture Link: \n"
            await reply_message(message, response)

        elif command == 'lurk':
            if message.author.nick:
                name = message.author.nick
            else:
                name = message.author.name
            responses = ["((*" + name + " lurks in the shadowy rafters with luminous orbs with parted tiers, trailing long digits through their platinum tresses.*))", "**" +name + " :** ((::lurk::))", "((*" + name + " flops on the lurker couch.*))"]
            await reply_message(message, random.choice(responses))
            await message.delete()
        elif command == 'ooc':
            if message.author.nick:
                name = message.author.nick
            else:
                name = message.author.name        
            await reply_message(message, "**" + name + ":** ((*" + parsed_string + "*))")
            await message.delete()
        elif command == 'me':
            if message.author.nick:
                name = message.author.nick
            else:
                name = message.author.name        
            await reply_message(message, "((*-" + name + " " + parsed_string + "-*))")
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
            await reply_message(message, response)
        elif command == 'givecurrency':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to give currency!")
                return        

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'givecurrency'
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterId","Currency"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            
            response = "Please select a character by replying to this DM with the character ID to give currency to:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to grant currency, <@" + str(message.author.id) + ">.")
        elif command == 'takecurrency':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to take currency!")
                return        

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'takecurrency'
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterId","Currency"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            
            response = "Please select a character by replying to this DM with the character ID to give currency to:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to take currency, <@" + str(message.author.id) + ">.")            
        elif command == 'equiparmament':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the Plaer role to equip armaments!")
                return        

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'equiparmament'
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterId","ArmamentId","Slot"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            records = await select_sql("""SELECT Id,CharacterName FROM CharacterProfiles WHERE ServerId=%s AND UserId=%s;""", (str(message.guild.id), str(message.author.id)))
            if not records:
                await reply_message(message, "No characters found for you!")
                return
            character_list = "**YOUR CHARACTERS**\n\n"    
            for row in records:
                char_id = row[0]
                char_name = row[1]
                character_list = character_list + "**" + str(char_id) + "** " + char_name + "\n"
            
            response = "Please select a character by replying to this DM with the character ID to equip an armament:\n\n" + character_list
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to equip armaments, <@" + str(message.author.id) + ">.")
        elif command == 'unequiparmament':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the Player role to unequip armaments!")
                return        

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'unequiparmament'
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterId","ArmamentId","Slot"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            records = await select_sql("""SELECT Id,CharacterName FROM CharacterProfiles WHERE ServerId=%s AND UserId=%s;""", (str(message.guild.id), str(message.author.id)))
            if not records:
                await reply_message(message, "No characters found for you!")
                return
            character_list = "**YOUR CHARACTERS**\n\n"    
            for row in records:
                char_id = row[0]
                char_name = row[1]
                character_list = character_list + "**" + str(char_id) + "** " + char_name + "\n"
            
            response = "Please select a character by replying to this DM with the character ID to equip an armament:\n\n" + character_list
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to equip armaments, <@" + str(message.author.id) + ">.")

        elif command == 'newmonster':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to create monsters!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newmonster'
            dm_tracker[message.author.id]["fieldlist"] = ["MonsterName","Description","Health","Level","Attack","Defense","Element","MagicAttack","MaxCurrencyDrop","PictureLink"]                                                   
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = [] 
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            
            await reply_message(message, "Please check your DMs for instructions on how to create a new monster, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested a new monster! Please type in the response the **name of the monster**, and then enter each field as a reply to the DMs. When you have filled out all fields, the monster will be created!")                

        elif command == 'editcharinfo':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to edit edit character info!")
                return        

            current_fields = await select_sql("""SELECT IFNULL(Biography,'None'),IFNULL(Skills,'None'),IFNULL(Strengths,'None'),IFNULL(Weaknesses,'None'),IFNULL(Powers,'None'),IFNULL(Personality,'None'),IFNULL(Description,'None') FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s;""", (str(message.guild.id), parsed_string))
            if not current_fields:
                await reply_message(message, "No character found by that name!")
                return
            for row in current_fields:
                fields = row
             
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterName","Biography","Skills","Strengths","Weaknesses","Powers","Personality","Description"]
            dm_tracker[message.author.id]["currentfield"] = 1
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["fielddict"].append(parsed_string)
            dm_tracker[message.author.id]["currentcommand"] = 'editcharinfo'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(fields[counter])
                counter = counter + 1
                if counter > len(dm_tracker[message.author.id]["fieldlist"]) - 2:
                    break
            
            await reply_message(message, "Please check your DMs for instructions on how to edit a character, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested to edit the character**" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the character will be updated!\nThe first field is **" + dm_tracker[message.author.id]["fieldlist"][1] + "** and its current value is **" + dm_tracker[message.author.id]["fielddict"][1] + "**.")             

        elif command == 'editmonster':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to edit monsters!")
                return        

            current_fields = await select_sql("""SELECT Description,Health,Element,Level,Attack,Defense,MagicAttack,IFNULL(MaxCurrencyDrop,0),IFNULL(PictureLink,'None') FROM Monsters WHERE ServerId=%s AND MonsterName=%s;""", (str(message.guild.id), parsed_string))
            if not current_fields:
                await reply_message(message, "No monster found by that name!")
                return
            for row in current_fields:
                fields = row
             
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["MonsterName","Description","Health","Element","Level","Attack","Defense","MagicAttack","MaxCurrencyDrop","PictureLink"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["fielddict"].append(parsed_string)
            dm_tracker[message.author.id]["currentcommand"] = 'editmonster'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(fields[counter])
                counter = counter + 1
                if counter > len(dm_tracker[message.author.id]["fieldlist"]) - 2:
                    break
            
            await reply_message(message, "Please check your DMs for instructions on how to edit a monster, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested to edit the monster **" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the monster will be updated!\nThe first field is **" + dm_tracker[message.author.id]["fieldlist"][1] + "** and its current value is **" + dm_tracker[message.author.id]["fielddict"][1] + "**.")            
   
        elif command == 'listmonsters':
            records = await select_sql("""SELECT MonsterName FROM Monsters WHERE ServerId=%s;""", (str(message.guild.id),))
            if not records:
                await reply_message(message, "No monsters are on this server yet!")
                return
            response = "**SERVER MONSTER LIST**\n\n"
            for row in records:
                response = response + row[0] + "\n"
            await reply_message(message, response)
        elif command == 'listmonster':
            if not parsed_string:
                await reply_message(message, "No monster name specified!")
                return
            records = await select_sql("""SELECT Description,Health,Level,Attack,Defense,Element,MagicAttack,IFNULL(PictureLink,' '),MaxCurrencyDrop FROM Monsters WHERE ServerId=%s AND MonsterName=%s;""", (str(message.guild.id),parsed_string))
            if not records:
                await reply_message(message, "No monster found with that name!")
                return
            response = "**MONSTER DATA**\n\n"
            for row in records:
                response = response + "Name: " + parsed_string + "\nDescription: " + str(row[0]) + "\nHealth: " + str(row[1]) + "\nLevel: " + str(row[2]) + "\nMelee Attack: " + str(row[3]) + "\nDefense: " + str(row[4]) + "\nMagic Attack: " + str(row[6]) + "\nElement: " + str(row[5]) + "\nPicture Link: " + str(row[7]) + "\nMax Currency Drop: " + str(row[8]) + "\n"
            await reply_message(message, response)
        elif command == 'listitem':
            if not parsed_string:
                await reply_message(message, "No item name specified!")
                return
            records = await select_sql("""SELECT EquipmentDescription, EquipmentCost, MinimumLevel, StatMod, Modifier, PictureLink FROM Equipment WHERE ServerId=%s AND EquipmentName=%s;""", (str(message.guild.id),parsed_string))
            if not records:
                await reply_message(message, "No item found with that name!")
                return
            response = "**ITEM DATA**\n\n"
            for row in records:
                response = response + "Name: " + parsed_string + "\nDescription: " + row[0] + "\nPrice: " + str(row[1]) + "\nMinimum Level: " + str(row[2]) + "\nStat Modified: " + str(row[3]) + "\nModifier Change: " + str(row[4]) + "\nPicture Link: " + row[5] + "\n"
            await reply_message(message, response)
        elif command == 'listarmament':
            if not parsed_string:
                await reply_message(message, "No item name specified!")
                return
            records = await select_sql("""SELECT Description, ArmamentCost, MinimumLevel, StatMod, Modifier, Slot, DamageMin, DamageMax, Defense, PictureLink FROM Armaments WHERE ServerId=%s AND ArmamentName=%s;""", (str(message.guild.id),parsed_string))
            if not records:
                await reply_message(message, "No armament found with that name!")
                return
            response = "**ARMAMENT DATA**\n\n"
            for row in records:
                response = response + "Name: " + parsed_string + "\nDescription: " + row[0] + "\nPrice: " + str(row[1]) + "\nMinimum Level: " + str(row[2]) + "\nStat Modified: " + str(row[3]) + "\nModifier Change: " + str(row[4]) + "\nSlot: " + row[5] + "\nMinimum Damage: " + str(row[6]) + "\nMaximum Damage: " + str(row[7]) + "\nDefense: " + str(row[8]) + "\nPicture Link: " + row[9] + "\n"
            await reply_message(message, response)
        elif command == 'listspell':
            if not parsed_string:
                await reply_message(message, "No spell name specified!")
                return
            records = await select_sql("""SELECT Element, ManaCost, MinimumLevel, DamageMultiplier, Description FROM Spells WHERE ServerId=%s AND SpellName=%s;""", (str(message.guild.id),parsed_string))
            if not records:
                await reply_message(message, "No spell found with that name!")
                return
            response = "**SPELL DATA**\n\n"
            for row in records:
                response = response + "Name: " + parsed_string + "\nElement: " + row[0] + "\nMana Cost: " + str(row[1]) + "\nMinimum Level: " + str(row[2]) + "\nDamage Multiplier: " + str(row[3]) + "\nDescription: " + str(row[4]) +  "\n"
            await reply_message(message, response) 
        elif command == 'listmelee':
            if not parsed_string:
                await reply_message(message, "No melee attack name specified!")
                return
            records = await select_sql("""SELECT StaminaCost, MinimumLevel,DamageMultiplier, Description FROM Melee WHERE ServerId=%s AND AttackName=%s;""", (str(message.guild.id),parsed_string))
            if not records:
                await reply_message(message, "No melee attack found with that name!")
                return
            response = "**MELEE DATA**\n\n"
            for row in records:
                response = response + "Name: " + parsed_string + "\nStamina Cost: " + str(row[0]) + "\nMinimum Level: " + str(row[1]) + "\nDamage Multiplier: " + str(row[2]) + "\nDescription: " + str(row[3]) +  "\n"
            await reply_message(message, response)             
        elif command == 'encountermonster':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to start an encounter!")
                return        
            if server_encounters[message.guild.id]:
                await reply_message(message, "Monster encounter already in progress! There can only be one encounter active per server!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["MonsterName"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'encountermonster'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            menu = await make_simple_menu(message, "Monsters", "MonsterName")
            response = "Please select a monster from the list of monsters below by replying with the ID in bold:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "<@" + str(message.author.id) + "> , please see your DMs for instructions on how to choose a monster.")

        
        elif command == 'newparty':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to create a server party!")
                return        
            if not message.mentions:
                await reply_message(message, "You didn't mention any party members!")
                return
            if server_party[message.guild.id]:
                await reply_message(message, "Server party already exists!")
                return
            server_party[message.guild.id] = message.mentions
            await reply_message(message, "Server party created successfully.")
        elif command == 'newspargroup':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to create a server spar group!")
                return        
            if not message.mentions:
                await reply_message(message, "You didn't mention any spar members!")
                return
            if mass_spar[message.guild.id]:
                await reply_message(message, "Server spar group already exists!")
                return
            mass_spar[message.guild.id] = message.mentions
            for user in mass_spar[message.guild.id]:
                mass_spar_confirm[message.guild.id][user.id] = { }
                mass_spar_confirm[message.guild.id][user.id]["Confirm"] = False
            await reply_message(message, "Spar group created successfully. Mentioned members, please type **=sparconfirm** or **=spardeny** to join or refuse the spar!")
        elif command == 'sparconfirm':
            server_id = message.guild.id
            user_id = message.author.id
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to confirm a spar group!")
                return
            in_party = next((item for item in mass_spar[server_id] if item.id == user_id), None)
            if not in_party:
                await reply_message(message, "You are not in the spar group!")
                return
            mass_spar_confirm[message.guild.id][message.author.id]["Confirm"] = True
            await reply_message(message, "User <@" + str(message.author.id) + "> confirmed spar join!")
        elif command == 'spardeny':
            server_id = message.guild.id
            user_id = message.author.id
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to deny a server spar group!")
                return 
            in_party = next((item for item in mass_spar[server_id] if item.id == user_id), None)
            if not in_party:
                await reply_message(message, "You are not in the spar group!")
                return                
            mass_spar[message.guild.id].remove(message.author)
            await reply_message(message, "User <@" + str(message.author.id) + "> denied the spar and has been removed from the spar!")
            if len(mass_spar[message.guild.id]) <= 1:
                await reply_message(message, "The spar has one member or less, so the spar has been canceled!")
                mass_spar[message.guild.id] = {}
        elif command == 'beginspar':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to start a spar!")
                return
            user_id = message.author.id
            server_id = message.guild.id
            in_party = next((item for item in mass_spar[server_id] if item.id == user_id), None)
            if not in_party:
                await reply_message(message, "You are not in the server party!")
                return
            all_players_ready = True    
            for user in mass_spar[message.guild.id]:
                if not mass_spar_confirm[message.guild.id][user.id]["Confirm"]:
                    all_players_ready = False
            if not all_players_ready:
                response = "Not all players have confirmed. The following players need to confirm spar participation: "
                for user in mass_spar_confirm[message.guild.id]:
                    if not mass_spar_confirm[message.guild.id][user.id]["Confirm"]:
                        response = response + "<@" + str(user.id) + ">, "
                await reply_message(message, response)
                return
            all_players_setchar = True
            for user in mass_spar[message.guild.id]:
                if not mass_spar_chars[message.guild.id][user.id]:
                    all_players_setchar = False
            if not all_players_setchar:
                response = "Not all players have set a spar character. The following players need to set a spar character: "
                for user in mass_spar[message.guild.id]:
                    if not mass_spar_chars[message.guild.id][user.id]:
                        response = response + "<@" + str(user.id) + ">, "
                await reply_message(message, response)
                return
            mass_spar_event[message.guild.id] = True
            mass_spar_turn[message.guild.id] = 0
            await reply_message(message, "The spar has begun! <@" + str(mass_spar[message.guild.id][0].id) + "> gets first blood!")
        elif command == 'castspar':
            server_id = message.guild.id
            user_id = message.author.id
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to cast spells!")
                return            
            if not mass_spar_event[server_id]:
                await reply_message(message, "Why are you casting Magic Missile? There's nothing to attack here!")
                return

            in_party = next((item for item in mass_spar[server_id] if item.id == user_id), None)
            if not in_party:
                await reply_message(message, "You are not in the spar group!")
                return
            if message.author != list(mass_spar[server_id])[mass_spar_turn[server_id]]:
                await reply_message(message, "It's not your turn!")
                return
                

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["SpellId","Target"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'castspar'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            menu = await make_menu(message,"MagicSkills","Spells","SpellId","CharacterId","SpellName", str(mass_spar_chars[server_id][user_id]["CharId"]))
            response = "Please select a spell from the list of your character's spells below by replying with the ID in bold:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "<@" + str(message.author.id) + "> , please see your DMs for instructions on how to cast a spell.")

        elif command == 'getchararms':
            char_name = parsed_string
            if not char_name:
                await reply_message(message, "No character specified!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = []
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            records = await select_sql("""SELECT Id FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s;""",(str(message.guild.id), parsed_string))
            if not records:
                await reply_message(message, "No character found by that name!")
                return
            for row in records:
                char_id = row[0]
            menu = await make_menu(message,"ArmamentInventory","Armaments","ArmamentId","CharacterId","ArmamentName", str(char_id))
            if menu == 'Menu error!':
                menu = "No armaments found."
            response = "**CHARACTER ARMAMENT INVENTORY:**\n\n" + menu             
            await reply_message(message, response)

        elif command == 'meleespar':
            server_id = message.guild.id
            user_id = message.author.id
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to use melee attacks!")
                return            
            if not mass_spar_event[server_id]:
                await reply_message(message, "Why are you casting " + parsed_string + "? There's nothing to attack here!")
                return

            in_party = next((item for item in mass_spar[server_id] if item.id == user_id), None)
            if not in_party:
                await reply_message(message, "You are not in the spar group!")
                return
            if message.author != list(mass_spar[server_id])[mass_spar_turn[server_id]]:
                await reply_message(message, "It's not your turn!")
                return
            
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["AttackId","Target"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'meleespar'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            menu = await make_menu(message,"MeleeSkills","Melee","MeleeId","CharacterId","AttackName", str(mass_spar_chars[server_id][user_id]["CharId"]))
            response = "Please select a spell from the list of your character's attacks below by replying with the ID in bold:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "<@" + str(message.author.id) + "> , please see your DMs for instructions on how to attack.")

        elif command == 'weaponspar':
            server_id = message.guild.id
            user_id = message.author.id
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to use melee attacks!")
                return            
            if not mass_spar_event[server_id]:
                await reply_message(message, "Why are you casting Magic Missile? There's nothing to attack here!")
                return

            in_party = next((item for item in mass_spar[server_id] if item.id == user_id), None)
            if not in_party:
                await reply_message(message, "You are not in the spar group!")
                return
            if message.author != list(mass_spar[server_id])[mass_spar_turn[server_id]]:
                await reply_message(message, "It's not your turn!")
                return
            
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["AttackId","Target"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'weaponspar'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            records = await select_sql("SELECT IFNULL(LeftHandId,'None'),IFNULL(RightHandId,'None') FROM CharacterArmaments Where CharacterId=%s;", (str(mass_spar_chars[server_id][user_id]["CharId"]),))
            if not records:
                await reply_message(message, "Your character has no armaments equipped!")
                return
            for row in records:
                left_hand = row[0]
                right_hand = row[1]
            if left_hand == 'None' and right_hand == 'None':
                await reply_message(message, "Your character has no armaments equipped!")
                return
            records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (left_hand,))
            for row in records:
                left_name = row[0]
            records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (right_hand,))
            for row in records:
                right_name = row[0]
            try: left_name
            except: left_name = 'None'
            try: right_name
            except: right_name = 'None'
            menu = "Armaments Equipped:\n\n" + left_hand + " - " + left_name + "\n" + right_hand + " - " + right_name
            response = "Please select an armament from the list of your character's equipment below by replying with the ID in bold:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "<@" + str(message.author.id) + "> , please see your DMs for instructions on how to attack.")

        elif command == 'setsparchar':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to set a sparring character!")
                return        
            if str(message.author.id) not in str(mass_spar[message.guild.id]):
                await reply_message(message, "You're not part of the spar group!")
                return
            name_re = re.compile(r"(?P<name>.+) (?P<lastname>.+)")
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'setsparchar'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId", str(message.author.id))
            await direct_message(message, "Please reply to this message with the ID in bold of the character you wish to spar with.\n\n**CHARACTER LIST**\n\n" + menu)
            await reply_message(message, "<@" + str(message.author.id) + "> , please check your DMs to select a character.")
        elif command == 'disbandparty':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to disband a party!")
                return        
            if server_encounters[message.guild.id]:
                await reply_message(message, "There's a server encounter in progress. Cannot disband!")
                return
            server_party[message.guild.id].clear()
            await reply_message(message, "Server party disbanded.")
        elif command == 'listparty':
            if not server_party[message.guild.id]:
                await reply_message(message, "No party currently exists!")
                return
            response = "***SERVER PARTY***\n\n"
            for party_member in server_party[message.guild.id]:
                if party_member.nick:
                    name = party_member.nick
                else:
                    name = party_member.name
                    
                response = response + name + "\n"
            await reply_message(message, response)
        elif command == 'abortencounter':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to abort an encounter!")
                return        
            server_encounters[message.guild.id] = False
            await reply_message(message, "Encounter aborted. No health will be deducted and no XP will be gained.")
        elif command == 'setencounterchar':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to set an encounter character!")
                return        
            if str(message.author.id) not in str(server_party[message.guild.id]):
                await reply_message(message, "You're not part of the server party!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'setencounterchar'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId", str(message.author.id))
            await direct_message(message, "Please reply to this message with the ID in bold of the character you wish to join the party with.\n\n**CHARACTER LIST**\n\n" + menu)
            await reply_message(message, "Please check your DMs for instructions on how to choose a character, <@" + str(message.author.id) + "> .")
        elif command == 'monsterattack':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to attack with the monster!")
                return        
            server_id = message.guild.id
            if not server_encounters[server_id]:
                await reply_message(message, "No encounter in progress!")
                return
            target = random.choice(list(server_party_chars[server_id].keys()))
            attack_text = " " + str(server_monsters[server_id]["MonsterName"]) + " attacks " + str(server_party_chars[server_id][target]["CharName"]) + "!"
            await post_webhook(message.channel, server_monsters[server_id]["MonsterName"], attack_text, server_monsters[server_id]["PictureLink"])
  #          await reply_message(message, " " + str(server_monsters[server_id]["MonsterName"]) + " attacks " + str(server_party_chars[server_id][target]["CharName"]) + "!")
            dodge = await calculate_dodge(server_monsters[server_id]["Level"], server_party_chars[server_id][target]["Agility"])
            if dodge:
                dodge_text = server_party_chars[server_id][target]["CharName"] + " dodged the attack! No damage taken!"
                await post_webhook(message.channel, server_party_chars[server_id][target]["CharName"], dodge_text, server_party_chars[server_id][target]["PictureLink"])
                # await reply_message(message, server_party_chars[server_id][target]["CharName"] + " dodged the attack! No damage taken!")
                return
            else:
                damage = await calculate_damage(server_monsters[server_id]["Attack"], server_party_chars[server_id][target]["Defense"], random.randint(1,5), server_monsters[server_id]["Level"], server_party_chars[server_id][target]["Level"])
                server_party_chars[server_id][target]["Health"] = int(server_party_chars[server_id][target]["Health"] - damage)
                hit_text = server_party_chars[server_id][target]["CharName"] + " was hit by " + server_monsters[server_id]["MonsterName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(server_party_chars[server_id][target]["Health"]) + "!"
                await post_webhook(message.channel, server_party_chars[server_id][target]["CharName"], hit_text, server_party_chars[server_id][target]["PictureLink"])
 #               await reply_message(message, server_party_chars[server_id][target]["CharName"] + " was hit by " + server_monsters[server_id]["MonsterName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(server_party_chars[server_id][target]["Health"]))
                if server_party_chars[server_id][target]["Health"] < 1:
                    await reply_message(message, server_party_chars[server_id][target]["CharName"] + " has no health left and is out of the fight!")
                    del server_party_chars[server_id][target]
                if len(server_party_chars[server_id]) < 1:
                    await reply_message(message, "The party has been vanquished! " +server_monsters[server_id]["MonsterName"] + " wins! No experience will be awarded.")
                    server_encounters[server_id] = False
                    
        elif command == 'castmonster':
            server_id = message.guild.id
            user_id = message.author.id
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to cast spells!")
                return            
            if not server_encounters[server_id]:
                await reply_message(message, "Why are you casting " + parsed_string + "? There's nothing to attack here!")
                return

            in_party = next((item for item in server_party[server_id] if item.id == user_id), None)
            if not in_party:
                await reply_message(message, "You are not in the server party!")
                return
            if message.author != list(server_party[server_id])[encounter_turn[server_id]]:
                await reply_message(message, "It's not your turn!")
                return
            menu = await make_menu(message,"MagicSkills","Spells","SpellId","CharacterId","SpellName", str(server_party_chars[server_id][user_id]["CharId"]))
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["SpellId"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'castmonster'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            response = "Please select a spell from the list of your character's spells below by replying with the ID in bold:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "<@" + str(message.author.id) + "> , please see your DMs for instructions on how to cast a spell.")

        elif command == 'meleemonster':
            server_id = message.guild.id
            user_id = message.author.id
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to cast spells!")
                return            
            if not server_encounters[server_id]:
                await reply_message(message, "Why are you casting Magic Missile? There's nothing to attack here!")
                return

            in_party = next((item for item in server_party[server_id] if item.id == user_id), None)
            if not in_party:
                await reply_message(message, "You are not in the server party!")
                return
            if message.author != list(server_party[server_id])[encounter_turn[server_id]]:
                await reply_message(message, "It's not your turn!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["MeleeId"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'meleemonster'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            menu = await make_menu(message,"MeleeSkills","Melee","MeleeId","CharacterId","AttackName", str(server_party_chars[server_id][user_id]["CharId"]))
            response = "Please select a spell from the list of your character's attacks below by replying with the ID in bold:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "<@" + str(message.author.id) + "> , please see your DMs for instructions on how to attack.")

        elif command == 'weaponmonster':
            server_id = message.guild.id
            user_id = message.author.id
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to cast spells!")
                return            
            if not server_encounters[server_id]:
                await reply_message(message, "Why are you casting Magic Missle? There's nothing to attack here!")
                return

            in_party = next((item for item in server_party[server_id] if item.id == user_id), None)
            if not in_party:
                await reply_message(message, "You are not in the server party!")
                return
            if message.author != list(server_party[server_id])[encounter_turn[server_id]]:
                await reply_message(message, "It's not your turn!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["ArmamentId"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'weaponmonster'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            records = await select_sql("SELECT IFNULL(LeftHandId,'None'),IFNULL(RightHandId,'None') FROM CharacterArmaments Where CharacterId=%s;", (str(server_party_chars[server_id][user_id]["CharId"]),))
            if not records:
                await reply_message(message, "Your character has no armaments equipped!")
                return
            for row in records:
                left_hand = row[0]
                right_hand = row[1]
            if left_hand == 'None' and right_hand == 'None':
                await reply_message(message, "Your character has no armaments equipped!")
                return
            records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (left_hand,))
            for row in records:
                left_name = row[0]
            records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (right_hand,))
            for row in records:
                right_name = row[0]
            try: left_name
            except: left_name = 'None'
            try: right_name
            except: right_name = 'None'
            menu = "Armaments Equipped:\n\n" + left_hand + " - " + left_name + "\n" + right_hand + " - " + right_name
            response = "Please select an armament from the list of your character's equipment below by replying with the ID in bold:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "<@" + str(message.author.id) + "> , please see your DMs for instructions on how to attack.")
        elif command == 'getmonstertemplate':
            response = "***NEW MONSTER TEMPLATE***\n\n=newmonster Monster Name: \nDescription: \nHealth: \nLevel: \nAttack: \nDefense: \nElement: \nMagic Power: \nPicture Link: \n"
            await reply_message(message, response)

        elif command == 'addstatpoints':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to add stat points!")
                return
            if not available_points[message.guild.id][message.author.id]:
                await reply_message(message, "You have no available points!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterName","StatMod","Modifier"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'addstatpoints'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId", str(message.author.id))
            response = "Please select a character to add points to from the list of your characters below by replying with the ID in bold:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "<@" + str(message.author.id) + "> , please see your DMs for instructions on how to add stat points.")                


        elif command == 'setgmrole':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to set other roles!")
                return
            if len(message.role_mentions) > 1:
                await reply_message(message, "Only one role can be defined as the GM role!")
                return
            role_id = message.role_mentions[0].id
            guild_settings[message.guild.id]["GameModeratorRole"] = role_id
            result = await commit_sql("""UPDATE GuildSettings SET GameModeratorRole=%s WHERE ServerId=%s;""", (str(role_id), str(message.guild.id)))
            if result:
                await reply_message(message, "GM role successfully set!")
            else:
                await reply_message(message, "Database error!")            

        elif command == 'setplayerrole':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to set other roles!")
                return
            if len(message.role_mentions) > 1:
                await reply_message(message, "Only one role can be defined as the player role!")
                return
            role_id = message.role_mentions[0].id
            guild_settings[message.guild.id]["PlayerRole"] = role_id
            result = await commit_sql("""UPDATE GuildSettings SET PlayerRole=%s WHERE ServerId=%s;""", (str(role_id),str(message.guild.id)))
            if result:
                await reply_message(message, "Player role successfully set!")
            else:
                await reply_message(message, "Database error!") 
        elif command == 'setaltrole':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to set other roles!")
                return        
            if len(message.role_mentions) > 1:
                await reply_message(message, "Only one role can be defined as the GM role!")
                return
            role_id = message.role_mentions[0].id
            guild_settings[message.guild.id]["NPCRole"] = role_id
            result = await commit_sql("""UPDATE GuildSettings SET NPCRole=%s WHERE ServerId=%s;""", (str(role_id),str(message.guild.id)))
            if result:
                await reply_message(message, "NPC role successfully set!")
            else:
                await reply_message(message, "Database error!")
        elif command == 'listroles':
            records = await select_sql("""SELECT IFNULL(AdminRole,'0'),IFNULL(GameModeratorRole,'0'),IFNULL(NPCRole, '0'),IFNULL(PlayerRole,'0') FROM GuildSettings WHERE ServerId=%s;""", (str(message.guild.id),))
            if not records:
                await reply_message(message, "Database error!")
                return
            for row in records:
                
                admin_role = message.guild.get_role(int(row[0]))
                gm_role = message.guild.get_role(int(row[1]))
                alt_role = message.guild.get_role(int(row[2]))
                player_role = message.guild.get_role(int(row[3]))
            response = "**Server Roles**\n\n**Admin Role:** " + str(admin_role) + "\n**Game Moderator Role:** " + str(gm_role) + "\n**Alt Role:** " + str(alt_role) + "\n**Player Role:** " + str(player_role) + "\n"
            await reply_message(message, response)
        elif  command == 'loaddefault':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to set other roles!")
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
            await reply_message(message, "Done!")
        elif command == 'setbank':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to set the bank assets!")
                return    
            if not parsed_string:
                await reply_message(message, "You did not set a bank asset total!")
                return
            result = await commit_sql("""UPDATE GuildSettings SET GuildBankBalance=%s WHERE ServerId=%s""", (str(parsed_string), str(message.guild.id)))
            if result:
                await reply_message(message, "Guild bank balance set successfully!")
            else:
                await reply_message(message, "Database error!")
        elif command == 'listsetup':
            server_id = message.guild.id
            records = await select_sql("""SELECT ServerId,IFNULL(AdminRole,'0'),IFNULL(GameModeratorRole,'0'),IFNULL(NPCRole,'0'),IFNULL(PlayerRole,'0'),IFNULL(GuildBankBalance,'0'),IFNULL(StartingHealth,'0'),IFNULL(StartingMana,'0'),IFNULL(StartingStamina,'0'),IFNULL(StartingAttack,'0'),IFNULL(StartingDefense,'0'),IFNULL(StartingMagicAttack,'0'),IFNULL(StartingAgility,'0'),IFNULL(StartingIntellect,'0'),IFNULL(StartingCharisma,'0'),IFNULL(HealthLevelRatio,'0'),IFNULL(ManaLevelRatio,'0'),IFNULL(StaminaLevelRatio,'0'),IFNULL(XPLevelRatio,'0'),IFNULL(HealthAutoHeal,'0'),IFNULL(ManaAutoHeal,'0'),IFNULL(StaminaAutoHeal,'0') FROM GuildSettings WHERE ServerId=%s;""",(str(message.guild.id),))
            if not records:
                await reply_message(message, "Not all settings found. Please run =newsetup to initialize all settings.")
                return
            for row in records:
                guild_settings[server_id]["AdminRole"] = int(row[1])
                guild_settings[server_id]["GameModeratorRole"] = int(row[2])
                guild_settings[server_id]["NPCRole"] = int(row[3])
                guild_settings[server_id]["PlayerRole"] = int(row[4])
                guild_settings[server_id]["GuildBankBalance"] = float(row[5])
                guild_settings[server_id]["StartingHealth"] = int(row[6])
                guild_settings[server_id]["StartingMana"] = int(row[7])
                guild_settings[server_id]["StartingStamina"] = int(row[8])
                guild_settings[server_id]["StartingAttack"] = int(row[9])
                guild_settings[server_id]["StartingDefense"] = int(row[10])
                guild_settings[server_id]["StartingMagicAttack"] = int(row[11])
                guild_settings[server_id]["StartingAgility"] = int(row[12])
                guild_settings[server_id]["StartingIntellect"] = int(row[13])
                guild_settings[server_id]["StartingCharisma"] = int(row[14])
                guild_settings[server_id]["HealthLevelRatio"] = int(row[15])
                guild_settings[server_id]["ManaLevelRatio"] = int(row[16])
                guild_settings[server_id]["StaminaLevelRatio"] = int(row[17])
                guild_settings[server_id]["XPLevelRatio"] = int(row[18])
                guild_settings[server_id]["HealthAutoHeal"] = float(row[19])
                guild_settings[server_id]["ManaAutoHeal"] = float(row[20])
                guild_settings[server_id]["StaminaAutoHeal"] = float(row[21])
            response = "**CURRENT SERVER SETTINGS**\n\n"
            for setting in list(guild_settings[server_id].keys()):
                if guild_settings[message.guild.id][setting] == 0:
                    setting_value = "Not set or 0"
                else:
                    setting_value = str(guild_settings[message.guild.id][setting])
                response = response + "**" + setting + ":** " + setting_value +  "\n"
            await reply_message(message, response)
            
        elif command == 'newsetup':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to perform initial setup!")
                return            
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            
            dm_tracker[message.author.id]["fieldlist"] = ["ServerId","GuildBankBalance","StartingHealth","StartingMana","StartingStamina","StartingAttack","StartingDefense","StartingMagicAttack","StartingAgility","StartingIntellect","StartingCharisma","HealthLevelRatio","ManaLevelRatio","StaminaLevelRatio","XPLevelRatio","HealthAutoHeal","ManaAutoHeal","StaminaAutoHeal"]
            dm_tracker[message.author.id]["currentfield"] = 1
            dm_tracker[message.author.id]["fielddict"]= [str(message.guild.id),"1000000","200","100","100","10","5","10","10","10","10","200","100","100","20","0.2","0.1","0.1"]
            dm_tracker[message.author.id]["currentcommand"] = 'editsetup'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = message.guild.id

            await reply_message(message, "Please check your DMs for instructions on how to edit server setup, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested to edit the server setup. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the monster will be updated!\nThe first field is **" + dm_tracker[message.author.id]["fieldlist"][1] + "** and its current value is **" + dm_tracker[message.author.id]["fielddict"][1] + "**.")
        elif command == 'editsetup':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to edit setup!")
                return            
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            
            dm_tracker[message.author.id]["fieldlist"] = ["ServerId","GuildBankBalance","StartingHealth","StartingMana","StartingStamina","StartingAttack","StartingDefense","StartingMagicAttack","StartingAgility","StartingIntellect","StartingCharisma","HealthLevelRatio","ManaLevelRatio","StaminaLevelRatio","XPLevelRatio","HealthAutoHeal","ManaAutoHeal","StaminaAutoHeal"]
            dm_tracker[message.author.id]["currentfield"] = 1
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'editsetup'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = message.guild.id 

            records = await select_sql("""SELECT ServerId,StartingHealth,StartingMana,StartingStamina,StartingAttack,StartingDefense,StartingMagicAttack,StartingAgility,StartingIntellect,StartingCharisma,HealthLevelRatio,ManaLevelRatio,StaminaLevelRatio,XPLevelRatio,HealthAutoHeal,ManaAutoHeal,StaminaAutoHeal FROM GuildSettings WHERE ServerId=%s;""", (str(message.guild.id),))
            counter = 0
            for row in records:
                for field in dm_tracker[message.author.id]["fieldlist"]:
                    dm_tracker[message.author.id]["fielddict"].append(row[counter])
                    counter = counter + 1
                    if counter < len(dm_tracker[message.author.id]["fieldlist"]) - 2:
                        break
                        
            await reply_message(message, "Please check your DMs for instructions on how to edit server setup, <@" + str(message.author.id) + ">.")
            
            await direct_message(message, "You have requested to edit the server setup. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the monster will be updated!\nThe first field is **" + dm_tracker[message.author.id]["fieldlist"][1] + "** and its current value is **" + dm_tracker[message.author.id]["fielddict"][1] + "**.")
        elif command == 'sendcurrency':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to send currency!")
                return
                
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterId","TargetId","Currency"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'sendcurrency'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId", str(message.author.id))
            await direct_message(message, "Please reply to this message with the ID in bold of the character you wish to send currency from.\n\n**CHARACTER LIST**\n\n" + menu)
            await reply_message(message, "Please check your DMs for instructions on how to send currency, <@" + str(message.author.id) + "> .")            
            
        elif command == 'addplayer':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to add players!")
                return
            if not message.mentions:
                await reply_message(message, "You didn't specify any users to add!")
                return
            role = discord.utils.get(message.guild.roles, id=guild_settings[message.guild.id]["PlayerRole"])
            for user in message.mentions:
                await user.add_roles(role)
            await reply_message(message, "Users added to player role!")
        elif command == 'addgm':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to add Game Moderators!")
                return
            if not message.mentions:
                await reply_message(message, "You didn't specify any users to add!")
                return
            role = discord.utils.get(message.guild.roles, id=guild_settings[message.guild.id]["GameModeratorRole"])
            for user in message.mentions:
                await user.add_roles(role)
            await reply_message(message, "Users added to GM role!")                
        elif command == 'addaltuser':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to add Alt Managers!")
                return
            if not message.mentions:
                await reply_message(message, "You didn't specify any users to add!")
                return
            role = discord.utils.get(message.guild.roles, id=guild_settings[message.guild.id]["NPCRole"])
            for user in message.mentions:
                await user.add_roles(role)
            await reply_message(message, "Users added to NPC role!")                
        elif command == 'addadmin':
            if message.author != message.guild.owner:
                await reply_message(message, "Only the server owner can add admins!")
                return
            if not message.mentions:
                await reply_message(message, "You didn't specify any users to add!")
                return
            role = discord.utils.get(message.guild.roles, id=guild_settings[message.guild.id]["AdminRole"])
            for user in message.mentions:
                await user.add_roles(role)
            await reply_message(message, "Users added to admin role!")                 
        elif command == 'deleteplayer':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to remove players!")
                return
            if not message.mentions:
                await reply_message(message, "You didn't specify any users to remove!")
                return
            role = discord.utils.get(message.guild.roles, id=guild_settings[message.guild.id]["PlayerRole"])
            for user in message.mentions:
                await user.remove_roles(role)
            await reply_message(message, "Users removed from player role!")                
        elif command == 'deletegm':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to remove game moderators!")
                return 
            if not message.mentions:
                await reply_message(message, "You didn't specify any users to remove!")
                return
            role = discord.utils.get(message.guild.roles, id=guild_settings[message.guild.id]["GameModeratorRole"])
            for user in message.mentions:
                await user.remove_roles(role)
            await reply_message(message, "Users removed from GM role!")                    
        elif command == 'deletealtuser':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to remove Alt Managers!")
                return 
            if not message.mentions:
                await reply_message(message, "You didn't specify any users to remove!")
                return
            role = discord.utils.get(message.guild.roles, id=guild_settings[message.guild.id]["NPCRole"])
            for user in message.mentions:
                await user.remove_roles(role)
            await reply_message(message, "Users removed from NPC role!")                    
        elif command == 'deleteadmin':
            if message.author != message.guild.owner:
                await reply_message(message, "Only the server owner can delete admins!")
                return
            if not message.mentions:
                await reply_message(message, "You didn't specify any users to remove!")
                return
            role = discord.utils.get(message.guild.roles, id=guild_settings[message.guild.id]["AdminRole"])
            for user in message.mentions:
                await user.remove_roles(role)
            await reply_message(message, "Users removed from admin role!") 
        elif command == 'resetserver':
            if message.author != message.guild.owner:
                await reply_message(message, "Only the server owner can wipe all server data!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            
            dm_tracker[message.author.id]["fieldlist"] = ["Confirm"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"]= []
            dm_tracker[message.author.id]["currentcommand"] = 'resetserver'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            await reply_message(message, "**WARNING! THIS WILL WIPE ALL SERVER SETTINGS, INCLUDING CHARACTERS, ITEMS, VENDORS, SPELLS, MONSTERS, MELEE ATTACKS, AND SERVER SETTINGS FROM THE BOT! PLEASE REPLY TO THE DM WITH** ```CONFIRM``` **TO PROCEED.**")
            await direct_message(message, "**WARNING! THIS WILL WIPE ALL SERVER SETTINGS, INCLUDING CHARACTERS, ITEMS, VENDORS, SPELLS, MONSTERS, MELEE ATTACKS, AND SERVER SETTINGS FROM THE BOT! PLEASE REPLY TO THE DM WITH** ```CONFIRM``` **TO PROCEED.**\n\nAre you sure you want to do this?")
        elif command == 'newcustomprofile':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to set the bank assets!")
                return
            if not parsed_string:
                await reply_message(message, "No fields were specified for the custom profile!")
                return
            fields = parsed_string.split(',')
            field_name = " "
            for line in fields:
                field_name = field_name + line.split('=')[0] + ","
            custom_profile_entry = """INSERT INTO CustomProfiles (ServerId, Fields) VALUES (%s,%s);"""
            result = await commit_sql(custom_profile_entry, (str(message.guild.id), field_name))
            if not result:
                await reply_message(mesage, "Could not create custom profile!")
                return
            create_custom_profile = "CREATE TABLE " + re.sub(r"[^A-Za-z0-9]","",message.guild.name) + str(message.guild.id) + " (Id int auto_increment, ServerId varchar(40), UserId varchar(40), Name TEXT, "
            custom_profile_tuple = (str(message.guild.id), str(message.author.id), "Name")
            display_name_entry = "INSERT INTO " + re.sub(r"[^A-Za-z0-9]","",message.guild.name) + str(message.guild.id) + " (ServerId, UserId, Name, " 
            display_name_values = " VALUES (%s, %s, %s, "
            for field in fields:
                split_fields = field.split('=')
                display_name = split_fields[1]
                create_custom_profile = create_custom_profile + split_fields[0] + " TEXT, "
                custom_profile_tuple = custom_profile_tuple + (display_name,)
                display_name_values = display_name_values + "%s, "
                display_name_entry = display_name_entry + split_fields[0] + ", "
            create_custom_profile = create_custom_profile + " PRIMARY KEY(Id));"
            await log_message("SQL: " + create_custom_profile)
            result = await execute_sql(create_custom_profile)
            if result:
                await reply_message(message, "Custom profile for server successfully created!")
            else:
                await reply_message(message, "Database error! Please ensure your field names have no spaces and are separated by commas!")
            
            display_name_entry = re.sub(r", $","", display_name_entry) + ")" + re.sub(r", $","", display_name_values) + ");"
            
            result = await commit_sql(display_name_entry, custom_profile_tuple)
            if result:
                await reply_message(message, "Display names for fields set successfully.")
            else:
                await reply_message(message, "Database error!")
        elif command == 'invite':
            await reply_message(message,"`Click here to invite RP Mastermind:` https://discordapp.com/api/oauth2/authorize?client_id=691353869841596446&permissions=805829696&scope=bot")
        else:
            pass        


client.run('REDACTED')

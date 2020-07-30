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
import json
import decimal
import asyncio
import aiohttp

webhook = {}
client = discord.Client(heartbeat_timeout=600)
server_monsters = {}
server_encounters = {}
encounter_turn = {0: 0}
server_party = {}
server_party_chars = {}
guild_settings = {}
monster_health = {}
mass_spar = {}
mass_spar_chars = {}
mass_spar_event = {}
mass_spar_turn = {0: 0}
mass_spar_confirm = {}
mass_spar_cooldown = {}
mass_spar_cooldown_turns = 3
alt_aliases = {}
dm_tracker = {}
fallen_chars = {}
narrator_url = "https://cdn.discordapp.com/attachments/701796158691082270/703247309613301790/header-brilliant-game-of-thrones-and-princess-bride-mashup-video.jpg"
npc_aliases = {}
daily = {}
custom_commands = {}
critter_spawn = {}
allowed_ids = {}
active_chars = {}
new_startup = True
connection = mysql.connector.connect(host='localhost', database='CharaTron', user='REDACTED', password='REDACTED')


def reconnect_db():
    global connection
    if connection is None or not connection.is_connected():
        connection = mysql.connector.connect(host='localhost', database='CharaTron', user='REDACTED',
                                             password='REDACTED')
    return connection


async def log_message(log_entry):
    current_time_obj = datetime.now()
    current_time_string = current_time_obj.strftime("%b %d, %Y-%H:%M:%S.%f")
    print(current_time_string + " - " + log_entry, flush=True)


async def commit_sql(sql_query, params=None):
    global connection
    await log_message("Commit SQL: " + sql_query + "\n" + "Parameters: " + str(params))
    try:
        cconnection = reconnect_db()
        cursor = connection.cursor()
        result = cursor.execute(sql_query, params)
        connection.commit()
        return True
    except mysql.connector.Error as error:
        await log_message("Database error! " + str(error))
        return False


async def select_sql(sql_query, params=None):
    global connection
    if sql_query != 'SELECT UsersAllowed, CharName, PictureLink FROM Alts WHERE ServerId=%s AND Shortcut=%s;' and sql_query != 'SELECT Id,CharacterName,Currency,Experience FROM CharacterProfiles WHERE ServerId=%s AND UserId=%s;':
        await log_message("Select SQL: " + sql_query + "\n" + "Parameters: " + str(params))
    try:
        connection = reconnect_db()
        cursor = connection.cursor()
        result = cursor.execute(sql_query, params)
        records = cursor.fetchall()
        if sql_query != 'SELECT UsersAllowed, CharName, PictureLink FROM Alts WHERE ServerId=%s AND Shortcut=%s;' and sql_query != 'SELECT Id,CharacterName,Currency,Experience FROM CharacterProfiles WHERE ServerId=%s AND UserId=%s;':
            await log_message("Returned " + str(records))
        return records
    except mysql.connector.Error as error:
        await log_message("Database error! " + str(error))
        return None


async def execute_sql(sql_query):
    global connection
    try:
        connection = reconnect_db()
        cursor = connection.cursor()
        result = cursor.execute(sql_query)
        return True
    except mysql.connector.Error as error:
        await log_message("Database error! " + str(error))
        return False


async def direct_message(message, response, embed=None):
    channel = await message.author.create_dm()
    await log_message("replied to user " + message.author.name + " in DM with " + response)
    if embed:
        await channel.send(embed=embed)
    else:
        try:
            message_chunks = [response[i:i + 1900] for i in range(0, len(response), 1900)]
            for chunk in message_chunks:
                await channel.send(">>> " + chunk)
                await asyncio.sleep(1)

        except discord.errors.Forbidden:
            await dm_tracker[message.author.id]["commandchannel"].send(
                ">>> You have DMs off. Please reply with =answer <reply> in the server channel.\n" + response)


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

    await log_message(
        "Message sent back to server " + server_name + " channel " + channel_name + " in response to user " + message.author.name + "\n\n" + response)

    message_chunks = [response[i:i + 1900] for i in range(0, len(response), 1900)]
    for chunk in message_chunks:
        await message.channel.send(">>> " + chunk)
        await asyncio.sleep(1)


async def admin_check(userid):
    if (userid != 610335542780887050):
        await log_message(str(userid) + " tried to call an admin message!")
        return False
    else:
        return True


async def calculate_damage(attack, defense, damage_multiplier, attacker_level, target_level):
    total_attack_power = attack * damage_multiplier + random.randint(-5, 5)

    effective_attack_power = total_attack_power
    total_damage = (effective_attack_power - defense)
    if total_damage < 20:
        total_damage = 20
    return int(total_damage)


async def calculate_dodge(attacker_agility, target_agility):
    dodge_chance = random.randint(0, target_agility)
    hit_chance = random.randint(0, attacker_agility)

    if hit_chance >= dodge_chance:
        return False
    else:
        return True


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
    global allowed_ids
    try:
        del allowed_ids[author_id]
    except:
        pass
    dm_tracker[author_id] = {}
    dm_tracker[author_id]["currentcommand"] = " "
    dm_tracker[author_id]["currentfield"] = 0
    dm_tracker[author_id]["fieldlist"] = []
    dm_tracker[author_id]["fielddict"] = []
    dm_tracker[author_id]["server_id"] = 0
    dm_tracker[author_id]["commandchannel"] = 0
    dm_tracker[author_id]["parameters"] = " "
    dm_tracker[author_id]["fieldmeans"] = []


async def ai_castspar(message):
    global mass_spar_chars
    global dm_tracker
    global client
    global fallen_chars

    user_id = client.user.id
    server_id = dm_tracker[message.author.id]["server_id"]

    target_id = message.author.id
    records = await select_sql(
        """SELECT Id,ManaCost,MinimumLevel,DamageMultiplier,SpellName,PictureLink FROM Spells WHERE ServerId=%s ORDER BY RAND ( ) LIMIT 1;""",
        (str(server_id),))
    if not records:
        await dm_tracker[message.author.id]["commandchannel"].send(">>> No spells defined! Try again.")
        return
    else:
        for row in records:
            spell_id = row[0]
            mana_cost = int(row[1])
            min_level = int(row[2])
            damage_multiplier = int(row[3])
            parsed_string = row[4]
            picture_link = row[5]

    if mass_spar_chars[server_id][user_id]["Mana"] < mana_cost:
        await dm_tracker[message.author.id]["commandchannel"].send(
            ">>> The AI does not have sufficient mana for this spell!")
        return

    mass_spar_chars[server_id][user_id]["Mana"] = mass_spar_chars[server_id][user_id]["Mana"] - mana_cost
    attack_text = "" + str(mass_spar_chars[server_id][user_id]["CharName"]) + " attacks " + str(
        mass_spar_chars[server_id][target_id]["CharName"]) + " with " + parsed_string + "!\nThis drained " + str(
        mana_cost) + " from " + mass_spar_chars[server_id][user_id]["CharName"] + ", leaving them with " + str(
        mass_spar_chars[server_id][user_id]["Mana"]) + " mana!\n\n"
    embed = discord.Embed(title=attack_text)
    if picture_link.startswith('http'):
        embed.set_thumbnail(url=picture_link)
    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
    await asyncio.sleep(1)

    dodge = await calculate_dodge(mass_spar_chars[server_id][user_id]["Agility"],
                                  mass_spar_chars[server_id][target_id]["Agility"])
    if dodge:

        dodge_text = "" + mass_spar_chars[server_id][target_id]["CharName"] + " dodged the attack! No damage taken!"
        embed = discord.Embed(title=dodge_text)
        if mass_spar_chars[server_id][target_id]["PictureLink"].startswith('http'):
            embed.set_thumbnail(url=mass_spar_chars[server_id][target_id]["PictureLink"])
        await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
        await asyncio.sleep(1)
    else:
        damage = await calculate_damage(mass_spar_chars[server_id][user_id]["MagicAttack"],
                                        mass_spar_chars[server_id][target_id]["Defense"], damage_multiplier,
                                        mass_spar_chars[server_id][user_id]["Level"],
                                        mass_spar_chars[server_id][target_id]["Level"])
        mass_spar_chars[server_id][target_id]["Health"] = mass_spar_chars[server_id][target_id]["Health"] - damage
        mass_spar_chars[server_id][user_id]["TotalDamage"] = mass_spar_chars[server_id][user_id]["TotalDamage"] + damage
        hit_text = "" + mass_spar_chars[server_id][target_id]["CharName"] + " was hit by " + \
                   mass_spar_chars[server_id][user_id]["CharName"] + " for " + str(
            damage) + " points!\n\nHealth now at " + str(mass_spar_chars[server_id][target_id]["Health"]) + "!"
        embed = discord.Embed(title=hit_text)
        if mass_spar_chars[server_id][target_id]["PictureLink"].startswith('http'):
            embed.set_thumbnail(url=mass_spar_chars[server_id][target_id]["PictureLink"])
        await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
        await asyncio.sleep(1)
        if mass_spar_chars[server_id][target_id]["Health"] < 1:

            out_text = "" + mass_spar_chars[server_id][target_id][
                "CharName"] + " has no health left and is out of the fight! The AI wins!"
            embed = discord.Embed(title=out_text)
            if mass_spar_chars[server_id][target_id]["PictureLink"].startswith('http'):
                embed.set_thumbnail(url=mass_spar_chars[server_id][target_id]["PictureLink"])
            await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
            await asyncio.sleep(1)

            fallen_chars[server_id] = {}
            fallen_chars[server_id] = [mass_spar_chars[server_id][message.author.id], ]

            response = "<@" + str(
                message.author.id) + "> is the last one standing and is the spar winner!\n\n**Experience gained:**\n\n"
            for char in fallen_chars[server_id]:

                char_id = char
                await log_message("Level " + str(char["Level"]))
                new_xp = await calculate_xp(char["Level"],
                                            char["Level"],
                                            char["TotalDamage"], 1) * 2
                response = response + "*" + char["CharName"] + "*: " + str(new_xp) + "\n"
                records = await select_sql("""SELECT Experience FROM CharacterProfiles WHERE Id=%s;""",
                                           (str(char["CharId"]),))
                for row in records:
                    old_xp = int(row[0])
                total_xp = old_xp + new_xp
                if total_xp > (guild_settings[server_id]["XPLevelRatio"] * char["Level"]):
                    char["Level"] = char["Level"] + 1
                    records = await select_sql("""SELECT StatPoints FROM CharacterProfiles WHERE Id=%s;""",
                                               (str(char["CharId"]),))
                    for row in records:
                        stat_points = int(row[0])

                    available_points = int(guild_settings[server_id]["StatPointsPerLevel"]) + stat_points
                    response = response + "**" + char[
                        "CharName"] + "** LEVELED UP TO LEVEL **" + str(
                        char["Level"]) + "!**\nYou have " + str(
                        available_points) + " stat points to spend!\n\n"
                    total_xp = 0
                    health = fallen_chars[server_id][user_id]["MaxHealth"] + guild_settings[server_id]["HealthLevelAdd"]
                    stamina = fallen_chars[server_id][user_id]["MaxStamina"] + guild_settings[server_id][
                        "StaminaLevelAdd"]
                    mana = fallen_chars[server_id][user_id]["MaxMana"] + guild_settings[server_id]["ManaLevelAdd"]
                    result = await commit_sql(
                        """UPDATE CharacterProfiles SET Level=%s,Experience=%s,Health=%s,Stamina=%s,Mana=%s,StatPoints=%s WHERE Id=%s;""",
                        (str(fallen_chars[server_id][target_id]["Level"] + 1), str(total_xp), str(health), str(stamina),
                         str(mana), str(available_points), str(fallen_chars[server_id][target_id]["CharId"])))
            mass_spar_event[server_id] = False

            for x in mass_spar_chars[server_id].keys():
                del mass_spar_chars[server_id][x]
            for x in mass_spar[server_id].keys():
                del mass_spar[server_id][x]

            embed = discord.Embed(title="Results", description=response)
            await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
            await asyncio.sleep(1)


async def ai_meleespar(message):
    global mass_spar_chars
    global dm_tracker
    global client
    global fallen_chars
    server_id = dm_tracker[message.author.id]["server_id"]

    user_id = client.user.id
    target_id = message.author.id
    records = await select_sql(
        """SELECT Id,StaminaCost,MinimumLevel,DamageMultiplier,AttackName,PictureLink FROM Melee WHERE ServerId=%s ORDER BY RAND () LIMIT 1;""",
        (str(server_id),))

    for row in records:
        melee_id = row[0]
        stamina_cost = int(row[1])
        min_level = int(row[2])
        damage_multiplier = int(row[3])
        parsed_string = row[4]
        picture_link = row[5]

    if mass_spar_chars[server_id][user_id]["Stamina"] < stamina_cost:
        await dm_tracker[message.author.id]["commandchannel"].send(
            ">>> The AI does not have sufficient stamina for this melee.")
        return

    mass_spar_chars[server_id][user_id]["Stamina"] = mass_spar_chars[server_id][user_id]["Stamina"] - stamina_cost

    attack_text = "" + str(mass_spar_chars[server_id][user_id]["CharName"]) + " attacks " + str(
        mass_spar_chars[server_id][target_id]["CharName"]) + " with " + parsed_string + "!\nThis drained " + str(
        stamina_cost) + " from " + mass_spar_chars[server_id][user_id]["CharName"] + ", leaving them with " + str(
        mass_spar_chars[server_id][user_id]["Stamina"]) + " stamina!\n\n"
    embed = discord.Embed(title=attack_text)
    if picture_link.startswith('http'):
        embed.set_thumbnail(url=picture_link)
    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
    await asyncio.sleep(1)
    dodge = await calculate_dodge(mass_spar_chars[server_id][user_id]["Agility"],
                                  mass_spar_chars[server_id][target_id]["Agility"])
    if dodge:
        dodge_text = mass_spar_chars[server_id][target_id]["CharName"] + " dodged the attack! No damage taken!"
        embed = discord.Embed(title=dodge_text)
        if mass_spar_chars[server_id][target_id]["PictureLink"].startswith('http'):
            embed.set_thumbnail(url=mass_spar_chars[server_id][target_id]["PictureLink"])
        await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
        await asyncio.sleep(1)

    else:
        damage = await calculate_damage(mass_spar_chars[server_id][user_id]["Attack"],
                                        mass_spar_chars[server_id][target_id]["Defense"], damage_multiplier,
                                        mass_spar_chars[server_id][user_id]["Level"],
                                        mass_spar_chars[server_id][target_id]["Level"])
        mass_spar_chars[server_id][target_id]["Health"] = mass_spar_chars[server_id][target_id]["Health"] - damage
        mass_spar_chars[server_id][user_id]["TotalDamage"] = mass_spar_chars[server_id][user_id]["TotalDamage"] + damage
        hit_text = "" + mass_spar_chars[server_id][target_id]["CharName"] + " was hit by " + \
                   mass_spar_chars[server_id][user_id]["CharName"] + " for " + str(
            damage) + " points!\n\nHealth now at " + str(mass_spar_chars[server_id][target_id]["Health"]) + "!"

        embed = discord.Embed(title=hit_text)
        if mass_spar_chars[server_id][target_id]["PictureLink"].startswith('http'):
            embed.set_thumbnail(url=mass_spar_chars[server_id][target_id]["PictureLink"])
        await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
        await asyncio.sleep(1)

        if mass_spar_chars[server_id][target_id]["Health"] < 1:
            fallen_text = mass_spar_chars[server_id][target_id][
                              "CharName"] + " has no health left and is out of the fight! The AI wins!"
            embed = discord.Embed(title=fallen_text)
            if mass_spar_chars[server_id][target_id]["PictureLink"].startswith('http'):
                embed.set_thumbnail(url=mass_spar_chars[server_id][target_id]["PictureLink"])
            await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
            await asyncio.sleep(1)

            response = "<@" + str(
                message.author.id) + "> is the last one standing and is the spar winner!\n\n**Experience gained:**\n\n"
            fallen_chars[server_id][message.author.id] = {}
            fallen_chars[server_id] = [mass_spar_chars[server_id][message.author.id], ]
            for char in fallen_chars[server_id]:

                char_id = char
                await log_message("Level " + str(char["Level"]))
                new_xp = await calculate_xp(char["Level"],
                                            char["Level"],
                                            char["TotalDamage"], 1) * 2
                response = response + "*" + char["CharName"] + "*: " + str(new_xp) + "\n"
                records = await select_sql("""SELECT Experience FROM CharacterProfiles WHERE Id=%s;""",
                                           (str(char["CharId"]),))
                for row in records:
                    old_xp = int(row[0])
                total_xp = old_xp + new_xp
                if total_xp > (guild_settings[server_id]["XPLevelRatio"] * char["Level"]):
                    char["Level"] = char["Level"] + 1
                    records = await select_sql("""SELECT StatPoints FROM CharacterProfiles WHERE Id=%s;""",
                                               (str(char["CharId"]),))
                    for row in records:
                        stat_points = int(row[0])

                    available_points = int(guild_settings[server_id]["StatPointsPerLevel"]) + stat_points
                    response = response + "**" + char[
                        "CharName"] + "** LEVELED UP TO LEVEL **" + str(
                        char["Level"]) + "!**\nYou have " + str(
                        available_points) + " stat points to spend!\n\n"
                    total_xp = 0
                    health = fallen_chars[server_id][user_id]["MaxHealth"] + guild_settings[server_id]["HealthLevelAdd"]
                    stamina = fallen_chars[server_id][user_id]["MaxStamina"] + guild_settings[server_id][
                        "StaminaLevelAdd"]
                    mana = fallen_chars[server_id][user_id]["MaxMana"] + guild_settings[server_id]["ManaLevelAdd"]
                    result = await commit_sql(
                        """UPDATE CharacterProfiles SET Level=%s,Experience=%s,Health=%s,Stamina=%s,Mana=%s,StatPoints=%s WHERE Id=%s;""",
                        (str(fallen_chars[server_id][target_id]["Level"] + 1), str(total_xp), str(health), str(stamina),
                         str(mana), str(available_points), str(fallen_chars[server_id][target_id]["CharId"])))
            mass_spar_event[server_id] = False

            embed = discord.Embed(title="Result", description=response)
            for x in mass_spar_chars[server_id].keys():
                del mass_spar_chars[server_id][x]
            for x in mass_spar[server_id].keys():
                del mass_spar[server_id][x]

            await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
            await asyncio.sleep(1)


async def generate_random_ai_char(message, character_level):
    male_first_name_list = ["Ferris", "Redmond", "Raphael", "Orion", "Caspian", "Aramis", "Lucian", "Storm", "Percival",
                            "Gawain", "Perseus", "Cormac", "Leon", "Patrick", "Robert", "Morgan", "Brandon", "Sven",
                            "Roland", "Ronan", "Edmund", "Adam", "Edric", "Martin", "Odin", "Bayard", "Laurent",
                            "Faramond", "Finn", "Edward", "Tristan", "Emil", "Zephyr", "Soren", "Arthur", "Robin",
                            "Marcel", "Roman", "Beowulf"", ""Seth", "Tristan", "Arthur", "Edmund", "Percival", "Ronan",
                            "Thor", "Leon", "Roman", "Adam", "Ferris", "Zephyr", "Gawain", "Perseus", "Cormac", "Lydan",
                            "Syrin", "Ptorik", "Joz", "Varog", "Gethrod", "Hezra", "Feron", "Ophni", "Colborn",
                            "Fintis", "Gatlin", "Jinto", "Hagalbar", "Krinn", "Lenox", "Revvyn", "Hodus", "Dimian",
                            "Paskel", "Kontas", "Weston", "Azamarr ", "Jather ", "Tekren ", "Jareth", "Adon", "Zaden",
                            "Eune ", "Graff", "Tez", "Jessop", "Gunnar", "Pike", "Domnhar", "Baske", "Jerrick",
                            "Mavrek", "Riordan", "Wulfe", "Straus", "Tyvrik ", "Henndar", "Favroe", "Whit", "Jaris",
                            "Renham", "Kagran", "Lassrin ", "Vadim", "Arlo", "Quintis", "Vale", "Caelan", "Yorjan",
                            "Khron", "Ishmael", "Jakrin", "Fangar", "Roux", "Baxar", "Hawke", "Gatlen", "Barak",
                            "Nazim", "Kadric", "Paquin", " ", "", "Kent", "Moki", "Rankar", "Lothe", "Ryven", "Clawsen",
                            "Pakker", "Embre", "Cassian", "Verssek", "Dagfinn", "Ebraheim", "Nesso", "Eldermar",
                            "Rivik", "Rourke", "Barton", "Hemm", "Sarkin", "Blaiz ", "Talon", "Agro", "Zagaroth",
                            "Turrek", "Esdel", " ", "", "Lustros", "Zenner", "Baashar ", "Dagrod ", "Gentar", "Feston"]
    female_first_name_list = ["Ayrana", "Resha", "Varin", "Wren", "Yuni", "Talis", "Kessa", "Magaltie", "Aeris",
                              "Desmina", "Krynna", "Asralyn ", "Herra", "Pret", "Kory", "Afia", "Tessel", "Rhiannon",
                              "Zara", "Jesi", "Belen", "Rei", "Ciscra", "Temy", "Renalee ", "Estyn", "Maarika",
                              "Lynorr", "Tiv", "Annihya", "Semet", "Tamrin", "Antia", "Reslyn", "Basak", "Vixra",
                              "Pekka ", "Xavia", "Beatha ", "Yarri", "Liris", "Sonali", "Razra ", "Soko", "Maeve",
                              "Everen", "Yelina", "Morwena", "Hagar", "Palra", "Elysa", "Sage", "Ketra", "Lynx",
                              "Agama", "Thesra ", "Tezani", "Ralia", "Esmee", "Heron", "Naima", "Rydna ", "Sparrow",
                              "Baakshi ", "Ibera", "Phlox", "Dessa", "Braithe", "Taewen", "Larke", "Silene", "Phressa",
                              "Esther", "Anika", "Rasy ", "Harper", "Indie", "Vita", "Drusila", "Minha", "Surane",
                              "Lassona", "Merula", "Kye", "Jonna", "Lyla", "Zet", "Orett", "Naphtalia", "Turi", "Rhays",
                              "Shike", "Hartie", "Beela", "Leska", "Vemery ", "Lunex", "Fidess", "Tisette", "Partha"]
    unisex_first_name_list = []
    last_name_list = ["Starbringer", "Leafgreen", "Smith", "Thundershaw", "Dreamweaver", "McAle", "Hale", "Zendor",
                      "Zoaraster", "Horserider", "Stormwalker", "Abawi", "Allard", "Adara", "Abbott", "Acampora",
                      "Ackerman", "Ackroyd", "Abbington", "Axworthy", "Ainge", "Abernathy", "Atkinson", "Abner",
                      "Abella", "Agholor", "Allred", "Asola", "Abrams", "Acker", "Abrell", "Acuff", "Archer", "Asterio",
                      "Adair", "Albright", "Adelson", "Atwood", "Aguillar", "Adler", "Arrowood", "Agnew", "Akuna",
                      "Alcott", "Alstott", "Austin", "Algarotti", "Alvarez", "Armani", "Anderson", "Amherst", "Adkins",
                      "Ayesa", "Argento", "Arrowood", "Andruzzi", "Abraham", "Angle", "Armstrong", "Attard",
                      "Annenberg", "Arrhenius", "Acosta", "Antrican", "Adderley", "Atwater", "Agassi", "Apatow",
                      "Archeletta", "Averescu", "Arrington", "Agrippa", "Aiken", "Albertson", "Alexander", "Amado",
                      "Anders", "Armas", "Akkad", "Aoki", "Aldrich", "Almond", "Alinsky", "Agnello", "Alterio",
                      "Atchley", "Bynes", "Bray", "Budreau", "Byrne", "Bragg", "Banner", "Bishop", "Burris", "Boggs",
                      "Brembilla", "Booth", "Bullard", "Booker", "Buckner", "Borden", "Breslin", "Bryant", "BIles",
                      "Brunt", "Brager", "Brandt", "Bosa", "Bradshaw", "Brubaker", "Berry", "Brooks", "Bandini",
                      "Bristow", "Barrick", "Biddle", "Brennan", "Brinkmann", "Benz", "Braddock", "Bright", "Berman",
                      "Bracco", "Bartley", "Briggs", "Bonanno", "Boyle", "Beeks", "Bernthal", "Boldon", "Bowser",
                      "Benwikere", "Bowman", "Bamberger", "Bowden", "Batch", "Blaustein", "Blow", "Boulware", "Bezos",
                      "Boulder", "Bauer", "Ballard", "Benton", "Bixby", "Bostwick", "Biles", "Bobusic", "Belinski",
                      "Blood", "Bisley", "Bettis", "Bensen", "Binion", "Bloch", "Blixt", "Bellisario", "Botkin",
                      "Benoit", "BInda", "Baldwin", "Bennett", "Bourland", "Bester", "Bender", "Best", "Bald", "Bersa",
                      "Belt", "Bourne", "Barks", "Beebe", "Banu", "Bozzelli", "Bogaerts", "Cyrus", "Craggs", "Crisper",
                      "Cotheran", "Curry", "Conard", "Cutler", "Coggins", "Cates", "Crisp", "Curio ", "Creed",
                      "Costner", "Cortse", "Cunningham", "Cooper", "Cullen", "Castle", "Cugat", "Click", "Cassidy",
                      "Crespo", "Crusher", "Cooper", "Coates", "Crowley", "Creel", "Crassus", "Cogdill", "Cross",
                      "Crabtree", "Cranham", "Carver", "Cox", "Coltrane", "Chatwin", "Conklin", "Colt", "Coulter",
                      "Cleveland", "Coppens", "Coolidge", "Copeland", "Celino", "Coffin", "Cena", "Conti ", "Coin",
                      "Connelly", "Cents", "Carney", "Carmichael", "Coffey", "Carling", "Christie", "Chadwick", "Cobo",
                      "Clay", "Capra", "Candy", "Clancy", "Chalk", "Chambers", "Callahan", "Cirque", "Cabrera-Bello",
                      "Cherry", "Cannon", "Chung", "Cave", "Challenger", "Cobb", "Calaway", "Chalut", "Cayce", "Cahill",
                      "Cruz", "Cohen", "Caylor", "Cagle", "Cline", "Crawford", "Cleary", "Cain", "Champ", "Cauley",
                      "Claxton"    "Dubois", "Darby", "Draper", "Dwyer", "Dixon", "Danton", "Devereaux", "Ditka",
                      "Dominguez", "Decker", "Dobermann", "Dunlop", "Dumont", "Dandridge", "Diamond", "Dobra ", "Dukas",
                      "Dyer", "Decarlo", "Delpy", "Dufner", "Driver", "Dalton", "Dark", "Dawkins", "Driskel",
                      "Derbyshire", "Davenport", "Dabney", "Dooley", "Dickerson", "Donovan", "Dallesandro", "Devlin",
                      "Donnelly", "Day", "Daddario", "Donahue", "Denver", "Denton", "Dodge", "Dempsey", "Dahl",
                      "Drewitt", "Earp", "Eberstark ", "Egan", "Elder", "Eldridge", "Ellenburg", "Eslinger", "England",
                      "Epps", "Eubanks", "Everhart", "Evert", "Eastwood", "Elway", "Eslinger", "Ellerbrock", "Edge",
                      "Endo", "Etter", "Ebersol", "Everson", "Earwood", "Ekker", "Escobar", "Edgeworth", "Future",
                      "Fitzpatrick", "Fontana", "Fenner", "Furyk", "Finch", "Fullbright", "Fassbinder", "Flood", "Fong",
                      "Fleetwood", "Fugger", "Frost", "Fsik", "Fawcett", "Fishman", "Freeze", "Fissolo", "Foley",
                      "Fairchild", "Freeman", "Flanagan", "Freed", "Fogerty", "Foster", "Finn", "Fletcher", "Floris",
                      "Flynn", "Fairbanks", "Fawzi ", "Finau", "Floquet ", "Fleiss", "Ferguson", "Froning",
                      "Fitzgerald", "Fingermann", "Flagg", "Finchum", "Flair", "Ferber", "Fuller", "Farrell", "Fenton",
                      "Fangio", "Faddis", "Ferenz", "Farley", "Gundlach", "Gannon", "Goulding", "Greenway", "Guest",
                      "Gillis", "Gellar", "Gaither", "Griffith", "Grubbs", "Glass", "Gotti", "Goodwin", "Grizzly",
                      "Glover", "Grimes", "Gleason", "Gardner", "Geske", "Griffo", "Glunt", "Golden", "Gardel",
                      "Gribble", "Grell", "Gearey", "Grooms", "Glaser", "Greer", "Geel", "Gallagher", "Glick",
                      "Graber ", "Gore", "Gabbard", "Gelpi", "Gilardi", "Goddard", "Gabel", "Hyde", "Hood", "Hull",
                      "Hogan", "Hitchens", "Higgins", "Hodder", "Huxx", "Hester", "Huxley", "Hess", "Hutton", "Hobgood",
                      "Husher", "Hitchcock", "Huffman", "Herrera", "Humber", "Hobbs", "Hostetler", "Henn", "Horry",
                      "Hightower", "Hindley", "Hitchens", "Holiday", "Holland", "Hitchcock", "Hoagland", "Hilliard",
                      "Harvick", "Hardison", "Hickey", "Heller", "Hartman", "Halliwell", "Hughes", "Hart", "Healy",
                      "Head", "Harper", "Hibben", "Harker", "Hatton", "Hawk", "Hardy", "Hadwin", "Hemmings", "Hembree",
                      "Helbig", "Hardin", "Hammer", "Hammond", "Haystack", "Howell", "Hatcher", "Hamilton", "Halleck",
                      "Hooper", "Hartsell", "Henderson", "Hale", "Hokoda", "Heers", "Homa", "Hanifin",
                      "Most Common Last Names Around the World", "Inch", "Inoki", "Ingram", "Idelson", "Irvin", "Ives",
                      "Ishikawa", "Irons", "Irwin", "Ibach", "Ivanenko", "Ibara"    "Jurado", "Jammer", "Jagger",
                      "Jackman", "Jishu", "Jingle", "Jessup", "Jameson", "Jett", "Jackson", "Kulikov ", "Kellett",
                      "Koo", "Kitt", "Keys", "Kaufman", "Kersey", "Keating", "Kotek ", "Kuchar", "Katts", "Kilmer",
                      "King", "Kubiak", "Koker", "Kerrigan", "Kumara", "Knox", "Koufax", "Keagan", "Kestrel", "Kinder",
                      "Koch", "Keats", "Keller", "Kessler", "Kobayashi", "Klecko", "Kicklighter", "Kincaid", "Kershaw",
                      "Kaminsky", "Kirby", "Keene", "Kenny", "Keogh", "Kipps", "Salvador Dali",
                      "Salvador Dali"    "Litvak", "Lawler", "London", "Lynch", "Lacroix", "Ledford", "LeMay",
                      "Lovejoy", "Lombardo", "Lovecraft", "Laudermilk", "Locke", "Leishman", "Leary", "Lott", "Ledger",
                      "Lords", "Lacer", "Longwood", "Lattimore", "Laker", "Lecter", "Liston", "Londos", "Lomax",
                      "Leaves ", "Lipman", "Lambert", "Lesnar", "Lazenby", "Lichter", "Lafferty", "Lovin", "Lucchesi",
                      "Landis", "Lopez", "Lentz", "Murray", "Morrison", "McKay", "Merchant", "Murillo", "Mooney",
                      "Murdock", "Matisse", "Massey", "McGee", "Minter", "Munson", "Mullard", "Mallory", "Meer ",
                      "Mercer", "Mulder", "Malik", "Moreau ", "Metz", "Mudd", "Meilyr", "Motter", "McNamara", "Malfoy",
                      "Moses", "Moody", "Morozov", "Mason", "Metcalf", "McGillicutty", "Montero", "Molinari", "Marsh",
                      "Moffett", "McCabe", "Manus", "Malenko", "Mullinax", "Morrissey", "Mantooth", "Mintz", "Messi",
                      "Mattingly", "Mannix", "Maker", "Montoya", "Marley", "McKnight", "Magnusson ", "Marino", "Maddox",
                      "Macklin", "Mackey", "Morikowa", "Mahan", "Necessary", "Nicely", "Nejem", "Nunn", "Neiderman",
                      "Naillon", "Nyland", "Novak", "Nygard", "Norwood", "Norris", "Namath", "Nabor", "Nash", "Noonan",
                      "Nolan ", "Nystrom", "Niles", "Napier", "Nunley", "Nighy", "Overholt", "Ogletree", "Opilio ",
                      "October", "Ozu", "O'Rourke", "Owusu", "Oduya", "Oaks", "Odenkirk", "Ottinger", "O'Donnell",
                      "Orton", "Oakley", "Oswald", "Ortega", "Ogle", "Orr", "Ogden", "Onassis", "Olson", "Ollenrenshaw",
                      "O'Leary", "O'Brien", "Oldman", "O'Bannon", "Oberman", "O'Malley", "Otto", "Oshima", "Prado",
                      "Prunk", "Piper", "Putnam", "Pittman", "Post", "Price", "Plunkett", "Pitcher", "Pinzer", "Punch",
                      "Paxton", "Powers", "Previn", "Pulman", "Puller", "Peck", "Pepin", "Platt", "Powell", "Pawar",
                      "Pinder", "Pickering", "Pollock", "Perrin", "Pell", "Pavlov", "Patterson", "Perabo", "Patnick",
                      "Panera", "Prescott", "Portis", "Perkins", "Palmer", "Paisley", "Pladino", "Pope", "Posada",
                      "Pointer", "Poston", "Porter", "Quinn", "Quan", "Quaice", "Quaid", "Quirico", "Quarters",
                      "Quimby", "Qua", "Quivers", "Quall", "Quick", "Qugg", "Quint", "Quintero", "Leonardo da Vinci",
                      "Leonardo da Vinci"    "Rudd", "Ripperton", "Renfro", "Rifkin", "Rand", "Root", "Rhodes",
                      "Rowland", "Ramos", "Ryan", "Rafus", "Radiguet", "Ripley", "Ruster", "Rush", "Race", "Rooney",
                      "Russo", "Rude", "Roland", "Reader", "Renshaw", "Rossi", "Riddle", "Ripa", "Richter", "Rosenberg",
                      "Romo", "Ramirez", "Reagan", "Rainwater", "Romirez", "Riker", "Riggs", "Redman", "Reinhart",
                      "Redgrave", "Rafferty", "Rigby", "Roman", "Reece", "Sutton", "Swift", "Sorrow", "Spinks", "Suggs",
                      "Seagate", "Story", "Soo", "Sullivan", "Sykes", "Skirth", "Silver", "Small", "Stoneking",
                      "Sweeney", "Surrett", "Swiatek", "Sloane", "Stapleton", "Seibert", "Stroud", "Strode", "Stockton",
                      "Scardino", "Spacek", "Spieth", "Stitchen", "Stiner", "Soria", "Saxon", "Shields", "Stelly",
                      "Steele", "Standifer", "Shock", "Simerly", "Swafford", "Stamper", "Sotelo", "Smoker", "Skinner",
                      "Shaver", "Shivers", "Savoy", "Small", "Skills", "Sinclair", "Savage", "Sereno", "Sasai",
                      "Silverman", "Silva", "Shippen", "Sasaki", "Sands", "Shute", "Sabanthia", "Sheehan", "Sarkis",
                      "Shea", "Santos", "Snedeker", "Stubbings", "Streelman", "Skaggs", "Spears", "Twigg", "Tracy",
                      "Truth", "Tillerson", "Thorisdottir ", "Tooms", "Tripper", "Tway", "Taymor", "Tamlin", "Toller",
                      "Tussac", "Turpin", "Tippett", "Tabrizi", "Tanner", "Tuco", "Trumbo", "Tucker", "Theo", "Thain",
                      "Trapp", "Trumbald ", "Trench", "Terrella", "Tait", "Tanaka", "Tapp", "Tepper", "Trainor",
                      "Turner", "Teague", "Templeton", "Temple", "Teach", "Tam"    "Udder", "Uso", "Uceda", "Umoh",
                      "Underhill", "Uplinger", "Ulett", "Urtz", "Unger", "Vroman", "Vess", "Voight", "Vegas", "Vasher",
                      "Vandal", "Vader", "Volek", "Vega", "Vestine", "Vaccaro", "Vickers", "Witt", "Wolownik",
                      "Winding", "Wooten ", "Whitner", "Winslow", "Winchell", "Winters", "Walsh", "Whalen", "Watson",
                      "Wooster", "Woodson", "Winthrop", "Wall", "Wight", "Webb", "Woodard", "Wixx", "Wong", "Whesker",
                      "Wolfenstein", "Winchester", "Wire", "Wolf", "Wheeler", "Warrick", "Walcott", "Wilde", "Wexler",
                      "Wells", "Weeks", "Wainright", "Wallace", "Weaver", "Wagner", "Wadd", "Withers", "Whitby",
                      "Woodland", "Woody", "Xavier", "Xanders", "Xang", "Ximinez", "Xie", "Xenakis", "Xu", "Xiang",
                      "Xuxa", "Yearwood", "Yellen", "Yaeger", "Yankovich", "Yamaguchi", "Yarborough", "Youngblood",
                      "Yanetta", "Yadao", "Yale", "Yasumoto", "Yates", "Younger", "Yoakum", "York", "Yount",
                      "Zuckerberg", "Zeck", "Zavaroni", "Zeller", "Zipser", "Zedillo", "Zook", "Zeigler", "Zimmerman",
                      "Zeagler", "Zale", "Zasso", "Zant", "Zappa", "Zapf", "Zahn", "Zabinski", "Zade", "Zabik", "Zader",
                      "Zukoff", "Zullo", "Zmich", "Zoller"]
    race_list = ["Human", "Elf", "Dwarf", "Gnome", "Troll", "Elemental", "Orc", "Angel", "Demon", "Vampire",
                 "Shadow walker", "Deity", "Xendorian", "Archangel", "Archdemon", "Undead", "Drow", "Ghost", "Dragon",
                 "Werewolf", "Fairy", "Dark Fairy", "Pixie", "Shifter", "Merperson", "Sentient animal", "Goblin",
                 "Halfling", "Kitsune", "Centaur", "Satyr", "Dryad", "Nightmare", "Incarnate", "Death walker", "Yeti",
                 "Wendigo", "Monster", "High Elf", "Wood Elf", "Dark Elf", "Manticore", "Gryphon", "Phoenix", "Ent"]
    height_min_feet = 4
    height_max_feet = 6
    height_inches_max = 11
    weight_min = 90
    weight_max = 250
    age_min = 18
    age_max = 2000
    occupation_list = ["Warrior", "Knight", "Hunter", "Blacksmith", "Noble", "Royalty", "Slave", "Mercenary", "Caster",
                       "Mage", "Wizard", "Warlock", "Protector", "Healer", "Medium", "Psychic", "Assassin", "Swordsman",
                       "Thief", "Cobbler", "Potion maker", "Preacher", "Priest", "Paladin", "Witch", "Warlock",
                       "Sorcerer", "Servant", "Escort", "Prostitute", "Solider", "Bartender", "Merchant", "Sailor",
                       "Pirate", "Archer", "Guard", "Slayer", "Alchemist", "Apothecary", "Shopkeeper", "Trader",
                       "Wizard", "Fighter", "Teacher", "Physician", "Philosopher", "Farmer", "Shepherd", "Harbinger",
                       "Messenger", "Horserider", "Chef", "Night watch", "None", "Beggar", "Researcher", "Advisor",
                       "Judge", "Executioner", "Commander", "Captain", "Fisher", "Ranchhand", "Druid"]
    gender_list = ["Male", "Female", "Non-binary", "Genderfluid"]
    origin_list = ["Unknown", "Earth", "Rhydin", "Offworld"]
    powers_list = ["Psychic", "Lightning", "Light", "Healing", "Destruction", "Darkness", "Telepathy", "Psychokinesis",
                   "Flight", "Storms", "Water", "Air", "Wind", "Earth", "Fire", "Talking to the dead", "Plane-walking",
                   "Illusion", "Glamor", "Holy", "White Magic", "Black Magic", "Seduction", "Speed",
                   "Superhuman strength", "Immortality", "Energy manipulation", "Reality warping", "Spaceflight",
                   "Cloaking", "Shadow"]
    strengths_list = ["Melee combat", "Magic", "Physical strength", "Physical speed", "Highly intelligent",
                      "Expert swordfighter", "Martial arts", "Strategic", "Charismatic", "Highly perceptive",
                      "Expert with firearms", "Expert archer", "Resistant to magic"]
    weaknesses_list = ["Black magic", "Light", "Holy power", "Evil power", "Easily seduced", "Gullible",
                       "Socially manipulatable", "Low intelligence", "Fire", "Water", "Lightning", "Darkness", "Shadow",
                       "Astral attacks", "Weak physically", "Lost immortality", "Reduced powers", "Trauma in past",
                       "Phobias", "Anxiety", "Poor training", "Little magical capacity"]
    personality_list = ["Warm", "Cold", "Aloof", "Caring", "Gregarious", "Affable", "Talkative", "Strong, silent type",
                        "Brash", "Boisterous", "Lazy", "Shy", "Fearful", "Happy-go-lucky", "Perky", "Perverted",
                        "Sociopathic", "Formal", "Casual", "Creative", "Nice", "Mean", "Rude", "Kind", "Gentle",
                        "Harsh", "Asexual", "Wild in bed", "Stoic", "Charismatic", "Charming", "Romantic", "Detached",
                        "Depressed", "Worrywart", "Troubled by their past", "Carries a grudge", "Loving", "Hateful",
                        "Spiteful", "Angry", "Short fuse", "Patient", "Passionate", "Empty"]
    skills_list = ["Archery", "Swordplay", "Reading", "Writing", "Science", "Technology", "Music", "Telling jokes",
                   "Lying when needed", "Magic", "Alchemy", "Healing", "Medicine", "Potions", "Elixirs", "Chemistry",
                   "Knowledge of the beyond", "Master illusionist", "Computers", "Mixing drinks", "Telling stories",
                   "Inspiring others", "Leading", "Fighting", "Organizing", "Art", "Scuplting", "Crafts",
                   "Metalworking", "Buidling structures", "Tinkering"]

    gender_picker = random.randint(1, 20)
    if 1 <= gender_picker <= 9:
        gender = "Male"
    elif 10 <= gender_picker <= 18:
        gender = "Female"
    else:
        gender = "Genderfluid"

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
        age = random.randint(18, 100)
    else:
        age = random.randint(age_min, age_max)

    origin = random.choice(origin_list)
    height_feet = random.randint(height_min_feet, height_max_feet)
    height_inches = random.randint(0, 11)
    weight = random.randint(weight_min, weight_max)

    number_of_strengths = random.randint(1, 5)
    strengths = ""
    for x in range(0, number_of_strengths):
        strengths = strengths + random.choice(strengths_list) + ", "
    number_of_weaknesses = random.randint(1, 5)
    weaknesses = ""
    for x in range(0, number_of_weaknesses):
        weaknesses = weaknesses + random.choice(weaknesses_list) + ", "
    powers = ""

    number_of_powers = random.randint(1, 3)
    for x in range(0, number_of_powers):
        powers = powers + random.choice(powers_list) + ", "
    number_of_skills = random.randint(1, 5)
    skills = ""
    for x in range(0, number_of_skills):
        skills = skills + random.choice(skills_list) + ", "
    personality = ""
    number_of_personality = random.randint(2, 6)
    for x in range(0, number_of_personality):
        personality = personality + random.choice(personality_list) + ", "

    server_id = message.guild.id

    counter = 0
    embed = discord.Embed(title="AI Character Data")

    server_id = server_id
    user_id = client.user.id

    mass_spar_chars[server_id][user_id] = {}
    mass_spar_chars[server_id][user_id]["CharName"] = first_name + " " + last_name
    mass_spar_chars[server_id][user_id]["Attack"] = character_level * random.randint(5, 30)
    mass_spar_chars[server_id][user_id]["Defense"] = character_level * random.randint(5, 20)

    mass_spar_chars[server_id][user_id]["MagicAttack"] = character_level * random.randint(5, 20)
    mass_spar_chars[server_id][user_id]["Health"] = character_level * guild_settings[server_id]["StartingHealth"]
    mass_spar_chars[server_id][user_id]["MaxHealth"] = character_level * guild_settings[server_id]["StartingHealth"]
    mass_spar_chars[server_id][user_id]["Mana"] = guild_settings[server_id]["StartingMana"] * character_level
    mass_spar_chars[server_id][user_id]["MaxMana"] = guild_settings[server_id]["StartingMana"] * character_level
    mass_spar_chars[server_id][user_id]["Level"] = character_level
    mass_spar_chars[server_id][user_id]["Experience"] = 0
    mass_spar_chars[server_id][user_id]["MaxStamina"] = guild_settings[server_id]["StartingStamina"] * character_level
    mass_spar_chars[server_id][user_id]["Stamina"] = guild_settings[server_id]["StartingStamina"] * character_level
    mass_spar_chars[server_id][user_id]["Agility"] = character_level * random.randint(10, 100)
    mass_spar_chars[server_id][user_id]["Intellect"] = 100
    mass_spar_chars[server_id][user_id]["Charisma"] = 100
    mass_spar_chars[server_id][user_id]["CharId"] = 0
    mass_spar_chars[server_id][user_id]["PictureLink"] = narrator_url
    mass_spar_chars[server_id][user_id]["TotalDamage"] = 0
    char_name = mass_spar_chars[server_id][user_id]["CharName"]

    response = "***AI CHARACTER INFORMATION**\n\n"
    for field in mass_spar_chars[server_id][user_id]:
        embed.add_field(name=field, value=mass_spar_chars[server_id][user_id][field])
        counter = counter + 1

    # await reply_message(message, response)
    await message.channel.send(embed=embed)
    await asyncio.sleep(1)
    await message.channel.send(">>> AI successfully set party character to " + char_name + ".")


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

    create_entry = re.sub(r", $", "", create_entry)
    create_entry = create_entry + " " + re.sub(r",\s*$", "", create_values) + ");"
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

    update_entry = re.sub(r", $", "", update_entry)
    update_entry = update_entry + " WHERE ServerId=%s AND " + field_list[0] + "=%s;"
    update_tuple = update_tuple + (str(dm_tracker[message.author.id]["server_id"]), field_value)

    result = await commit_sql(update_entry, update_tuple)
    return result


async def make_menu(message, table1, table2, id_field1, id_field2, name_field, id):
    global dm_tracker
    global allowed_ids

    records = await select_sql(
        """SELECT """ + id_field1 + """ FROM """ + table1 + """ WHERE ServerId=%s AND """ + id_field2 + """=%s;""",
        (str(dm_tracker[message.author.id]["server_id"]), id))
    if not records:
        return "No records found!"
    response = " "
    allowed_ids[message.author.id] = []
    for row in records:

        allowed_ids[message.author.id].append(str(row[0]))
        item_record = await select_sql("SELECT " + name_field + " FROM " + table2 + " WHERE Id=%s AND ServerId=%s;",
                                       (str(row[0]), str(dm_tracker[message.author.id]["server_id"])))
        for item_row in item_record:
            response = response + "**" + str(row[0]) + "** - " + item_row[0] + "\n"
    return response


async def monster_attack(author_id):
    global server_party_chars
    global server_monsters
    global dm_tracker
    global encounter_turn

    server_id = dm_tracker[author_id]["server_id"]
    target = random.choice(list(server_party_chars[server_id].keys()))
    attack_text = " " + str(server_monsters[server_id]["MonsterName"]) + " attacks " + str(
        server_party_chars[server_id][target]["CharName"]) + "!"
    #           await post_webhook(dm_tracker[author_id]["commandchannel"], server_monsters[server_id]["MonsterName"], attack_text, server_monsters[server_id]["PictureLink"])
    embed = discord.Embed(title=attack_text)
    if server_monsters[server_id]["PictureLink"].startswith('http'):
        embed.set_thumbnail(url=server_monsters[server_id]["PictureLink"])
    await dm_tracker[author_id]["commandchannel"].send(embed=embed)

    asyncio.sleep(1)
    #          await reply_message(message, " " + str(server_monsters[server_id]["MonsterName"]) + " attacks " + str(server_party_chars[server_id][target]["CharName"]) + "!")
    dodge = await calculate_dodge(server_monsters[server_id]["Level"], server_party_chars[server_id][target]["Agility"])
    if dodge:
        dodge_text = server_party_chars[server_id][target]["CharName"] + " dodged the attack! No damage taken!"
        embed = discord.Embed(title=dodge_text)
        if server_monsters[server_id]["PictureLink"].startswith('http'):
            embed.set_thumbnail(url=server_party_chars[server_id][target]["PictureLink"])
        await dm_tracker[author_id]["commandchannel"].send(embed=embed)
    #                await post_webhook(dm_tracker[author_id]["commandchannel"], server_party_chars[server_id][target]["CharName"], dodge_text, server_party_chars[server_id][target]["PictureLink"])
    # await reply_message(message, server_party_chars[server_id][target]["CharName"] + " dodged the attack! No damage taken!")

    else:
        damage = await calculate_damage(server_monsters[server_id]["Attack"],
                                        server_party_chars[server_id][target]["Defense"], random.randint(4, 6),
                                        server_monsters[server_id]["Level"],
                                        server_party_chars[server_id][target]["Level"])
        server_party_chars[server_id][target]["Health"] = int(server_party_chars[server_id][target]["Health"] - damage)
        hit_text = server_party_chars[server_id][target]["CharName"] + " was hit by " + server_monsters[server_id][
            "MonsterName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(
            server_party_chars[server_id][target]["Health"]) + "!"
        embed = discord.Embed(title=hit_text)
        if server_party_chars[server_id][target]["PictureLink"].startswith('http'):
            embed.set_thumbnail(url=server_party_chars[server_id][target]["PictureLink"])
        await dm_tracker[author_id]["commandchannel"].send(embed=embed)

        if server_party_chars[server_id][target]["Health"] < 1:
            await dm_tracker[author_id]["commandchannel"].send(
                server_party_chars[server_id][target]["CharName"] + " has no health left and is out of the fight!")

            server_party[server_id].remove(client.get_user(id=target))
            del server_party_chars[server_id][target]

        if len(server_party_chars[server_id]) < 1:
            await dm_tracker[author_id]["commandchannel"].send(
                ">>> The party has been vanquished! " + server_monsters[server_id][
                    "MonsterName"] + " wins! No experience will be awarded.")
            server_encounters[server_id] = False


async def make_simple_menu(message, table1, name_field):
    global dm_tracker
    global allowed_ids

    records = await select_sql("""SELECT Id,""" + name_field + """ FROM """ + table1 + """ WHERE ServerId=%s;""",
                               (str(dm_tracker[message.author.id]["server_id"]),))
    if not records:
        return "No records found!"
    response = " "
    allowed_ids[message.author.id] = []
    for row in records:
        allowed_ids[message.author.id].append(str(row[0]))
        response = response + "**" + str(row[0]) + "** - " + row[1] + "\n"
    return response


async def make_less_simple_menu(message, table1, name_field, id_field, id):
    global dm_tracker
    global allowed_ids
    records = await select_sql(
        """SELECT Id,""" + name_field + """ FROM """ + table1 + """ WHERE ServerId=%s AND """ + id_field + """=%s;""",
        (str(dm_tracker[message.author.id]["server_id"]), id))
    allowed_ids[message.author.id] = []
    if not records:
        return "No records found!"
    response = " "
    for row in records:
        response = response + "**" + str(row[0]) + "** - " + row[1] + "\n"
        allowed_ids[message.author.id].append(str(row[0]))
    return response


@client.event
async def on_ready():
    global webhook
    global server_monsters
    global server_encounters
    global server_party
    global server_party_chars
    global guild_settings
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
    global new_startup
    global daily
    global custom_commands
    global client
    global critter_spawn
    global allowed_ids
    global mass_spar_cooldown
    global mass_spar_cooldown_turns
    global active_chars

    await log_message("Logged in!")

    if new_startup:
        await client.change_presence(activity=discord.Game(name="with dice..."))
        for guild in client.guilds:
            await log_message("Loading guild " + guild.name)
            try:
                alt_aliases[guiild.id]
            except:
                alt_aliases[guild.id] = {}
            try:
                npc_aliases[guiild.id]
            except:
                npc_aliases[guild.id] = {}
            server_encounters[guild.id] = False
            server_monsters[guild.id] = {}
            server_party[guild.id] = {}
            server_party_chars[guild.id] = {}
            guild_settings[guild.id] = {}
            mass_spar[guild.id] = {}
            mass_spar_event[guild.id] = False
            mass_spar_chars[guild.id] = {}
            mass_spar_turn[guild.id] = 0
            mass_spar_confirm[guild.id] = {}
            mass_spar_cooldown[guild.id] = {}
            daily[guild.id] = {}
            fallen_chars[guild.id] = {}
            custom_commands[guild.id] = {}
            active_chars[guild.id] = {}
            critter_spawn[guild.id] = 10
            encounter_turn[guild.id] = 0
        #            for user in guild.members:
        #                daily[guild.id][user.id] = 0
        #                try: alt_aliases[guiild.id][user.id]
        #                except: alt_aliases[guild.id][user.id] = {}
        #                try: npc_aliases[guiild.id][user.id]
        #                except: npc_aliases[guild.id][user.id] = {}
        #                allowed_ids[user.id] = []
        #                for channel in guild.text_channels:
        #                    try: alt_aliases[guild.id][user.id][channel.id]
        #                    except: alt_aliases[guild.id][user.id][channel.id] = ""
        #                    try: npc_aliases[guild.id][user.id][channel.id]
        #                    except: npc_aliases[guild.id][user.id][channel.id] = ""
        # GMRole,NPCRole,PlayerRole,GuildBankBalance,StartingHealth,StartingMana,StartingStamina,StartingAttack,StartingDefense,StartingMagicAttack,StartingAgility,StartingIntellect,StartingCharisma,HealthLevelAdd,ManaLevelAdd,StaminaLevelAdd,XPLevelRatio,HealthAutoHeal,ManaAutoHeal,StaminaAutoHeal
        # ALTER TABLE GuildSettings ADD COLUMN StartingHealth Int, StartingMana Int, StartingStamina Int, StartingAttack Int, StartingDefense Int, StartingMagicAttack Int, StartingAgility Int, StartingIntellect Int, StartingCharisma Int, HealthLevelAdd Int, ManaLevelAdd Int, StaminaLevelAdd Int, XPLevelRatio Int, HealthAutoHeal DECIMAL(1,2), ManaAutoHeal DECIMAL (1,2), StaminaAutoHeal DECIMAL(1,2);
        await log_message("Loading guild settings...")
        records = await select_sql(
            """SELECT ServerId,IFNULL(AdminRole,'0'),IFNULL(GameModeratorRole,'0'),IFNULL(NPCRole,'0'),IFNULL(PlayerRole,'0'),IFNULL(StartingHealth,'0'),IFNULL(StartingMana,'0'),IFNULL(StartingStamina,'0'),IFNULL(StartingAttack,'0'),IFNULL(StartingDefense,'0'),IFNULL(StartingMagicAttack,'0'),IFNULL(StartingAgility,'0'),IFNULL(StartingIntellect,'0'),IFNULL(StartingCharisma,'0'),IFNULL(HealthLevelAdd,'0'),IFNULL(ManaLevelAdd,'0'),IFNULL(StaminaLevelAdd,'0'),IFNULL(XPLevelRatio,'0'),IFNULL(HealthAutoHeal,'0'),IFNULL(ManaAutoHeal,'0'),IFNULL(StaminaAutoHeal,'0'),IFNULL(XPChannelId,'0'),IFNULL(AutoCharApproval,'0'),IFNULL(StatPointsPerLevel,'0'), IFNULL(CritterChannelId,'0') FROM GuildSettings;""")
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
                    guild_settings[server_id]["HealthLevelAdd"] = int(row[14])
                if row[15] is not None:
                    guild_settings[server_id]["ManaLevelAdd"] = int(row[15])
                if row[16] is not None:
                    guild_settings[server_id]["StaminaLevelAdd"] = int(row[16])
                if row[17] is not None:
                    guild_settings[server_id]["XPLevelRatio"] = int(row[17])
                if row[18] is not None:
                    guild_settings[server_id]["HealthAutoHeal"] = float(row[18])
                if row[19] is not None:
                    guild_settings[server_id]["ManaAutoHeal"] = float(row[19])
                if row[20] is not None:
                    guild_settings[server_id]["StaminaAutoHeal"] = float(row[20])
                if row[21] is not None:
                    guild_settings[server_id]["XPChannel"] = client.get_channel(int(row[21]))
                if row[22] is not None:
                    guild_settings[server_id]["AutoCharApproval"] = int(row[22])
                if row[23] is not None:
                    guild_settings[server_id]["StatPointsPerLevel"] = int(row[23])
                if row[24] is not None:
                    guild_settings[server_id]["CritterChannel"] = client.get_channel(int(row[24]))
        await log_message("Loading alt channels...")
        records = await select_sql("""SELECT ServerId, UserId, ChannelId, Shortcut FROM AltChannels;""")
        for row in records:
            server_id = int(row[0])
            user_id = int(row[1])
            channel_id = int(row[2])
            shortcut = row[3]

            alt_aliases[server_id] = {}
            alt_aliases[server_id][user_id] = {}
            alt_aliases[server_id][user_id][channel_id] = shortcut
        #        records = await select_sql("""SELECT UserId, CurrentCommand, CurrentField, FieldList, FieldDict, ServerId, CommandChannel, Parameters, FieldMeans FROM DMTracker;""")
        #        for row in records:
        #            user = int(row[0])
        #            dm_tracker[user] = { }
        #            dm_tracker[user]["currentcommand"] = row[1]
        #            dm_tracker[user]["currentfield"] = int(row[2])
        #            dm_tracker[user]["fieldlist"] = row[3].split(',')
        #            dm_tracker[user]["fielddict"] = row[4].split(',')
        #            dm_tracker[user]["server_id"] = int(row[5])
        #            dm_tracker[user]["commandchannel"] = client.get_channel(int(row[6]))
        #            dm_tracker[user]["parameters"] = row[7]
        #            dm_tracker[user]["fieldmeans"] = row[8].split('|')
        await log_message("Loading active characters...")
        records = await select_sql("""SELECT ServerId,UserId,CharacterId FROM ActiveChars;""")
        for row in records:
            active_chars[int(row[0])] = {}
            active_chars[int(row[0])][int(row[1])] = int(row[2])

        await log_message("Loading custom commands...")
        records = await select_sql("""SELECT ServerId,Command,Responses FROM CustomCommands;""")
        for row in records:
            server_id = int(row[0])
            custom_commands[server_id] = {}
            custom_commands[server_id][row[1]] = row[2].split('|')
        await log_message("All SQL loaded for guilds.")
        new_startup = False


@client.event
async def on_guild_join(guild):
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
    global mass_spar_cooldown
    global alt_aliases
    global fallen_chars
    global encounter_turn
    global npc_aliases
    global active_chars
    global daily
    global custom_commands
    global critter_spawn
    

    await log_message("Joined guild " + guild.name)
    server_encounters[guild.id] = False
    server_monsters[guild.id] = {}
    server_party[guild.id] = {}
    server_party_chars[guild.id] = {}
    guild_settings[guild.id] = {}
    mass_spar[guild.id] = {}
    mass_spar_event[guild.id] = False
    mass_spar_confirm[guild.id] = {}
    mass_spar_turn = 0
    alt_aliases[guild.id] = {}
    npc_aliases[guild.id] = {}
    active_chars[guild.id] = {}
    fallen_chars[guild.id] = {}
    custom_commands[guild.id] = {}
    mass_spar_cooldown[guild.id] = {}
    critter_spawn[guild.id] = 10

    result = await commit_sql(
        """INSERT INTO GuildSettings (ServerId,GuildBankBalance,StartingHealth,StartingMana,StartingStamina,StartingAttack,StartingDefense,StartingMagicAttack,StartingAgility,StartingIntellect,StartingCharisma,HealthLevelAdd,ManaLevelAdd,StaminaLevelAdd,XPLevelRatio,HealthAutoHeal,ManaAutoHeal,StaminaAutoHeal,XPChannelId,StatPointsLevel) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, %s, %s);""",
        (str(guild.id), "1000000", "200", "100", "100", "10", "5", "10", "10", "10", "10", "200", "100", "100", "200",
         "0.05", "0.1", "0.1", "0", "10"))
    guild_settings[guild.id]["StartingHealth"] = 200
    guild_settings[guild.id]["StartingMana"] = 100

    guild_settings[guild.id]["StartingStamina"] = 100

    guild_settings[guild.id]["StartingAttack"] = 10

    guild_settings[guild.id]["StartingDefense"] = 10

    guild_settings[guild.id]["StartingMagicAttack"] = 100

    guild_settings[guild.id]["StartingAgility"] = 10

    guild_settings[guild.id]["StartingIntellect"] = 10

    guild_settings[guild.id]["StartingCharisma"] = 10

    guild_settings[guild.id]["HealthLevelAdd"] = 200

    guild_settings[guild.id]["ManaLevelAdd"] = 100

    guild_settings[guild.id]["StaminaLevelAdd"] = 100

    guild_settings[guild.id]["XPLevelRatio"] = 200

    guild_settings[guild.id]["HealthAutoHeal"] = 0.05

    guild_settings[guild.id]["ManaAutoHeal"] = 0.1

    guild_settings[guild.id]["StaminaAutoHeal"] = 0.1
    guild_settings[guild.id]["XPChannel"] = None
    guild_settings[guild.id] = {}

    custom_commands[guild.id] = {}
    encounter_turn[guild.id] = 0

    daily[guild.id] = {}
    for user in guild.members:
        daily[guild.id][user.id] = {}
        npc_aliases[guild.id][user.id] = {}
        alt_aliases[guild.id][user.id] = {}
        for channel in guild.text_channels:
            npc_aliases[guild.id][user.id][channel.id] = ""
            alt_aliases[guild.id][user.id][channel.id] = ""

    embed = discord.Embed(title="RP Mastermind",
                          description="Thank you for inviting RP Mastermind, the Discord RP bot! See below for how to get started!")
    embed.add_field(name="Getting help",
                    value="Use =info or =help to see the bot help. There are categories of help for each set of commands. Type =info category (such as **=info setup**) to see a category's command list.\nIf you need help, check the wiki at http://rpmm.wikidot.com/ or join the support server at https://discord.gg/3CKdNPx")
    embed.add_field(name="Required Permissions",
                    value="The bot should be granted proper permissions in the invite, but the following Discord permissions are needed:\n• Read Text Channels and See Voice Channels\n• Manage Roles\n• Manage Webhooks\n• Manage Messages\n• Send Messages\n• Read Message History\n• Read Messages\n• Embed Links\n• Attach Files\n• Add Reactions\n\nThe user setting up the bot must have at least Manage Server permissions.",
                    inline=False)
    embed.add_field(name="Getting started",
                    value="There are two options for setting up the bot: default and custom. For default setup:\n\n• Type **=createroles** for the bot to create the four required management roles.\n• Type **=addadmin @user1 @user2** (Discord mentions) to set bot administrators.\n• Type **=loaddefault** to load basic spells, monsters, items, armaments, and melee attacks to the server.\n• Type **=addgm @user1 @user2** for game moderators.\n• Type **=addplayer @user1 @user2** for roleplayers.\n\nFor custom setup:\n\n•Type **=setadminrole @DiscordRole** (role mention) to set the bot admin role.\n• Type **=newsetup** to start the DM setup of the server settings, like starting HP and bank balance.\n• Type **=setgmrole @DiscordRole** (role mention) to set the bot GM role.\n• Type **=setplayerrole @DiscordRole** (role mention) to set the roleplayer role.\n",
                    inline=False)
    embed.add_field(name="Bot Roles",
                    value="`Admin:` The admin can run all commands of the bot, such as adding and deleting spells or items. A user with manage server permissions must set the admin role.\n\n`Game Moderator:` The game moderator is able to start random encounters, add or delete monsters, give money, and give items.\n\n`Alt Manager:` The Alt manager is able to create, edit and delete Alts.\n\n`Player:` A player is able to add, edit, and delete their character profile, and play as their character, and post as Alts if allowed, and buy and sell items, and trade with other players. An admin role user must approve new characters.",
                    inline=False)
    await guild.text_channels[0].send(embed=embed)


@client.event
async def on_guild_remove(guild):
    await log_message("Left guild " + guild.name)
    result = await commit_sql("""DELETE FROM GuildSettings WHERE ServerId=%s;""", (str(guild.id),))


@client.event
async def on_message(message):
    global webhook
    global server_monsters
    global server_encounters
    global server_party
    global server_party_chars
    global guild_settings
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
    global daily
    global custom_commands
    global allowed_ids
    global mass_spar_cooldown
    global active_chars
    global critter_spawn
    

    if message.author.bot:
        return
    if message.author == client.user:
        return
    try:
        npc_aliases[message.guild.id]
    except:
        try:
            message.guild.id
            npc_aliases[message.guild.id] = {}
        except:
            pass

    try:
        npc_aliases[message.guild.id][message.author.id]

    except:
        try:
            message.guild.id
            npc_aliases[message.guild.id][message.author.id] = {}

        except:
            pass

    try:
        npc_aliases[message.guild.id][message.author.id][message.channel.id]
    except:
        try:
            message.guild.id
            pc_aliases[message.guild.id][message.author.id][message.channel.id] = None
        except:
            pass

    try:
        alt_aliases[message.guild.id]
    except:
        try:
            message.guild.id
            alt_aliases[message.guild.id] = {}
        except:
            pass

    try:
        alt_aliases[message.guild.id][message.author.id]

    except:
        try:
            message.guild.id
            alt_aliases[message.guild.id][message.author.id] = {}

        except:
            pass

    try:
        alt_aliases[message.guild.id][message.author.id][message.channel.id]
    except:
        try:
            message.guild.id
            npc_aliases[message.guild.id][message.author.id][message.channel.id] = None
        except:
            pass
    try:
        active_chars[message.guild.id][message.author.id]
    except:
        try:
            message.guild.id
            active_chars[message.guild.id][message.author.id] = None
        except:
            pass

    das_server = message.guild

    if message.content.startswith('=answer'):
        das_server = None
        message.content = message.content.replace('=answer ', '')

    if not das_server:
        await log_message("Received DM from user " + message.author.name + " with content " + message.content)

        try:
            allowed_ids[message.author.id][0]
            await log_message(str(allowed_ids[messasge.author.id][0]))
            if allowed_ids[message.author.id][0] is not None:
                allowed_to_continue = False
                if message.content == '0' or message.content == 'end':
                    allowed_to_continue = True
                for x in allowed_ids[message.author.id]:
                    if x == message.content:
                        allowed_to_continue = True
                if not allowed_to_continue:
                    await direct_message(message, "The ID you gave is not in the list. Please try again.")
                    return
                else:
                    allowed_ids[message.author.id] = None
        except:
            pass

        current_command = dm_tracker[message.author.id]["currentcommand"]
        current_field = dm_tracker[message.author.id]["currentfield"]
        field_list = dm_tracker[message.author.id]["fieldlist"]
        field_dict = dm_tracker[message.author.id]["fielddict"]
        server_id = dm_tracker[message.author.id]["server_id"]
        field_means = dm_tracker[message.author.id]["fieldmeans"]
        
        if message.attachments and current_command.startswith('new'):
        
            field_dict.append(message.attachments[0].url)        
        elif message.attachments and current_command.startswith('edit'):
            field_dict[-1] = message.attachments[0].url
        #        result = await commit_sql("""DELETE FROM DMTracker WHERE UserId=%s;""",(str(message.author.id),))
        #        temp_list = []
        #       for x in field_dict:
        #           temp_list.append(str(x))
        #       if current_command.startswith('new') or current_command.startswith('edit'):
        #           result = await commit_sql("""INSERT INTO DMTracker (UserId, CurrentCommand, CurrentField, FieldList, FieldDict, ServerId, CommandChannel, Parameters, FieldMeans) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);""",(str(message.author.id), current_command, str(current_field+ 1), ','.join(field_list), ','.join(temp_list), str(server_id), str(dm_tracker[message.author.id]["commandchannel"].id), dm_tracker[message.author.id]["parameters"], str(','.join(dm_tracker[message.author.id]["fieldmeans"]))))

        await log_message("Command : " + current_command + " Field: " + str(current_field) + " Field list: " + str(
            field_list) + " Field dict: " + str(field_dict))

        if current_field > len(field_list) + 1:
            await direct_message(message,
                                 "You've gone beyond the field list limit. Please rerun your command and try again.")
            return
        if message.content == 'stop' or message.content == 'Stop':
            dm_tracker[message.author.id] = {}
            allowed_ids[message.author.id] = {}
            await direct_message(message, "Command stopped!")
            return
        if current_field < len(field_list):
            if re.search(r"Id", field_list[current_field]) and re.search(r"[^0-9]", message.content) and not re.search(
                    r"setup", current_command):
                await direct_message(message,
                                     "That is not a valid ID. Please enter one of the IDs specified above as a reply and try again.")
                return
            if field_list[current_field] == 'StatMod' and not re.search(
                    r"Attack|Defense|MagicAttack|Health|Mana|Stamina|Agility|Intellect|Charisma|None",
                    message.content) and not re.search(r"skip", message.content, re.IGNORECASE):
                await direct_message(message,
                                     "That is not a valid response. Valid stats are Attack, Defense, MagicAttack, Health, Mana, Stamina, Agility, Intellect or Charisma, and these are case sensitive. Please reply again with a valid stat.")
                return
            if (re.search(
                    r"Health$|Attack$|Defense|MagicAttack|Modifier|Level|Mana$|Stamina$|Agility|Charisma|Intellect|Modifier|ManaCost|StaminaCost|DamageMultiplier|MinimumLevel|DamageMin|DamageMax|exit",
                    field_list[current_field]) and re.search(r"[^0-9\-\.]", message.content) and not (
                    message.content == 'skip' or message.content == 'Skip')):
                await reply_message(message,
                                    "This field only allows numerical integer values. Please only use 0-9 or a hyphen (-, to indicate negative numbers) and reply again.")
                return

            if re.search(r"ArmamentCost|EquipmentCost|MaxCurrencyDrop", field_list[current_field]) and re.search(
                    r"[^0-9\.]", message.content) and not (message.content == 'skip' or message.content == 'Skip'):
                await direct_message(message,
                                     "This field only allows positive decimal values. Please reply with a valid decimal number and try again.")
                return
            if field_list[current_field] == 'Race':
                records = await select_sql("""SELECT Name FROM Races WHERE ServerId=%s;""",
                                           (str(dm_tracker[message.author.id]["server_id"]),))
                if not records:
                    pass
                else:
                    race_list = ["None"]
                    for row in records:
                        race_list.append(row[0])
                    if message.content not in list(race_list):
                        await direct_message(message,
                                             "That is not a valid choice for race. Please choose a race from the server list.")
                        return

            if field_list[current_field] == 'Class':
                records = await select_sql("""SELECT Name FROM Classes WHERE ServerId=%s;""",
                                           (str(dm_tracker[message.author.id]["server_id"]),))
                if not records:
                    pass
                else:
                    class_list = ["None"]
                    for row in records:
                        class_list.append(row[0])
                    if message.content not in list(class_list):
                        await direct_message(message,
                                             "That is not a valid choice for class. Please choose a class from the server list.")
                        return
        if re.search(r"skip", message.content, re.IGNORECASE) and current_field < len(
                field_list) - 1 and current_command.startswith('edit'):
            if field_list[current_field + 1] == 'Race':
                dm_tracker[message.author.id]["parameters2"] = field_dict[current_field + 1]
            dm_tracker[message.author.id]["currentfield"] = dm_tracker[message.author.id]["currentfield"] + 1
            if current_field < len(field_list) - 1:
                #                embed=discord.Embed(title=field_list[current_field + 1],description=current_command)
                #                embed.add_field(name="Next field:",value=dm_tracker[message.author.id]["fieldlist"][current_field + 1])
                if not re.search(r"Description",field_list[current_field + 1]):
                    embed = discord.Embed(title=field_list[current_field + 1], description=field_means[current_field + 1])
                    embed.add_field(name="Value:", value=str(dm_tracker[message.author.id]["fielddict"][current_field + 1]))
                else:
                    response = "**Current field:** " + field_list[current_field + 1] + "\n**Field Definition:**" + field_means[current_field + 1] + "\n**Value:** " + str(dm_tracker[message.author.id]["fielddict"][current_field + 1])
                    await direct_message(message, response)
                    return
                #                embed.add_field(name="Description:",value=field_means[current_field + 1])
                #                embed.add_field(name="Last field status:",value="Skipped")
                embed.add_field(name="Instructions:",
                                value="Enter the desired value as a reply, or *skip* to keep the current value, or *stop* to stop this command completely.")
                if field_list[current_field + 1] == 'Race':
                    records = await select_sql("""SELECT Name FROM Races WHERE ServerId=%s;""",
                                               (str(dm_tracker[message.author.id]["server_id"]),))
                    if not records:
                        pass
                    else:
                        race_list = ""
                        for row in records:
                            race_list = race_list + row[0] + ","
                        embed.add_field(name="Server Races", value=race_list)
                if field_list[current_field + 1] == 'Class':
                    records = await select_sql("""SELECT Name FROM Classes WHERE ServerId=%s;""",
                                               (str(dm_tracker[message.author.id]["server_id"]),))
                    if not records:
                        pass
                    else:
                        class_list = ""
                        for row in records:
                            class_list = class_list + row[0] + ","
                        embed.add_field(name="Server Classes", value=class_list)
                await direct_message(message, " ", embed)
                #                await direct_message(message, "Value:" + str(dm_tracker[message.author.id]["fielddict"][current_field + 1]))
                # await direct_message(message, "Skipping field **"  + field_list[current_field] + "** and not changing its value.\n\nThe next field is **" + dm_tracker[message.author.id]["fieldlist"][current_field + 1] + "**\n\nwith a description of: " + field_means[current_field + 1] + "\n\nand its value is **" + str(dm_tracker[message.author.id]["fielddict"][current_field + 1]) + "**. Reply with the new value or *skip* to leave the current value.")

                return
            else:
                embed = discord.Embed(title=field_list[current_field + 1])
                embed.add_field(name="Field status:", value="Skipped")
                embed.add_field(name="Instructions:",
                                value="That was the last field. Type *end* to commit changes or *stop* to cancel.")
                await direct_message(message, " ", embed=embed)
                # await direct_message(message, "Skipping field **"  + field_list[current_field] + "** and not changing its value. That was the last field. Reply *end* to commit to the database.")
                return

        if current_command.startswith('edit') and current_field < len(field_list) - 1:

            if current_field == 0 and message.content.strip() != dm_tracker[message.author.id]["fielddict"][
                0] and current_command != 'editstats':
                dm_tracker[message.author.id]["parameters"] = dm_tracker[message.author.id]["fielddict"][0]
            if field_list[current_field + 1] == 'Race':
                dm_tracker[message.author.id]["parameters2"] = field_dict[current_field + 1]
            dm_tracker[message.author.id]["fielddict"][current_field] = message.content
            dm_tracker[message.author.id]["currentfield"] = current_field + 1
                #                embed = discord.Embed(title=field_list[current_field + 1],description=current_command)
                #                embed.add_field(name="Next field:",value=dm_tracker[message.author.id]["fieldlist"][current_field + 1])
                #                embed.add_field(name="Next field description:",value=field_means[current_field + 1])
                #                embed.add_field(name="Last field:",value=dm_tracker[message.author.id]["fieldlist"][current_field])
                #                embed.add_field(name="Last field status:",value="Value edited")
                #                embed.add_field(name="Instructions:",value="Reply with the new desired value, type *skip* to keep the current value, or type *stop* to cancel the command.")
            if current_field < len(field_list) - 1:
                #                embed=discord.Embed(title=field_list[current_field + 1],description=current_command)
                #                embed.add_field(name="Next field:",value=dm_tracker[message.author.id]["fieldlist"][current_field + 1])
                if not re.search(r"Description",field_list[current_field + 1]):
                    embed = discord.Embed(title=field_list[current_field + 1], description=field_means[current_field + 1])
                    embed.add_field(name="Value:", value=str(dm_tracker[message.author.id]["fielddict"][current_field + 1]))
                else:
                    response = "**Current field:** " + field_list[current_field + 1] + "\n**Field Definition:**" + field_means[current_field + 1] + "\n**Value:** " + str(dm_tracker[message.author.id]["fielddict"][current_field + 1])
                    await direct_message(message, response)
                    return
                embed.add_field(name="Instructions:",
                                value="Reply with the new desired value, type *skip* to keep the current value, or type *stop* to cancel the command.")
                if field_list[current_field + 1] == 'Race':

                    records = await select_sql("""SELECT Name FROM Races WHERE ServerId=%s;""",
                                               (str(dm_tracker[message.author.id]["server_id"]),))
                    if not records:
                        pass
                    else:
                        race_list = ""
                        for row in records:
                            race_list = race_list + row[0] + ","
                        embed.add_field(name="Server Races", value=race_list)
                if field_list[current_field + 1] == 'Class':
                    records = await select_sql("""SELECT Name FROM Classes WHERE ServerId=%s;""",
                                               (str(dm_tracker[message.author.id]["server_id"]),))
                    if not records:
                        pass
                    else:
                        class_list = ""
                        for row in records:
                            class_list = class_list + row[0] + ","
                        embed.add_field(name="Server Classes", value=class_list)

                await direct_message(message, " ", embed)


            else:

                embed = discord.Embed(title=dm_tracker[message.author.id]["fieldlist"][current_field],
                                      description=field_means[current_field])
                embed.add_field(name="Value:", value=str(dm_tracker[message.author.id]["fielddict"][current_field]))
                embed.add_field(name="Instructions:",
                                value="That was the last field. Type *end* to commit all edits to the database or *stop* to cancel.")
                await direct_message(message, " ", embed)
            #                await direct_message(message, "Value set to: " + str(dm_tracker[message.author.id]["fielddict"][current_field]))
            #                await direct_message(message, "Setting field **"  + dm_tracker[message.author.id]["fieldlist"][current_field] + "** to **" + message.content.strip() + "**. That was the last field. Reply *end* to commit to the database.")

            return
        elif current_command == 'newvendor':
            if current_field == 0:
                menu = await make_simple_menu(message, "Equipment", "EquipmentName")
                await direct_message(message,
                                     "Vendor now named " + message.content + ". Please enter the ID of each item as a single reply until you have added all items the vendor should sell, then type **end** to commit.\n\n" + menu)
                dm_tracker[message.author.id]["currentfield"] = 1
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                dm_tracker[message.author.id]["fielddict"].append(" ")
                return
            elif current_field == 1:
                if message.content == 'end':
                    dm_tracker[message.author.id]["currentfield"] = 2
                    await direct_message(message,
                                         "Please upload or enter a picture link, or type None or N/A for no picture.")
                    return
                dm_tracker[message.author.id]["fielddict"][1] = str(
                    dm_tracker[message.author.id]["fielddict"][1]) + message.content + ", "
                menu = await make_simple_menu(message, "Equipment", "EquipmentName")
                response = "Please reply with the ID of the item to add, or **end** to commit the item list.\n\n" + menu
                await direct_message(message, response)
                return
            elif current_field == 2:
                if dm_tracker[message.author.id]["fielddict"][-2] == 'end':
                    dm_tracker[message.author.id]["fielddict"].remove('end')
                if message.attachments:
                    dm_tracker[message.author.id]["fielddict"].append(message.attachments[0].url)
                else:
                    dm_tracker[message.author.id]["fielddict"].append(message.content)
                result = await insert_into(message, "Vendors")
                if result:
                    await direct_message(message, "Vendor " + field_dict[0] + " created successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Vendor " + field_dict[0] + " created successfully.")
                else:
                    await direct_message(message, "Database error!")
                return
        elif current_command == 'newcustomcommand' and message.content != 'end':
            if current_field == 0:
                await direct_message(message,
                                     "Command now named " + message.content + ". Please enter the possible responses as a single reply until you have added all desired responses, then type **end** to commit.\n\n")
                dm_tracker[message.author.id]["currentfield"] = 1
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                dm_tracker[message.author.id]["fielddict"].append(" ")
                return
            else:
                dm_tracker[message.author.id]["fielddict"][1] = str(
                    dm_tracker[message.author.id]["fielddict"][1]) + message.content + "|"
                response = "Please reply with the response desired, or **end** to commit the item list.\n\n"
                await direct_message(message, response)
                return
        elif current_command == 'addvendoritem' and message.content != 'end':
            if current_field == 0:
                menu = await make_simple_menu(message, "Equipment", "EquipmentName")
                await direct_message(message,
                                     "Please enter the ID of each item as a single reply until you have added all items the vendor should sell, then type **end** to commit.\n\n" + menu)
                dm_tracker[message.author.id]["currentfield"] = 1
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                dm_tracker[message.author.id]["fielddict"].append(" ")
                return
            else:
                dm_tracker[message.author.id]["fielddict"][1] = str(
                    dm_tracker[message.author.id]["fielddict"][1]) + message.content + ", "
                menu = await make_simple_menu(message, "Equipment", "EquipmentName")
                response = "Please reply with the ID of the item to add, or **end** to commit the item list.\n\n" + menu
                await direct_message(message, response)
                return
        elif current_command == 'newarmory':
            if current_field == 0:
                menu = await make_simple_menu(message, "Armaments", "ArmamentName")
                await direct_message(message,
                                     "Vendor now named " + message.content + ". Please enter the ID of each item as a single reply until you have added all items the armory should sell, then type **end** to commit.\n\n" + menu)
                dm_tracker[message.author.id]["currentfield"] = 1
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                dm_tracker[message.author.id]["fielddict"].append(" ")
                return
            elif current_field == 1:
                if message.content == 'end':
                    dm_tracker[message.author.id]["currentfield"] = 2
                    await direct_message(message,
                                         "Please upload or enter a picture link, or type None or N/A for no picture.")
                    return
                dm_tracker[message.author.id]["fielddict"][1] = str(
                    dm_tracker[message.author.id]["fielddict"][1]) + message.content + ", "
                menu = await make_simple_menu(message, "Armaments", "ArmamentName")
                response = "Please reply with the ID of the item to add, or **end** to commit the item list.\n\n" + menu
                await direct_message(message, response)
                return
            elif current_field == 2:
                if dm_tracker[message.author.id]["fielddict"][-2] == 'end':
                    dm_tracker[message.author.id]["fielddict"].remove('end')
                if message.attachments:
                    dm_tracker[message.author.id]["fielddict"].append(message.attachments[0].url)
                else:
                    dm_tracker[message.author.id]["fielddict"].append(message.content)
                result = await insert_into(message, "Armory")
                if result:
                    await direct_message(message, "Armory " + field_dict[0] + " created successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Armory " + field_dict[0] + " created successfully.")
                else:
                    await direct_message(message, "Database error!")
                return

        elif current_command == 'addarmoryitem' and message.content != 'end':
            if current_field == 0:
                menu = await make_simple_menu(message, "Armaments", "ArmamentName")
                await direct_message(message,
                                     "Please enter the ID of each item as a single reply until you have added all items the armory should sell, then type **end** to commit.\n\n" + menu)
                dm_tracker[message.author.id]["currentfield"] = 1
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                dm_tracker[message.author.id]["fielddict"].append(" ")
                return
            else:
                dm_tracker[message.author.id]["fielddict"][1] = str(
                    dm_tracker[message.author.id]["fielddict"][1]) + message.content + ", "
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
                for x in range(0, 10):
                    delete_tuple = delete_tuple + (str(dm_tracker[message.author.id]["server_id"]),)
                deletions = ["Alts", "ArmamentInventory", "Armaments", "Armory", "BuffSkills", "Buffs",
                             "CharacterArmaments", "CharacterProfiles", "CustomProfiles", "Equipment", "GuildSettings",
                             "Inventory", "MagicSkills", "Melee", "MeleeSkills", "Monsters", "NonPlayerCharacters",
                             "Quests", "Spells", "UnapprovedCharacterProfiles", "Vendors","Races","Classes","AltChannels","ActiveChars","Critters","CustomCommands","SummonInventory"]
                for delete in deletions:
                    await commit_sql("""DELETE FROM """ + delete + """ WHERE ServerId=%s;""",
                                     (str(dm_tracker[message.author.id]["server_id"]),))
                result = await commit_sql(
                    """INSERT INTO GuildSettings (ServerId,GuildBankBalance,StartingHealth,StartingMana,StartingStamina,StartingAttack,StartingDefense,StartingMagicAttack,StartingAgility,StartingIntellect,StartingCharisma,HealthLevelAdd,ManaLevelAdd,StaminaLevelAdd,XPLevelRatio,HealthAutoHeal,ManaAutoHeal,StaminaAutoHeal) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);""",
                    (str(dm_tracker[message.author.id]["server_id"]), "1000000", "200", "100", "100", "10", "5", "10",
                     "10", "10", "10", "200", "100", "100", "200", "0.05", "0.1", "0.1"))
                await direct_message(message, "Server reset complete!")
                await dm_tracker[message.author.id]["commandchannel"].send(
                    ">>> Server reset complete! Please run =setadminrole @adminrole followed by =newsetup to create a new setup for this server!")
                return

        elif current_command == 'deletevendoritem':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                records = await select_sql("""SELECT ItemList,VendorName FROM Vendors WHERE Id=%s;""",
                                           (message.content,))
                if not records:
                    await reply_message(message, "No vendor found by that ID!")
                    return
                for row in records:
                    items = row[0]
                    vendor_name = row[1]
                response = "**ITEMS FOR VENDOR " + message.content + "**\n\n"
                item_list = items.split(',')
                for item in item_list:
                    item_record = await select_sql("""SELECT EquipmentName FROM Equipment WHERE Id=%s""", (item,))
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
                items = items.replace(message.content + ",", "")
                result = await commit_sql("UPDATE Vendors SET ItemList=%s WHERE Id=%s", (items, field_dict[0]))
                if result:
                    await direct_message(message, "Item deleted from vendor successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Item deleted from vendor successfully.")
                return
        elif current_command == 'randomprofile':
            if message.content == 'YES':
                if guild_settings[dm_tracker[message.author.id]["server_id"]]["AutoCharApproval"] == 1:
                    result = await insert_into(message, "UnapprovedCharacterProfiles")

                    if result:
                        await direct_message(message,
                                             "Character application for " + field_dict[0] + " created successfully.")
                        await dm_tracker[message.author.id]["commandchannel"].send(
                            ">>> Character application for  " + field_dict[
                                0] + " successfully created.\n\nAfter approval, you may edit any character fields with =change.\n\n<@&" + str(
                                guild_settings[dm_tracker[message.author.id]["server_id"]][
                                    "AdminRole"]) + ">, please approve or decline the character with =approve or =deny.")
                    else:
                        await direct_message(message, "Database error!")
                else:
                    result = await insert_into(message, "CharacterProfiles")

                    if result:
                        await direct_message(message,
                                             "Character application for " + field_dict[0] + " created successfully.")
                        await dm_tracker[message.author.id]["commandchannel"].send(">>> Character  " + field_dict[
                            0] + " successfully created. You may edit any character fields with =change.")
                    else:
                        await direct_message(message, "Database error!")
            else:
                await direct_message(message, "Character discarded.")
            return
        elif current_command == 'deletearmoryitem':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                records = await select_sql("""SELECT ItemList,ArmamentName FROM Armory WHERE Id=%s;""",
                                           (message.content,))
                if not records:
                    await reply_message(message, "No armory found by that ID!")
                    return
                for row in records:
                    items = row[0]
                    armory_name = row[1]
                response = "**ITEMS FOR VENDOR " + message.content + "**\n\n"
                item_list = items.split(',')
                for item in item_list:
                    item_record = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s""", (item,))
                    for item_name in item_record:
                        response = response + item_name[0] + "\n"
                menu = "Type the ID of the item you'd like to delete from this armory in a reply below.\n\n"
                await direct_message(message, menu + response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            elif current_field == 1:
                records = await select_sql("""SELECT ItemList,ArmamentName FROM Armory WHERE Id=%s;""",
                                           (field_dict[0],))
                if not records:
                    await reply_message(message, "No armory found by that ID!")
                    return
                for row in records:
                    items = row[0]
                    armory_name = row[1]
                items = items.replace(message.content + ",", "")
                result = await commit_sql("UPDATE Armory SET ItemList=%s WHERE Id=%s", (items, field_dict[0]))
                if result:
                    await direct_message(message, "Item deleted from armory successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Item deleted from armory successfully.")
        elif current_command == 'approve':
            unapproved_char_id = message.content
            records = await select_sql("""SELECT CharacterName,UserId FROM UnapprovedCharacterProfiles WHERE Id=%s""",
                                       (message.content,))
            for row in records:
                char_name = row[0]
                char_user_id = row[1]
            # Copy to Character profiles
            records = await select_sql(
                """SELECT ServerId,UserId,CharacterName,Age,Race,Gender,Height,Weight,Playedby,Origin,Occupation,PictureLink,Attack,Defense,MagicAttack,Health,Mana,Level,Experience,Stamina,Agility,Intellect,Charisma,Currency,IFNULL(Biography,'None'),IFNULL(Description,'None'),IFNULL(Personality,'None'),IFNULL(Powers,'None'),IFNULL(Strengths,'None'),IFNULL(Weaknesses,'None'),IFNULL(Skills,'None'),StatPoints,Class,MaxHealth,MaxStamina,MaxMana FROM UnapprovedCharacterProfiles WHERE Id=%s;""",
                (message.content,))
            insert_statement = """INSERT INTO CharacterProfiles (ServerId,UserId,CharacterName,Age,Race,Gender,Height,Weight,Playedby,Origin,Occupation,PictureLink,Attack,Defense,MagicAttack,Health,Mana,Level,Experience,Stamina,Agility,Intellect,Charisma,Currency,Biography,Description,Personality,Powers,Strengths,Weaknesses,Skills,StatPoints,Class,MaxHealth,MaxStamina,MaxMana) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, %s, %s, %s);"""
            insert_tuple = ()
            for row in records:
                for item in row:
                    insert_tuple = insert_tuple + (item,)
            result = await commit_sql(insert_statement, insert_tuple)
            #            result = await commit_sql("""INSERT INTO CharacterProfiles (SELECT * FROM UnapprovedCharacterProfiles WHERE Id=%s);""", (message.content,))
            if result:
                await dm_tracker[message.author.id]["commandchannel"].send(
                    ">>> <@" + char_user_id + ">, your character is approved! You may now play as " + char_name + ".")
            else:
                await direct_message(message, "Database error!")
                return
            result = await commit_sql("""DELETE FROM UnapprovedCharacterProfiles WHERE Id=%s;""", (message.content,))
            if result:
                await direct_message(message,
                                     "Character confirmed deletion and moved to approved characters list. User will be notiified of the approval.")
                deleted = True
            else:
                await direct_message(message, "Database error!")

            return
        elif current_command == 'deny':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                await direct_message(message,
                                     "Enter a reason why this character is declined. Please specify what needs to be changed to approve it, and if nothing can be changed, why it was deleted.")
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                await direct_message(message,
                                     "Please type **DELETE** in reply to this message if the character profile will be deleted from the unapproved character list.")
                dm_tracker[message.author.id]["currentfield"] = 2
                return
            if current_field == 2:
                records = await select_sql(
                    """SELECT UserId,CharacterName FROM UnapprovedCharacterProfiles WHERE Id=%s;""",
                    (dm_tracker[message.author.id]["fielddict"][0],))
                for row in records:
                    user_id = row[0]
                    char_name = row[1]

                if message.content == 'DELETE':
                    result = await commit_sql("""DELETE FROM UnapprovedCharacterProfiles WHERE Id=%s;""",
                                              (dm_tracker[message.author.id]["fielddict"][0],))
                    if result:
                        await direct_message(message,
                                             "Character confirmed deletion and not moved to approved characters list. User will be notiified of the decline and reason.")
                        deleted = True
                    else:
                        await direct_message(message, "Database error!")
                        return
                else:
                    deleted = False
                response = "Your character was declined. The reason given was:\n```" + \
                           dm_tracker[message.author.id]["fielddict"][1] + "```"
                if deleted:
                    response = response + "\n\nThe character was also deleted from unapproved profiles for the above reason. Please create a new application that fits the server rules.\n"
                user_obj = client.get_user(int(user_id))
                channel = await user_obj.create_dm()
                await channel.send(">>> " + response)
                await dm_tracker[message.author.id]["commandchannel"].send(
                    ">>> " + char_name + " was declined. <@" + str(
                        user_id) + ">, please check your DMs for the reason.")
                return

        elif current_command == 'monster2':
            records = await select_sql(
                """SELECT UserId,Attack,Defense,MagicAttack,Health,Mana,Level,Experience,Stamina,Agility,Intellect,Charisma,Id,CharacterName,Currency,PictureLink,MaxHealth,MaxStamina,MaxMana FROM CharacterProfiles WHERE Id=%s;""",
                (message.content,))
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
                server_party_chars[server_id][user_id] = {}
                server_party_chars[server_id][user_id]["CharName"] = row[13]
                server_party_chars[server_id][user_id]["Attack"] = int(row[1])
                server_party_chars[server_id][user_id]["Defense"] = int(row[2])
                server_party_chars[server_id][user_id]["MagicAttack"] = int(row[3])
                server_party_chars[server_id][user_id]["Health"] = int(row[4])
                server_party_chars[server_id][user_id]["MaxHealth"] = int(row[16])
                server_party_chars[server_id][user_id]["Mana"] = int(row[5])
                server_party_chars[server_id][user_id]["MaxMana"] = int(row[18])
                server_party_chars[server_id][user_id]["Level"] = int(row[6])
                server_party_chars[server_id][user_id]["Experience"] = int(row[7])
                server_party_chars[server_id][user_id]["Stamina"] = int(row[8])
                server_party_chars[server_id][user_id]["MaxStamina"] = int(row[17])
                server_party_chars[server_id][user_id]["Agility"] = int(row[9])
                server_party_chars[server_id][user_id]["Intellect"] = int(row[10])
                server_party_chars[server_id][user_id]["Charisma"] = int(row[11])
                server_party_chars[server_id][user_id]["CharId"] = int(row[12])
                server_party_chars[server_id][user_id]["Currency"] = float(row[14])

                if re.search(r"http", row[15]):
                    server_party_chars[server_id][user_id]["PictureLink"] = row[15]
                else:
                    server_party_chars[server_id][user_id]["PictureLink"] = narrator_url
                char_name = row[13]
            records = await select_sql(
                """SELECT IFNULL(HeadId,'None'),IFNULL(ChestId,'None'),IFNULL(LeftHandId,'None'),IFNULL(RightHandId,'None'),IFNULL(FeetId,'None'),IFNULL(FormId,'None') FROM CharacterArmaments WHERE CharacterId=%s;""",
                (str(server_party_chars[server_id][user_id]["CharId"]),))
            if records:
                for row in records:
                    for x in range(0, len(row)):
                        item = row[x]
                        if item != 'None':
                            arm_records = await select_sql(
                                """SELECT MinimumLevel,Defense,StatMod,Modifier FROM Armaments WHERE Id=%s;""",
                                (str(item),))
                            for arm_row in arm_records:
                                if int(arm_row[0]) < server_party_chars[server_id][user_id]["Level"]:
                                    if int(arm_row[1]) > 0:
                                        server_party_chars[server_id][user_id]["Defense"] = \
                                            server_party_chars[server_id][user_id]["Defense"] + int(arm_row[1])
                                        await log_message("applying defense!")
                                    if re.search(r"Attack|MagicAttack|Agility", arm_row[2]):
                                        server_party_chars[server_id][user_id][arm_row[2]] = \
                                            server_party_chars[server_id][user_id][arm_row[2]] + int(arm_row[3])
                                        await log_message("applying " + str(arm_row[3]) + " to " + str(arm_row[2]))

            await dm_tracker[message.author.id]["commandchannel"].send(
                ">>> " + message.author.name + " successfully set party character to " + char_name + ".")
            await direct_message(message, "You successfully set your party character to " + char_name + ".")
            return
        elif current_command == 'monster3':
            records = await select_sql(
                """SELECT IFNULL(Description,'None'),Health,Level,Attack,Defense,MagicAttack,IFNULL(PictureLink,' '),MaxCurrencyDrop,MonsterName FROM Monsters WHERE Id=%s""",
                (message.content,))
            if not records:
                await reply_message(message, "No monsters found!")
                return
            server_id = dm_tracker[message.author.id]["server_id"]
            for row in records:
                server_monsters[server_id]["MonsterName"] = row[8]
                monster_name = row[8]
                server_monsters[server_id]["Description"] = row[0]
                server_monsters[server_id]["Health"] = int(row[1])
                server_monsters[server_id]["Level"] = int(row[2])
                server_monsters[server_id]["Attack"] = int(row[3])
                server_monsters[server_id]["Defense"] = int(row[4])
                server_monsters[server_id]["Agility"] = server_monsters[server_id]["Level"] * random.randint(3, 7)
                server_monsters[server_id]["MagicAttack"] = int(row[5])
                server_monsters[server_id]["PictureLink"] = row[6]
                if not row[6].startswith('http'):
                    server_monsters[server_id]["PictureLink"] = narrator_url
                server_monsters[server_id]["MaxCurrencyDrop"] = int(row[7])
                monster_health[server_id] = int(row[1])
            server_encounters[server_id] = True
            await direct_message(message, "Beginning monster encounter with " + monster_name + ".")
            embed = discord.Embed(title="Monster Encounter Begins!",
                                  description="A **" + monster_name + "** has appeared in " + str(
                                      dm_tracker[message.author.id]["commandchannel"].name) + "!")
            if server_monsters[server_id]["PictureLink"].startswith('http'):
                embed.set_thumbnail(url=server_monsters[server_id]["PictureLink"])
            embed.add_field(name="Monster Level:", value=str(server_monsters[server_id]["Level"]))
            embed.add_field(name="Monster Description:", value=server_monsters[server_id]["Description"])
            embed.add_field(name="First Turn:",
                            value="<@" + str(list(server_party[server_id])[encounter_turn[server_id]].id) + ">")
            await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)

            # await dm_tracker[message.author.id]["commandchannel"].send(">>> The level " + str(server_monsters[server_id]["Level"]) + " **" + monster_name + "** has appeared in " + str(dm_tracker[message.author.id]["commandchannel"].name) + "! As described: " + server_monsters[server_id]["Description"] + "\n" + server_monsters[server_id]["PictureLink"] + "\n\nGood luck!\n\n<@" + str(list(server_party[server_id])[encounter_turn[server_id]].id) + "> gets first blood!")
            return
        elif current_command == 'hunt':
            server_encounters[server_id] = True
            await direct_message(message, "Beginning critter hunt with " + server_monsters[server_id]["MonsterName"] + ".")
            records = await select_sql(
                """SELECT UserId,Attack,Defense,MagicAttack,Health,Mana,Level,Experience,Stamina,Agility,Intellect,Charisma,Id,CharacterName,Currency,PictureLink,MaxHealth,MaxStamina,MaxMana FROM CharacterProfiles WHERE Id=%s;""",
                (message.content,))
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
                server_party_chars[server_id][user_id] = {}
                server_party_chars[server_id][user_id]["CharName"] = row[13]
                server_party_chars[server_id][user_id]["Attack"] = int(row[1])
                server_party_chars[server_id][user_id]["Defense"] = int(row[2])
                server_party_chars[server_id][user_id]["MagicAttack"] = int(row[3])
                server_party_chars[server_id][user_id]["Health"] = int(row[4])
                server_party_chars[server_id][user_id]["MaxHealth"] = int(row[16])
                server_party_chars[server_id][user_id]["Mana"] = int(row[5])
                server_party_chars[server_id][user_id]["MaxMana"] = int(row[18])
                server_party_chars[server_id][user_id]["Level"] = int(row[6])
                server_party_chars[server_id][user_id]["Experience"] = int(row[7])
                server_party_chars[server_id][user_id]["Stamina"] = int(row[8])
                server_party_chars[server_id][user_id]["MaxStamina"] = int(row[17])
                server_party_chars[server_id][user_id]["Agility"] = int(row[9])
                server_party_chars[server_id][user_id]["Intellect"] = int(row[10])
                server_party_chars[server_id][user_id]["Charisma"] = int(row[11])
                server_party_chars[server_id][user_id]["CharId"] = int(row[12])
                server_party_chars[server_id][user_id]["Currency"] = float(row[14])

                if re.search(r"http", row[15]):
                    server_party_chars[server_id][user_id]["PictureLink"] = row[15]
                else:
                    server_party_chars[server_id][user_id]["PictureLink"] = narrator_url
                char_name = row[13]
            records = await select_sql(
                """SELECT IFNULL(HeadId,'None'),IFNULL(ChestId,'None'),IFNULL(LeftHandId,'None'),IFNULL(RightHandId,'None'),IFNULL(FeetId,'None'),IFNULL(FormId,'None') FROM CharacterArmaments WHERE CharacterId=%s;""",
                (str(server_party_chars[server_id][user_id]["CharId"]),))
            if records:
                for row in records:
                    for x in range(0, len(row)):
                        item = row[x]
                        if item != 'None':
                            arm_records = await select_sql(
                                """SELECT MinimumLevel,Defense,StatMod,Modifier FROM Armaments WHERE Id=%s;""",
                                (str(item),))
                            for arm_row in arm_records:
                                if int(arm_row[0]) < server_party_chars[server_id][user_id]["Level"]:
                                    if int(arm_row[1]) > 0:
                                        server_party_chars[server_id][user_id]["Defense"] = \
                                            server_party_chars[server_id][user_id]["Defense"] + int(arm_row[1])
                                        await log_message("applying defense!")
                                    if re.search(r"Attack|MagicAttack|Agility", arm_row[2]):
                                        server_party_chars[server_id][user_id][arm_row[2]] = \
                                            server_party_chars[server_id][user_id][arm_row[2]] + int(arm_row[3])
                                        await log_message("applying " + str(arm_row[3]) + " to " + str(arm_row[2]))

            await dm_tracker[message.author.id]["commandchannel"].send(
                ">>> " + message.author.name + " successfully set party character to " + char_name + ".")
            await direct_message(message, "You successfully set your party character to " + char_name + ".")
            await dm_tracker[message.author.id]["commandchannel"].send(">>> Beginning hunt!")
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
                records = await select_sql("""SELECT AllowedClasses FROM Buffs WHERE Id=%s;""", (str(spell_id),))
                for row in records:
                    allowed_classes = row[0].split(',')

                char_record = await select_sql("""SELECT CharacterName,Class FROM CharacterProfiles WHERE Id=%s;""",
                                               (str(char_id),))

                for row in char_record:
                    char_name = row[0]
                    char_class = row[1]

                if char_class not in list(allowed_classes) and ("All" not in list(allowed_classes)):
                    await direct_message(message, char_name + " is not in the allowed clases for this buff!")
                    return
                result = await commit_sql(
                    """INSERT INTO BuffSkills (ServerId, UserId, CharId, BuffId) VALUES (%s, %s, %s, %s);""",
                    (str(dm_tracker[message.author.id]["server_id"]), str(message.author.id), char_id, spell_id))

                spell_record = await select_sql("""SELECT BuffName FROM Buffs WHERE Id=%s;""", (str(spell_id),))
                for row in spell_record:
                    spell_name = row[0]

                if result:
                    await direct_message(message, char_name + " can now use the buff " + spell_name + "!")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> " + char_name + " can now use the buff " + spell_name + "!")
                    await initialize_dm(message.author.id)
                else:
                    await direct_message(message, "Database error!")
                return
        elif current_command == 'givestatpoints':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                await direct_message(message, "Enter the number of stat points to grant.")
                dm_tracker[message.author.id]["currentfield"] = 1
                await log_message("value after givestat: " + str(dm_tracker[message.author.id]["currentfield"]))
                return
            if current_field == 1:
                records = await select_sql(
                    """SELECT UserId,CharacterName,StatPoints,Id FROM CharacterProfiles WHERE Id=%s""",
                    (dm_tracker[message.author.id]["fielddict"][0],))
                for row in records:
                    char_user = int(row[0])
                    char_name = row[1]
                    stat_points = int(row[2])
                    char_id = row[3]
                stat_points = int(message.content) + stat_points
                result = await commit_sql("""UPDATE CharacterProfiles SET StatPoints=%s WHERE Id=%s;""",
                                          (str(stat_points), str(char_id)))
                await direct_message(message,
                                     "You have granted " + char_name + " " + message.content + " points to spend.")
                await dm_tracker[message.author.id]["commandchannel"].send(">>> " + char_name + ", played by <@" + str(
                    char_user) + ">, has been granted " + message.content + " stat points to spend!\n\n")
                return
        elif current_command == 'givexp':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                await direct_message(message, "Enter the number of experience points to grant.")
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                records = await select_sql(
                    """SELECT UserId,CharacterName,Experience,Level,Health,Stamina,Mana FROM CharacterProfiles WHERE Id=%s""",
                    (dm_tracker[message.author.id]["fielddict"][0],))
                for row in records:
                    char_user = int(row[0])
                    char_name = row[1]
                    current_xp = int(row[2])
                    level = int(row[3])
                    health = int(row[4])
                    stamina = int(row[5])
                    mana = int(row[6])

                granted_xp = int(message.content)
                total_xp = current_xp + granted_xp
                if total_xp > (guild_settings[server_id]["XPLevelRatio"] * level):
                    available_points = 0
                    stat_points = 0
                    level = level + 1
                    records = await select_sql("""SELECT StatPoints FROM CharacterProfiles WHERE Id=%s;""",
                                               (str(field_dict[0]),))
                    for row in records:
                        stat_points = int(row[0])

                    available_points = int(guild_settings[server_id]["StatPointsPerLevel"]) + stat_points
                    response = "**" + char_name + "** LEVELED UP TO LEVEL **" + str(level) + "!**\nYou have " + str(
                        int(available_points)) + " stat points to spend!\n\n"
                    total_xp = 0
                    health = level * guild_settings[server_id]["HealthLevelAdd"]
                    stamina = level * guild_settings[server_id]["StaminaLevelAdd"]
                    mana = level * guild_settings[server_id]["ManaLevelAdd"]
                    result = await commit_sql("""UPDATE CharacterProfiles SET Level=%s,Experience=%s,Health=%s,Stamina=%s,Mana=%s,StatPoints=%s WHERE Id=%s;""",(str(level), str(total_xp), str(health), str(stamina), str(mana), str(available_points),  str(field_dict[0])))

                await direct_message(message,
                                     "You have granted " + char_name + " " + message.content + " experience points.")
                await dm_tracker[message.author.id]["commandchannel"].send(">>> " + char_name + ", played by <@" + str(
                    char_user) + ">, has been granted " + message.content + " experience points!\n\n")
                try:
                    response
                    await dm_tracker[message.author.id]["commandchannel"].send(response)

                except:
                    pass
                return
        elif current_command == 'equip':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_menu(message, "ArmamentInventory", "Armaments", "ArmamentId", "CharacterId",
                                       "ArmamentName", message.content)
                response = "Select an armament from your inventory to equip by replying with the ID below:\n\n" + menu
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:

                dm_tracker[message.author.id]["fielddict"].append(message.content.replace(' ', ''))
                target_slot = message.content.replace(' ', '') + "Id"
                records = await select_sql(
                    """SELECT ArmamentName,Slot,MinimumLevel,AllowedClasses FROM Armaments WHERE Id=%s""",
                    (field_dict[1],))
                for row in records:
                    arm_name = row[0]
                    slot = row[1]
                    minimumlevel = row[2]
                    allowed_classes = row[3].split(',')
                target_slot = slot + "Id"
                if not re.search(r"Hand",slot):
                    if allowed_classes[0] != 'All':
                        records = await select_sql("""SELECT Class FROM CharacterProfiles WHERE Id=%s;""",
                                                   (str(field_dict[0]),))
                        for row in records:
                            char_class = row[0]
                        if char_class not in list(allowed_classes) and ("All" not in list(allowed_classes)):
                            await direct_message(message, "You aren't the proper class to equip this armament!")
                            return
                    records = await select_sql("""SELECT CharacterName,Level FROM CharacterProfiles WHERE Id=%s""",
                                               (field_dict[0],))
                    for row in records:
                        char_name = row[0]
                        level = row[1]
                    records = await select_sql(
                        """SELECT IFNULL(""" + target_slot + """,'None') FROM CharacterArmaments WHERE CharacterId=%s;""",
                        (field_dict[0],))
                    for row in records:
                        char_slot = row[0]
                    try:
                        char_slot
                    except:
                        char_slot = 'None'
                        result = await commit_sql(
                            """INSERT INTO CharacterArmaments (ServerId,UserId,CharacterId, HeadId, LeftHandId, RightHandId, ChestId, FeetId, FormId) VALUES (%s, %s, %s, NULL, NULL, NULL, NULL, NULL, NULL);""",
                            (str(dm_tracker[message.author.id]["server_id"]), str(message.author.id), field_dict[0]))
                        if not result:
                            await direct_message(message, "Database error!")
                            return
                    if int(level) < int(minimumlevel):
                        await direct_message(message, char_name + " isn't a high enough level to equip this armament!")
                        return
                    if char_slot != 'None' and int(char_slot) != 0:
                        await direct_message(message, "You already have an armament equipped in this slot!")
                        return
                    if (slot == 'Hand' and not re.search('Hand', target_slot)) and (slot != target_slot):
                        await direct_message(message, "This armament does not go in this slot!")
                        return

                    result = await commit_sql(
                        """UPDATE CharacterArmaments SET """ + target_slot + """=%s WHERE CharacterId=%s""",
                        (field_dict[1], field_dict[0]))
                    if result:
                        await direct_message(message,
                                             char_name + " now has equipped " + arm_name + " on the " + slot + ".")
                        await dm_tracker[message.author.id]["commandchannel"].send(
                            ">>> " + char_name + " now has equipped " + arm_name + " on the " + slot + ".")
                    else:
                        await direct_message(mesage, "Database error!")
                    return
                else:
                    dm_tracker[message.author.id]["fielddict"].append(message.content)
                    response = "Please select a slot for this item (Left Hand, Right Hand):\n\n"
                    await direct_message(message, response)
                    dm_tracker[message.author.id]["currentfield"] = 2
                    return
            if current_field == 2:
                dm_tracker[message.author.id]["fielddict"].append(message.content.replace(' ', ''))
                target_slot = message.content.replace(' ', '') + "Id"
                records = await select_sql(
                    """SELECT ArmamentName,Slot,MinimumLevel,AllowedClasses FROM Armaments WHERE Id=%s""",
                    (field_dict[1],))
                for row in records:
                    arm_name = row[0]
                    slot = row[1]
                    minimumlevel = row[2]
                    allowed_classes = row[3].split(',')            
                if allowed_classes[0] != 'All':
                    records = await select_sql("""SELECT Class FROM CharacterProfiles WHERE Id=%s;""",
                                               (str(field_dict[0]),))
                    for row in records:
                        char_class = row[0]
                    if char_class not in list(allowed_classes) and ("All" not in list(allowed_classes)):
                        await direct_message(message, "You aren't the proper class to equip this armament!")
                        return
                records = await select_sql("""SELECT CharacterName,Level FROM CharacterProfiles WHERE Id=%s""",
                                           (field_dict[0],))
                for row in records:
                    char_name = row[0]
                    level = row[1]
                records = await select_sql(
                    """SELECT IFNULL(""" + target_slot + """,'None') FROM CharacterArmaments WHERE CharacterId=%s;""",
                    (field_dict[0],))
                for row in records:
                    char_slot = row[0]
                try:
                    char_slot
                except:
                    char_slot = 'None'
                    result = await commit_sql(
                        """INSERT INTO CharacterArmaments (ServerId,UserId,CharacterId, HeadId, LeftHandId, RightHandId, ChestId, FeetId, FormId) VALUES (%s, %s, %s, NULL, NULL, NULL, NULL, NULL, NULL);""",
                        (str(dm_tracker[message.author.id]["server_id"]), str(message.author.id), field_dict[0]))
                    if not result:
                        await direct_message(message, "Database error!")
                        return
                if int(level) < int(minimumlevel):
                    await direct_message(message, char_name + " isn't a high enough level to equip this armament!")
                    return
                if char_slot != 'None' and int(char_slot) != 0:
                    await direct_message(message, "You already have an armament equipped in this slot!")
                    return
                if (slot == 'Hand' and not re.search('Hand', target_slot)) and (slot != target_slot):
                    await direct_message(message, "This armament does not go in this slot!")
                    return

                result = await commit_sql(
                    """UPDATE CharacterArmaments SET """ + target_slot + """=%s WHERE CharacterId=%s""",
                    (field_dict[1], field_dict[0]))
                if result:
                    await direct_message(message,
                                         char_name + " now has equipped " + arm_name + " in the " + message.content)
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> " + char_name + " now has equipped " + arm_name + " in the " + message.content)
                else:
                    await direct_message(mesage, "Database error!")
                return            

        elif current_command == 'unequip':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                records = await select_sql(
                    """SELECT IFNULL(HeadId,'0'), IFNULL(LeftHandId,'0'), IFNULL(RightHandId,'0'), IFNULL(ChestId,'0'), IFNULL(FeetId,'0'), IFNULL(FormId,'0') FROM CharacterArmaments WHERE CharacterId=%s;""",
                    (message.content,))
                for row in records:
                    head_id = row[0]
                    left_id = row[1]
                    right_id = row[2]
                    chest_id = row[3]
                    feet_id = row[4]
                    form_id = row[5]
                if not records:
                    await direct_message(message, "This character has nothing equipped!")
                    return
                records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (head_id,))
                for row in records:
                    head_name = row[0]
                try:
                    head_name
                except:
                    head_name = "None"
                records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (left_id,))
                for row in records:
                    left_name = row[0]
                try:
                    left_name
                except:
                    left_name = "None"
                records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (right_id,))
                for row in records:
                    right_name = row[0]
                try:
                    right_name
                except:
                    right_name = "None"
                records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (chest_id,))
                for row in records:
                    chest_name = row[0]
                try:
                    chest_name
                except:
                    chest_name = "None"
                records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (feet_id,))
                for row in records:
                    feet_name = row[0]
                try:
                    feet_name
                except:
                    feet_name = "None"
                records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (form_id,))
                for row in records:
                    form_name = row[0]
                try:
                    form_name
                except:
                    form_name = "None"

                menu = "Current Armaments Equipped\n\nHead: **" + head_id + "** - " + head_name + "\nLeftHand: **" + left_id + "** - " + left_name + "\nRightHand: **" + right_id + "** - " + right_name + "\nChest: **" + chest_id + "** - " + chest_name + "\nFeet: **" + feet_id + "** - " + feet_name + "\nForm: **" + form_name + "**"

                response = "Select an armament from your inventory to unequip by replying with the slot below:\n\n" + menu
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                if not re.search(r"Hand|Feet|Chest|Head|Form", message.content):
                    await direct_message(message, "Invalid slot for armaments! Please try again.")
                    return

                result = await commit_sql(
                    """UPDATE CharacterArmaments SET """ + message.content + "Id=%s WHERE CharacterId=%s;",
                    ('0', field_dict[0]))
                if result:
                    await direct_message(message, "Unequipped the " + message.content + " slot.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Unequipped " + message.content + " slot.")
                else:
                    await direct_message(message, "Database error!")
                return

        elif current_command == 'trade':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_menu(message, "Inventory", "Equipment", "EquipmentId", "CharacterId", "EquipmentName",
                                       dm_tracker[message.author.id]["fielddict"][0])
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
                records = await select_sql("""SELECT EquipmentName,EquipmentCost FROM Equipment WHERE Id=%s""",
                                           (dm_tracker[message.author.id]["fielddict"][1],))

                if not records:
                    await reply_message(message, "No item found by that ID!")
                    return
                for row in records:
                    equip_name = row[0]
                    cost = float(row[1])
                records = await select_sql(
                    """SELECT CharacterName,UserId,Currency FROM CharacterProfiles WHERE Id=%s;""",
                    (dm_tracker[message.author.id]["fielddict"][0],))
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
                records = await select_sql("""SELECT CharacterName,UserId FROM CharacterProfiles WHERE Id=%s;""",
                                           (dm_tracker[message.author.id]["fielddict"][2],))
                if not records:
                    await direct_message(message, "No character exists by that target ID!")
                    return
                for row in records:
                    target_name = row[0]
                    target_user = row[1]

                result = await commit_sql(
                    """DELETE FROM Inventory WHERE ServerId=%s AND UserId=%s AND CharacterId=%s AND EquipmentId=%s;""",
                    (str(dm_tracker[message.author.id]["server_id"]), str(message.author.id),
                     dm_tracker[message.author.id]["fielddict"][0], item_id))
                if result:

                    result_2 = await commit_sql(
                        """INSERT INTO Inventory (ServerId,UserId,CharacterId ,EquipmentId) VALUES (%s, %s, %s, %s);""",
                        (str(dm_tracker[message.author.id]["server_id"]), str(target_user),
                         str(dm_tracker[message.author.id]["fielddict"][2]),
                         dm_tracker[message.author.id]["fielddict"][1]))
                    if not result_2:
                        await direct_message(message, "Database error!")
                        return
                    await direct_message(message, char_name + " traded to " + target_name + " with mun of <@" + str(
                        target_user) + ">.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> " + char_name + " traded to " + target_name + " with mun of <@" + str(target_user) + ">.")
                else:
                    await reply_message(message, "You don't own this item!")
                await initialize_dm(message.author.id)
                return
        elif current_command == 'tradearms':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_menu(message, "ArmamentInventory", "Armaments", "ArmamentId", "CharacterId",
                                       "ArmamentName", dm_tracker[message.author.id]["fielddict"][0])
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
                records = await select_sql("""SELECT ArmamentName,ArmamentCost FROM Armaments WHERE Id=%s""",
                                           (dm_tracker[message.author.id]["fielddict"][1],))

                if not records:
                    await reply_message(message, "No item found by that ID!")
                    return
                for row in records:
                    equip_name = row[0]
                    cost = float(row[1])
                records = await select_sql(
                    """SELECT CharacterName,UserId,Currency FROM CharacterProfiles WHERE Id=%s;""",
                    (dm_tracker[message.author.id]["fielddict"][0],))
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
                records = await select_sql("""SELECT CharacterName,UserId FROM CharacterProfiles WHERE Id=%s;""",
                                           (dm_tracker[message.author.id]["fielddict"][2],))
                if not records:
                    await direct_message(message, "No character exists by that target ID!")
                    return
                for row in records:
                    target_name = row[0]
                    target_user = row[1]

                result = await commit_sql(
                    """DELETE FROM ArmamentInventory WHERE ServerId=%s AND UserId=%s AND CharacterId=%s AND ArmamentId=%s;""",
                    (str(dm_tracker[message.author.id]["server_id"]), str(message.author.id),
                     dm_tracker[message.author.id]["fielddict"][0], item_id))
                if result:

                    result_2 = await commit_sql(
                        """INSERT INTO ArmamentInventory (ServerId,UserId,CharacterId ,ArmamentId) VALUES (%s, %s, %s, %s);""",
                        (str(dm_tracker[message.author.id]["server_id"]), str(target_user),
                         str(dm_tracker[message.author.id]["fielddict"][2]),
                         dm_tracker[message.author.id]["fielddict"][1]))
                    if not result_2:
                        await direct_message(message, "Database error!")
                        return
                    await direct_message(message, char_name + " traded to " + target_name + " with mun of <@" + str(
                        target_user) + ">.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> " + char_name + " traded to " + target_name + " with mun of <@" + str(target_user) + ">.")
                else:
                    await reply_message(message, "You don't own this item!")
                await initialize_dm(message.author.id)
                return
        elif current_command == 'givesummon':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_simple_menu(message, "Monsters", "MonsterName")
                response = "Select a monster summon to give to the character by replying to the DM with the ID of the item:\n\n"
                await direct_message(message, response + menu)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                records = await select_sql("""SELECT CharacterName FROM CharacterProfiles WHERE Id=%s""",
                                           (str(dm_tracker[message.author.id]["fielddict"][0]),))
                for row in records:
                    char_name = row[0]
                records = await select_sql("""SELECT MonsterName FROM Monsters WHERE Id=%s""",
                                           (str(message.content),))
                for row in records:
                    item_name = row[0]
                result = await commit_sql(
                    """INSERT INTO SummonInventory (ServerId, UserId, CharacterId, MonsterId) VALUES (%s, %s, %s, %s);""", (
                        str(dm_tracker[message.author.id]["server_id"]), str(message.author.id),
                        dm_tracker[message.author.id]["fielddict"][0], message.content))
                if result:
                    await reply_message(message, char_name + " can now summon the monster " + item_name + "!")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> " + char_name + " can now summon the monster " + item_name + "!")
                else:
                    await reply_message(message, "Database error!")
        elif current_command == 'giveitem':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_simple_menu(message, "Equipment", "EquipmentName")
                response = "Select an item to give to the character by replying to the DM with the ID of the item:\n\n"
                await direct_message(message, response + menu)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                records = await select_sql("""SELECT CharacterName FROM CharacterProfiles WHERE Id=%s""",
                                           (str(dm_tracker[message.author.id]["fielddict"][0]),))
                for row in records:
                    char_name = row[0]
                records = await select_sql("""SELECT EquipmentName FROM Equipment WHERE Id=%s""",
                                           (str(message.content),))
                for row in records:
                    item_name = row[0]
                result = await commit_sql(
                    """INSERT INTO Inventory (ServerId, UserId, CharacterId, EquipmentId) VALUES (%s, %s, %s, %s);""", (
                        str(dm_tracker[message.author.id]["server_id"]), str(message.author.id),
                        dm_tracker[message.author.id]["fielddict"][0], message.content))
                if result:
                    await reply_message(message, char_name + " can now use the item " + item_name + "!")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> " + char_name + " can now use the item " + item_name + "!")
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
                records = await select_sql("""SELECT CharacterName FROM CharacterProfiles WHERE Id=%s""",
                                           (str(dm_tracker[message.author.id]["fielddict"][0]),))
                for row in records:
                    char_name = row[0]
                records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s""",
                                           (str(message.content),))
                for row in records:
                    item_name = row[0]
                result = await commit_sql(
                    """INSERT INTO ArmamentInventory (ServerId, UserId, CharacterId, ArmamentId) VALUES (%s, %s, %s, %s);""",
                    (str(dm_tracker[message.author.id]["server_id"]), str(message.author.id),
                     dm_tracker[message.author.id]["fielddict"][0], message.content))
                if result:
                    await reply_message(message, char_name + " can now use the armament " + item_name + "!")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> " + char_name + " can now use the armament " + item_name + "!")
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
                records = await select_sql("""SELECT AllowedClasses FROM Spells WHERE Id=%s;""", (str(spell_id),))
                for row in records:
                    allowed_classes = row[0].split(',')

                char_record = await select_sql("""SELECT CharacterName,Class FROM CharacterProfiles WHERE Id=%s;""",
                                               (str(char_id),))

                for row in char_record:
                    char_name = row[0]
                    char_class = row[1]

                if char_class not in list(allowed_classes) and ("All" not in list(allowed_classes)):
                    await direct_message(message, char_name + " is not in the allowed clases for this spell!")
                    return

                result = await commit_sql(
                    """INSERT INTO MagicSkills (ServerId, UserId, CharacterId, SpellId) VALUES (%s, %s, %s, %s);""",
                    (str(dm_tracker[message.author.id]["server_id"]), str(message.author.id), char_id, spell_id))
                char_record = await select_sql("""SELECT CharacterName FROM CharacterProfiles WHERE Id=%s;""",
                                               (str(char_id),))

                for row in char_record:
                    char_name = row[0]
                spell_record = await select_sql("""SELECT SpellName FROM Spells WHERE Id=%s;""", (str(spell_id),))
                for row in spell_record:
                    spell_name = row[0]

                if result:
                    await direct_message(message, char_name + " can now use the spell " + spell_name + "!")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> " + char_name + " can now use the spell " + spell_name + "!")

                else:
                    await direct_message(message, "Database error!")
                await initialize_dm(message.author.id)
                return

        elif current_command == 'takebuff':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_menu(message, "BuffSkills", "Buffs", "BuffId", "UserId", "SpellName",
                                       str(message.author.id))
                if not menu:
                    await direct_message(message, "This character has no buffs!")
                    return
                response = "Please select a buff to take from the character.\n\n" + menu

                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                spell_id = message.content
                char_id = dm_tracker[message.author.id]["fielddict"][0]
                result = await commit_sql(
                    """DELETE FROM BuffSkills WHERE ServerId=%s AND CharacterId=%s AND BuffId=%s;""",
                    (str(dm_tracker[message.author.id]["server_id"]), char_id, spell_id))
                char_record = await select_sql("""SELECT CharacterName FROM CharacterProfiles WHERE Id=%s;""",
                                               (str(char_id),))

                for row in char_record:
                    char_name = row[0]
                spell_record = await select_sql("""SELECT BuffName FROM Buffs WHERE Id=%s;""", (str(spell_id),))
                for row in spell_record:
                    spell_name = row[0]

                if result:
                    await direct_message(message, char_name + " can no longer use the buff " + spell_name + "!")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> " + char_name + " can no longer uae the spell " + spell_name + "!")
                else:
                    await direct_message(message, "Database error!")
                await initialize_dm(message.author.id)
                return
        elif current_command == 'takespell':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_menu(message, "MagicSkills", "Spells", "SpellId", "UserId", "SpellName",
                                       str(message.author.id))
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
                result = await commit_sql(
                    """DELETE FROM MagicSkills WHERE ServerId=%s AND CharacterId=%s AND SpellId=%s;""",
                    (str(dm_tracker[message.author.id]["server_id"]), char_id, spell_id))
                char_record = await select_sql("""SELECT CharacterName FROM CharacterProfiles WHERE Id=%s;""",
                                               (str(char_id),))

                for row in char_record:
                    char_name = row[0]
                spell_record = await select_sql("""SELECT SpellName FROM Spells WHERE Id=%s;""", (str(spell_id),))
                for row in spell_record:
                    spell_name = row[0]

                if result:
                    await direct_message(message, char_name + " can no longer use the spell " + spell_name + "!")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> " + char_name + " can no longer uae the spell " + spell_name + "!")
                else:
                    await direct_message(message, "Database error!")
                await initialize_dm(message.author.id)
                return
        elif current_command == 'takeitem':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_menu(message, "Inventory", "Equipment", "EquipmentId", "UserId", "EquipmentName",
                                       str(message.author.id))
                if not menu:
                    await direct_message(message, "This character has no items!")
                    return
                response = "Please select an item to take from the character.\n\n" + menu

                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                spell_id = message.content
                char_id = dm_tracker[message.author.id]["fielddict"][0]
                result = await commit_sql(
                    """DELETE FROM Inventory WHERE ServerId=%s AND CharacterId=%s AND EquipmentId=%s;""",
                    (str(dm_tracker[message.author.id]["server_id"]), char_id, spell_id))
                char_record = await select_sql("""SELECT CharacterName FROM CharacterProfiles WHERE Id=%s;""",
                                               (str(char_id),))

                for row in char_record:
                    char_name = row[0]
                spell_record = await select_sql("""SELECT EquipmentName FROM Equipment WHERE Id=%s;""", (str(spell_id),))
                for row in spell_record:
                    spell_name = row[0]

                if result:
                    await direct_message(message, char_name + " can no longer use the item " + spell_name + "!")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> " + char_name + " can no longer uae the item " + spell_name + "!")
                else:
                    await direct_message(message, "Database error!")
                await initialize_dm(message.author.id)
                return
        elif current_command == 'takesummon':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_menu(message, "SummonInventory", "Monsters", "MonsterId", "UserId", "MonsterName",
                                       str(message.author.id))
                if not menu:
                    await direct_message(message, "This character has no summons!")
                    return
                response = "Please select a summon to take from the character.\n\n" + menu

                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                spell_id = message.content
                char_id = dm_tracker[message.author.id]["fielddict"][0]
                result = await commit_sql(
                    """DELETE FROM SummonInventory WHERE ServerId=%s AND CharacterId=%s AND MonsterId=%s;""",
                    (str(dm_tracker[message.author.id]["server_id"]), char_id, spell_id))
                char_record = await select_sql("""SELECT CharacterName FROM CharacterProfiles WHERE Id=%s;""",
                                               (str(char_id),))

                for row in char_record:
                    char_name = row[0]
                spell_record = await select_sql("""SELECT MonsterName FROM Monsters WHERE Id=%s;""", (str(spell_id),))
                for row in spell_record:
                    spell_name = row[0]

                if result:
                    await direct_message(message, char_name + " can no longer use the summon " + spell_name + "!")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> " + char_name + " can no longer uae the summon " + spell_name + "!")
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
                records = await select_sql("""SELECT AllowedClasses FROM Melee WHERE Id=%s;""", (str(melee_id),))
                for row in records:
                    allowed_classes = row[0].split(',')

                char_record = await select_sql("""SELECT CharacterName,Class FROM CharacterProfiles WHERE Id=%s;""",
                                               (str(char_id),))

                for row in char_record:
                    char_name = row[0]
                    char_class = row[1]

                if char_class not in list(allowed_classes) and ("All" not in list(allowed_classes)):
                    await direct_message(message, char_name + " is not in the allowed clases for this melee attack!")
                    return

                result = await commit_sql(
                    """INSERT INTO MeleeSkills (ServerId, UserId, CharacterId, MeleeId) VALUES (%s, %s, %s, %s);""",
                    (str(dm_tracker[message.author.id]["server_id"]), str(message.author.id), char_id, melee_id))
                melee_record = await select_sql("""SELECT AttackName FROM Melee WHERE Id=%s;""", (str(melee_id),))
                for row in melee_record:
                    melee_name = row[0]

                if result:
                    await direct_message(message, char_name + " can now use the melee " + melee_name + "!")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> " + char_name + " can now use the melee " + melee_name + "!")
                else:
                    await direct_message(message, "Database error!")
                await initialize_dm(message.author.id)
                return
        elif current_command == 'changeowner':
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
                result = await commit_sql("""UPDATE CharacterProfiles SET UserId=%s WHERE Id=%s;""",
                                          (message.content, field_dict[0]))
                if result:
                    await direct_message(message, "Character owner updated.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Character ID " + field_dict[0] + " updated to be owned by <@" + message.content + ">")
                else:
                    await direct_message("Database error!")

        elif current_command == 'addstatpoints':

            if current_field == 1:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                if not re.search(r"Attack|MagicAttack|Defense|Agility|Intellect|Charisma", message.content):
                    await direct_message(message, "Invalid field! Please try again.")
                    return
                await direct_message(message,
                                     "Please enter the number of points to add (current number of points **" + str(
                                         dm_tracker[message.author.id]["parameters"]) + "**):")
                dm_tracker[message.author.id]["currentfield"] = 2
                return
            if current_field == 0:
                records = await select_sql("""SELECT StatPoints FROM CharacterProfiles WHERE Id=%s;""",
                                           (str(message.content),))
                for row in records:
                    stat_points = int(row[0])
                dm_tracker[message.author.id]["parameters"] = stat_points
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                await direct_message(message,
                                     "Please enter a statistic to modify (Attack, MagicAttack, Defense, Agility, Intellect, Charisma):")
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 2:
                points = int(message.content)
                if points > int(dm_tracker[message.author.id]["parameters"]):
                    await direct_message(message,
                                         "You don't have that many points! Please enter a number less than " + str(
                                             dm_tracker[message.author.id]["parameters"]))
                    return
                records = await select_sql("SELECT " + field_dict[1] + " FROM CharacterProfiles WHERE Id=%s;",
                                           (str(field_dict[0]),))
                for row in records:
                    current_stat = int(row[0])

                result = await commit_sql(
                    "UPDATE CharacterProfiles SET " + field_dict[1] + "=%s,StatPoints=%s WHERE Id=%s;", (
                        str(points + current_stat), str(dm_tracker[message.author.id]["parameters"] - int(points)),
                        str(field_dict[0])))
                if result:
                    response = "Character successfully added " + str(points) + " to " + field_dict[1] + "."
                    dm_tracker[message.author.id]["parameters"] = dm_tracker[message.author.id]["parameters"] - int(
                        points)
                    await direct_message(message, response)
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
                else:
                    await direct_message(message, "Database error!")
                return
        elif current_command == 'takecurrency':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                records = await select_sql("""SELECT Currency FROM CharacterProfiles WHERE ServerId=%s;""",
                                           (str(dm_tracker[message.author.id]["server_id"]),))
                for row in records:
                    balance = int(row[0])
                dm_tracker[message.author.id]["parameters"] = str(balance)
                await direct_message(message, "Current character balance: " + str(
                    balance) + "\nPlease enter the amount to take from the character:")
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                amount = int(message.content)
                if amount > int(dm_tracker[message.author.id]["parameters"]):
                    await direct_message(message,
                                         "There isn't that much in their wallet! Please choose an amount lower than that!")
                    return
                records = await select_sql("""SELECT Currency FROM CharacterProfiles WHERE Id=%s;""",
                                           (str(dm_tracker[message.author.id]["fielddict"][0]),))
                for row in records:
                    current_currency = int(row[0])
                new_total = current_currency - amount
                balance = int(dm_tracker[message.author.id]["parameters"])
                new_bank = balance - amount
                result = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s WHERE Id=%s;""",
                                          (str(new_total), str(dm_tracker[message.author.id]["fielddict"][0])))
                if result:
                    result2 = await commit_sql("""UPDATE GuildSettings SET GuildBankBalance=%s WHERE ServerId=%s;""",
                                               (str(new_bank), str(dm_tracker[message.author.id]["server_id"])))
                    if result2:
                        await direct_message(message, "Character now has a thinner wallet!")
                        await dm_tracker[message.author.id]["commandchannel"].send(
                            ">>> Character now has a fatter wallet!")
                    else:
                        await direct_message(message, "Database error!")
                else:
                    await direct_message(message, "Database error!")
        elif current_command == 'givecurrency':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                records = await select_sql("""SELECT GuildBankBalance FROM GuildSettings WHERE ServerId=%s;""",
                                           (str(dm_tracker[message.author.id]["server_id"]),))
                for row in records:
                    balance = int(row[0])
                dm_tracker[message.author.id]["parameters"] = str(balance)
                await direct_message(message, "Current bank balance: " + str(
                    balance) + "\nPlease enter the amount to grant the character:")
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                amount = int(message.content)
                if amount > int(dm_tracker[message.author.id]["parameters"]):
                    await direct_message(message,
                                         "There isn't that much in the bank! Please choose an amount lower than the bank balance!")
                    return
                records = await select_sql("""SELECT Currency FROM CharacterProfiles WHERE Id=%s;""",
                                           (str(dm_tracker[message.author.id]["fielddict"][0]),))
                for row in records:
                    current_currency = int(row[0])
                new_total = current_currency + amount
                balance = int(dm_tracker[message.author.id]["parameters"])
                new_bank = balance - amount
                result = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s WHERE Id=%s;""",
                                          (str(new_total), str(dm_tracker[message.author.id]["fielddict"][0])))
                if result:
                    result2 = await commit_sql("""UPDATE GuildSettings SET GuildBankBalance=%s WHERE ServerId=%s;""",
                                               (str(new_bank), str(dm_tracker[message.author.id]["server_id"])))
                    if result2:
                        await direct_message(message, "Character now has a fatter wallet!")
                        await dm_tracker[message.author.id]["commandchannel"].send(
                            ">>> Character now has a fatter wallet!")
                    else:
                        await direct_message(message, "Database error!")
                else:
                    await direct_message(message, "Database error!")
        elif current_command == 'takemelee':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_menu(message, "MeleeSkills", "Melee", "MeleeId", "CharacterId", "AttackName",
                                       message.content)
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
                result = await commit_sql(
                    """DELETE FROM MeleeSkills WHERE ServerId=%s AND CharacterId=%s AND MeleeId=%s;""",
                    (str(dm_tracker[message.author.id]["server_id"]), char_id, melee_id))
                char_record = await select_sql("""SELECT CharacterName FROM CharacterProfiles WHERE Id=%s;""",
                                               (str(char_id),))

                for row in char_record:
                    char_name = row[0]
                melee_record = await select_sql("""SELECT AttackName FROM Melee WHERE Id=%s;""", (str(melee_id),))
                for row in melee_record:
                    melee_name = row[0]

                if result:
                    await direct_message(message, char_name + " can no longer use the melee " + melee_name + "!")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> " + char_name + " can no longer uae the melee " + melee_name + "!")
                else:
                    await direct_message(message, "Database error!")
                await initialize_dm(message.author.id)
                return
            pass
        elif current_command == 'spar2':
            records = await select_sql(
                """SELECT UserId,Attack,Defense,MagicAttack,Health,Mana,Level,Experience,Stamina,Agility,Intellect,Charisma,Id,CharacterName,PictureLink,MaxHealth,MaxStamina,MaxMana FROM CharacterProfiles WHERE Id=%s;""",
                (message.content,))
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
                mass_spar_chars[server_id][user_id] = {}
                mass_spar_chars[server_id][user_id]["CharName"] = row[13]
                mass_spar_chars[server_id][user_id]["Attack"] = int(row[1])
                mass_spar_chars[server_id][user_id]["Defense"] = int(row[2])
                mass_spar_chars[server_id][user_id]["MagicAttack"] = int(row[3])
                mass_spar_chars[server_id][user_id]["Health"] = int(row[4])
                mass_spar_chars[server_id][user_id]["MaxHealth"] = int(row[15])
                mass_spar_chars[server_id][user_id]["Mana"] = int(row[5])
                mass_spar_chars[server_id][user_id]["MaxMana"] = int(row[17])
                mass_spar_chars[server_id][user_id]["Level"] = int(row[6])
                mass_spar_chars[server_id][user_id]["Experience"] = int(row[7])
                mass_spar_chars[server_id][user_id]["MaxStamina"] = int(row[16])
                mass_spar_chars[server_id][user_id]["Stamina"] = int(row[8])
                mass_spar_chars[server_id][user_id]["Agility"] = int(row[9])
                mass_spar_chars[server_id][user_id]["Intellect"] = int(row[10])
                mass_spar_chars[server_id][user_id]["Charisma"] = int(row[11])
                mass_spar_chars[server_id][user_id]["CharId"] = int(row[12])
                mass_spar_cooldown[server_id][user_id] = 0

                if re.search(r"http", row[14]):
                    mass_spar_chars[server_id][user_id]["PictureLink"] = row[14]
                else:
                    mass_spar_chars[server_id][user_id]["PictureLink"] = narrator_url
                mass_spar_chars[server_id][user_id]["TotalDamage"] = 0
                char_name = row[13]
            records = await select_sql(
                """SELECT IFNULL(HeadId,'None'),IFNULL(ChestId,'None'),IFNULL(LeftHandId,'None'),IFNULL(RightHandId,'None'),IFNULL(FeetId,'None'),IFNULL(FormId,'None') FROM CharacterArmaments WHERE CharacterId=%s;""",
                (str(mass_spar_chars[server_id][user_id]["CharId"]),))
            if records:
                for row in records:
                    for x in range(0, len(row)):
                        item = row[x]
                        if item != 'None':
                            arm_records = await select_sql(
                                """SELECT MinimumLevel,Defense,StatMod,Modifier FROM Armaments WHERE Id=%s;""",
                                (str(item),))
                            for arm_row in arm_records:
                                if int(arm_row[0]) < mass_spar_chars[server_id][user_id]["Level"]:
                                    if int(arm_row[1]) > 0:
                                        mass_spar_chars[server_id][user_id]["Defense"] = \
                                            mass_spar_chars[server_id][user_id]["Defense"] + int(arm_row[1])
                                        await log_message("applying defense!")
                                    if re.search(r"Attack|MagicAttack|Agility", arm_row[2]):
                                        mass_spar_chars[server_id][user_id][arm_row[2]] = \
                                            mass_spar_chars[server_id][user_id][arm_row[2]] + int(arm_row[3])
                                        await log_message("applying " + str(arm_row[3]) + " to " + str(arm_row[2]))
            await dm_tracker[message.author.id]["commandchannel"].send(
                ">>> " + message.author.name + " successfully set party character to " + char_name + ".")
            await direct_message(message, "You successfully set your spar character to " + char_name)
            await initialize_dm(message.author.id)
            return
        elif current_command == 'disarm':
            if dm_tracker[message.author.id]["currentfield"] == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)

                records = await select_sql(
                    "SELECT IFNULL(LeftHandId,'None'),IFNULL(RightHandId,'None') FROM CharacterArmaments Where CharacterId=%s;",
                    (message.content,))
                if not records:
                    await direct_message(message, "That character has no armaments equipped!")
                    return
                for row in records:
                    left_hand = row[0]
                    right_hand = row[1]
                if left_hand == 'None' and right_hand == 'None':
                    await direct_message(message, "That character has no armaments equipped!")
                    return
                records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (left_hand,))
                for row in records:
                    left_name = row[0]
                records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (right_hand,))
                for row in records:
                    right_name = row[0]
                try:
                    left_name
                except:
                    left_name = 'None'
                try:
                    right_name
                except:
                    right_name = 'None'
                menu = "Armaments Equipped:\n\n" + left_hand + " - " + left_name + "\n" + right_hand + " - " + right_name
                response = "Select an armament to disarm:\n\n" + menu
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            elif dm_tracker[message.author.id]["currentfield"] == 1:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                chance_of_disarm = random.randint(0, 100)
                if chance_of_disarm >= 60:
                    result = await commit_sql(
                        """DELETE FROM CharacterArmaments WHERE CharacterId=%s AND (LeftHandId=%s OR RightHandId=%s);""",
                        (str(dm_tracker[message.author.id]["fielddict"][0]),
                         str(dm_tracker[message.author.id]["fielddict"][1]),
                         str(dm_tracker[message.author.id]["fielddict"][1])))
                    await direct_message(message, "Character disarmed!")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Character <@" + str(
                        dm_tracker[message.author.id]["parameters"][
                            int(dm_tracker[message.author.id]["fielddict"][0])]) + "> has had an armament disarmed!")

                else:
                    await direct_message(message, "Character disarm failed!")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> You were unable to disarm anyone!")
                if mass_spar_turn[server_id] > len(mass_spar_chars[server_id]) - 2:
                    mass_spar_turn[server_id] = 0
                else:
                    mass_spar_turn[server_id] = mass_spar_turn[server_id] + 1
                await dm_tracker[message.author.id]["commandchannel"].send(
                    ">>> <@" + str(list(mass_spar[server_id])[mass_spar_turn[server_id]].id) + ">, it is your turn!")
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
                dm_tracker[message.author.id]["parameters"] = char_map
                return
            elif dm_tracker[message.author.id]["currentfield"] == 1:
                user_id = message.author.id
                target_id = dm_tracker[message.author.id]["parameters"][int(message.content)]
            records = await select_sql(
                """SELECT Id,ArmamentName,MinimumLevel,DamageMin,DamageMax,StatusChange,StatusChangedBy,PictureLink FROM Armaments WHERE Id=%s;""",
                (field_dict[0],))
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
                    status_change = row[5]
                    status_changed_by = int(row[6])
                    picture_link = row[7]
                if (min_level > mass_spar_chars[server_id][user_id]["Level"]):
                    await direct_message(message,
                                         "You're not a high enough level for this armament. How did you even get it?")
                    return
                await direct_message(message, "Attacking with " + arm_name)
                attack_text = "" + str(mass_spar_chars[server_id][user_id]["CharName"]) + " attacks " + str(
                    mass_spar_chars[server_id][target_id]["CharName"]) + " with " + arm_name + "!\n"
                embed = discord.Embed(title=attack_text)
                if picture_link.startswith('http'):
                    embed.set_thumbnail(url=picture_link)
                await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                await asyncio.sleep(1)
                #                await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][user_id]["CharName"], attack_text, mass_spar_chars[server_id][user_id]["PictureLink"])
                #                await dm_tracker[message.author.id]["commandchannel"].send(">>> " + str(mass_spar_chars[server_id][user_id]["CharName"]) + " attacks " + str(mass_spar_chars[server_id][target_id]["CharName"]) + " with " + arm_name + "!\n")
                dodge = await calculate_dodge(mass_spar_chars[server_id][user_id]["Agility"],
                                              mass_spar_chars[server_id][target_id]["Agility"])
                if dodge:
                    dodge_text = mass_spar_chars[server_id][target_id][
                                     "CharName"] + " dodged the attack! No damage taken!"
                    embed = discord.Embed(title=dodge_text)
                    if mass_spar_chars[server_id][target_id]["PictureLink"].startswith('http'):
                        embed.set_thumbnail(url=mass_spar_chars[server_id][target_id]["PictureLink"])
                    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                    await asyncio.sleep(1)
                #  await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][target_id]["CharName"], dodge_text, mass_spar_chars[server_id][target_id]["PictureLink"])
                #                    await reply_message(message, mass_spar_chars[server_id][target_id]["CharName"] + " dodged the attack! No damage taken!")
                else:
                    damage = await calculate_damage(random.randint(damage_min, damage_max) + mass_spar_chars[server_id][user_id]["Attack"] / 2,
                                                    mass_spar_chars[server_id][target_id]["Defense"], 1,
                                                    mass_spar_chars[server_id][user_id]["Level"],
                                                    mass_spar_chars[server_id][target_id]["Level"])
                    mass_spar_chars[server_id][target_id]["Health"] = mass_spar_chars[server_id][target_id][
                                                                          "Health"] - damage
                    mass_spar_chars[server_id][user_id]["TotalDamage"] = mass_spar_chars[server_id][user_id][
                                                                             "TotalDamage"] + damage
                    if status_change != 'None':
                        if mass_spar_cooldown[server_id][target_id] == 0:
                            result = await commit_sql("""UPDATE CharacterProfiles SET Status=%s WHERE Id=%s;""", (
                                str(status_change + '=' + str(status_changed_by)),
                                str(mass_spar_chars[server_id][target_id]["CharId"])))
                            mass_spar_cooldown[server_id][target_id] = mass_spar_cooldown_turns
                            embed2 = discord.Embed(title=mass_spar_chars[server_id][target_id][
                                                             "CharName"] + "'s status has changed to " + status_change + "!")
                        else:
                            embed2 = discord.Embed(title="The status change failed to take effect!")
                            mass_spar_cooldown[server_id][target_id] = mass_spar_cooldown[server_id][target_id] - 1
                        await dm_tracker[message.author.id]["commandchannel"].send(embed=embed2)
                    hit_text = "" + mass_spar_chars[server_id][target_id]["CharName"] + " was hit by " + \
                               mass_spar_chars[server_id][user_id]["CharName"] + " for " + str(
                        damage) + " points!\n\nHealth now at " + str(
                        mass_spar_chars[server_id][target_id]["Health"]) + "!"
                    embed = discord.Embed(title=hit_text)
                    if mass_spar_chars[server_id][target_id]["PictureLink"].startswith('http'):
                        embed.set_thumbnail(url=mass_spar_chars[server_id][target_id]["PictureLink"])
                    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                    await asyncio.sleep(1)
                    #                    await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][target_id]["CharName"], hit_text, mass_spar_chars[server_id][target_id]["PictureLink"])
                    #                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + mass_spar_chars[server_id][target_id]["CharName"] + " was hit by " + mass_spar_chars[server_id][user_id]["CharName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(mass_spar_chars[server_id][target_id]["Health"]))
                    if mass_spar_chars[server_id][target_id]["Health"] < 1:
                        fallen_text = mass_spar_chars[server_id][target_id][
                                          "CharName"] + " has no health left and is out of the fight!"
                        embed = discord.Embed(title=fallen_text)
                        if mass_spar_chars[server_id][target_id]["PictureLink"].startswith('http'):
                            embed.set_thumbnail(url=mass_spar_chars[server_id][target_id]["PictureLink"])
                        await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                        await asyncio.sleep(1)
                        #                        await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][target_id]["CharName"], fallen_text, mass_spar_chars[server_id][target_id]["PictureLink"])
                        # await reply_message(message, mass_spar_chars[server_id][target_id]["CharName"] + " has no health left and is out of the fight!")

                        fallen_chars[dm_tracker[message.author.id]["server_id"]][target_id] = {}
                        fallen_chars[dm_tracker[message.author.id]["server_id"]][target_id] = \
                            mass_spar_chars[server_id][target_id]
                        del mass_spar_chars[server_id][target_id]

                if len(mass_spar_chars[server_id]) < 2:
                    response = "<@" + str(
                        message.author.id) + "> is the last one standing and is the spar winner!\n\n**Experience gained:**\n\n"
                    fallen_chars[dm_tracker[message.author.id]["server_id"]][message.author.id] = {}
                    fallen_chars[dm_tracker[message.author.id]["server_id"]][message.author.id] = \
                        mass_spar_chars[server_id][message.author.id]
                    for char in fallen_chars[dm_tracker[message.author.id]["server_id"]].keys():

                        char_id = fallen_chars[server_id][char]["CharId"]
                        if char_id == client.user.id:
                            continue
                        await log_message("Level " + str(fallen_chars[server_id][char]["Level"]))
                        new_xp = await calculate_xp(fallen_chars[server_id][char]["Level"],
                                                    fallen_chars[server_id][char]["Level"],
                                                    fallen_chars[server_id][char]["TotalDamage"], 1) * 2
                        response = response + "*" + fallen_chars[server_id][char]["CharName"] + "*: " + str(
                            new_xp) + "\n"
                        records = await select_sql("""SELECT Experience FROM CharacterProfiles WHERE Id=%s;""",
                                                   (str(fallen_chars[server_id][char]["CharId"]),))
                        for row in records:
                            old_xp = int(row[0])
                        try:
                            old_xp
                        except:
                            old_xp = 0
                        total_xp = old_xp + new_xp
                        if total_xp > (
                                guild_settings[server_id]["XPLevelRatio"] * fallen_chars[server_id][char]["Level"]):
                            if fallen_chars[server_id][char]["CharId"] == 0:
                                continue
                            fallen_chars[server_id][char]["Level"] = fallen_chars[server_id][char]["Level"] + 1
                            records = await select_sql("""SELECT StatPoints FROM CharacterProfiles WHERE Id=%s;""",
                                                       (str(fallen_chars[server_id][char]["CharId"]),))
                            for row in records:
                                stat_points = int(row[0])

                            available_points = int(guild_settings[server_id]["StatPointsPerLevel"]) + stat_points

                            response = response + "**" + fallen_chars[server_id][char][
                                "CharName"] + "** LEVELED UP TO LEVEL **" + str(
                                fallen_chars[server_id][char]["Level"]) + "!**\nYou have " + str(
                                available_points) + " stat points to spend!\n\n"
                            total_xp = 0
                            health = fallen_chars[server_id][char]["MaxHealth"] + guild_settings[server_id][
                                "HealthLevelAdd"]
                            stamina = fallen_chars[server_id][char]["MaxStamina"] + guild_settings[server_id][
                                "StaminaLevelAdd"]
                            mana = fallen_chars[server_id][char]["MaxMana"] + guild_settings[server_id][
                                "ManaLevelAdd"]
                            result = await commit_sql(
                                """UPDATE CharacterProfiles SET Level=%s,Experience=%s,Health=%s,Stamina=%s,Mana=%s,StatPoints=%s WHERE Id=%s;""",
                                (str(fallen_chars[server_id][char]["Level"]), str(total_xp), str(health),
                                 str(stamina), str(mana), str(available_points),
                                 str(fallen_chars[server_id][char]["CharId"])))
                        else:
                            result = await commit_sql("""UPDATE CharacterProfiles SET Experience=%s WHERE Id=%s;""", (
                                str(total_xp), str(fallen_chars[server_id][char]["CharId"])))
                    mass_spar_event[server_id] = False

                    embed = discord.Embed(title="Results", description=response)
                    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                    await asyncio.sleep(1)
                    # await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
                    return

                if mass_spar_turn[server_id] > len(mass_spar_chars[server_id]) - 2:
                    mass_spar_turn[server_id] = 0
                else:
                    mass_spar_turn[server_id] = mass_spar_turn[server_id] + 1
                await dm_tracker[message.author.id]["commandchannel"].send(
                    ">>> <@" + str(list(mass_spar[server_id])[mass_spar_turn[server_id]].id) + ">, it is your turn!")
                if mass_spar[server_id][mass_spar_turn[server_id]] == client.user:
                    picker = random.randint(1, 2)
                    if picker == 1:
                        await ai_castspar(message)
                    else:
                        await ai_meleespar(message)
                    mass_spar_turn[server_id] = mass_spar_turn[server_id] = 0
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> <@" + str(
                        list(mass_spar[server_id])[mass_spar_turn[server_id]].id) + ">, it is your turn!")
                await initialize_dm(message.author.id)
            return
        elif current_command == 'weaponmonster':
            user_id = message.author.id
            server_id = dm_tracker[message.author.id]["server_id"]
            records = await select_sql(
                """SELECT Id,ArmamentName,MinimumLevel,DamageMin,DamageMax,PictureLink FROM Armaments WHERE Id=%s;""",
                (message.content,))
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
                    await direct_message(message,
                                         "You're not a high enough level for this armament. How did you even get it?")
                    return
            await direct_message(message, "Attacking the monster with " + arm_name + ".")
            attack_text = "" + str(server_party_chars[server_id][user_id]["CharName"]) + " attacks " + str(
                server_monsters[server_id]["MonsterName"]) + " with " + arm_name + "!\n\n"
            embed = discord.Embed(title=attack_text)
            if picture_link.startswith('http'):
                embed.set_thumbnail(url=picture_link)
            await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
            await asyncio.sleep(1)
            #           await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_party_chars[server_id][user_id]["CharName"], attack_text, server_party_chars[server_id][user_id]["PictureLink"])
            #            await dm_tracker[message.author.id]["commandchannel"].send(">>> " + str(server_party_chars[server_id][user_id]["CharName"]) + " attacks " + str(server_monsters[server_id]["MonsterName"]) + " with " + arm_name + "!")

            dodge = await calculate_dodge(server_party_chars[server_id][user_id]["Agility"],
                                          server_monsters[server_id]["Agility"], )
            if dodge:
                dodge_text = "" + server_monsters[server_id]["MonsterName"] + " dodged the attack! No damage taken!"
                embed = discord.Embed(title=dodge_text)
                if server_party_chars[server_id][user_id]["PictureLink"].startswith('http'):
                    embed.set_thumbnail(url=server_party_chars[server_id][target_id]["PictureLink"])
                await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                await asyncio.sleep(1)
            #                await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_monsters[server_id]["MonsterName"], dodge_text, server_monsters[server_id]["PictureLink"])
            #  await dm_tracker[message.author.id]["commandchannel"].send(">>> " + server_monsters[server_id]["MonsterName"] + " dodged the attack! No damage taken!")
            else:
                damage = await calculate_damage(random.randint(damage_min, damage_max) + server_party_chars[server_id][user_id]["Attack"] / 2,
                                                server_monsters[server_id]["Defense"], 1,
                                                server_party_chars[server_id][user_id]["Level"],
                                                server_monsters[server_id]["Level"])
                server_monsters[server_id]["Health"] = int(server_monsters[server_id]["Health"] - damage)
                # await dm_tracker[message.author.id]["commandchannel"].send(">>> " + server_monsters[server_id]["MonsterName"] + " was hit by " + server_party_chars[server_id][user_id]["CharName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(server_monsters[server_id]["Health"]))
                hit_text = "" + server_monsters[server_id]["MonsterName"] + " was hit by " + \
                           server_party_chars[server_id][user_id]["CharName"] + " for " + str(
                    damage) + " points!\n\nHealth now at " + str(server_monsters[server_id]["Health"]) + "!"
                embed = discord.Embed(title=hit_text)
                if server_monsters[server_id]["PictureLink"].startswith('http'):
                    embed.set_thumbnail(url=server_monsters[server_id]["PictureLink"])
                await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                await asyncio.sleep(1)
                #                await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_monsters[server_id]["MonsterName"], hit_text, server_monsters[server_id]["PictureLink"])
                if server_monsters[server_id]["Health"] < 1:
                    fallen_text = "" + server_monsters[server_id][
                        "MonsterName"] + " has no health left and is out of the fight!"
                    embed = discord.Embed(title=fallen_text)
                    if server_monsters[server_id]["PictureLink"].startswith('http'):
                        embed.set_thumbnail(url=server_monsters[server_id]["PictureLink"])
                    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                    await asyncio.sleep(1)
                    # await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_monsters[server_id]["MonsterName"], hit_text, server_monsters[server_id]["PictureLink"])
                    # await dm_tracker[message.author.id]["commandchannel"].send(">>> " + server_monsters[server_id]["MonsterName"] + " has no health left and is out of the fight!")
                    currency_earned = server_monsters[dm_tracker[message.author.id]["server_id"]]["MaxCurrencyDrop"]
                    server_encounters[server_id] = False
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Victory!")
                    response = "**Experience gained:**\n\n"
                    for user in server_party_chars[server_id].keys():
                        char_id = server_party_chars[server_id][user]["CharId"]
                        await log_message("Level " + str(server_party_chars[server_id][user]["Level"]))
                        new_xp = await calculate_xp(server_party_chars[server_id][user]["Level"],
                                                    server_monsters[server_id]["Level"], monster_health[server_id],
                                                    len(server_party_chars[server_id]))
                        response = response + "*" + server_party_chars[server_id][user]["CharName"] + "*: " + str(
                            new_xp) + "\n"
                        records = await select_sql("""SELECT Experience FROM CharacterProfiles WHERE Id=%s;""",
                                                   (str(server_party_chars[server_id][user]["CharId"]),))
                        for row in records:
                            old_xp = int(row[0])
                        total_xp = int(old_xp + new_xp)
                        response = response + "Currency earned: " + str(currency_earned) + "\n"
                        server_party_chars[server_id][user]["Currency"] = server_party_chars[server_id][user][
                                                                              "Currency"] + currency_earned
                        result = await commit_sql("""UPDATE CharacterProfiles SET CURRENCY=%s WHERE Id=%s;""", (
                            str(server_party_chars[server_id][user_id]["Currency"]),
                            str(server_party_chars[server_id][user]["CharId"])))
                        if total_xp > (guild_settings[server_id]["XPLevelRatio"] * server_party_chars[server_id][user][
                            "Level"]):
                            server_party_chars[server_id][user]["Level"] = server_party_chars[server_id][user][
                                                                               "Level"] + 1
                            records = await select_sql("""SELECT StatPoints FROM CharacterProfiles WHERE Id=%s;""",
                                                       (str(server_party_chars[server_id][user]["CharId"]),))
                            for row in records:
                                stat_points = int(row[0])

                            available_points = guild_settings[server_id]["StatPointsPerLevel"] + stat_points
                            response = response + "**" + server_party_chars[server_id][user][
                                "CharName"] + "** LEVELED UP TO LEVEL **" + str(
                                server_party_chars[server_id][user]["Level"]) + "!**\nYou have " + str(
                                available_points) + " stat points to spend!\n\n"
                            total_xp = 0
                            health = server_party_chars[server_id][user_id]["MaxHealth"] + guild_settings[server_id][
                                "HealthLevelAdd"]
                            stamina = server_party_chars[server_id][user_id]["MaxStamina"] + guild_settings[server_id][
                                "StaminaLevelAdd"]
                            mana = server_party_chars[server_id][user_id]["MaxMana"] + guild_settings[server_id][
                                "ManaLevelAdd"]
                            result = await commit_sql(
                                """UPDATE CharacterProfiles SET Level=%s,Experience=%s,Health=%s,Stamina=%s,Mana=%s,StatPoints=%s WHERE Id=%s;""",
                                (str(server_party_chars[server_id][user]["Level"]), str(total_xp), str(health),
                                 str(stamina), str(mana), str(available_points),
                                 str(server_party_chars[server_id][user]["CharId"])))
                        else:
                            result = await commit_sql(
                                """UPDATE CharacterProfiles SET Level=%s,Experience=%s WHERE Id=%s;""", (
                                    str(server_party_chars[server_id][user]["Level"]), str(total_xp),
                                    str(server_party_chars[server_id][user]["CharId"])))
                    embed = discord.Embed(title="Results", description=response)
                    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                    await asyncio.sleep(1)
                    #  await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
                    return
            await monster_attack(message.author.id)

            if not server_encounters[server_id]:
                return
            if encounter_turn[server_id] > len(server_party[server_id]) - 2:
                encounter_turn[server_id] = 0
                await dm_tracker[message.author.id]["commandchannel"].send(
                    ">>> <@" + str(list(server_party[server_id])[encounter_turn[server_id]].id) + ">, it is your turn!")
            else:
                encounter_turn[server_id] = encounter_turn[server_id] + 1
            await dm_tracker[message.author.id]["commandchannel"].send(
                ">>> <@" + str(list(server_party[server_id])[encounter_turn[server_id]].id) + ">, it is your turn!")
            return
        elif current_command == 'meleemonster':
            user_id = message.author.id
            server_id = dm_tracker[message.author.id]["server_id"]
            records = await select_sql(
                """SELECT Id,StaminaCost,MinimumLevel,DamageMultiplier,AttackName,PictureLink FROM Melee WHERE Id=%s;""",
                (message.content,))
            if not records:
                await reply_message(message, "That's not a valid attack. Try again.")
                return
            else:
                for row in records:
                    melee_id = row[0]
                    stamina_cost = float(row[1])
                    min_level = int(row[2])
                    damage_multiplier = int(row[3])
                    attack_name = row[4]
                    picture_link = row[5]
                melee_records = await select_sql("""SELECT CharacterId FROM MeleeSkills WHERE CharacterId=%s""",
                                                 (server_party_chars[server_id][user_id]["CharId"],))
                if not melee_records:
                    await reply_message(message, "You do not know this attack. Try something you do know!")
                    return
                if (min_level > server_party_chars[server_id][user_id]["Level"]):
                    await direct_message(message,
                                         "You're not a high enough level for this attack. How did you even learn it?")
                    return
            if stamina_cost < 1.0:
                stamina_cost = server_party_chars[server_id][user_id]["MaxStamina"] * stamina_cost                    
            if server_party_chars[server_id][user_id]["Stamina"] < stamina_cost:
                await direct_message(message,
                                     "You do not have sufficient stamina for this melee. Try another melee or restore stamina!")
                return
            await direct_message(message, "Attacking the monster with " + attack_name + ".")
            server_party_chars[server_id][user_id]["Stamina"] = server_party_chars[server_id][user_id][
                                                                    "Stamina"] - stamina_cost

            # await dm_tracker[message.author.id]["commandchannel"].send(">>> " + str(server_party_chars[server_id][user_id]["CharName"]) + " attacks " + str(server_monsters[server_id]["MonsterName"]) + " with " + attack_name + "!\nThis drained " + str(stamina_cost) + " from " + server_party_chars[server_id][user_id]["CharName"] + ", leaving them with " + str(server_party_chars[server_id][user_id]["Stamina"]) + " stamina!")
            attack_text = "" + str(server_party_chars[server_id][user_id]["CharName"]) + " attacks " + str(
                server_monsters[server_id]["MonsterName"]) + " with " + attack_name + "!\nThis drained " + str(
                stamina_cost) + " from " + server_party_chars[server_id][user_id][
                              "CharName"] + ", leaving them with " + str(
                server_party_chars[server_id][user_id]["Stamina"]) + " stamina!\n"
            embed = discord.Embed(title=attack_text)
            if picture_link.startswith('http'):
                embed.set_thumbnail(url=picture_link)
            await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
            await asyncio.sleep(1)
            #            await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_party_chars[server_id][user_id]["CharName"], attack_text, server_party_chars[server_id][user_id]["PictureLink"])
            dodge = await calculate_dodge(server_party_chars[server_id][user_id]["Agility"],
                                          server_monsters[server_id]["Agility"], )
            if dodge:
                dodge_text = "" + server_monsters[server_id]["MonsterName"] + " dodged the attack! No damage taken!"
                embed = discord.Embed(title=dodge_text)
                if server_monsters[server_id]["PictureLink"].startswith('http'):
                    embed.set_thumbnail(url=server_monsters[server_id]["PictureLink"])
                await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                await asyncio.sleep(1)
            #                await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_monsters[server_id]["MonsterName"], dodge_text, server_monsters[server_id]["PictureLink"])
            # await dm_tracker[message.author.id]["commandchannel"].send(">>> " + server_monsters[server_id]["MonsterName"] + " dodged the attack! No damage taken!")
            else:
                damage = await calculate_damage(server_party_chars[server_id][user_id]["Attack"],
                                                server_monsters[server_id]["Defense"], damage_multiplier,
                                                server_party_chars[server_id][user_id]["Level"],
                                                server_monsters[server_id]["Level"])
                server_monsters[server_id]["Health"] = int(server_monsters[server_id]["Health"] - damage)
                # await dm_tracker[message.author.id]["commandchannel"].send(">>> " + server_monsters[server_id]["MonsterName"] + " was hit by " + server_party_chars[server_id][user_id]["CharName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(server_monsters[server_id]["Health"]))
                hit_text = "" + server_monsters[server_id]["MonsterName"] + " was hit by " + \
                           server_party_chars[server_id][user_id]["CharName"] + " for " + str(
                    damage) + " points!\n\nHealth now at " + str(server_monsters[server_id]["Health"])
                embed = discord.Embed(title=hit_text)
                if server_monsters[server_id]["PictureLink"].startswith('http'):
                    embed.set_thumbnail(url=server_monsters[server_id]["PictureLink"])
                await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                await asyncio.sleep(1)
                #               await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_monsters[server_id]["MonsterName"], hit_text, server_monsters[server_id]["PictureLink"])
                if server_monsters[server_id]["Health"] < 1:
                    fallen_text = "" + server_monsters[server_id][
                        "MonsterName"] + " has no health left and is out of the fight!"
                    embed = discord.Embed(title=fallen_text)
                    if server_monsters[server_id]["PictureLink"].startswith('http'):
                        embed.set_thumbnail(url=server_monsters[server_id]["PictureLink"])
                    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                    await asyncio.sleep(1)
                    # await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_monsters[server_id]["MonsterName"], fallen_text, server_monsters[server_id]["PictureLink"])
                    # await dm_tracker[message.author.id]["commandchannel"].send(">>> " + server_monsters[server_id]["MonsterName"] + " has no health left and is out of the fight!")
                    currency_earned = server_monsters[server_id]["MaxCurrencyDrop"]
                    server_encounters[server_id] = False
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Victory!")
                    response = "**Experience gained:**\n\n"
                    for user in server_party_chars[server_id].keys():
                        char_id = server_party_chars[server_id][user]["CharId"]
                        await log_message("Level " + str(server_party_chars[server_id][user]["Level"]))
                        new_xp = await calculate_xp(server_party_chars[server_id][user]["Level"],
                                                    server_monsters[server_id]["Level"], monster_health[server_id],
                                                    len(server_party_chars[server_id]))
                        response = response + "*" + server_party_chars[server_id][user]["CharName"] + "*: " + str(
                            new_xp) + "\n"
                        records = await select_sql("""SELECT Experience FROM CharacterProfiles WHERE Id=%s;""",
                                                   (str(server_party_chars[server_id][user]["CharId"]),))
                        for row in records:
                            old_xp = int(row[0])
                        total_xp = int(old_xp + new_xp)
                        response = response + "Currency earned: " + str(currency_earned) + "\n"
                        server_party_chars[server_id][user]["Currency"] = server_party_chars[server_id][user][
                                                                              "Currency"] + currency_earned
                        result = await commit_sql("""UPDATE CharacterProfiles SET CURRENCY=%s WHERE Id=%s;""", (
                            str(server_party_chars[server_id][user]["Currency"]),
                            str(server_party_chars[server_id][user]["CharId"])))
                        if total_xp > (guild_settings[server_id]["XPLevelRatio"] * server_party_chars[server_id][user][
                            "Level"]):
                            server_party_chars[server_id][user]["Level"] = server_party_chars[server_id][user][
                                                                               "Level"] + 1
                            records = await select_sql("""SELECT StatPoints FROM CharacterProfiles WHERE Id=%s;""",
                                                       (str(server_party_chars[server_id][user]["CharId"]),))
                            for row in records:
                                stat_points = int(row[0])

                            available_points = guild_settings[server_id]["StatPointsPerLevel"] + stat_points
                            response = response + "**" + server_party_chars[server_id][user][
                                "CharName"] + "** LEVELED UP TO LEVEL **" + str(
                                server_party_chars[server_id][user]["Level"]) + "!**\nYou have " + str(
                                int(available_points)) + " stat points to spend!\n\n"
                            total_xp = 0
                            health = server_party_chars[server_id][user_id]["MaxHealth"] + guild_settings[server_id][
                                "HealthLevelAdd"]
                            stamina = server_party_chars[server_id][user_id]["MaxStamina"] + guild_settings[server_id][
                                "StaminaLevelAdd"]
                            mana = server_party_chars[server_id][user_id]["MaxMana"] + guild_settings[server_id][
                                "ManaLevelAdd"]
                            result = await commit_sql(
                                """UPDATE CharacterProfiles SET Level=%s,Experience=%s,Health=%s,Stamina=%s,Mana=%s,StatPoints=%s WHERE Id=%s;""",
                                (str(server_party_chars[server_id][user]["Level"]), str(total_xp), str(health),
                                 str(stamina), str(mana), str(available_points),
                                 str(server_party_chars[server_id][user]["CharId"])))
                        else:
                            result = await commit_sql(
                                """UPDATE CharacterProfiles SET Level=%s,Experience=%s WHERE Id=%s;""", (
                                    str(server_party_chars[server_id][user]["Level"]), str(total_xp),
                                    str(server_party_chars[server_id][user]["CharId"])))
                    embed = discord.Embed(title="Results", description=response)
                    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                    await asyncio.sleep(1)
                    #   await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
                    return
            await monster_attack(message.author.id)
            if not server_encounters[server_id]:
                return

            if encounter_turn[server_id] > len(server_party[server_id]) - 2:
                encounter_turn[server_id] = 0
                await dm_tracker[message.author.id]["commandchannel"].send(
                    ">>> <@" + str(list(server_party[server_id])[encounter_turn[server_id]].id) + ">, it is your turn!")
            else:
                encounter_turn[server_id] = encounter_turn[server_id] + 1
            await dm_tracker[message.author.id]["commandchannel"].send(
                ">>> <@" + str(list(server_party[server_id])[encounter_turn[server_id]].id) + ">, it is your turn!")
            return
        elif current_command == 'castmonster':
            user_id = message.author.id

            server_id = dm_tracker[message.author.id]["server_id"]
            records = await select_sql(
                """SELECT Id,ManaCost,MinimumLevel,DamageMultiplier,SpellName,PictureLink FROM Spells WHERE Id=%s;""",
                (message.content,))
            if not records:
                await direct_message(message, "That's not a valid spell. Try again.")
                return
            else:
                for row in records:
                    spell_id = row[0]
                    mana_cost = float(row[1])
                    min_level = int(row[2])
                    damage_multiplier = int(row[3])
                    spell_name = row[4]
                    picture_link = row[5]
                spell_records = await select_sql("""SELECT CharacterId FROM MagicSkills WHERE CharacterId=%s""",
                                                 (server_party_chars[server_id][user_id]["CharId"],))
                if not spell_records:
                    await direct_message(message, "You do not know this spell. Try something you do know!")
                    return
                if (min_level > server_party_chars[server_id][user_id]["Level"]):
                    await direct_message(message,
                                         "You're not a high enough level for this spell. How did you even learn it?")
                    return
            if mana_cost < 1.0:
                mana_cost = server_party_chars[server_id][user_id]["MaxMana"] * mana_cost
                
            if server_party_chars[server_id][user_id]["Mana"] < mana_cost:
                await direct_message(message,
                                     "You do not have sufficient mana for this spell. Try another spell or restore mana!")
                return
            await direct_message(message, "Attacking monster with " + spell_name + ".")
            server_party_chars[server_id][user_id]["Mana"] = int(
                server_party_chars[server_id][user_id]["Mana"] - mana_cost)
            attack_text = "" + str(server_party_chars[server_id][user_id]["CharName"]) + " attacks " + str(
                server_monsters[server_id]["MonsterName"]) + " with " + spell_name + "!\nThis drained " + str(
                mana_cost) + " mana from " + server_party_chars[server_id][user_id][
                              "CharName"] + ", leaving them with " + str(
                server_party_chars[server_id][user_id]["Mana"]) + " mana!\n\n"
            embed = discord.Embed(title=attack_text)
            if picture_link.startswith('http'):
                embed.set_thumbnail(url=picture_link)
            await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
            await asyncio.sleep(1)

            dodge = await calculate_dodge(server_party_chars[server_id][user_id]["Agility"],
                                          server_monsters[server_id]["Agility"], )
            if dodge:
                dodge_text = "" + server_monsters[server_id]["MonsterName"] + " dodged the attack! No damage taken!"
                embed = discord.Embed(title=dodge_text)
                if server_monsters[server_id]["PictureLink"].startswith('http'):
                    embed.set_thumbnail(url=server_monsters[server_id]["PictureLink"])
                await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                await asyncio.sleep(1)
            #                await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_monsters[server_id]["MonsterName"], dodge_text, server_monsters[server_id]["PictureLink"])
            # await dm_tracker[user_id]["commandchannel"].send(">>> " + server_monsters[server_id]["MonsterName"] + " dodged the attack! No damage taken!")
            else:
                damage = await calculate_damage(server_party_chars[server_id][user_id]["MagicAttack"],
                                                server_monsters[server_id]["Defense"], damage_multiplier,
                                                server_party_chars[server_id][user_id]["Level"],
                                                server_monsters[server_id]["Level"])
                server_monsters[server_id]["Health"] = int(server_monsters[server_id]["Health"] - damage)
                hit_text = "" + server_monsters[server_id]["MonsterName"] + " was hit by " + \
                           server_party_chars[server_id][user_id]["CharName"] + " for " + str(
                    damage) + " points!\n\nHealth now at " + str(server_monsters[server_id]["Health"])
                embed = discord.Embed(title=hit_text)
                if server_monsters[server_id]["PictureLink"].startswith('http'):
                    embed.set_thumbnail(url=server_monsters[server_id]["PictureLink"])
                await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                asyncio.sleep(1)
                #   await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_monsters[server_id]["MonsterName"], hit_text, server_monsters[server_id]["PictureLink"])
                #                await dm_tracker[user_id]["commandchannel"].send(">>> " + server_monsters[server_id]["MonsterName"] + " was hit by " + server_party_chars[server_id][user_id]["CharName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(server_monsters[server_id]["Health"]))
                if server_monsters[server_id]["Health"] < 1:
                    fallen_text = "" + server_monsters[server_id][
                        "MonsterName"] + " has no health left and is out of the fight!"
                    #   await post_webhook(dm_tracker[message.author.id]["commandchannel"], server_monsters[server_id]["MonsterName"], hit_text, server_monsters[server_id]["PictureLink"])
                    #                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + server_monsters[server_id]["MonsterName"] + " has no health left and is out of the fight!")
                    embed = discord.Embed(title=fallen_text)
                    if server_monsters[server_id]["PictureLink"].startswith('http'):
                        embed.set_thumbnail(url=server_monsters[server_id]["PictureLink"])
                    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                    await asyncio.sleep(1)
                    server_encounters[server_id] = False
                    currency_earned = server_monsters[server_id]["MaxCurrencyDrop"]
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Victory!")
                    response = "**Experience gained:**\n\n"
                    for user in server_party_chars[server_id].keys():
                        char_id = server_party_chars[server_id][user]["CharId"]
                        await log_message("Level " + str(server_party_chars[server_id][user]["Level"]))
                        new_xp = await calculate_xp(server_party_chars[server_id][user]["Level"],
                                                    server_monsters[server_id]["Level"], monster_health[server_id],
                                                    len(server_party_chars[server_id]))
                        response = response + "*" + server_party_chars[server_id][user]["CharName"] + "*: " + str(
                            new_xp) + "\n"
                        records = await select_sql("""SELECT Experience FROM CharacterProfiles WHERE Id=%s;""",
                                                   (str(server_party_chars[server_id][user]["CharId"]),))
                        for row in records:
                            old_xp = int(row[0])
                        total_xp = old_xp + new_xp
                        response = response + "Currency earned: " + str(currency_earned) + "\n"
                        server_party_chars[server_id][user]["Currency"] = server_party_chars[server_id][user][
                                                                              "Currency"] + currency_earned
                        result = await commit_sql("""UPDATE CharacterProfiles SET CURRENCY=%s WHERE Id=%s;""", (
                            str(server_party_chars[server_id][user]["Currency"]),
                            str(server_party_chars[server_id][user]["CharId"])))
                        if total_xp > (guild_settings[server_id]["XPLevelRatio"] * server_party_chars[server_id][user][
                            "Level"]):
                            server_party_chars[server_id][user]["Level"] = server_party_chars[server_id][user][
                                                                               "Level"] + 1
                            records = await select_sql("""SELECT StatPoints FROM CharacterProfiles WHERE Id=%s;""",
                                                       (str(server_party_chars[server_id][user]["CharId"]),))
                            for row in records:
                                stat_points = int(row[0])

                            available_points = guild_settings[server_id]["StatPointsPerLevel"] + stat_points
                            response = response + "**" + server_party_chars[server_id][user][
                                "CharName"] + "** LEVELED UP TO LEVEL **" + str(
                                server_party_chars[server_id][user]["Level"]) + "!**\nYou have " + str(
                                available_points) + " stat points to spend!\n\n"
                            health = server_party_chars[server_id][user_id]["MaxHealth"] + guild_settings[server_id][
                                "HealthLevelAdd"]
                            stamina = server_party_chars[server_id][user_id]["MaxStamina"] + guild_settings[server_id][
                                "StaminaLevelAdd"]
                            mana = server_party_chars[server_id][user_id]["MaxMana"] + guild_settings[server_id][
                                "ManaLevelAdd"]
                            result = await commit_sql(
                                """UPDATE CharacterProfiles SET Level=%s,Experience=%s,Health=%s,Stamina=%s,Mana=%s,StatPoints=%s WHERE Id=%s;""",
                                (str(server_party_chars[server_id][user]["Level"]), str(total_xp), str(health),
                                 str(stamina), str(mana), str(available_points),
                                 str(server_party_chars[server_id][user]["CharId"])))
                        else:
                            result = await commit_sql(
                                """UPDATE CharacterProfiles SET Level=%s,Experience=%s WHERE Id=%s;""", (
                                    str(server_party_chars[server_id][user]["Level"]), str(total_xp),
                                    str(server_party_chars[server_id][user]["CharId"])))
                    embed = discord.Embed(title="Results", description=response)
                    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                    await asyncio.sleep(1)

                    server_monsters[server_id] = {}
                    return
            await monster_attack(message.author.id)
            if not server_encounters[server_id]:
                return

            if encounter_turn[server_id] > len(server_party[server_id]) - 2:
                encounter_turn[server_id] = 0
                await dm_tracker[message.author.id]["commandchannel"].send(
                    ">>> <@" + str(list(server_party[server_id])[encounter_turn[server_id]].id) + ">, it is your turn!")
            else:
                encounter_turn[server_id] = encounter_turn[server_id] + 1
                await dm_tracker[message.author.id]["commandchannel"].send(
                    ">>> <@" + str(list(server_party[server_id])[encounter_turn[server_id]].id) + ">, it is your turn!")
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
                dm_tracker[message.author.id]["parameters"] = char_map
                return
            elif dm_tracker[message.author.id]["currentfield"] == 1:
                user_id = message.author.id
                target_id = dm_tracker[message.author.id]["parameters"][int(message.content)]
                records = await select_sql(
                    """SELECT Id,StaminaCost,MinimumLevel,DamageMultiplier,AttackName,StatusChange,StatusChangedBy,PictureLink FROM Melee WHERE Id=%s;""",
                    (dm_tracker[message.author.id]["fielddict"][0],))
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
                        status_change = row[5]
                        status_changed_by = int(row[6])
                        picture_link = row[7]
                    melee_records = await select_sql("""SELECT CharacterId FROM MeleeSkills WHERE CharacterId=%s""",
                                                     (mass_spar_chars[server_id][user_id]["CharId"],))
                    if not melee_records:
                        await reply_message(message, "You do not know this melee. Try something you do know!")
                        return
                    if (min_level > mass_spar_chars[server_id][user_id]["Level"]):
                        await direct_message(message,
                                             "You're not a high enough level for this melee. How did you even learn it?")
                        return
                if stamina_cost < 1.0:
                    stamina_cost = mass_spar_chars[server_id][user_id]["MaxStamina"] * stamina_cost             
                    
                if mass_spar_chars[server_id][user_id]["Stamina"] < stamina_cost:
                    await direct_message(message,
                                         "You do not have sufficient stamina for this melee. Try another melee or restore stamina!")
                    return
                mass_spar_chars[server_id][user_id]["Stamina"] = mass_spar_chars[server_id][user_id][
                                                                     "Stamina"] - stamina_cost
                await direct_message(message, "Attacking with " + parsed_string)
                #               await dm_tracker[message.author.id]["commandchannel"].send(">>> " + str(mass_spar_chars[server_id][user_id]["CharName"]) + " attacks " + str(mass_spar_chars[server_id][target_id]["CharName"]) + " with " + parsed_string + "!\nThis drained " + str(stamina_cost) + " from " + mass_spar_chars[server_id][user_id]["CharName"] + ", leaving them with " + str(mass_spar_chars[server_id][user_id]["Stamina"]) + " stamina!")
                attack_text = "" + str(mass_spar_chars[server_id][user_id]["CharName"]) + " attacks " + str(
                    mass_spar_chars[server_id][target_id][
                        "CharName"]) + " with " + parsed_string + "!\nThis drained " + str(stamina_cost) + " from " + \
                              mass_spar_chars[server_id][user_id]["CharName"] + ", leaving them with " + str(
                    mass_spar_chars[server_id][user_id]["Stamina"]) + " stamina!\n\n"
                embed = discord.Embed(title=attack_text)
                if picture_link.startswith('http'):
                    embed.set_thumbnail(url=picture_link)
                await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                await asyncio.sleep(1)
                #                await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][user_id]["CharName"], attack_text, mass_spar_chars[server_id][user_id]["PictureLink"])
                dodge = await calculate_dodge(mass_spar_chars[server_id][user_id]["Agility"],
                                              mass_spar_chars[server_id][target_id]["Agility"])
                if dodge:
                    dodge_text = mass_spar_chars[server_id][target_id][
                                     "CharName"] + " dodged the attack! No damage taken!"
                    embed = discord.Embed(title=dodge_text)
                    if mass_spar_chars[server_id][target_id]["PictureLink"].startswith('http'):
                        embed.set_thumbnail(url=mass_spar_chars[server_id][target_id]["PictureLink"])
                    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                    await asyncio.sleep(1)
                #                    await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][target_id]["CharName"], dodge_text, mass_spar_chars[server_id][target_id]["PictureLink"])
                #                   await reply_message(message, mass_spar_chars[server_id][target_id]["CharName"] + " dodged the attack! No damage taken!")
                else:
                    damage = await calculate_damage(mass_spar_chars[server_id][user_id]["Attack"],
                                                    mass_spar_chars[server_id][target_id]["Defense"], damage_multiplier,
                                                    mass_spar_chars[server_id][user_id]["Level"],
                                                    mass_spar_chars[server_id][target_id]["Level"])
                    if status_change != 'None':
                        if mass_spar_cooldown[server_id][target_id] == 0:
                            result = await commit_sql("""UPDATE CharacterProfiles SET Status=%s WHERE Id=%s;""", (
                                str(status_change + '=' + str(status_changed_by)),
                                str(mass_spar_chars[server_id][target_id]["CharId"])))
                            mass_spar_cooldown[server_id][target_id] = mass_spar_cooldown_turns
                            embed2 = discord.Embed(title=mass_spar_chars[server_id][target_id][
                                                             "CharName"] + "'s status has changed to " + status_change + "!")
                        else:
                            embed2 = discord.Embed(title="The status change failed to take effect!")
                            mass_spar_cooldown[server_id][target_id] = mass_spar_cooldown[server_id][target_id] - 1
                        await dm_tracker[message.author.id]["commandchannel"].send(embed=embed2)
                    mass_spar_chars[server_id][target_id]["Health"] = mass_spar_chars[server_id][target_id][
                                                                          "Health"] - damage
                    mass_spar_chars[server_id][user_id]["TotalDamage"] = mass_spar_chars[server_id][user_id][
                                                                             "TotalDamage"] + damage
                    hit_text = "" + mass_spar_chars[server_id][target_id]["CharName"] + " was hit by " + \
                               mass_spar_chars[server_id][user_id]["CharName"] + " for " + str(
                        damage) + " points!\n\nHealth now at " + str(
                        mass_spar_chars[server_id][target_id]["Health"]) + "!"
                    # await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][target_id]["CharName"], hit_text, mass_spar_chars[server_id][target_id]["PictureLink"])
                    embed = discord.Embed(title=hit_text)
                    if mass_spar_chars[server_id][target_id]["PictureLink"].startswith('http'):
                        embed.set_thumbnail(url=mass_spar_chars[server_id][target_id]["PictureLink"])
                    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                    await asyncio.sleep(1)
                    # await dm_tracker[message.author.id]["commandchannel"].send(">>> " + mass_spar_chars[server_id][target_id]["CharName"] + " was hit by " + mass_spar_chars[server_id][user_id]["CharName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(mass_spar_chars[server_id][target_id]["Health"]))
                    if mass_spar_chars[server_id][target_id]["Health"] < 1:
                        fallen_text = mass_spar_chars[server_id][target_id][
                                          "CharName"] + " has no health left and is out of the fight!"
                        embed = discord.Embed(title=fallen_text)
                        if mass_spar_chars[server_id][target_id]["PictureLink"].startswith('http'):
                            embed.set_thumbnail(url=mass_spar_chars[server_id][target_id]["PictureLink"])
                        await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                        await asyncio.sleep(1)
                        # await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][target_id]["CharName"], fallen_text, mass_spar_chars[server_id][target_id]["PictureLink"])
                        # await reply_message(message, mass_spar_chars[server_id][target_id]["CharName"] + " has no health left and is out of the fight!")

                        fallen_chars[dm_tracker[message.author.id]["server_id"]][target_id] = {}
                        fallen_chars[dm_tracker[message.author.id]["server_id"]][target_id] = \
                            mass_spar_chars[server_id][target_id]
                        del mass_spar_chars[server_id][target_id]

                if len(mass_spar_chars[server_id]) < 2:
                    response = "<@" + str(
                        message.author.id) + "> is the last one standing and is the spar winner!\n\n**Experience gained:**\n\n"
                    fallen_chars[dm_tracker[message.author.id]["server_id"]][message.author.id] = {}
                    fallen_chars[dm_tracker[message.author.id]["server_id"]][message.author.id] = \
                        mass_spar_chars[server_id][message.author.id]
                    for char in fallen_chars[dm_tracker[message.author.id]["server_id"]].keys():

                        char_id = fallen_chars[server_id][char]["CharId"]
                        if char_id == client.user.id:
                            continue
                        await log_message("Level " + str(fallen_chars[server_id][char]["Level"]))
                        new_xp = await calculate_xp(fallen_chars[server_id][char]["Level"],
                                                    fallen_chars[server_id][char]["Level"],
                                                    fallen_chars[server_id][char]["TotalDamage"], 1) * 2
                        response = response + "*" + fallen_chars[server_id][char]["CharName"] + "*: " + str(
                            new_xp) + "\n"
                        records = await select_sql("""SELECT Experience FROM CharacterProfiles WHERE Id=%s;""",
                                                   (str(fallen_chars[server_id][char]["CharId"]),))
                        for row in records:
                            old_xp = int(row[0])
                        try:
                            old_xp
                        except:
                            old_xp = 0
                        total_xp = old_xp + new_xp
                        if total_xp > (
                                guild_settings[server_id]["XPLevelRatio"] * fallen_chars[server_id][char]["Level"]):
                            if fallen_chars[server_id][char]["CharId"] == 0:
                                continue
                            fallen_chars[server_id][char]["Level"] = fallen_chars[server_id][char]["Level"] + 1
                            records = await select_sql("""SELECT StatPoints FROM CharacterProfiles WHERE Id=%s;""",
                                                       (str(fallen_chars[server_id][char]["CharId"]),))
                            for row in records:
                                stat_points = int(row[0])

                            available_points = int(guild_settings[server_id]["StatPointsPerLevel"]) + stat_points
                            response = response + "**" + fallen_chars[server_id][char][
                                "CharName"] + "** LEVELED UP TO LEVEL **" + str(
                                fallen_chars[server_id][char]["Level"]) + "!**\nYou have " + str(
                                available_points) + " stat points to spend!\n\n"
                            total_xp = 0
                            health = fallen_chars[server_id][char]["MaxHealth"] + guild_settings[server_id][
                                "HealthLevelAdd"]
                            stamina = fallen_chars[server_id][char]["MaxStamina"] + guild_settings[server_id][
                                "StaminaLevelAdd"]
                            mana = fallen_chars[server_id][char]["MaxMana"] + guild_settings[server_id][
                                "ManaLevelAdd"]
                            result = await commit_sql(
                                """UPDATE CharacterProfiles SET Level=%s,Experience=%s,Health=%s,Stamina=%s,Mana=%s,StatPoints=%s WHERE Id=%s;""",
                                (str(fallen_chars[server_id][char]["Level"]), str(total_xp), str(health),
                                 str(stamina), str(mana), str(available_points),
                                 str(fallen_chars[server_id][char]["CharId"])))
                        else:
                            result = await commit_sql("""UPDATE CharacterProfiles SET Experience=%s WHERE Id=%s;""", (
                                str(total_xp), str(fallen_chars[server_id][char]["CharId"])))
                    mass_spar_event[server_id] = False

                    embed = discord.Embed(title="Result", description=response)
                    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                    await asyncio.sleep(1)
                    #    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
                    return

                if mass_spar_turn[server_id] > len(mass_spar_chars[server_id]) - 2:
                    mass_spar_turn[server_id] = 0
                else:
                    mass_spar_turn[server_id] = mass_spar_turn[server_id] + 1
                await dm_tracker[message.author.id]["commandchannel"].send(
                    ">>> <@" + str(list(mass_spar[server_id])[mass_spar_turn[server_id]].id) + ">, it is your turn!")
                if mass_spar[server_id][mass_spar_turn[server_id]] == client.user:
                    picker = random.randint(1, 2)
                    if picker == 1:
                        await ai_castspar(message)
                    else:
                        await ai_meleespar(message)
                    mass_spar_turn[server_id] = mass_spar_turn[server_id] = 0
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> <@" + str(
                        list(mass_spar[server_id])[mass_spar_turn[server_id]].id) + ">, it is your turn!")
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
                dm_tracker[message.author.id]["parameters"] = char_map
                return
            elif dm_tracker[message.author.id]["currentfield"] == 1:
                user_id = message.author.id
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                target_id = dm_tracker[message.author.id]["parameters"][int(message.content)]
                records = await select_sql(
                    """SELECT Id,ManaCost,MinimumLevel,DamageMultiplier,SpellName,StatusChange,StatusChangedBy,PictureLink FROM Spells WHERE Id=%s;""",
                    (dm_tracker[message.author.id]["fielddict"][0],))
                if not records:
                    await direct_message(message, "That's not a valid spell. Try again.")
                    return
                else:
                    for row in records:
                        spell_id = row[0]
                        mana_cost = float(row[1])
                        min_level = int(row[2])
                        damage_multiplier = int(row[3])
                        parsed_string = row[4]
                        status_change = row[5]
                        status_changed_by = int(row[6])
                        picture_link = row[7]
                    spell_records = await select_sql("""SELECT CharacterId FROM MagicSkills WHERE CharacterId=%s""",
                                                     (mass_spar_chars[server_id][user_id]["CharId"],))
                    if not spell_records:
                        await direct_message(message, "You do not know this spell. Try something you do know!")
                        return
                    if (min_level > mass_spar_chars[server_id][user_id]["Level"]):
                        await direct_message(message,
                                             "You're not a high enough level for this spell. How did you even learn it?")
                        return
                        
                if mana_cost < 1.0:
                    mana_cost = mass_spar_chars[server_id][user_id]["MaxMana"] * mana_cost
                    
                if mass_spar_chars[server_id][user_id]["Mana"] < mana_cost:
                    await direct_message(message,
                                         "You do not have sufficient mana for this spell. Try another spell or restore mana!")
                    return
                await direct_message(message, "Attacking with " + parsed_string)
                mass_spar_chars[server_id][user_id]["Mana"] = mass_spar_chars[server_id][user_id]["Mana"] - mana_cost
                attack_text = "" + str(mass_spar_chars[server_id][user_id]["CharName"]) + " attacks " + str(
                    mass_spar_chars[server_id][target_id][
                        "CharName"]) + " with " + parsed_string + "!\nThis drained " + str(mana_cost) + " from " + \
                              mass_spar_chars[server_id][user_id]["CharName"] + ", leaving them with " + str(
                    mass_spar_chars[server_id][user_id]["Mana"]) + " mana!\n\n"
                embed = discord.Embed(title=attack_text)
                if picture_link.startswith('http'):
                    embed.set_thumbnail(url=picture_link)
                await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                await asyncio.sleep(1)

                dodge = await calculate_dodge(mass_spar_chars[server_id][user_id]["Agility"],
                                              mass_spar_chars[server_id][target_id]["Agility"])
                if dodge:
                    #  await dm_tracker[message.author.id]["commandchannel"].send(">>> " + mass_spar_chars[server_id][target_id]["CharName"] + " dodged the attack! No damage taken!")
                    dodge_text = "" + mass_spar_chars[server_id][target_id][
                        "CharName"] + " dodged the attack! No damage taken!"
                    embed = discord.Embed(title=dodge_text)
                    if mass_spar_chars[server_id][target_id]["PictureLink"].startswith('http'):
                        embed.set_thumbnail(url=mass_spar_chars[server_id][target_id]["PictureLink"])
                    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                    await asyncio.sleep(1)
                #  await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][target_id]["CharName"], dodge_text, mass_spar_chars[server_id][target_id]["PictureLink"])
                else:
                    damage = await calculate_damage(mass_spar_chars[server_id][user_id]["MagicAttack"],
                                                    mass_spar_chars[server_id][target_id]["Intellect"],
                                                    damage_multiplier, mass_spar_chars[server_id][user_id]["Level"],
                                                    mass_spar_chars[server_id][target_id]["Level"])
                    mass_spar_chars[server_id][target_id]["Health"] = mass_spar_chars[server_id][target_id][
                                                                          "Health"] - damage
                    if status_change != 'None':
                        if mass_spar_cooldown[server_id][target_id] == 0:
                            result = await commit_sql("""UPDATE CharacterProfiles SET Status=%s WHERE Id=%s;""", (
                                str(status_change + '=' + str(status_changed_by)),
                                str(mass_spar_chars[server_id][target_id]["CharId"])))
                            mass_spar_cooldown[server_id][target_id] = mass_spar_cooldown_turns
                            embed2 = discord.Embed(title=mass_spar_chars[server_id][target_id][
                                                             "CharName"] + "'s status has changed to " + status_change + "!")
                        else:
                            embed2 = discord.Embed(title="The status change failed to take effect!")
                            mass_spar_cooldown[server_id][target_id] = mass_spar_cooldown[server_id][target_id] - 1
                        await dm_tracker[message.author.id]["commandchannel"].send(embed=embed2)
                    mass_spar_chars[server_id][user_id]["TotalDamage"] = mass_spar_chars[server_id][user_id][
                                                                             "TotalDamage"] + damage
                    hit_text = "" + mass_spar_chars[server_id][target_id]["CharName"] + " was hit by " + \
                               mass_spar_chars[server_id][user_id]["CharName"] + " for " + str(
                        damage) + " points!\n\nHealth now at " + str(
                        mass_spar_chars[server_id][target_id]["Health"]) + "!"
                    embed = discord.Embed(title=hit_text)
                    if mass_spar_chars[server_id][target_id]["PictureLink"].startswith('http'):
                        embed.set_thumbnail(url=mass_spar_chars[server_id][target_id]["PictureLink"])
                    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                    await asyncio.sleep(1)

                    if mass_spar_chars[server_id][target_id]["Health"] < 1:

                        # await dm_tracker[message.author.id]["commandchannel"].send(">>> " + mass_spar_chars[server_id][target_id]["CharName"] + " has no health left and is out of the fight!")
                        out_text = "" + mass_spar_chars[server_id][target_id][
                            "CharName"] + " has no health left and is out of the fight!"
                        embed = discord.Embed(title=out_text)
                        if mass_spar_chars[server_id][target_id]["PictureLink"].startswith('http'):
                            embed.set_thumbnail(url=mass_spar_chars[server_id][target_id]["PictureLink"])
                        await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                        await asyncio.sleep(1)

                        fallen_chars[dm_tracker[message.author.id]["server_id"]][target_id] = {}
                        fallen_chars[dm_tracker[message.author.id]["server_id"]][target_id] = \
                            mass_spar_chars[server_id][target_id]
                        del mass_spar_chars[server_id][target_id]

                if len(mass_spar_chars[server_id]) < 2:
                    fallen_chars[dm_tracker[message.author.id]["server_id"]][message.author.id] = {}
                    fallen_chars[dm_tracker[message.author.id]["server_id"]][message.author.id] = \
                        mass_spar_chars[server_id][message.author.id]
                    response = "<@" + str(
                        message.author.id) + "> is the last one standing and is the spar winner!\n\n**Experience gained:**\n\n"
                    for char in fallen_chars[dm_tracker[message.author.id]["server_id"]].keys():

                        char_id = fallen_chars[server_id][char]["CharId"]
                        if char_id == client.user.id:
                            continue
                        await log_message("Level " + str(fallen_chars[server_id][char]["Level"]))
                        new_xp = await calculate_xp(fallen_chars[server_id][char]["Level"],
                                                    fallen_chars[server_id][char]["Level"],
                                                    fallen_chars[server_id][char]["TotalDamage"], 1) * 2
                        response = response + "*" + fallen_chars[server_id][char]["CharName"] + "*: " + str(
                            new_xp) + "\n"
                        records = await select_sql("""SELECT Experience FROM CharacterProfiles WHERE Id=%s;""",
                                                   (str(fallen_chars[server_id][char]["CharId"]),))
                        for row in records:
                            old_xp = int(row[0])
                        try:
                            old_xp
                        except:
                            old_xp = 0
                        total_xp = old_xp + new_xp
                        if total_xp > (
                                guild_settings[server_id]["XPLevelRatio"] * fallen_chars[server_id][char]["Level"]):
                            if fallen_chars[server_id][char]["CharId"] == 0:
                                continue
                            fallen_chars[server_id][char]["Level"] = fallen_chars[server_id][char]["Level"] + 1
                            records = await select_sql("""SELECT StatPoints FROM CharacterProfiles WHERE Id=%s;""",
                                                       (str(fallen_chars[server_id][char]["CharId"]),))
                            for row in records:
                                stat_points = int(row[0])

                            available_points = int(guild_settings[server_id]["StatPointsPerLevel"]) + stat_points
                            response = response + "**" + fallen_chars[server_id][char][
                                "CharName"] + "** LEVELED UP TO LEVEL **" + str(
                                fallen_chars[server_id][char]["Level"]) + "!**\nYou have " + str(
                                available_points) + " stat points to spend!\n\n"
                            total_xp = 0
                            health = fallen_chars[server_id][char]["MaxHealth"] + guild_settings[server_id][
                                "HealthLevelAdd"]
                            stamina = fallen_chars[server_id][char]["MaxStamina"] + guild_settings[server_id][
                                "StaminaLevelAdd"]
                            mana = fallen_chars[server_id][char]["MaxMana"] + guild_settings[server_id][
                                "ManaLevelAdd"]
                            result = await commit_sql(
                                """UPDATE CharacterProfiles SET Level=%s,Experience=%s,Health=%s,Stamina=%s,Mana=%s,StatPoints=%s WHERE Id=%s;""",
                                (str(fallen_chars[server_id][char]["Level"]), str(total_xp), str(health),
                                 str(stamina), str(mana), str(available_points),
                                 str(fallen_chars[server_id][char]["CharId"])))
                        else:
                            result = await commit_sql("""UPDATE CharacterProfiles SET Experience=%s WHERE Id=%s;""", (
                                str(total_xp), str(fallen_chars[server_id][target_id]["CharId"])))
                    mass_spar_event[server_id] = False

                    embed = discord.Embed(title="Results", description=response)
                    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                    await asyncio.sleep(1)
                    #   await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
                    return

                if mass_spar_turn[server_id] > len(mass_spar_chars[server_id]) - 2:
                    mass_spar_turn[server_id] = 0
                else:
                    mass_spar_turn[server_id] = mass_spar_turn[server_id] + 1
                await dm_tracker[message.author.id]["commandchannel"].send(
                    ">>> <@" + str(list(mass_spar[server_id])[mass_spar_turn[server_id]].id) + ">, it is your turn!")

                if mass_spar[server_id][mass_spar_turn[server_id]] == client.user:
                    picker = random.randint(1, 2)
                    if picker == 1:
                        await ai_castspar(message)
                    else:
                        await ai_meleespar(message)
                    mass_spar_turn[server_id] = mass_spar_turn[server_id] = 0
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> <@" + str(
                        list(mass_spar[server_id])[mass_spar_turn[server_id]].id) + ">, it is your turn!")
                await initialize_dm(message.author.id)
                return
        elif current_command == 'summonspar':
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
                dm_tracker[message.author.id]["parameters"] = char_map
                return
            elif dm_tracker[message.author.id]["currentfield"] == 1:
                user_id = message.author.id
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                target_id = dm_tracker[message.author.id]["parameters"][int(message.content)]
                records = await select_sql(
                    """SELECT Id,MonsterName,Attack,Level,PictureLink FROM Monsters WHERE Id=%s;""",
                    (dm_tracker[message.author.id]["fielddict"][0],))
                if not records:
                    await direct_message(message, "That's not a valid summoning. Try again.")
                    return
                else:
                    for row in records:
                        monster_id = row[0]
                        monster_name = row[1]
                        monster_level = int(row[3])
                        damage_multiplier = int(row[2])
                        picture_link = row[4]
                    spell_records = await select_sql("""SELECT CharacterId FROM SummonInventory WHERE CharacterId=%s""",
                                                     (mass_spar_chars[server_id][user_id]["CharId"],))
                    if not spell_records:
                        await direct_message(message, "You do not know this summoning. Try something you do know!")
                        return
                    if (monster_level * 2 > mass_spar_chars[server_id][user_id]["Level"]):
                        await direct_message(message,
                                             "You're not a high enough level for this summon. How did you even learn it?")
                        return
                if mass_spar_chars[server_id][user_id]["Mana"] < mass_spar_chars[server_id][user_id]["MaxMana"] * 0.2:
                    await direct_message(message,
                                         "You do not have sufficient mana for this summon. Try another spell or restore mana!")
                    return
                await direct_message(message, "Attacking with " + monster_name)
                mass_spar_chars[server_id][user_id]["Mana"] = mass_spar_chars[server_id][user_id]["Mana"] - \
                                                              mass_spar_chars[server_id][user_id]["MaxMana"] * 0.2
                attack_text = "" + str(mass_spar_chars[server_id][user_id][
                                           "CharName"]) + " summons a " + monster_name + "to attack " + str(
                    mass_spar_chars[server_id][target_id][
                        "CharName"]) + "!\nThis drained " + str(
                    mass_spar_chars[server_id][user_id]["MaxMana"] * 0.2) + " from " + \
                              mass_spar_chars[server_id][user_id]["CharName"] + ", leaving them with " + str(
                    mass_spar_chars[server_id][user_id]["Mana"]) + " mana!\n\n"
                embed = discord.Embed(title=attack_text)
                if picture_link.startswith('http'):
                    embed.set_thumbnail(url=picture_link)
                await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                await asyncio.sleep(1)

                dodge = await calculate_dodge(monster_level * random.randint(10, 200),
                                              mass_spar_chars[server_id][target_id]["Agility"])
                if dodge:
                    #  await dm_tracker[message.author.id]["commandchannel"].send(">>> " + mass_spar_chars[server_id][target_id]["CharName"] + " dodged the attack! No damage taken!")
                    dodge_text = "" + mass_spar_chars[server_id][target_id][
                        "CharName"] + " dodged the attack! No damage taken!"
                    embed = discord.Embed(title=dodge_text)
                    if mass_spar_chars[server_id][target_id]["PictureLink"].startswith('http'):
                        embed.set_thumbnail(url=mass_spar_chars[server_id][target_id]["PictureLink"])
                    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                    await asyncio.sleep(1)
                #  await post_webhook(dm_tracker[message.author.id]["commandchannel"], mass_spar_chars[server_id][target_id]["CharName"], dodge_text, mass_spar_chars[server_id][target_id]["PictureLink"])
                else:
                    damage = await calculate_damage(damage_multiplier,
                                                    mass_spar_chars[server_id][target_id]["Defense"],
                                                    random.randint(3, 10), monster_level,
                                                    mass_spar_chars[server_id][target_id]["Level"])
                    mass_spar_chars[server_id][target_id]["Health"] = mass_spar_chars[server_id][target_id][
                                                                          "Health"] - damage

                    mass_spar_chars[server_id][user_id]["TotalDamage"] = mass_spar_chars[server_id][user_id][
                                                                             "TotalDamage"] + damage
                    hit_text = "" + mass_spar_chars[server_id][target_id]["CharName"] + " was hit by " + \
                               monster_name + " for " + str(
                        damage) + " points!\n\nHealth now at " + str(
                        mass_spar_chars[server_id][target_id]["Health"]) + "!"
                    embed = discord.Embed(title=hit_text)
                    if mass_spar_chars[server_id][target_id]["PictureLink"].startswith('http'):
                        embed.set_thumbnail(url=mass_spar_chars[server_id][target_id]["PictureLink"])
                    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                    await asyncio.sleep(1)

                    if mass_spar_chars[server_id][target_id]["Health"] < 1:

                        # await dm_tracker[message.author.id]["commandchannel"].send(">>> " + mass_spar_chars[server_id][target_id]["CharName"] + " has no health left and is out of the fight!")
                        out_text = "" + mass_spar_chars[server_id][target_id][
                            "CharName"] + " has no health left and is out of the fight!"
                        embed = discord.Embed(title=out_text)
                        if mass_spar_chars[server_id][target_id]["PictureLink"].startswith('http'):
                            embed.set_thumbnail(url=mass_spar_chars[server_id][target_id]["PictureLink"])
                        await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                        await asyncio.sleep(1)

                        fallen_chars[dm_tracker[message.author.id]["server_id"]][target_id] = {}
                        fallen_chars[dm_tracker[message.author.id]["server_id"]][target_id] = \
                            mass_spar_chars[server_id][target_id]
                        del mass_spar_chars[server_id][target_id]

                if len(mass_spar_chars[server_id]) < 2:
                    fallen_chars[dm_tracker[message.author.id]["server_id"]][message.author.id] = {}
                    fallen_chars[dm_tracker[message.author.id]["server_id"]][message.author.id] = \
                        mass_spar_chars[server_id][message.author.id]
                    response = "<@" + str(
                        message.author.id) + "> is the last one standing and is the spar winner!\n\n**Experience gained:**\n\n"
                    for char in fallen_chars[dm_tracker[message.author.id]["server_id"]].keys():

                        char_id = fallen_chars[server_id][char]["CharId"]
                        if char_id == client.user.id:
                            continue
                        await log_message("Level " + str(fallen_chars[server_id][char]["Level"]))
                        new_xp = await calculate_xp(fallen_chars[server_id][char]["Level"],
                                                    fallen_chars[server_id][char]["Level"],
                                                    fallen_chars[server_id][char]["TotalDamage"], 1) * 2
                        response = response + "*" + fallen_chars[server_id][char]["CharName"] + "*: " + str(
                            new_xp) + "\n"
                        records = await select_sql("""SELECT Experience FROM CharacterProfiles WHERE Id=%s;""",
                                                   (str(fallen_chars[server_id][char]["CharId"]),))
                        for row in records:
                            old_xp = int(row[0])
                        try:
                            old_xp
                        except:
                            old_xp = 0
                        total_xp = old_xp + new_xp
                        if total_xp > (
                                guild_settings[server_id]["XPLevelRatio"] * fallen_chars[server_id][char]["Level"]):
                            if fallen_chars[server_id][char]["CharId"] == 0:
                                continue
                            fallen_chars[server_id][char]["Level"] = fallen_chars[server_id][char]["Level"] + 1
                            records = await select_sql("""SELECT StatPoints FROM CharacterProfiles WHERE Id=%s;""",
                                                       (str(fallen_chars[server_id][char]["CharId"]),))
                            for row in records:
                                stat_points = int(row[0])

                            available_points = int(guild_settings[server_id]["StatPointsPerLevel"]) + stat_points
                            response = response + "**" + fallen_chars[server_id][char][
                                "CharName"] + "** LEVELED UP TO LEVEL **" + str(
                                fallen_chars[server_id][char]["Level"]) + "!**\nYou have " + str(
                                available_points) + " stat points to spend!\n\n"
                            total_xp = 0
                            health = fallen_chars[server_id][user_id]["MaxHealth"] + guild_settings[server_id][
                                "HealthLevelAdd"]
                            stamina = fallen_chars[server_id][user_id]["MaxStamina"] + guild_settings[server_id][
                                "StaminaLevelAdd"]
                            mana = fallen_chars[server_id][user_id]["MaxMana"] + guild_settings[server_id][
                                "ManaLevelAdd"]
                            result = await commit_sql(
                                """UPDATE CharacterProfiles SET Level=%s,Experience=%s,Health=%s,Stamina=%s,Mana=%s,StatPoints=%s WHERE Id=%s;""",
                                (str(fallen_chars[server_id][target_id]["Level"]), str(total_xp), str(health),
                                 str(stamina), str(mana), str(available_points),
                                 str(fallen_chars[server_id][target_id]["CharId"])))
                        else:
                            result = await commit_sql("""UPDATE CharacterProfiles SET Experience=%s WHERE Id=%s;""", (
                                str(total_xp), str(fallen_chars[server_id][target_id]["CharId"])))
                    mass_spar_event[server_id] = False

                    embed = discord.Embed(title="Results", description=response)
                    await dm_tracker[message.author.id]["commandchannel"].send(embed=embed)
                    await asyncio.sleep(1)
                    #   await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
                    return

                if mass_spar_turn[server_id] > len(mass_spar_chars[server_id]) - 2:
                    mass_spar_turn[server_id] = 0
                else:
                    mass_spar_turn[server_id] = mass_spar_turn[server_id] + 1
                await dm_tracker[message.author.id]["commandchannel"].send(
                    ">>> <@" + str(list(mass_spar[server_id])[mass_spar_turn[server_id]].id) + ">, it is your turn!")

                if mass_spar[server_id][mass_spar_turn[server_id]] == client.user:
                    picker = random.randint(1, 2)
                    if picker == 1:
                        await ai_castspar(message)
                    else:
                        await ai_meleespar(message)
                    mass_spar_turn[server_id] = mass_spar_turn[server_id] = 0
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> <@" + str(
                        list(mass_spar[server_id])[mass_spar_turn[server_id]].id) + ">, it is your turn!")
                await initialize_dm(message.author.id)
                return
        elif current_command == 'buy':
            if dm_tracker[message.author.id]["currentfield"] == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_simple_menu(message, "Vendors", "VendorName")
                response = "Please select from the list of available vendors by replying with the ID that is in bold.\n\n**VENDOR LIST**\n\n" + menu
                dm_tracker[message.author.id]["currentfield"] = 1
                await direct_message(message, response)
                return
            elif dm_tracker[message.author.id]["currentfield"] == 1:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                records = await select_sql("""SELECT ItemList FROM Vendors WHERE Id=%s;""", (message.content,))
                response = "Select an item from the vendor by using the ID in bold in your reply.\n\n**VENDOR ITEMS**\n\n"
                for row in records:
                    item_list = row[0].split(',')
                for item in item_list:
                    item_record = await select_sql("SELECT EquipmentName,EquipmentCost FROM Equipment WHERE Id=%s;",
                                                   (item,))
                    for item_obj in item_record:
                        response = response + "**" + item + "** - " + item_obj[0] + " - *" + str(item_obj[1]) + "*\n"
                        allowed_ids[message.author.id] = []
                        for x in item_list:
                            allowed_ids[message.author.id].append(x.strip())
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 2
                return


            elif dm_tracker[message.author.id]["currentfield"] == 2:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                records = await select_sql("""SELECT EquipmentName,EquipmentCost FROM Equipment WHERE Id=%s;""",
                                           (dm_tracker[message.author.id]["fielddict"][2],))

                if not records:
                    await direct_message(message, "No item found by that Id")
                    return
                for row in records:
                    item_name = row[0]
                    cost = float(row[1])
                records = await select_sql(
                    """SELECT UserId,Currency,CharacterName,Charisma,Level FROM CharacterProfiles WHERE Id=%s;""",
                    (dm_tracker[message.author.id]["fielddict"][0],))
                if not records:
                    await direct_message(message, "No character found by that ID")
                    return
                for row in records:
                    user_id = row[0]
                    currency = float(row[1])
                    char_name = row[2]
                    charisma = int(row[3])
                    level = int(row[4])
                if int(user_id) != message.author.id:
                    await direct_message(message, "This isn't your character!")
                    return
                haggle = random.randint(1, 10)
                if (haggle <= 2):
                    discount = (cost * (level / charisma))
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> You haggled a discount of " + str(discount) + "!")
                    cost = cost - discount
                if currency < cost:
                    await direct_message(message, "You don't have enough money to buy this!")
                    return

                currency = currency - cost
                records = await select_sql("""SELECT GuildBankBalance FROM GuildSettings WHERE ServerId=%s;""",
                                           (str(dm_tracker[message.author.id]["server_id"]),))
                for row in records:
                    balance = int(row[0])
                new_bank = balance + cost
                result2 = await commit_sql("""UPDATE GuildSettings SET GuildBankBalance=%s WHERE ServerId=%s;""",
                                           (str(new_bank), str(dm_tracker[message.author.id]["server_id"])))
                if result2:
                    pass
                else:
                    await direct_message(message, "Database error!")
                result = await commit_sql(
                    """INSERT INTO Inventory (ServerId, UserId, CharacterId, EquipmentId) VALUES (%s, %s, %s, %s);""", (
                        str(dm_tracker[message.author.id]["server_id"]), str(message.author.id),
                        dm_tracker[message.author.id]["fielddict"][0], dm_tracker[message.author.id]["fielddict"][2]))
                if result:
                    await direct_message(message, char_name + " purchased " + item_name + " for " + str(
                        cost) + " and has " + str(currency) + " left.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> " + char_name + " purchased " + item_name + " for " + str(cost) + " and has " + str(
                            currency) + " left.")
                    result_2 = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s WHERE Id=%s""",
                                                (str(currency), dm_tracker[message.author.id]["fielddict"][0]))
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
                menu = await make_simple_menu(message, "Armory", "ArmoryName")
                response = "Please select from the list of available armories by replying with the ID that is in bold.\n\n**VENDOR LIST**\n\n" + menu
                dm_tracker[message.author.id]["currentfield"] = 1
                await direct_message(message, response)
                return
            elif dm_tracker[message.author.id]["currentfield"] == 1:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                records = await select_sql("""SELECT ArmamentList FROM Armory WHERE Id=%s;""", (message.content,))
                allowed_ids[message.author.id] = []
                response = "Select an armament from the armory by using the ID in bold in your reply.\n\n**ARMORY ITEMS**\n\n"
                for row in records:
                    item_list = row[0].split(',')
                for item in item_list:
                    item_record = await select_sql("SELECT ArmamentName,ArmamentCost FROM Armaments WHERE Id=%s;",
                                                   (item,))
                    for item_obj in item_record:
                        response = response + "**" + item + "** - " + item_obj[0] + " - *" + str(item_obj[1]) + "*\n"
                    allowed_ids[message.author.id].append(item.strip())
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 2
                return


            elif dm_tracker[message.author.id]["currentfield"] == 2:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                records = await select_sql("""SELECT ArmamentName,ArmamentCost FROM Armaments WHERE Id=%s;""",
                                           (dm_tracker[message.author.id]["fielddict"][2],))

                if not records:
                    await direct_message(message, "No item found by that Id")
                    return
                for row in records:
                    item_name = row[0]
                    cost = float(row[1])
                records = await select_sql(
                    """SELECT UserId,Currency,CharacterName,Level,Charisma FROM CharacterProfiles WHERE Id=%s;""",
                    (dm_tracker[message.author.id]["fielddict"][0],))
                if not records:
                    await direct_message(message, "No character found by that ID")
                    return
                for row in records:
                    user_id = row[0]
                    currency = float(row[1])
                    char_name = row[2]
                    level = int(row[3])
                    charisma = int(row[4])
                if int(user_id) != message.author.id:
                    await direct_message(message, "This isn't your character!")
                    return
                haggle = random.randint(1, 10)
                if (haggle <= 2):
                    discount = (cost * (level / charisma))
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> You haggled a discount of " + str(discount) + "!")
                if currency < cost:
                    await direct_message(message, "You don't have enough money to buy this!")
                    return
                currency = currency - cost
                records = await select_sql("""SELECT GuildBankBalance FROM GuildSettings WHERE ServerId=%s;""",
                                           (str(dm_tracker[message.author.id]["server_id"]),))
                for row in records:
                    balance = int(row[0])
                new_bank = balance + cost
                result2 = await commit_sql("""UPDATE GuildSettings SET GuildBankBalance=%s WHERE ServerId=%s;""",
                                           (str(new_bank), str(dm_tracker[message.author.id]["server_id"])))
                if result2:
                    pass
                else:
                    await direct_message(message, "Database error!")
                result = await commit_sql(
                    """INSERT INTO ArmamentInventory (ServerId, UserId, CharacterId, ArmamentId) VALUES (%s, %s, %s, %s);""",
                    (str(dm_tracker[message.author.id]["server_id"]), str(message.author.id),
                     dm_tracker[message.author.id]["fielddict"][0], dm_tracker[message.author.id]["fielddict"][2]))
                if result:
                    await direct_message(message, char_name + " purchased " + item_name + " for " + str(
                        cost) + " and has " + str(currency) + " left.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> " + char_name + " purchased " + item_name + " for " + str(cost) + " and has " + str(
                            currency) + " left.")
                    result_2 = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s WHERE Id=%s""",
                                                (str(currency), dm_tracker[message.author.id]["fielddict"][0]))
                    if not result_2:
                        await reply_message(message, "Database error!")
                        return
                else:
                    await reply_message(message, "Database error!")
                await initialize_dm(message.author.id)
        elif current_command == 'sell':
            if dm_tracker[message.author.id]["currentfield"] == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_menu(message, "Inventory", "Equipment", "EquipmentId", "CharacterId", "EquipmentName",
                                       dm_tracker[message.author.id]["fielddict"][0])
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
                records = await select_sql("""SELECT EquipmentName,EquipmentCost FROM Equipment WHERE Id=%s""",
                                           (dm_tracker[message.author.id]["fielddict"][1],))

                if not records:
                    await reply_message(message, "No item found by that ID!")
                    return
                for row in records:
                    equip_name = row[0]
                    cost = float(row[1])
                records = await select_sql(
                    """SELECT CharacterName,UserId,Currency FROM CharacterProfiles WHERE Id=%s;""",
                    (dm_tracker[message.author.id]["fielddict"][0],))
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
                records = await select_sql("""SELECT GuildBankBalance FROM GuildSettings WHERE ServerId=%s;""",
                                           (str(dm_tracker[message.author.id]["server_id"]),))
                for row in records:
                    balance = int(row[0])
                if cost > balance:
                    await direct_message(message,
                                         "The guild bank doesn't have enough to buy your item! Contact an admin or GM to update the bank balance!")
                    return
                new_bank = balance - cost
                result2 = await commit_sql("""UPDATE GuildSettings SET GuildBankBalance=%s WHERE ServerId=%s;""",
                                           (str(new_bank), str(dm_tracker[message.author.id]["server_id"])))
                if result2:
                    pass
                else:
                    await direct_message(message, "Database error!")
                currency = currency + cost
                result = await commit_sql(
                    """DELETE FROM Inventory WHERE ServerId=%s AND UserId=%s AND CharacterId=%s AND EquipmentId=%s;""",
                    (str(dm_tracker[message.author.id]["server_id"]), str(message.author.id),
                     dm_tracker[message.author.id]["fielddict"][0], item_id))
                if result:
                    await direct_message(message,
                                         char_name + " sold for " + str(cost) + " and has " + str(currency) + " left.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> " + char_name + " sold for " + str(cost) + " and has " + str(currency) + " left.")
                    result_2 = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s WHERE Id=%s""",
                                                (str(currency), dm_tracker[message.author.id]["fielddict"][0]))
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
                menu = await make_menu(message, "ArmamentInventory", "Armaments", "ArmamentId", "CharacterId",
                                       "ArmamentName", dm_tracker[message.author.id]["fielddict"][0])
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
                records = await select_sql("""SELECT ArmamentName,ArmamentCost FROM Armaments WHERE Id=%s""",
                                           (dm_tracker[message.author.id]["fielddict"][1],))

                if not records:
                    await reply_message(message, "No item found by that ID!")
                    return
                for row in records:
                    equip_name = row[0]
                    cost = float(row[1])
                records = await select_sql(
                    """SELECT CharacterName,UserId,Currency FROM CharacterProfiles WHERE Id=%s;""",
                    (dm_tracker[message.author.id]["fielddict"][0],))
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
                records = await select_sql("""SELECT GuildBankBalance FROM GuildSettings WHERE ServerId=%s;""",
                                           (str(dm_tracker[message.author.id]["server_id"]),))
                for row in records:
                    balance = int(row[0])
                if cost > balance:
                    await direct_message(message,
                                         "The guild bank doesn't have enough to buy your item! Contact an admin or GM to update the bank balance!")
                    return
                new_bank = balance - cost
                result2 = await commit_sql("""UPDATE GuildSettings SET GuildBankBalance=%s WHERE ServerId=%s;""",
                                           (str(new_bank), str(dm_tracker[message.author.id]["server_id"])))
                if result2:
                    pass
                else:
                    await direct_message(message, "Database error!")
                currency = currency + cost
                result = await commit_sql(
                    """DELETE FROM ArmamentInventory WHERE ServerId=%s AND UserId=%s AND CharacterId=%s AND ArmamentId=%s;""",
                    (str(dm_tracker[message.author.id]["server_id"]), str(message.author.id),
                     dm_tracker[message.author.id]["fielddict"][0], item_id))
                if result:
                    await direct_message(message,
                                         char_name + " sold for " + str(cost) + " and has " + str(currency) + " left.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> " + char_name + " sold for " + str(cost) + " and has " + str(currency) + " left.")
                    result_2 = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s WHERE Id=%s""",
                                                (str(currency), dm_tracker[message.author.id]["fielddict"][0]))
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
                menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
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
                records = await select_sql("""SELECT CharacterName,Currency FROM CharacterProfiles WHERE Id=%s;""",
                                           (dm_tracker[message.author.id]["fielddict"][0],))
                for row in records:
                    user_name = row[0]
                    user_currency = float(row[1])
                records = await select_sql(
                    """SELECT CharacterName,Currency,UserId FROM CharacterProfiles WHERE Id=%s;""",
                    (dm_tracker[message.author.id]["fielddict"][1],))
                for row in records:
                    target_name = row[0]
                    target_currency = float(row[1])
                    target_id = row[2]
                if sent_amount > user_currency:
                    await direct_message(message, "You don't have enough currency! Send an amount less than " + str(
                        user_currency) + "!")
                    return
                result = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s WHERE Id=%s;""", (
                    str(user_currency - sent_amount), dm_tracker[message.author.id]["fielddict"][0]))
                if result:
                    result_2 = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s WHERE Id=%s;""", (
                        str(target_currency + sent_amount), dm_tracker[message.author.id]["fielddict"][1]))
                    if result_2:
                        await direct_message(message, user_name + " has given " + target_name + " " + str(
                            sent_amount) + " of currency!")
                        await dm_tracker[message.author.id]["commandchannel"].send(
                            ">>> " + user_name + " has sent " + target_name + " " + str(
                                sent_amount) + " of currency, a character played by <@" + target_id + "> .")
                return
        elif current_command == 'buff':
            if current_field == 0:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_menu(message, "BuffSkills", "Buffs", "BuffId", "CharId", "BuffName", message.content)
                response = "Please choose a buff from your character by replying with the ID below.\n\n"
                response = response + menu
                await direct_message(message, response)
                dm_tracker[message.author.id]["currentfield"] = 1
                return
            if current_field == 1:
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
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
                records = await select_sql(
                    """SELECT Id,MinimumLevel,StatMod,Modifier,BuffName,ManaCost FROM Buffs WHERE ServerId=%s AND Id=%s;""",
                    (str(dm_tracker[message.author.id]["server_id"]), buff_id))
                if not records:
                    await reply_message(message, "No buff found by that ID")
                    return
                for row in records:
                    min_level = int(row[1])
                    stat_mod = row[2]
                    mod = int(row[3])
                    buff = row[4]
                    mana_cost = int(row[5])

                records = await select_sql(
                    """SELECT Id FROM BuffSkills WHERE ServerId=%s AND CharId=%s AND BuffId=%s;""",
                    (str(dm_tracker[message.author.id]["server_id"]), char_id, buff_id))
                if not records:
                    await reply_message(message, "That buff is not in your skillset!")
                    return
                for row in records:
                    inventory_id = row[0]
                records = await select_sql("SELECT CharacterName,Level FROM CharacterProfiles WHERE Id=%s",
                                           (str(char_id),))
                for row in records:
                    char_name = row[0]
                    level = int(row[1])
                if level < min_level:
                    await direct_message(message, "You aren't a high enough level to use this buff! Level up!")
                    return

                    
                records = await select_sql(
                    """SELECT CharacterName,""" + stat_mod + """,UserId FROM CharacterProfiles WHERE Id=%s;""",
                    (str(target_id),))
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
                        mass_spar_chars[dm_tracker[message.author.id]["server_id"]][target_user][stat_mod] = stat_to_mod
                        if mana_cost < 1.0:
                            mana_cost = mass_spar_chars[server_id][message.author.id]["MaxMana"] * mana_cost
                        if mass_spar_chars[server_id][message.author.id]["Mana"] < mana_cost:
                            await direct_message(message, "You don't have sufficient mana for this buff!")
                            return
                        mass_spar_chars[dm_tracker[message.author.id]["server_id"]][message.author.id]["Mana"] = \
                            mass_spar_chars[dm_tracker[message.author.id]["server_id"]][message.author.id][
                                "Mana"] - mana_cost
                        mana_left = mass_spar_chars[dm_tracker[message.author.id]["server_id"]][message.author.id][
                            "Mana"]
                elif server_party[dm_tracker[message.author.id]["server_id"]]:
                    if server_party_chars[dm_tracker[message.author.id]["server_id"]][message.author.id]:
                        server_party_chars[dm_tracker[message.author.id]["server_id"]][target_user][
                            stat_mod] = stat_to_mod
                        if mana_cost < 1.0:
                            mana_cost = server_party_chars[dm_tracker[message.author.id]["server_id"]][message.author.id]["Mana"] * mana_cost
                        if server_party_chars[dm_tracker[message.author.id]["server_id"]][message.author.id]["Mana"] < mana_cost:
                            await direct_message(message, "You don't have sufficient mana for this buff!")
                            return
                        server_party_chars[dm_tracker[message.author.id]["server_id"]][message.author.id]["Mana"] = \
                            server_party_chars[dm_tracker[message.author.id]["server_id"]][message.author.id][
                                "Mana"] - mana_cost
                        mana_left = server_party_chars[dm_tracker[message.author.id]["server_id"]][message.author.id][
                            "Mana"]
                response = char_name + " used buff " + buff + " and changed " + stat_mod + " by " + str(
                    mod) + " points to " + str(stat_to_mod) + " on " + target_name + " and has " + str(
                    mana_left) + " mana remaining!"
                await direct_message(message, response)
                await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
                if mass_spar_turn[server_id] > len(mass_spar_chars[server_id]) - 2:
                    mass_spar_turn[server_id] = 0
                else:
                    mass_spar_turn[server_id] = mass_spar_turn[server_id] + 1
                await dm_tracker[message.author.id]["commandchannel"].send(
                    ">>> <@" + str(list(mass_spar[server_id])[mass_spar_turn[server_id]].id) + ">, it is your turn!")
                if mass_spar[server_id][mass_spar_turn[server_id]] == client.user:
                    picker = random.randint(1, 2)
                    if picker == 1:
                        await ai_castspar(message)
                    else:
                        await ai_meleespar(message)
                    mass_spar_turn[server_id] = mass_spar_turn[server_id] = 0
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> <@" + str(
                        list(mass_spar[server_id])[mass_spar_turn[server_id]].id) + ">, it is your turn!")

                await initialize_dm(message.author.id)
                return
        elif current_command == 'useitem1':
            char_id = message.content

            response = "**YOUR INVENTORY**\n\n"
            menu = await make_menu(message, "Inventory", "Equipment", "EquipmentId", "CharacterId", "EquipmentName",
                                   char_id)
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
            records = await select_sql(
                """SELECT Id,MinimumLevel,StatMod,Modifier,EquipmentName,StatusChange,StatusChangedBy,AllowedClasses FROM Equipment WHERE ServerId=%s AND Id=%s;""",
                (str(dm_tracker[message.author.id]["server_id"]), item_id))
            if not records:
                await reply_message(message, "No item found by that ID")
                return
            for row in records:
                min_level = int(row[1])
                stat_mod = str(row[2])
                mod = float(row[3])
                item = row[4]
                status_change = str(row[5])
                status_changed_by = float(row[6])
                allowed_classes = row[7].split(',')

            if allowed_classes[0] != 'All':
                records = await select_sql("""SELECT Class FROM CharacterProfiles WHERE Id=%s;""", (str(char_id),))
                for row in records:
                    char_class = row[0]
                if char_class not in list(allowed_classes) and ("All" not in list(allowed_classes)):
                    await direct_message(message, "You aren't the proper class to use this item!")
                    return

            records = await select_sql(
                """SELECT Id FROM Inventory WHERE ServerId=%s AND CharacterId=%s AND EquipmentId=%s;""",
                (str(dm_tracker[message.author.id]["server_id"]), char_id, item_id))
            if not records:
                await reply_message(message, "That item is not in your inventory!")
                return
            for row in records:
                inventory_id = row[0]
            if stat_mod != 'None':
                records = await select_sql(
                    "SELECT CharacterName,Level," + stat_mod + " FROM CharacterProfiles WHERE Id=%s", (str(char_id),))
            else:
                records = await select_sql("SELECT CharacterName,Level FROM CharacterProfiles WHERE Id=%s",
                                           (str(char_id),))
            for row in records:
                char_name = row[0]
                level = int(row[1])
                if stat_mod != 'None':
                    stat_to_mod = float(row[2])
                else:
                    stat_to_mod = 0.
            if level < min_level:
                await direct_message(message,
                                     "You aren't a high enough level to use this item! Level up or sell it for cash!")
                return

            if stat_mod == 'Health':
                records = await select_sql("""SELECT Health,MaxHealth FROM CharacterProfiles WHERE Id=%s;""",
                                           (str(char_id),))
                for row in records:
                    health = int(row[0])
                    max_health = int(row[1])
                if health + mod >= max_health:
                    mod = max_health - health
            if stat_mod == 'Stamina':
                records = await select_sql("""SELECT Stamina,MaxStamina FROM CharacterProfiles WHERE Id=%s;""",
                                           (str(char_id),))
                for row in records:
                    stamina = int(row[0])
                    max_stamina = int(row[1])
                if stamina + mod >= max_stamina:
                    mod = max_stamina - stamina
            if stat_mod == 'Mana':
                records = await select_sql("""SELECT Mana,MaxMana FROM CharacterProfiles WHERE Id=%s;""",
                                           (str(char_id),))
                for row in records:
                    mana = int(row[0])
                    max_mana = int(row[1])
                if mana + mod >= max_mana:
                    mod = max_mana - mana

            if stat_mod != 'None':
                stat_to_mod = stat_to_mod + mod
            if not mass_spar_event[dm_tracker[message.author.id]["server_id"]] and not server_party[
                dm_tracker[message.author.id]["server_id"]] and stat_mod != 'None':
                result = await commit_sql("""UPDATE CharacterProfiles SET """ + stat_mod + """=%s WHERE Id=%s""",
                                          (str(stat_to_mod), char_id))
                response = char_name + " consumed item " + item + " and changed " + stat_mod + " by " + str(
                    mod) + " points to " + str(stat_to_mod) + "!"
                await direct_message(message, response)
                await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
                await initialize_dm(message.author.id)
                return
            elif not mass_spar_event[dm_tracker[message.author.id]["server_id"]] and not server_party[
                dm_tracker[message.author.id]["server_id"]]:
                records = await select_sql("""SELECT IFNULL(Status,'None') FROM CharacterProfiles WHERE Id=%s;""",
                                           (str(char_id),))
                for row in records:
                    current_status = row[0]
                result = await commit_sql("""UPDATE CharacterProfiles SET Status=%s WHERE Id=%s;""",
                                          (str(status_change + "=" + str(status_changed_by)), str(char_id)))
                result = await commit_sql("""DELETE FROM Inventory WHERE Id=%s;""", (inventory_id,))
                response = "Your character has had a status change to " + status_change + " by the item " + item + "!"
                await direct_message(message, response)
                await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
                await initialize_dm(message.author.id)
                return
            else:
                dm_tracker[message.author.id]["currentcommand"] = "useitem3"
                dm_tracker[message.author.id]["char_id"] = char_id
                dm_tracker[message.author.id]["stat_mod"] = stat_mod
                dm_tracker[message.author.id]["stat_to_mod"] = stat_to_mod
                dm_tracker[message.author.id]["mod"] = mod
                dm_tracker[message.author.id]["item"] = item
                dm_tracker[message.author.id]["status_change"] = status_change
                dm_tracker[message.author.id]["status_changed_by"] = status_changed_by
                dm_tracker[message.author.id]["inventory_id"] = inventory_id
                dm_tracker[message.author.id]["char_name"] = char_name
                char_map = {}
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                response = "Select a target:\n\n"
                for character in mass_spar_chars[server_id]:
                    char_name = mass_spar_chars[server_id][character]["CharName"]
                    char_id = mass_spar_chars[server_id][character]["CharId"]
                    char_map[char_id] = character
                    response = response + "**" + str(char_id) + "** - " + char_name + "\n"
                await direct_message(message, response)
                dm_tracker[message.author.id]["parameters"] = char_map
                return
        elif current_command == 'useitem3':
            char_id = dm_tracker[message.author.id]["char_id"]
            stat_mod = dm_tracker[message.author.id]["stat_mod"]
            char_map = dm_tracker[message.author.id]["parameters"]
            char_name = dm_tracker[message.author.id]["char_name"]
            mod = dm_tracker[message.author.id]["mod"]
            await log_message("Item3 command.")
            if stat_mod != 'None':
                stat_to_mod = dm_tracker[message.author.id]["stat_to_mod"]
            else:
                stat_to_mod = 0
            item = dm_tracker[message.author.id]["item"]
            status_change = dm_tracker[message.author.id]["status_change"]
            status_changed_by = dm_tracker[message.author.id]["status_changed_by"]
            inventory_id = dm_tracker[message.author.id]["inventory_id"]
            if stat_mod != 'None':
                if mass_spar_event[dm_tracker[message.author.id]["server_id"]] and stat_mod != 'None':
                    if mass_spar_chars[dm_tracker[message.author.id]["server_id"]][
                        dm_tracker[message.author.id]["parameters"][int(message.content)]]:
                        mass_spar_chars[dm_tracker[message.author.id]["server_id"]][
                            dm_tracker[message.author.id]["parameters"][int(message.content)]][stat_mod] = stat_to_mod
                if server_party[dm_tracker[message.author.id]["server_id"]] and stat_mod != 'None':
                    if server_party_chars[dm_tracker[message.author.id]["server_id"]][
                        dm_tracker[message.author.id]["parameters"][int(message.content)]]:
                        server_party_chars[dm_tracker[message.author.id]["server_id"]][
                            dm_tracker[message.author.id]["parameters"][int(message.content)]][stat_mod] = stat_to_mod
                result = await commit_sql("""UPDATE CharacterProfiles SET """ + stat_mod + """=%s WHERE Id=%s""",
                                          (str(stat_to_mod), message.content))

                if not result:
                    await reply_message(message, "Database error!")
                    return
                result = await commit_sql("""DELETE FROM Inventory WHERE Id=%s;""", (inventory_id,))
                if not result:
                    await reply_message(message, "Database error!")
                    return
                response = char_name + " used item " + item + " on <@" + str(
                    dm_tracker[message.author.id]["parameters"][
                        int(message.content)]) + "> and changed " + stat_mod + " by " + str(mod) + " points to " + str(
                    stat_to_mod) + "!"
                await direct_message(message, response)
                await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)

            else:
                target_id = dm_tracker[message.author.id]["parameters"][int(message.content)]
                if status_changed_by > -1.0 and status_changed_by < 1.0:
                    if status_change == 'Poison':
                        status_changed_by = float(mass_spar_chars[server_id][target_id]["MaxHealth"]) * status_changed_by
                    if status_change == 'ManaDrain':
                        status_changed_by = float(mass_spar_chars[server_id][target_id]["MaxMana"]) * status_changed_by
                    if status_change == 'StaminaDrain':
                        status_changed_by = status_changed_by * float(mass_spar_chars[server_id][target_id]["MaxStamina"])
                chance_of_success = random.randint(1, 100)
                if chance_of_success >= 30:
                    records = await select_sql("""SELECT IFNULL(Status,'None') FROM CharacterProfiles WHERE Id=%s;""",
                                               (str(message.content),))
                    for row in records:
                        current_status = row[0]
                    result = await commit_sql("""UPDATE CharacterProfiles SET Status=%s WHERE Id=%s;""",
                                              (str(status_change + "=" + str(int(status_changed_by))), str(message.content)))
                    result = await commit_sql("""DELETE FROM Inventory WHERE Id=%s;""", (inventory_id,))
                    response = "<@" + str(dm_tracker[message.author.id]["parameters"][int(
                        message.content)]) + "> has had a status change to " + status_change + " by the item " + item + "!"
                    await direct_message(message, response)
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
                else:
                    result = await commit_sql("""DELETE FROM Inventory WHERE Id=%s;""", (inventory_id,))
                    response = "The item effect failed!"
                    await direct_message(message, response)
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> " + response)
            if mass_spar_turn[server_id] > len(mass_spar_chars[server_id]) - 2:
                mass_spar_turn[server_id] = 0
            else:
                mass_spar_turn[server_id] = mass_spar_turn[server_id] + 1
            await dm_tracker[message.author.id]["commandchannel"].send(
                ">>> <@" + str(list(mass_spar[server_id])[mass_spar_turn[server_id]].id) + ">, it is your turn!")
            if mass_spar[server_id][mass_spar_turn[server_id]] == client.user:
                picker = random.randint(1, 2)
                if picker == 1:
                    await ai_castspar(message)
                else:
                    await ai_meleespar(message)
                mass_spar_turn[server_id] = mass_spar_turn[server_id] = 0
                await dm_tracker[message.author.id]["commandchannel"].send(">>> <@" + str(
                    list(mass_spar[server_id])[mass_spar_turn[server_id]].id) + ">, it is your turn!")
            await initialize_dm(message.author.id)
            return
        if not message.attachments:
            dm_tracker[message.author.id]["fielddict"].append(message.content.strip())
        dm_tracker[message.author.id]["currentfield"] = dm_tracker[message.author.id]["currentfield"] + 1
        if dm_tracker[message.author.id]["currentfield"] < len(field_list):
            #            embed = discord.Embed(title=field_list[current_field + 1], description=current_command)
            #            embed.add_field(name="Next field:",value=dm_tracker[message.author.id]["fieldlist"][dm_tracker[message.author.id]["currentfield"]])
            #            embed.add_field(name="Next field description:",value=dm_tracker[message.author.id]["fieldmeans"][dm_tracker[message.author.id]["currentfield"]])
            #            embed.add_field(name="Last field:", value = dm_tracker[message.author.id]["fieldlist"][dm_tracker[message.author.id]["currentfield"] - 1])
            #            embed.add_field(name="Value set to:", value=message.content.strip())
            embed = discord.Embed(title=field_list[current_field + 1],
                                  description=dm_tracker[message.author.id]["fieldmeans"][
                                      dm_tracker[message.author.id]["currentfield"]])

            embed.add_field(name="Instructions:", value="Please reply with the desired value or *stop* to cancel.")
            if field_list[current_field + 1] == 'Race':
                records = await select_sql("""SELECT Name FROM Races WHERE ServerId=%s;""",
                                           (str(dm_tracker[message.author.id]["server_id"]),))
                if not records:
                    pass
                else:
                    race_list = ""
                    for row in records:
                        race_list = race_list + row[0] + ","
                    embed.add_field(name="Server Races", value=race_list)
            if field_list[current_field + 1] == 'Class':
                records = await select_sql("""SELECT Name FROM Classes WHERE ServerId=%s;""",
                                           (str(dm_tracker[message.author.id]["server_id"]),))
                if not records:
                    pass
                else:
                    class_list = ""
                    for row in records:
                        class_list = class_list + row[0] + ","
                    embed.add_field(name="Server Classes", value=class_list)

            await direct_message(message, " ", embed)
            # await direct_message(message, "Reply received. Next field is " + "**" + dm_tracker[message.author.id]["fieldlist"][dm_tracker[message.author.id]["currentfield"]] + "**\n\nwith a description of " + dm_tracker[message.author.id]["fieldmeans"][dm_tracker[message.author.id]["currentfield"]])
        if current_field > len(field_list) - 2 and current_command != 'randomprofile':
            if current_command == 'newcustomchar':
                new_custom_profile = """INSERT INTO Server""" + str(
                    dm_tracker[message.author.id]["server_id"]) + """(UserId, Name, """
                create_values = """VALUES (%s, """
                create_tuple = (str(message.author.id))
                for key in field_list:
                    new_custom_profile = new_custom_profile + key + """, """
                    create_values = create_values + """%s, """
                    create_tuple = create_tuple + (field_dict[key],)
                new_custom_profile = re.sub(r", , $", "", new_custom_profile) + ")" + re.sub(r", %s, $", "",
                                                                                             create_values) + """);"""
                create_tuple = create_tuple[: len(create_tuple) - 1]
                await log_message("SQL: " + new_custom_profile)
                result = await commit_sql(new_custom_profile, create_tuple)
                if result:
                    await direct_message(message, "Custom character created successfully!")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Custom character successfully created.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'newdefaultchar':
                char_name = field_dict[0]
                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url
                if guild_settings[server_id]["AutoCharApproval"] == 0:
                    create_char_entry = "INSERT INTO UnapprovedCharacterProfiles (ServerId, UserId, "
                else:
                    create_char_entry = "INSERT INTO CharacterProfiles (ServerId, UserId, "
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

                create_char_entry = re.sub(r", $", "", create_char_entry)
                create_char_entry = create_char_entry + ", Attack, Defense, MagicAttack, Health, MaxHealth, Mana, MaxMana, Level, Experience, Stamina, MaxStamina, Agility, Intellect, Charisma,Currency, StatPoints) " + re.sub(
                    r", $", "", create_value) + ", %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1000, 0);"
                attack_bonus = 0
                defense_bonus = 0
                magicattack_bonus = 0
                health_bonus = 0
                mana_bonus = 0
                stamina_bonus = 0
                agility_bonus = 0
                intellect_bonus = 0
                charisma_bonus = 0

                records = await select_sql(
                    """SELECT AttackBonus,DefenseBonus,MagicAttackBonus,HealthBonus,ManaBonus,StaminaBonus,AgilityBonus,IntellectBonus,CharismaBonus FROM Races WHERE Name=%s AND ServerId=%s;""",
                    (field_dict[field_list.index("Race")], str(dm_tracker[message.author.id]["server_id"])))
                if not records:
                    pass
                else:
                    for row in records:
                        attack_bonus = int(row[0])
                        defense_bonus = int(row[1])
                        magicattack_bonus = int(row[2])
                        health_bonus = int(row[3])
                        mana_bonus = int(row[4])
                        stamina_bonus = int(row[5])
                        agility_bonus = int(row[6])
                        intellect_bonus = int(row[7])
                        charisma_bonus = int(row[8])
                await log_message("SQL: " + create_char_entry)
                char_tuple = char_tuple + (str(guild_settings[server_id]["StartingAttack"] + attack_bonus),
                                           str(guild_settings[server_id]["StartingDefense"] + defense_bonus),
                                           str(guild_settings[server_id]["StartingMagicAttack"] + magicattack_bonus),
                                           str(guild_settings[server_id]["StartingHealth"] + health_bonus),
                                           str(guild_settings[server_id]["StartingHealth"] + health_bonus),
                                           str(guild_settings[server_id]["StartingMana"] + mana_bonus),
                                           str(guild_settings[server_id]["StartingMana"] + mana_bonus), '1', '0',
                                           str(guild_settings[server_id]["StartingStamina"] + stamina_bonus),
                                           str(guild_settings[server_id]["StartingStamina"] + stamina_bonus),
                                           str(guild_settings[server_id]["StartingAgility"] + agility_bonus),
                                           str(guild_settings[server_id]["StartingIntellect"] + intellect_bonus),
                                           str(guild_settings[server_id]["StartingCharisma"] + charisma_bonus))

                result = await commit_sql(create_char_entry, char_tuple)
                if result:
                    await direct_message(message, "Character " + char_name + " successfully created.")
                    if guild_settings[server_id]["AutoCharApproval"] == 0:
                        await dm_tracker[message.author.id]["commandchannel"].send(
                            ">>> Character " + char_name + " successfully created.\n\n<@&" + str(
                                guild_settings[dm_tracker[message.author.id]["server_id"]][
                                    "AdminRole"]) + ">, please approve or decline the character with =approve or =deny.")
                    else:
                        await dm_tracker[message.author.id]["commandchannel"].send(
                            ">>> Character " + char_name + " successfully created and ready for play!")
                else:
                    await direct_message(message, "Database error!")

            elif current_command == 'newspell':
                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url
                result = await insert_into(message, "Spells")
                if result:
                    await direct_message(message, "Spell " + field_dict[0] + " successfully created.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Spell " + field_dict[0] + " successfully created.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'newmelee':
                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url
                result = await insert_into(message, "Melee")
                if result:
                    await direct_message(message, "melee " + field_dict[0] + " created successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Melee attack " + field_dict[0] + " successfully created.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'newarmament':
                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url
                result = await insert_into(message, "Armaments")
                if result:
                    await direct_message(message, "Armament " + field_dict[0] + " created successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Armament " + field_dict[0] + " successfully created.")
                else:
                    await direct_message(message, "Database error!")

            elif current_command == 'newrace':
                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url
                result = await insert_into(message, "Races")
                if result:
                    await direct_message(message, "Race " + field_dict[0] + " created successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Race " + field_dict[0] + " successfully created.")
                else:
                    await direct_message(message, "Database error!")

            elif current_command == 'newitem':
                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url
                result = await insert_into(message, "Equipment")
                if result:
                    await direct_message(message, "Item " + field_dict[0] + " created successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Item " + field_dict[0] + " successfully created.")
                else:
                    await direct_message(message, "Database error!")

            elif current_command == 'newclass':
                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url
                result = await insert_into(message, "Classes")
                if result:
                    await direct_message(message, "Class " + field_dict[0] + " created successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Class " + field_dict[0] + " successfully created.")
                else:
                    await direct_message(message, "Database error!")

            elif current_command == 'newbuff':
                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url
                result = await insert_into(message, "Buffs")
                if result:
                    await direct_message(message, "Buff " + field_dict[0] + " created successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Buff " + field_dict[0] + " successfully created.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'newcritter':
                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url
                result = await insert_into(message, "Critters")
                if result:
                    await direct_message(message, "Critter " + field_dict[0] + " successfully created.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Critter " + field_dict[0] + " successfully created.")
                else:
                    await direct_message(message, "Database error!")                    
            elif current_command == 'newmonster':
                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url
                result = await insert_into(message, "Monsters")
                if result:
                    await direct_message(message, "Monster " + field_dict[0] + " successfully created.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Monster " + field_dict[0] + " successfully created.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'newalt':
                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url
                field_dict.append(str(dm_tracker[message.author.id]["parameters"]))
                field_list.append("UsersAllowed")
                result = await insert_into(message, "Alts")
                if result:
                    await direct_message(message, "Alt " + field_dict[0] + " successfully created.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Alt " + field_dict[0] + " successfully created.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'editalt':
                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url

                for field in field_dict:
                    m = re.search(r"(?P<skip>skip)", field, re.IGNORECASE)
                    if m:
                        skip = m.group('skip')
                        field_dict.remove(skip)
                        break
                field_list = field_list[:len(field_list) - 1]
                field_list.append("UsersAllowed")
                field_dict.append(str(dm_tracker[message.author.id]["parameters"]))

                result = await update_table(message, "Alts")
                if result:
                    await direct_message(message, "Alt " + field_dict[0] + " successfully edited.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Alt " + field_dict[0] + " successfully edited.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'newnpc':
                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url
                field_dict.append(str(dm_tracker[message.author.id]["parameters"]))
                result = await insert_into(message, "NonPlayerCharacters")
                if result:
                    await direct_message(message, "NPC " + field_dict[0] + " successfully created.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> NPC " + field_dict[0] + " successfully created.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'editnpc':
                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url

                result = await update_table(message, "NonPlayerCharacters")
                if result:
                    await direct_message(message, "NPC " + field_dict[0] + " successfully edited.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> NPC " + field_dict[0] + " successfully edited.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'editsetup':
                records = await select_sql("""SELECT ServerId FROM GuildSettings WHERE ServerId=%s;""",
                                           (str(dm_tracker[message.author.id]["server_id"]),))
                if not records:
                    result = await commit_sql("""INSERT INTO GuildSettings (ServerId) VALUES (%s);""",
                                              (str(dm_tracker[message.author.id]["server_id"]),))
                    if not result:
                        await direct_message(message, "Database error!")
                        return
                result = await update_table(message, "GuildSettings")
                if result:
                    await direct_message(message, "Guild settings successfully edited.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Guild settings successfully edited.")
                else:
                    await direct_message(message, "Database error!")
                return
            elif current_command == 'editchar':
                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url
                if dm_tracker[message.author.id]["parameters2"] != dm_tracker[message.author.id]["fielddict"][
                    field_list.index('Race')]:
                    records = await select_sql(
                        """SELECT Attack,Defense,MagicAttack,Health,Mana,Stamina,Agility,Intellect,Charisma FROM CharacterProfiles WHERE CharacterName=%s AND ServerId=%s;""",
                        (str(dm_tracker[message.author.id]["parameters"]),
                         str(dm_tracker[message.author.id]["server_id"])))
                    for row in records:
                        current_attack = int(row[0])
                        current_defense = int(row[1])
                        current_magicattack = int(row[2])
                        current_health = int(row[3])
                        current_mana = int(row[4])
                        current_stamina = int(row[5])
                        current_agility = int(row[6])
                        current_intellect = int(row[7])
                        current_charisma = int(row[8])

                    attack_bonus = 0
                    defense_bonus = 0
                    magicattack_bonus = 0
                    health_bonus = 0
                    mana_bonus = 0
                    stamina_bonus = 0
                    agility_bonus = 0
                    intellect_bonus = 0
                    charisma_bonus = 0

                    records = await select_sql(
                        """SELECT AttackBonus,DefenseBonus,MagicAttackBonus,HealthBonus,ManaBonus,StaminaBonus,AgilityBonus,IntellectBonus,CharismaBonus FROM Races WHERE Name=%s AND ServerId=%s;""",
                        (dm_tracker[message.author.id]["parameters2"], str(dm_tracker[message.author.id]["server_id"])))
                    if not records:
                        pass
                    else:
                        for row in records:
                            attack_bonus = int(row[0])
                            defense_bonus = int(row[1])
                            magicattack_bonus = int(row[2])
                            health_bonus = int(row[3])
                            mana_bonus = int(row[4])
                            stamina_bonus = int(row[5])
                            agility_bonus = int(row[6])
                            intellect_bonus = int(row[7])
                            charisma_bonus = int(row[8])
                    records = await select_sql(
                        """SELECT AttackBonus,DefenseBonus,MagicAttackBonus,HealthBonus,ManaBonus,StaminaBonus,AgilityBonus,IntellectBonus,CharismaBonus FROM Races WHERE Name=%s AND ServerId=%s;""",
                        (str(field_dict[field_list.index('Race')]), str(dm_tracker[message.author.id]["server_id"])))
                    if not records:
                        pass
                    else:
                        for row in records:
                            new_attack_bonus = int(row[0])
                            new_defense_bonus = int(row[1])
                            new_magicattack_bonus = int(row[2])
                            new_health_bonus = int(row[3])
                            new_mana_bonus = int(row[4])
                            new_stamina_bonus = int(row[5])
                            new_agility_bonus = int(row[6])
                            new_intellect_bonus = int(row[7])
                            new_charisma_bonus = int(row[8])
                        current_attack = current_attack - attack_bonus + new_attack_bonus
                        current_defense = current_defense - defense_bonus + new_defense_bonus
                        current_magicattack = current_magicattack - magicattack_bonus + new_magicattack_bonus

                        current_health = current_health - health_bonus + new_health_bonus
                        current_mana = current_mana - mana_bonus + new_mana_bonus
                        current_stamina = current_stamina - stamina_bonus + new_stamina_bonus
                        current_agility = current_agility - agility_bonus + new_agility_bonus
                        current_intellect = current_intellect - intellect_bonus + new_intellect_bonus
                        current_charisma = current_charisma - charisma_bonus + new_charisma_bonus
                        result = await commit_sql(
                            """UPDATE CharacterProfiles SET Attack=%s, Defense=%s, MagicAttack=%s, Health=%s, Mana=%s, Stamina=%s, Agility=%s,Intellect=%s,Charisma=%s WHERE CharacterName=%s AND ServerId=%s;""",
                            (str(current_attack), str(current_defense), str(current_magicattack), str(current_health),
                             str(current_mana), str(current_stamina), str(current_agility), str(current_intellect),
                             str(current_charisma), dm_tracker[message.author.id]["parameters"],
                             str(dm_tracker[message.author.id]["server_id"])))
                        await direct_message(message,
                                             "Your race has been changed and statistic bonuses have been modified.")
                result = await update_table(message, "CharacterProfiles")
                if result:
                    await direct_message(message, "Character " + field_dict[0] + " successfully edited.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Character " + field_dict[0] + " successfully edited.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'editinfo':
                dm_tracker[message.author.id]["fielddict"].append(message.content)
                result = await update_table(message, "CharacterProfiles")
                if result:
                    await direct_message(message, "Character " + dm_tracker[message.author.id][
                        "parameters"] + " successfully edited.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Character " + dm_tracker[message.author.id]["parameters"] + " successfully edited.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'editmonster':
                if dm_tracker[message.author.id]["fielddict"][-1] == 'end':
                    dm_tracker[message.author.id]["fielddict"].remove('end')

                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url
                result = await update_table(message, "Monsters")
                if result:
                    await direct_message(message, "Monster " + dm_tracker[message.author.id][
                        "parameters"] + " successfully edited.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Monster " + dm_tracker[message.author.id]["parameters"] + " successfully edited.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'editcritter':
                if dm_tracker[message.author.id]["fielddict"][-1] == 'end':
                    dm_tracker[message.author.id]["fielddict"].remove('end')

                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url
                result = await update_table(message, "Critters")
                if result:
                    await direct_message(message, "Critter " + dm_tracker[message.author.id][
                        "parameters"] + " successfully edited.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Critter " + dm_tracker[message.author.id]["parameters"] + " successfully edited.")
                else:
                    await direct_message(message, "Database error!")                    
            elif current_command == 'edititem':
                if 'end' in list(dm_tracker[message.author.id]["fielddict"]):
                    dm_tracker[message.author.id]["fielddict"].remove('end')
                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url
                result = await update_table(message, "Equipment")
                if result:
                    await direct_message(message, "Item edited successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Item edited successfully.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'editrace':
                if 'end' in list(dm_tracker[message.author.id]["fielddict"]):
                    dm_tracker[message.author.id]["fielddict"].remove('end')
                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url
                result = await update_table(message, "Races")
                if result:
                    await direct_message(message, "Race edited successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Race edited successfully.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'editclass':
                if 'end' in list(dm_tracker[message.author.id]["fielddict"]):
                    dm_tracker[message.author.id]["fielddict"].remove('end')
                result = await update_table(message, "Classes")
                if result:
                    await direct_message(message, "Class edited successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Class edited successfully.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'editarmament':
                if dm_tracker[message.author.id]["fielddict"][-1] == 'end':
                    dm_tracker[message.author.id]["fielddict"].remove('end')

                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url
                result = await update_table(message, "Armaments")
                if result:
                    await direct_message(message, "Armament edited successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Armament edited successfully.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'editbuff':
                if dm_tracker[message.author.id]["fielddict"][-1] == 'end':
                    dm_tracker[message.author.id]["fielddict"].remove('end')
                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url                    
                result = await update_table(message, "Buffs")
                if result:
                    await direct_message(message, "Buff edited successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Buff edited successfully.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'editmelee':
                if dm_tracker[message.author.id]["fielddict"][-1] == 'end':
                    dm_tracker[message.author.id]["fielddict"].remove('end')

                if message.attachments:
                    field_dict[len(field_dict) - 1] = message.attachments[0].url
                result = await update_table(message, "Melee")
                if result:
                    await direct_message(message, "Melee attack " + dm_tracker[message.author.id][
                        "parameters"] + " edited successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Melee attack " + dm_tracker[message.author.id]["parameters"] + " edited successfully.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'editspell':
                if dm_tracker[message.author.id]["fielddict"][-1] == 'end':
                    dm_tracker[message.author.id]["fielddict"].remove('end')

                if message.attachments:
                    field_dict.append(message.attachments[0].url)
                result = await update_table(message, "Spells")
                if result:
                    await direct_message(message, "Spell " + dm_tracker[message.author.id][
                        "parameters"] + " edited successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Spell attack " + dm_tracker[message.author.id]["parameters"] + " edited successfully.")
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
                create_char_entry = re.sub(r", $", "", create_char_entry)
                create_char_entry = create_char_entry + " WHERE ServerId=%s AND CharacterName=%s ;"
                char_tuple = char_tuple + (str(dm_tracker[message.author.id]["server_id"]),)
                char_tuple = char_tuple + (char_name,)
                await log_message("SQL: " + create_char_entry)
                result = await commit_sql(create_char_entry, char_tuple)
                if result:
                    await direct_message(message, "Character " + str(char_name) + " successfully updated.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Character " + str(char_name) + " successfully updated.")
                else:
                    await reply_message(message, "Database error!")
            elif current_command == 'newcustomcommand':
                if dm_tracker[message.author.id]["fielddict"][-1] == 'end':
                    dm_tracker[message.author.id]["fielddict"].remove('end')

                result = await insert_into(message, "CustomCommands")
                if result:
                    custom_commands[server_id][field_dict[0]] = list(field_dict[1].split('|'))
                    await direct_message(message, "Custom command " + field_dict[0] + " created successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Custom command " + field_dict[0] + " created successfully.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'addvendoritem':
                records = await select_sql("SELECT ItemList FROM Vendors WHERE Id=%s;",
                                           (str(dm_tracker[message.author.id]["fielddict"][0]),))
                for row in records:
                    item_list = row[0]
                item_list = item_list + str(dm_tracker[message.author.id]["fielddict"][1])
                result = await commit_sql("UPDATE Vendors SET UserId=%s,ItemList=%s WHERE Id=%s;",
                                          (str(message.author.id), item_list, field_dict[0]))
                if result:
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Vendor updated successfully.")
                    await direct_message(message, "Vendor updated successfully.")
            elif current_command == 'newarmory':
                if dm_tracker[message.author.id]["fielddict"][-1] == 'end':
                    dm_tracker[message.author.id]["fielddict"].remove('end')
                dm_tracker[message.author.id]["fielddict"].remove('')
                if message.attachments:
                    dm_tracker[message.author.id]["fielddict"].append(message.attachments[0].url)
                result = await insert_into(message, "Armory")
                if result:
                    await direct_message(message, "Armory " + field_dict[0] + " updated successfully.")
                    await dm_tracker[message.author.id]["commandchannel"].send(
                        ">>> Armory " + field_dict[0] + " createed successfully.")
                else:
                    await direct_message(message, "Database error!")
            elif current_command == 'addarmoryitem':
                records = await select_sql("SELECT ArmamentList FROM Armory WHERE Id=%s;",
                                           (str(dm_tracker[message.author.id]["fielddict"][0]),))
                for row in records:
                    item_list = row[0]
                item_list = item_list + str(dm_tracker[message.author.id]["fielddict"][1])
                result = await commit_sql("UPDATE Armory SET UserId=%s,ArmamentList=%s WHERE Id=%s;",
                                          (str(message.author.id), item_list, field_dict[0]))
                if result:
                    await dm_tracker[message.author.id]["commandchannel"].send(">>> Armory updated successfully.")
                    await direct_message(message, "Armory updated successfully.")
                return
            await initialize_dm(message.author.id)
        else:
            pass
        return

    elif not message.content.startswith('='):
        active_chars[message.guild.id][message.author.id]
        if active_chars[message.guild.id][message.author.id] is not None:
            get_char = """SELECT CharacterName,PictureLink FROM CharacterProfiles WHERE Id=%s;"""
            records = await select_sql(get_char, (str(active_chars[message.guild.id][message.author.id]),))
            for row in records:
                name = row[0]
                picture = row[1]

            response = message.content
            m = re.findall(r":(.*?):", response)
            if m:
                for emoji in m:
                    emoji_string = str(discord.utils.get(message.guild.emojis, name=emoji))
                    response.replace(emoji, emoji_string)

            temp_webhook = await message.channel.create_webhook(name='Chara-Tron')
            if picture.startswith('http'):
                await temp_webhook.send(content=response, username=name, avatar_url=picture)
            else:
                await temp_webhook.send(content=response, username=name, avatar_url=client.user.avatar_url)
            await message.delete()
            await temp_webhook.delete()
        try:
            alt_aliases[message.guild.id][message.author.id][message.channel.id]
            get_alt = """SELECT UsersAllowed, CharName, PictureLink FROM Alts WHERE ServerId=%s AND Shortcut=%s;"""
            alt_tuple = (str(message.guild.id), alt_aliases[message.guild.id][message.author.id][message.channel.id])
            records = await select_sql(get_alt, alt_tuple)
            for row in records:
                if str(message.author.id) not in row[0]:
                    await reply_message(message,
                                        "<@" + str(message.author.id) + "> is not allowed to use Alt " + row[1] + "!")
                    return
                response = message.content
                m = re.findall(r":(.*?):", response)
                if m:
                    for emoji in m:
                        emoji_string = str(discord.utils.get(message.guild.emojis, name=emoji))
                        response.replace(emoji, emoji_string)

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
        command = command_string[0].replace('=', '')
        parsed_string = message.content.replace("=" + command + " ", "")
        await log_message(
            "Command " + message.content + " called by " + message.author.name + " from server " + message.guild.name + " in channel " + message.channel.name)
        await log_message("Parsed string: " + parsed_string)
        if re.search(command, parsed_string):
            parsed_string = ""

        for comm in custom_commands[message.guild.id]:
            if command == comm:
                pick = random.randint(1, len(custom_commands[message.guild.id][comm]))
                response = str(pick) + " - " + custom_commands[message.guild.id][comm][pick - 1]
                await reply_message(message, response)
                return

        if command == 'createroles':
            roles = ["RPAdministrator", "GameModerator", "NPCUser", "Roleplayer"]

            for role in roles:
                try:
                    new_role = await message.guild.create_role(name=role)
                    if role == "RPAdministrator":
                        result = await commit_sql("""UPDATE GuildSettings SET AdminRole=%s WHERE ServerId=%s;""",
                                                  (str(new_role.id), str(message.guild.id)))
                        guild_settings[message.guild.id]["AdminRole"] = new_role.id
                    if role == "GameModerator":
                        result = await commit_sql(
                            """UPDATE GuildSettings SET GameModeratorRole=%s WHERE ServerId=%s;""",
                            (str(new_role.id), str(message.guild.id)))
                        guild_settings[message.guild.id]["GameModeratorRole"] = new_role.id
                    if role == "NPCUser":
                        result = await commit_sql("""UPDATE GuildSettings SET NPCRole=%s WHERE ServerId=%s;""",
                                                  (str(new_role.id), str(message.guild.id)))
                        guild_settings[message.guild.id]["NPCRole"] = new_role.id
                    if role == "Roleplayer":
                        result = await commit_sql("""UPDATE GuildSettings SET PlayerRole=%s WHERE ServerId=%s;""",
                                                  (str(new_role.id), str(message.guild.id)))
                        guild_settings[message.guild.id]["PlayerRole"] = new_role.id
                except discord.errors.Forbidden:
                    await reply_message(message, "Cannot create roles due to permissions!")
                    return

            await reply_message(message, "Roles created!")
        elif command == 'setadminrole':
            if not message.author.guild_permissions.manage_guild:
                await reply_message(message, "You must have manage server permissions to set the admin role!")
                return
            if not message.role_mentions:
                await reply_message(message, "You didn't mention a role!")
                return

            if len(message.role_mentions) > 1:
                await reply_message(message, "Only one role can be defined as the admin role!")
                return

            role_id = message.role_mentions[0].id
            guild_settings[message.guild.id]["AdminRole"] = role_id
            records = await select_sql("""SELECT AdminRole FROM GuildSettings Where ServerId=%s;""",
                                       (str(message.guild.id),))
            if not records:

                result = await commit_sql("""INSERT INTO GuildSettings (ServerId,AdminRole) Values (%s,%s);""",
                                          (str(message.guild.id), str(role_id)))
                if result:
                    await reply_message(message, "Admin role successfully set!")
                else:
                    await reply_message(message, "Database error!")
                return
            for row in records:
                admin_role = row[0]
            result = await commit_sql("""UPDATE GuildSettings SET AdminRole=%s WHERE ServerId=%s;""",
                                      (str(role_id), str(message.guild.id)))
            if result:
                await reply_message(message, "Admin role successfully set!")
            else:
                await reply_message(message, "Database error!")
        if command == 'help' or command == 'info':
            fields = ""
            if parsed_string == "":
                parsed_string = "Main Help"
            response = "`Welcome to RP Mastermind, the Discord RP Bot Master!`\n\n*Using Help:*\n- Type =info or =help followed by one of these categories to see a list of commands, such as **=info setup.**.\n- To see help for a specific command, type =info command <name>, such as **=info command create**\n- For quick references, use **=cheatsheet** **setup**, **spar**, **player**, **admin**, **gm**, **hunt**, or **encounter**.\n\n**COMMAND CATEGORIES**\n`general`: Not commands, but information on how the bot works.\n`setup`: Commands for getting the bot running.\n`characters`: Commands for managing characters.\n`alts`: Commands for managing Alts.\n`npcs`: Commands for managing NPCs.\n`monsters` Commands for managing monsters.\n`critters`: Commands for managing critters.\n`items`: Commands for managing equipment.\n`encounters`: Commands for managing encounters.\n`melee`: Commands for managing melee attacks.\n`spells`: Commands for managing spells.\n`sparring`: Commands for managing sparring.\n`inventory`: Commands for managing inventory.\n`economy`: Commands for buying, selling and the guild bank.\n`vendors`: Commands for creating, editing and deleting vendors and adding items to them.\n`buffs`: Commands for adding, editing, deleting, and giving and taking away buffs.\n`races`: Commands for managing races.\n`classes`: Commands for managing classes.\n`armaments`: Commands for managing armaments\n`armories`: Commands for managing armories.\n`fun`: Commands for old time RP fun.\n`customcommands`: Commands for creating custom dice responses.\n`credits`: Those who helped develop and test the bot.\n\nMore advanced documentation can be found on the wiki: http://rpmm.wikidot.com/\n\nSupport server: https://discord.gg/QRWem3w"
            if parsed_string == 'setup':
                response = "**SETUP COMMANDS**\n\n\n\n`=createroles`,`=setadminrole`,`=newsetup`,`=editsetup`,`=setgmrole`,`=setnpcrole`,`=listroles`,`=addadmin`, `=addnpcuser`,`=addplayer`,`=addgm`,`=deleteadmin`,`=deletenpcuser`,`=deleteplayer`,`=deletegm`,`=resetserver`,`=invite`,`=setxpchannel`,`=setcritterchannel`"

            elif parsed_string == 'characters':
                response = "**CHARACTER COMMANDS**\n\n\n\n`=create`,`=editstats`,`=change`,`=remove`,`=skills`,`=pending`,`=profile`,`=listprofiles` ,`=addstatpoints`,`=givestatpoints`,`=approve`,`=deny`, `=armaments`,`=equipped`,`=randomprofile`,`=givexp`,`=active`,`=inactive`,`=daily`"


            elif parsed_string == 'alts':
                response = "**Alt COMMANDS**\n\n`=newalt`,`=postalt`,`=editalt`,`=deletealt`,`=listalts`,`=setalt`,`=unsetalt`"
            elif parsed_string == 'npcs':
                response = "**NPC COMMANDS**\n\n`=newpc`,`=postnpc`,`=editnpc`,`=deletenpc` ,`=listnpcs`"
            elif parsed_string == 'monsters':
                response = "**MONSTER COMMANDS**\n\n`=newmonster`,`=editmonster`,`=deletemonster`,`=listmonsters`,`=listmonster`"

            elif parsed_string == 'items':
                response = "**ITEM COMMANDS**\n\n`=newitem`,`=edititem`,`=deleteitem`,`=listitems`,`=giveitem`,`=takeitem`,`=listitem`,`=listitems`"
            elif parsed_string == 'critters':
                response = "**CRITTER COMMANDS**\n\n`=newcritter`,`=editcritter`,`=deletecritter`,`=listcritters`,`=setcritterchannel`,`=listcritter`"
            elif parsed_string == 'encounters':
                response = "**ENCOUNTER COMMANDS**\n\n`=monster1`,`=disbandparty`,`=monster2`,`=monster3`,`=monsterattack`,`=castmonster`,`=meleemonster`,`=weaponmonster`,`=abortencounter` ,`=pass`"

            elif parsed_string == 'melee':
                response = "**MELEE COMMANDS**\n\n`=newmelee`,`=editmelee`,`=deletemelee`,`=listmelees`,`=listmelee`,`=givemelee`,`=takemelee`"

            elif parsed_string == 'spells':
                response = "**SPELL COMMANDS**\n\n`=newspell`,`=editspell`,`=deletespell`,`=listspells`,`=listspell`,`=givespell`,`=takespell`"

            elif parsed_string == 'sparring':
                response = "**SPARRING COMMANDS**\n\n`=spar1`,`=yes`,`=no` ,`=spar2`,`=spar3`,`=meleespar` ,`=castspar`,`=weaponspar`,`=summonspar`,`=leavespar`,`=mysparstats`,`=randomspar`"
            elif parsed_string == 'summons':
                response = "**SUMMONING COMMANDS**\n\n`=givesummon`,`=takesummon`,`=summons`"
            elif parsed_string == 'inventory':
                response = "**INVENTORY COMMANDS**\n\n`=inventory`,`=useitem`"
            elif parsed_string == 'economy':
                response = "**ECONOMY COMMANDS**\n\n`=givecurrency`,`=buy`,`=sell`,`=trade`,`=sendcurrency`,`=buyarms`,`=sellarms`,`=tradearms`,`=setbankbalance`,`=wallet`"
            elif parsed_string == 'vendors':
                response = "**VENDOR COMMANDS**\n\n`=newvendor`,`=addvendoritem`,`=deletevendor` ,`=deletevendoritem` ,`=listvendors`,`=listvendor`"
            elif parsed_string == 'credits':
                response = "**CREDITS**\n\nRP Mastermind is the result of blood, sweat and tears by many people.\n\n*Developer and Architect*: The Midnight#1984\n*Critter data and QA*: SantaSmurf\n*QA and Feature Input*: Zeldisaster\n*Initial Testing*: Smurfette"
            elif parsed_string == 'fun':
                response = "**FUN AND UTILITY COMMANDS**\n\n`=lurk`,`=ooc` ,`=randomooc`,`=roll`,`=me`,`=newscene`,`=endscene` ,`=pause` ,`=unpause`,`=postnarr`,`=enter`,`=exit`"
            elif parsed_string == 'general':
                response = "**GENERAL INFO**\n\nWelcome to the RP Mastermind, a multipurpose Discord bot for managing chat-based or gaming server roleplaying. RP Mastermind supports the following features:\n\n• Character profiles\n• Character statistics such as melee and spell attack power, mana, stamina and agility\n• Monsters and encounters\n• Melee attacks for characters\n• Spells for characters\n• Buffs for characters\n• Armaments and armories, and equippable armaments with status modifiers.\n• Items and inventory\n• Trading items and currency between characters\n• Vendors and buying and selling from them\n• Guild bank\n• Experience and leveling\n• Mass sparring between characters\n• Dice rolls\n• OOC bracketing\n• Non-player character posting (NPCs)\n• Character application and approval\n• Custom server settings for leveling and restoration during encounters\n• Four levels of access and control\n• Random OOC fun commands\n• Option for loading default items, spells, melee attacks, vendors and monsters\n\n**ROLES**\n\n`Admin:` The admin can run all commands of the bot, such as adding and deleting spells or items. The server owner must set the admin role.\n\n`Game Moderator:` The game moderator is able to start random encounters, add or delete monsters, give money, and give items.\n\n`NPC Manager:` The NPC manager is able to create, edit and delete Alts and NPCs.\n\n`Player:` A player is able to add, edit, and delete their character profile, and play as their character, and post as Alts if allowed, and buy and sell items, and trade with other players. An admin role user must approve new characters.\n\n**LEVELING**\n\nLeveling is granted by gaining experience. Experience is gained by random encounters, sparring, or granted by a game moderator. A new level is achieved when experience totals twenty times the current level (default).\n\nFor more information, see the wiki: https://github.com/themidnight12am/rpmastermind/wiki#general-information\n\n"
            elif parsed_string == 'buffs':
                response = "**BUFF COMMANDS**\n\n`=newbuff`,`=editbuff`,`=deletebuff`,`=givebuff`,`=takebuff`,`=buff`,`=listbuffs`,`=listbuff`"

            elif parsed_string == 'armaments':
                response = "**ARMAMENTS COMMANDS**\n\n`=newarmament`,`=editarmament`,`=deletearmament`,`=givearmament`,`=takearmament`,`=equip`,`=unequip`"

            elif parsed_string == 'armories':
                response = "**ARMORY COMMANDS**\n\n`=newarmory`,`=deletearmory`,`=addarmoryitem`,`=deletearmoryitem`"

            elif parsed_string == 'races':
                response = "**RACE COMMANDS**\n\n`=newrace`,`=editrace`,`=deleterace`,`=listraces`,`=listrace`"
            elif parsed_string == 'classes':
                response = "**CLASS COMMANDS**\n\n`=newclass`,`=editclass`,`=deleteclass`,`=listclasses`,`=listclass`"
            elif parsed_string.startswith('command'):
                help_command = parsed_string.replace('command ', '')

                command_does = " "
                role_needed = " "
                params = " "
                example = " "

                if not help_command:
                    await reply_message(message, "No command specified!")
                    return

                if help_command == 'createroles':
                    command_does = "Creates the four default roles required for the bot and assigns them to the server settings. The roles are called RPAdministrator, GameModerator, NPCUser and Roleplayer."
                    role_needed = "Manage Server Permissions"
                    params = "None"
                    example = "=createroles"
                elif help_command == 'active':
                    command_does = "Set your active character for XP/currency and posting as an alt."
                    role_needed = "Player"
                    params = "Character Name"
                    example = "=active Smokey the Bear"
                elif help_command == 'inactive':
                    command_does = "Clear your current active character. You will not post as the alt and XP/currency will randomize among your characters."
                    role_needed = "=inactive"
                    params = "None"
                    example = "=createroles"
                elif help_command == 'setadminrole':
                    command_does = "Sets the bot administrator role for the bot to an existing role."
                    role_needed = "Manage Server Permissions"
                    params = "Discord role mention"
                    example = "=setadminrole @RPAdministrator"
                elif help_command == 'setgmrole':
                    command_does = "Set the game moderator role for the bot to an existing role."
                    role_needed = "Admin"
                    params = "Discord role mention"
                    example = "=setgmrole @GameModerator"
                elif help_command == 'setnpcrole':
                    command_does = "Set the NPC role for the bot to an existing role."
                    params = "Discord role mention"
                    role_needed = "Admin"
                    example = "=setnpcrole @NPCUser"
                elif help_command == 'newsetup':
                    command_does = "Change the default server settings for RP, such as the bank balance, starting health, ratios for XP/leveling, etc. The bot will DM you for each field."
                    role_needed = "Admin"
                    params = "None"
                    example = "=newsetup"
                elif help_command == 'inventory':
                    command_does = "Show the item inventory of the named character."
                    role_needed = "None"
                    params = "Character Name"
                    example = "=inventory Richard Stallman"
                elif help_command == 'listroles':
                    command_does = "Show the names of the bot roles currently set on this server."
                    role_needed = "None"
                    params = "None"
                    example = "=listroles"
                elif help_command == 'addadmin':
                    command_does = "Add mentioned users to the bot administrator role."
                    role_needed = "Manage server permissions"
                    params = "Discord user mentions"
                    example = "=addadmin @Super RP Guy @Super RP Gal"
                elif help_command == 'deleteadmin':
                    command_does = "Remove mentioned users from the bot administrator role"
                    role_needed = "Manage Server Permissions"
                    params = "Discord user mentions"
                    example = "=deleteadmin @Disgraced RPer @Bad Admin"
                elif help_command == 'addgm':
                    command_does = "Add mentioned users to the bot game moderator role."
                    role_needed = "Admin"
                    params = "Discord user mentions"
                    example = "=addgm @Super RP Guy @Super RP Gal"
                elif help_command == 'daily':
                    command_does = "Earn daily XP and currency rewards. Resets at midnight central US time."
                    role_needed = "Player"
                    params = "None"
                    example = "=daily"
                elif help_command == 'deletegm':
                    command_does = "Remove mentioned users from the bot game moderator role"
                    role_needed = "Admin"
                    params = "Discord user mentions"
                    example = "=deletegm @Disgraced RPer @Lousy GM"
                elif help_command == 'addplayer':
                    command_does = "Add mentioned uses to the bot player role."
                    role_needed = "Admin"
                    params = "Discord user mentions"
                    example = "=addplayer @New RP Dude @Veteran AOL Person"
                elif help_command == 'deleteplayer':
                    role_needed = "Admin"
                    command_does = "Remove mentioned users from the bot player role"
                    params = "Discord user mentions"
                    example = "=deleteplayer @Retired RPer @GodModer"
                elif help_command == 'addnpcuser':
                    command_does = "Add mentioned players to the NPC user role."
                    role_needed = "Admin"
                    params = "Discord user mentions"
                    example = "=addnpcuser @Likes to Play Bartenders @Has 200 Characters"
                elif help_command == 'wallet':
                    command_does = "Show a character's currency balance."
                    params = "Character Name"
                    role_needed = "None"
                    example = "=wallet Richie Rich"
                elif help_command == 'randomspar':
                    command_does = "Generate a random character of the specified level and initiate a two-character spar against the bot. The AI character will select a random spell or melee from the server list, and its stats do not regenerate."
                    role_needed = "Player"
                    params = "Level of random character"
                    example = "=randomspar 10"

                elif help_command == 'deletenpcuser':
                    command_does = "Remove mentioned players from the NPC user role"
                    role_needed = "Admin"
                    params = "Discord user mentions"
                    example = "=deletenpcuser @Doesnt Need NPCs @Posted as the barista in NSFW"
                elif help_command == 'listsetup':
                    command_does = "List all current server settings for RP."
                    role_needed = "None"
                    params = "None"
                    example = "=listsetup"
                elif help_command == 'resetserver':
                    role_needed = "Manage Server Permissions"
                    command_does = "Clears EVERYTHING from the server. There will be no characters, spells, items, etc left, and the settings will revert to default."
                    params = "None"
                    example = "=resetserver"
                elif help_command == 'loaddefault':
                    command_does = "Load some basic melee attacks, spells, buffs, items, armaments, and monsters into the server."
                    role_needed = "Admin"
                    params = "None"
                    example = "=loaddefault"
                elif help_command == 'randomprofile':
                    command_does = "Generate a randomized character for approval. Useful for players who cannot decide, for creating choices for a new server, or experimentation for ideas. The height and weight are arbitrary and may not make logical sense, so edit them after creation if needed."
                    role_needed = "Player"
                    params = "None"
                    example = "=randomprofile"
                elif help_command == 'summons':
                    command_does = "List the monsters that can be summoned by a character."
                    role_needed = "Player"
                    params = "Character Name"
                    example = "=summons High Priest Zuul"
                elif help_command == 'givesummon':
                    command_does = "Give a character a monster to summon."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=givesummon"
                elif help_command == 'takesummon':
                    command_does = "Take a monster summon away from a character."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=takesummon"
                elif help_command == 'summonspar':
                    command_does = "Attack another character with a monster during a spar. Costs 20% of total mana."
                    role_needed = "Player"
                    params = "None"
                    example = "=summonspar"
                elif help_command == 'create':
                    command_does = "Starts a new character application using DMs."
                    role_needed = "Player"
                    params = "None"
                    example = "=create"
                elif help_command == 'change':
                    command_does = "Edit an existing, approved character using DMs."
                    role_needed = "Player"
                    params = "Character Name"
                    example = "=change Vlad Dracul"
                elif help_command == 'remove':
                    command_does = "Deletes a character from the server."
                    role_needed = "Player, Admin"
                    params = "Character Name"
                    example = "=remove Chad Wickdick"
                elif help_command == 'approve':
                    command_does = "Approves a character application and moves the profile to the active list."
                    role_needed = "Admin"
                    params = "None"
                    example = "=approve"
                elif help_command == 'deny':
                    command_does = "Denies a character application and alternately deletes the application. A reason should be provided in DMs with the bot."
                    role_needed = "Admin"
                    params = "None"
                    example = "=deny"

                elif help_command == 'pending':
                    command_does = "View an unapproved character's profile application."
                    role_needed = "None"
                    params = "Character Name"
                    example = "=pending Joey Hopeful"
                elif help_command == 'mysparstats':
                    command_does = "View your character's current statistics during a spar."
                    role_needed = "Player"
                    params = "None"
                    example = "=mysparstats"

                elif help_command == 'profile':
                    command_does = "View a character's entire approved profile."
                    role_needed = "None"
                    params = "Character Name"
                    example = "=profile Benjamin Dover"
                elif help_command == 'listprofiles':
                    command_does = "List all characters currently on the server."
                    role_needed = "None"
                    params = "None"
                    example = "=listprofiles"
                elif help_command == 'showpending':
                    command_does = "List applied but not approved characters on the server."
                    role_needed = "None"
                    params = "None"
                    example = "=showpending"
                elif help_command == 'skills':
                    command_does = "List the character's buffs, melee attacks and spells."
                    params = "Character Name"
                    role_needed = "None"
                    example = "=skills Merlin"
                elif help_command == 'addstatpoints':
                    command_does = "Start a DM command to add earned stat points to a character's statistics after leveling."
                    role_needed = "Player"
                    params = "None"
                    example = "=addstatpoints"
                elif help_command == 'givestatpoints':
                    command_does = "Grant stat points to a player's character for a reason that isn't automatic to the bot. Done via DMs."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=givestatpoints"
                elif help_command == 'armaments':
                    command_does = "List the armaments currently in a character's inventory."
                    role_needed = "None"
                    params = "Character Name"
                    example = "=armaments Valerie Firebow"
                elif help_command == 'equipped':
                    command_does = "Show a character's current slots and their equipped armaments."
                    role_needed = "None"
                    params = "Character Name"
                    example = "=equipped Jason Bourne"
                elif help_command == 'newalt':
                    command_does = "Create a new alt using the DM system (character name, picture link, shortcut)."
                    role_needed = "NPC User"
                    params = "None"
                    example = "=newalt"
                elif help_command == 'editalt':
                    command_does = "Edit an existing alt using the DM system."
                    role_needed = "NPC User"
                    params = "NPC Name"
                    example = "=editalt Joe Schmoe"
                elif help_command == 'deletealt':
                    command_does = "Delete an alt from the server."
                    role_needed = "NPC User"
                    params = "NPC Name"
                    example = "=deletealt King Arthur"
                elif help_command == 'setalt':
                    command_does = "Set your name to post as an alt every post in a channel until unset."
                    role_needed = "NPC User"
                    params = "Shortcut"
                    example = "=setalt joe"
                elif help_command == 'unsetalt':
                    command_does = "Unset the alt default for yourself in a channel."
                    role_needed = "NPC User"
                    params = "None"
                    example = "=unsetalt"
                elif help_command == 'postalt':
                    command_does = "Post as the alt instead of as your name."
                    role_needed = "NPC User"
                    params = "shortcut -post-"
                    example = "=postalt mallory She stepped forward and took a fighting stance, daring him to step out of the shadows."
                elif help_command == 'newnpc':
                    command_does = "Create a new npc using the DM system (character name, picture link, shortcut)."
                    role_needed = "NPC User"
                    params = "None"
                    example = "=newnpc"
                elif help_command == 'editnpc':
                    command_does = "Edit an existing npc using the DM system."
                    role_needed = "NPC User"
                    params = "NPC Name"
                    example = "=editnpc Joe Schmoe"
                elif help_command == 'deletenpc':
                    command_does = "Delete an npc from the server."
                    role_needed = "NPC User"
                    params = "NPC Name"
                    example = "=deletenpc King Arthur"
                elif help_command == 'setnpc':
                    command_does = "Set your name to post as an npc every post in a channel until unset."
                    role_needed = "NPC User"
                    params = "Shortcut"
                    example = "=setnpc joe"
                elif help_command == 'unsetnpc':
                    command_does = "Unset the npc default for yourself in a channel."
                    role_needed = "NPC User"
                    params = "None"
                    example = "=unsetnpc"
                elif help_command == 'postnpc':
                    command_does = "Post as the npc instead of as your name."
                    role_needed = "NPC User"
                    params = "shortcut -post-"
                    example = "=postnpc ace The smell of the flatulence was so overpowering that he immediately puked."
                elif help_command == 'newcritter':
                    command_does = "Create a new critter for the server using the DM system."
                    role_needed = "Admin"
                    params = "None"
                    example = "=newcritter"
                elif help_command == 'editcritter':
                    command_does = "Edit an existing critter on the server."
                    role_needed = "Admin"
                    params = "Critter Name"
                    example = "=editcritter Rodent of Unusual Size"
                elif help_command == 'deletecritter':
                    command_does = "Delete an existing critter from the server."
                    role_needed = "Admin"
                    params = "Critter Name"
                    example = "=deletecritter Killer Rabbit"
                elif help_command == 'listcritters':
                    command_does = "List all critters on the server."
                    role_needed = "None"
                    params = "None"
                    example = "=listcritters"
                elif help_command == 'listcritter':
                    command_does = "Show details for a critter."
                    role_needed = "None"
                    params = "Critter Name"
                    example = "=listcritter Little Bunny FooFoo"                    
                elif help_command == 'newmonster':
                    command_does = "Create a new monster for the server using the DM system."
                    role_needed = "Admin"
                    params = "None"
                    example = "=newmonster"
                elif help_command == 'editmonster':
                    command_does = "Edit an existing monster on the server."
                    role_needed = "Admin"
                    params = "Monster Name"
                    example = "=editmonster Jabberwocky"
                elif help_command == 'deletemonster':
                    command_does = "Delete an existing monster from the server."
                    role_needed = "Admin"
                    params = "Monster Name"
                    example = "=deletemonster Anal-dwelling butt monkey"
                elif help_command == 'listmonsters':
                    command_does = "List all monsters on the server."
                    role_needed = "None"
                    params = "None"
                    example = "=listmonsters"
                elif help_command == 'listmonster':
                    command_does = "Show details for a monster."
                    role_needed = "None"
                    params = "Monster Name"
                    example = "=listmonster Balrog"
                elif help_command == 'newitem':
                    command_does = "Create a new item using the DM system."
                    role_needed = "Admin"
                    params = "None"
                    example = "=newitem"
                elif help_command == 'edititem':
                    command_does = "Edit an existing item on the server."
                    role_needed = "Admin"
                    params = "Item Name"
                    example = "=edititem Minor Stamina Potion"
                elif help_command == 'deleteitem':
                    command_does = "Delete an item from the server."
                    role_needed = "Admin"
                    params = "Item Name"
                    example = "=deleteitem Overpowered Healing Potion"
                elif help_command == 'listitems':
                    command_does = "List all items on the server."
                    role_needed = "None"
                    params = "None"
                    example = "=listitems"
                elif help_command == 'listitem':
                    command_does = "Show data for an item."
                    role_needed = "None"
                    params = "Item Name"
                    example = "=listitem Apple Cider"
                elif help_command == 'newrace':
                    command_does = "Create a new race using the DM system."
                    role_needed = "Admin"
                    params = "None"
                    example = "=newrace"
                elif help_command == 'editrace':
                    command_does = "Edit an existing race on the server."
                    role_needed = "Admin"
                    params = "Race Name"
                    example = "=editrace Vampire"
                elif help_command == 'deleterace':
                    command_does = "Delete an race from the server."
                    role_needed = "Admin"
                    params = "Race Name"
                    example = "=deleterace Martian"
                elif help_command == 'listraces':
                    command_does = "List all races on the server."
                    role_needed = "None"
                    params = "None"
                    example = "=listraces"
                elif help_command == 'listrace':
                    command_does = "Show data for an race."
                    role_needed = "None"
                    params = "Race Name"
                    example = "=listrace Orc"
                elif help_command == 'newclass':
                    command_does = "Create a new class using the DM system."
                    role_needed = "Admin"
                    params = "None"
                    example = "=newclass"
                elif help_command == 'editclass':
                    command_does = "Edit an existing class on the server."
                    role_needed = "Admin"
                    params = "Class Name"
                    example = "=editclass Warrior"
                elif help_command == 'deleteclass':
                    command_does = "Delete an class from the server."
                    role_needed = "Admin"
                    params = "Class Name"
                    example = "=deleteclass Death Knight"
                elif help_command == 'listclasses':
                    command_does = "List all classes on the server."
                    role_needed = "None"
                    params = "None"
                    example = "=listclasss"
                elif help_command == 'listclass':
                    command_does = "Show data for an class."
                    role_needed = "None"
                    params = "Class Name"
                    example = "=listclass Mage"
                elif help_command == 'giveitem':
                    command_does = "Grant an item to a character without having the character purchase it. The item and character are picked from a list in DMs."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=giveitem"
                elif help_command == 'takeitem':
                    command_does = "Take an item away from a character and result in no currency for losing it."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=takeitem"
                elif help_command == 'editstats':
                    command_does = "Edit the statistics of a character (Attack, Health, etc). When a character levels, the statistics tied to level reset. The character is selected and stats edited in DMs."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=editstats"
                elif help_command == 'monster1':
                    command_does = "Create a new monster encounter party with the mentioned users, or a new monster encounter against your own character."
                    role_needed = "Game Moderator/Player"
                    params = "Discord user mentions/None"
                    example = "=monster1 @Tank @Healer @DPS @Noob/=monster1"
                elif help_command == 'disbandparty':
                    command_does = "Disband a server party entirely."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=disbandparty"
                elif help_command == 'monster2':
                    command_does = "Set your character for the monster encounter. The bot will DM you a list of characters."
                    role_needed = "Player"
                    params = "None"
                    example = "=monster2"
                elif help_command == 'monster3':
                    command_does = "Initiates a monster encounter with the monster selected in DMs, then prompts the first player for their move."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=monster3"
                elif help_command == 'monsterattack':
                    command_does = "Attacks a random party character with the monster's attack power, multiplied by a random number between one and five."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=monsterattack"
                elif help_command == 'castmonster':
                    command_does = "Use a spell to attack the monster. You must have sufficient mana and be the minimum level to cast it. The spell is selected in DMs."
                    role_needed = "Player"
                    params = "None"
                    example = "=castmonster"
                elif help_command == 'meleemonster':
                    command_does = "Uses a melee attack to damage the monster. You must have sufficient stamina and be the minimum level to attack with it. The attack is selected in DMs."
                    role_needed = "Player"
                    params = "None"
                    example = "=meleemonster"
                elif help_command == 'weaponmonster':
                    command_does = "Use one of the hand-equipped armaments to attack a monster. No stamina or mana required, but the minimum level must be met. The armament will be selected in DMs."
                    role_needed = "Player"
                    params = "None"
                    example = "=weaponmonster"
                elif help_command == 'pass':
                    command_does = "Pass on your turn in the encounter. Useful if you are out of mana, stamina, have nothing equipped, and no items to recover. Let's hope your auto-heal is fast or you have others in the party!"
                    role_needed = "Player"
                    params = "None"
                    example = "=pass"
                elif help_command == 'abortencounter':
                    command_does = "Stop the encounter without disbanding the party, leaving all item and buff effects behind and restoring all stats, but canceling experience and currency."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=abortencounter"
                elif help_command == 'newmelee':
                    command_does = "Create a new melee attack using the DM system."
                    role_needed = "Admin"
                    params = "None"
                    example = "=newmelee"
                elif help_command == 'editmelee':
                    command_does = "Edit an existing melee using the DM system."
                    role_needed = "Admin"
                    params = "Melee Attack Name"
                    example = "=editmelee Punch"
                elif help_command == 'deletemelee':
                    command_does = "Delete a melee attack from the server."
                    role_needed = "Admin"
                    params = "Melee Attack Name"
                    example = "=deletemelee Five Finger Death Punch"
                elif help_command == 'listmelees':
                    command_does = "List all melee attacks on the server."
                    role_needed = "None"
                    params = "None"
                    example = "=listmelees"
                elif help_command == 'listmelee':
                    command_does = "List data for a named melee attack."
                    role_needed = "None"
                    params = "Melee Attack Name"
                    example = "=listmelee Five Point Palm Exploding Heart Technique"
                elif help_command == 'givemelee':
                    command_does = "Grant a melee attack to a character using the DM system."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=givemelee"
                elif help_command == 'takemelee':
                    command_does = "Take a melee attack away from a character using DMs."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=takemelee"
                elif help_command == 'changeowner':
                    command_does = "Change the owner player of a character. Useful for continuing a player who has left the server or editing a character profile as an admin. Character and new owner are selected in DMs."
                    role_needed = "Admin"
                    params = "None"
                    example = "=changeowner"
                elif help_command == 'newspell':
                    command_does = "Create a new spell using the DM system."
                    role_needed = "Admin"
                    params = "None"
                    example = "=newspell"
                elif help_command == 'editspell':
                    command_does = "Edit an existing spell using the DM system."
                    role_needed = "Admin"
                    params = "Spell Name"
                    example = "=editspell Fireball"
                elif help_command == 'deletespell':
                    command_does = "Delete a spell from the server."
                    role_needed = "Admin"
                    params = "Spell Name"
                    example = "=deletespell Magic Missile"
                elif help_command == 'listspells':
                    command_does = "List all spells on the server."
                    role_needed = "None"
                    params = "None"
                    example = "=listspells"
                elif help_command == 'listspell':
                    command_does = "List data for a named spell."
                    role_needed = "None"
                    params = "Spell Name"
                    example = "=listspell Kamehameha"
                elif help_command == 'givespell':
                    command_does = "Grant a spell to a character using the DM system."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=givespell"
                elif help_command == 'takespell':
                    command_does = "Take a spell away from a character using DMs."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=takespell"
                elif help_command == 'newbuff':
                    command_does = "Create a new buff using the DM system."
                    role_needed = "Admin"
                    params = "None"
                    example = "=newbuff"
                elif help_command == 'editbuff':
                    command_does = "Edit an existing buff using the DM system."
                    role_needed = "Admin"
                    params = "Buff Name"
                    example = "=editbuff Healing Hands"
                elif help_command == 'deletebuff':
                    command_does = "Delete a buff from the server."
                    role_needed = "Admin"
                    params = "Buff Name"
                    example = "=deletebuff Overpowered Instant Heal"
                elif help_command == 'listbuffs':
                    command_does = "List all buffs on the server."
                    role_needed = "None"
                    params = "None"
                    example = "=listbuffs"
                elif help_command == 'listbuff':
                    command_does = "List data for a named buff."
                    role_needed = "None"
                    params = "Buff Name"
                    example = "=listbuff Berserk"
                elif help_command == 'givebuff':
                    command_does = "Grant a buff to a character using the DM system."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=givebuff"
                elif help_command == 'takebuff':
                    command_does = "Take a buff away from a character using DMs."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=takebuff"
                elif help_command == 'spar1':
                    command_does = "Creates a new spar group with the mentioned players. Players may respond with =yes to join the spar or =no to leave the group."
                    role_needed = "Player"
                    params = "Discord Mentions"
                    example = "=spar1 @Me @My Biggest Rival @Some Guy Who Needs Experience"
                elif help_command == 'yes':
                    command_does = "Confirm participation in a spar group you were mentioned in."
                    role_needed = "Player"
                    params = "None"
                    example = "=yes"
                elif help_command == 'no':
                    command_does = "Decline the spar invitation and remove yourself from the spar group."
                    role_needed = "Player"
                    params = "None"
                    example = "=no"
                elif help_command == 'spar2':
                    command_does = "Set your character for the mass spar, using the DM system."
                    role_needed = "Player"
                    params = "None"
                    example = "=spar2"
                elif help_command == 'spar3':
                    command_does = "Initiate the mass spar and indicate who gets first strike."
                    role_needed = "Player"
                    params = "None"
                    example = "=spar3"
                elif help_command == 'meleespar':
                    command_does = "Attack any character with a melee attack. The bot will DM you to select a melee attack and target character."
                    role_needed = "Player"
                    params = "None"
                    example = "=meleespar"
                elif help_command == 'castspar':
                    command_does = "Attack any character with a spell. The bot will DM you to select a spell and target character."
                    role_needed = "Player"
                    params = "None"
                    example = "=castspar"
                elif help_command == 'weaponspar':
                    command_does = "Attack any character with an armament.  The bot will DM you to select an armament and target character."
                    role_needed = "Player"
                    params = "None"
                    example = "=weaponspar"
                elif help_command == 'leavespar':
                    command_does = "Bows out of a spar and leaves the group. Keeps from any stat changes, but loses experience. Game moderators may enact consequences if someone leaves a spar to avoid losing rather than because they have real life things to do."
                    role_needed = "Player"
                    params = "None"
                    example = "=leavespar"
                elif help_command == 'givecurrency':
                    command_does = "Gives a character currency from the guild bank, for completing a quest, for example. The character and amount are selected in DMs."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=givecurrency"
                elif help_command == 'takecurrency':
                    command_does = "Takes currency from a character and deposits it in the guild bank, for an item outside the bot or a fine for an IC crime, for example. The character and amount are selected in DMs."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=takecurrency"
                elif help_command == 'buy':
                    command_does = "Purchase an item from any vendor defined in the server. If no vendors are defined, purchases cannot be completed. Funds go to the guild bank. Purchases are completed in DMs."
                    role_needed = "Player"
                    params = "None"
                    example = "=buy"
                elif help_command == 'sell':
                    command_does = "Sell an item in your inventory back to the server. Funds come from the guild bank. The sale is completed in DMs."
                    role_needed = "Player"
                    params = "None"
                    example = "=sell"
                elif help_command == 'trade':
                    command_does = "Trade an item to another character, including your own. No fairness is enforced, so transfer items at your own risk! Select an item and character in DMs."
                    role_needed = "Player"
                    params = "None"
                    example = "=trade"
                elif help_command == 'sendcurrency':
                    command_does = "Send money to another character, including your own. No fairness is enforced, so transfer currency at your own risk! Select the character and amount in DMs."
                    role_needed = "Player"
                    params = "None"
                    example = "=sendcurrency"
                elif help_command == 'buyarms':
                    command_does = "Purchase a new armament from an armory. An armory must be defined on the server, or purchases cannot be completed. Funds are deposited in the guild bank and purchases are completed in DMs."
                    role_needed = "Player"
                    example = "=buyarms"
                elif help_command == 'sellarms':
                    command_does = "Sell an armament in your inventory back to the server. Funds are deposited in the guild bank. The sale is completed in DMs."
                    role_needed = "Player"
                    params = "None"
                    example = "=sellarms"
                elif help_command == 'tradearms':
                    command_does = "Trade an armament to another character, including your own. Fairness is not enforced, so trade at your own risk! Select the character and target in DMs."
                    role_needed = "Player"
                    params = "None"
                    example = "=tradearms"
                elif help_command == 'newvendor':
                    ommand_does = "Create a new vendor on the server, giving the vendor a name, picture link and item inventory. The creation is completed in DMs."
                    role_needed = "Admin"
                    params = "None"
                    example = "=newvendor"
                elif help_command == 'addvendoritem':
                    command_does = "Add additional items to an existing vendor in DMs."
                    role_needed = "Admin"
                    params = "None"
                    example = "=addvendoritem"
                elif help_command == 'deletevendoritem':
                    command_does = "Delete items from an existing vendor in DMs."
                    role_needed = "Admin"
                    params = "None"
                    example = "=deletevendoritem"
                elif help_command == 'deletevendor':
                    command_does = "Delete a vendor from the server."
                    role_needed = "Admin"
                    params = "Vendor Name"
                    example = "=deletevendor Apothecary"
                elif help_command == 'listvendors':
                    command_does = "List all vendors defined on the server."
                    role_needed = "None"
                    params = "None"
                    example = "=listvendors"
                elif help_command == 'listvendor':
                    command_does = "Show the name, items and picture of a vendor."
                    role_needed = "None"
                    params = "Vendor Name"
                    example = "=listvendor Wayne's Wizarding World Emporium"
                elif help_command == 'newarmament':
                    command_does = "Create a new armament using the DM system."
                    role_needed = "Admin"
                    params = "None"
                    example = "=newarmament"
                elif help_command == 'editarmament':
                    command_does = "Edit an existing armament on the server."
                    role_needed = "Admin"
                    params = "Item Name"
                    example = "=editarmament Excalibur"
                elif help_command == 'deletearmament':
                    command_does = "Delete an armament from the server."
                    role_needed = "Admin"
                    params = "Item Name"
                    example = "=deletearmament Iron Shield"
                elif help_command == 'listarmaments':
                    command_does = "List all armaments on the server."
                    role_needed = "None"
                    params = "None"
                    example = "=listarmaments"
                elif help_command == 'listarmament':
                    command_does = "Show data for an armament."
                    role_needed = "None"
                    params = "Item Name"
                    example = "=listarmament Apple Cider"
                elif help_command == 'givearmament':
                    command_does = "Grant an armament to a character without having the character purchase it. The armament and character are picked from a list in DMs."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=givearmament"
                elif help_command == 'takearmament':
                    command_does = "Take an armament away from a character and result in no currency for losing it."
                    role_needed = "Game Moderator"
                    params = "None"
                    example = "=takearmament"
                elif help_command == 'newarmory':
                    ommand_does = "Create a new armory on the server, giving the armory a name, picture link and item inventory. The creation is completed in DMs."
                    role_needed = "Admin"
                    params = "None"
                    example = "=newarmory"
                elif help_command == 'addarmoryitem':
                    command_does = "Add additional items to an existing armory in DMs."
                    role_needed = "Admin"
                    params = "None"
                    example = "=addarmoryitem"
                elif help_command == 'deletearmoryitem':
                    command_does = "Delete items from an existing armory in DMs."
                    role_needed = "Admin"
                    params = "None"
                    example = "=deletearmoryitem"
                elif help_command == 'deletearmory':
                    command_does = "Delete a armory from the server."
                    role_needed = "Admin"
                    params = "Vendor Name"
                    example = "=deletearmory Rhy'Din Blacksmith"
                elif help_command == 'listarmories':
                    command_does = "List all armories defined on the server."
                    role_needed = "None"
                    params = "None"
                    example = "=listarmories"
                elif help_command == 'listarmory':
                    command_does = "Show the name, items and picture of a armory."
                    role_needed = "None"
                    params = "Vendor Name"
                    example = "=listarmory Dwarven Forge"
                elif help_command == 'equip':
                    command_does = "Equips an armament in an available character slot, the armament, character and slot are selected in DMs."
                    role_needed = "Player"
                    params = "None"
                    example = "=equip"
                elif help_command == 'unequip':
                    command_does = "Unequips an armament from the character. The character and armament/slot are selected in DMs."
                    role_needed = "Player"
                    params = "None"
                    example = "=unequip"
                elif help_command == 'lurk':
                    command_does = "Post a random lurk command."
                    role_needed = "None"
                    params = "None"
                    example = "=lurk"
                elif help_command == 'ooc':
                    command_does = "Repost with OOC brackets (())."
                    role_needed = "None"
                    params = "Text to post"
                    example = "=ooc Wait, Luke wouldn't react like that!"
                elif help_command == 'me':
                    command_does = "Post an OOC action as yourself."
                    role_needed = "None"
                    params = "Action to post"
                    example = "=me sneaks behind her and yells BOO!"
                elif help_command == 'randomooc':
                    command_does = "Perform a random OOC action (not all are completely SFW) to another mentioned user."
                    role_needed = "None"
                    params = "Discord user mention"
                    example = "=randomooc @My Best Fwiend"
                elif help_command == 'roll':
                    command_does = "Roll X number of Y sided dice."
                    role_needed = "None"
                    params = "XdY"
                    example = "=roll 4d100"
                elif help_command == 'newscene':
                    command_does = "Post --new scene-- as the bot narrator."
                    role_required = "None"
                    params = "None"
                    example = "=newscene"
                elif help_command == 'endscene':
                    command_does = "Post --scene paused-- as the bot narrator to indicate a scene pause."
                    role_required = "None"
                    params = "None"
                    example = "=pause"
                elif help_command == 'unpause':
                    command_does = "Post --scene resumed-- as the bot narrator to indicate a scene resumption."
                    role_required = "None"
                    params = "None"
                    example = "=unpause"
                elif help_command == 'endscene':
                    command_does = "Post --end scene-- as the bot narrator to indicate a scene is closed."
                    role_required = "None"
                    params = "None"
                    example = "=endscene"
                elif help_command == 'postnarr':
                    command_does = "Post as the narrator to indicate a game master action or third-person narration of events."
                    role_required = "None"
                    params = "Text to post"
                    example = "=postnarr It was a dark and stormy night."
                elif help_command == 'enter':
                    command_does = "Post *Player name has entered* as the bot narrator to indicate a character has entered."
                    role_required = "None"
                    params = "None"
                    example = "=enter"
                elif help_command == 'exit':
                    command_does = "Post *Player name has exited* as the bot narrator to indicate a character has exited."
                    role_required = "None"
                    params = "None"
                    example = "=exit"
                else:

                    command_does = "Command Not Found!"
                    role_needed = "None"
                    example = "None"
                    params = "None"

                embed = discord.Embed(title=help_command, description="Detailed help for " + help_command)
                embed.add_field(name="What the command does", value=command_does)
                embed.add_field(name="Role required for command:", value=role_needed)
                embed.add_field(name="Parameters for command:", value=params)
                embed.add_field(name="Example usage:", value=example)
                await message.channel.send(embed=embed)
                return

            if fields:
                message_chunks = [response[i:i + 2000] for i in range(0, len(response), 2000)]
                for chunk in message_chunks:
                    embed = discord.Embed(title="RP Mastermind Help", description=chunk)

                    await message.channel.send(embed=embed)
                    await asyncio.sleep(1)
                if fields.strip():
                    message_chunks = [fields[i:i + 2000] for i in range(0, len(fields), 2000)]
                    for chunk in message_chunks:
                        embed = discord.Embed(title="RP Mastermind Help", description=chunk)

                        await message.channel.send(embed=embed)
                        await asyncio.sleep(1)

                        # await reply_message(message, response + fields)
            else:
                message_chunks = [response[i:i + 2000] for i in range(0, len(response), 2000)]
                for chunk in message_chunks:
                    embed = discord.Embed(title="RP Mastermind Help", description=chunk)

                    await message.channel.send(embed=embed)
                    await asyncio.sleep(1)
            return
        try:
            guild_settings[message.guild.id]["AdminRole"]
        except:
            return
        if message.guild and re.search(r"cast|melee|weapon|disarm|buff|pass", message.content):

            if mass_spar_event[message.guild.id] and message.author.id in list(
                    mass_spar_chars[message.guild.id].keys()):
                server_id = message.guild.id
                user_id = message.author.id
                records = await select_sql("""SELECT IFNULL(Status,'None=0') FROM CharacterProfiles WHERE Id=%s;""",
                                           (str(mass_spar_chars[server_id][user_id]["CharId"]),))
                for row in records:
                    pulled_stat = row[0].split('=')
                    if float(pulled_stat[1]) > -1.0 and float(pulled_stat[1]) < 1.0:
                        if pulled_stat[0] == 'Health':
                            pulled_stat[1] = float(pulled_stat[1]) * mass_spar_chars[server_id][user_id]["MaxHealth"]
                        if pulled_stat[0] == 'Mana':
                            pulled_stat[1] = float(pulled_stat[1]) * mass_spar_chars[server_id][user_id]["MaxMana"]
                        if pulled_stat[0] == 'Stamina':
                            pulled_stat[1] = float(pulled_stat[1]) * mass_spar_chars[server_id][user_id]["MaxStamina"]                        
                if pulled_stat[0] == 'Poison':
                    mass_spar_chars[server_id][user_id]["Health"] = mass_spar_chars[server_id][user_id]["Health"] + int(
                        pulled_stat[1])
                    await reply_message(message, mass_spar_chars[server_id][user_id][
                        "CharName"] + " is poisoned and lost **" + str(pulled_stat[1]) + "** health this turn!")
                elif pulled_stat[0] == 'Stunned':
                    pulled_stat[1] = int(pulled_stat[1]) - 1
                    if pulled_stat[1] < 1:
                        result = await commit_sql("""UPDATE CharacterProfiles SET Status=%s WHERE Id=%s;""",
                                                  (str('None=0'), str(mass_spar_chars[server_id][user_id]["CharId"])))
                        await reply_message(message,
                                            mass_spar_chars[server_id][user_id]["CharName"] + " is no longer stunned!")
                    else:
                        recover_chance = random.randint(1, 100)
                        if recover_chance <= 20:
                            await reply_message(message, mass_spar_chars[server_id][user_id][
                                "CharName"] + " has recovered from the stun!")
                            result = await commit_sql("""UPDATE CharacterProfiles SET Status=%s WHERE Id=%s;""", (
                                str('None=0'), str(mass_spar_chars[server_id][user_id]["CharId"])))
                        else:
                            result = await commit_sql("""UPDATE CharacterProfiles SET Status=%s WHERE Id=%s;""", (
                                str('Stunned=' + str(pulled_stat[1])),
                                str(mass_spar_chars[server_id][user_id]["CharId"])))
                            await reply_message(message, mass_spar_chars[server_id][user_id][
                                "CharName"] + " is stunned and cannot attack! Use **=pass** if you have no items to use!")
                            return
                elif pulled_stat[0] == 'Asleep':
                    pulled_stat[1] = int(pulled_stat[1]) - 1
                    if pulled_stat[1] < 1:
                        result = await commit_sql("""UPDATE CharacterProfiles SET Status=%s WHERE Id=%s;""",
                                                  (str('None=0'), str(mass_spar_chars[server_id][user_id]["CharId"])))
                        await reply_message(message,
                                            mass_spar_chars[server_id][user_id]["CharName"] + " is no longer asleep!")
                    else:
                        recover_chance = random.randint(1, 100)
                        if recover_chance <= 50:
                            await reply_message(message, mass_spar_chars[server_id][user_id][
                                "CharName"] + " has awakened on their own!")
                            result = await commit_sql("""UPDATE CharacterProfiles SET Status=%s WHERE Id=%s;""", (
                                str('None=0'), str(mass_spar_chars[server_id][user_id]["CharId"])))
                        else:
                            result = await commit_sql("""UPDATE CharacterProfiles SET Status=%s WHERE Id=%s;""", (
                                str('Asleep=' + str(pulled_stat[1])),
                                str(mass_spar_chars[server_id][user_id]["CharId"])))
                            await reply_message(message, mass_spar_chars[server_id][user_id][
                                "CharName"] + " is asleep and cannot attack! Use **=pass** if you have no items to use!")
                            return
                elif pulled_stat[0] == 'ManaDrain':
                    mass_spar_chars[server_id][user_id]["Mana"] = mass_spar_chars[server_id][user_id]["Mana"] + int(
                        pulled_stat[1])
                    await reply_message(message, mass_spar_chars[server_id][user_id][
                        "CharName"] + " is having their mana drained and lost **" + str(
                        pulled_stat[1]) + "** mana this turn!")
                elif pulled_stat[0] == 'StaminaDrain':
                    mass_spar_chars[server_id][user_id]["Stamina"] = mass_spar_chars[server_id][user_id][
                                                                         "Stamina"] + int(pulled_stat[1])
                    await reply_message(message, mass_spar_chars[server_id][user_id][
                        "CharName"] + " is having their stamina drained and lost **" + str(
                        pulled_stat[1]) + "** stamina this turn!")
                elif pulled_stat[0] == 'Delusional':
                    pulled_stat[1] = int(pulled_stat[1]) - 1
                    if pulled_stat[1] < 1:
                        result = await commit_sql("""UPDATE CharacterProfiles SET Status=%s WHERE Id=%s;""",
                                                  (str('None=0'), str(mass_spar_chars[server_id][user_id]["CharId"])))
                        await reply_message(message, mass_spar_chars[server_id][user_id][
                            "CharName"] + " is no longer delusional!")
                    else:
                        chance_of_pain = random.randint(0, 100)
                        if chance_of_pain > 50:
                            mass_spar_chars[server_id][user_id]["Health"] = mass_spar_chars[server_id][user_id][
                                                                                "Health"] + int(pulled_stat[1])
                            await reply_message(message, mass_spar_chars[server_id][user_id][
                                "CharName"] + " is delusional and harmed themselves, losing **" + str(pulled_stat[
                                                                                                          1]) + "** health this turn, and cannot attack! Use =pass if you have no items to regain sanity!")
                            return
                        else:
                            await reply_message(message, mass_spar_chars[server_id][user_id][
                                "CharName"] + " is delusional and cannot attack! Use =pass if you have no items to regain sanity!")
                            return
                elif pulled_stat[0] == 'None':
                    if mass_spar_chars[server_id][user_id]["Health"] < mass_spar_chars[server_id][user_id]["MaxHealth"]:
                        health_gained = int(
                            guild_settings[server_id]["HealthAutoHeal"] * mass_spar_chars[server_id][user_id][
                                "MaxHealth"])
                        mass_spar_chars[server_id][user_id]["Health"] = mass_spar_chars[server_id][user_id][
                                                                            "Health"] + health_gained
                    else:
                        health_gained = "0 (at max)"
                    if mass_spar_chars[server_id][user_id]["Mana"] < mass_spar_chars[server_id][user_id]["MaxMana"]:
                        mana_gained = int(
                            guild_settings[server_id]["ManaAutoHeal"] * mass_spar_chars[server_id][user_id]["Mana"])
                        mass_spar_chars[server_id][user_id]["Mana"] = mass_spar_chars[server_id][user_id][
                                                                          "Mana"] + mana_gained
                    else:
                        mana_gained = "0 (at max)"

                    if mass_spar_chars[server_id][user_id]["Stamina"] < mass_spar_chars[server_id][user_id][
                        "MaxStamina"]:
                        stamina_gained = int(
                            guild_settings[server_id]["StaminaAutoHeal"] * mass_spar_chars[server_id][user_id][
                                "Stamina"])
                        mass_spar_chars[server_id][user_id]["Stamina"] = mass_spar_chars[server_id][user_id][
                                                                             "Stamina"] + stamina_gained
                    else:
                        stamina_gained = "0 (at max)"

                    await reply_message(message, mass_spar_chars[server_id][user_id][
                        "CharName"] + " automatically gained **" + str(health_gained) + "** health, **" + str(
                        mana_gained) + "** mana and **" + str(stamina_gained) + "** stamina this turn!")
            if server_encounters[message.guild.id] and message.author.id in list(
                    server_party_chars[message.guild.id].keys()):
                server_id = message.guild.id
                user_id = message.author.id
                if server_party_chars[server_id][user_id]["Health"] < server_party_chars[server_id][user_id][
                    "MaxHealth"]:
                    health_gained = int(
                        guild_settings[server_id]["HealthAutoHeal"] * server_party_chars[server_id][user_id][
                            "MaxHealth"])
                    server_party_chars[server_id][user_id]["Health"] = server_party_chars[server_id][user_id][
                                                                           "Health"] + health_gained
                else:
                    health_gained = "0 (at max)"
                if server_party_chars[server_id][user_id]["Mana"] < server_party_chars[server_id][user_id]["MaxMana"]:
                    mana_gained = int(
                        guild_settings[server_id]["ManaAutoHeal"] * server_party_chars[server_id][user_id]["Mana"])
                    server_party_chars[server_id][user_id]["Mana"] = server_party_chars[server_id][user_id][
                                                                         "Mana"] + mana_gained
                else:
                    mana_gained = "0 (at max)"

                if server_party_chars[server_id][user_id]["Stamina"] < server_party_chars[server_id][user_id][
                    "MaxStamina"]:
                    stamina_gained = int(
                        guild_settings[server_id]["StaminaAutoHeal"] * server_party_chars[server_id][user_id][
                            "Stamina"])
                    server_party_chars[server_id][user_id]["Stamina"] = server_party_chars[server_id][user_id][
                                                                            "Stamina"] + stamina_gained
                else:
                    stamina_gained = "0 (at max)"

                await reply_message(message, server_party_chars[server_id][user_id][
                    "CharName"] + " automatically gained **" + str(health_gained) + "** health, **" + str(
                    mana_gained) + "** mana and **" + str(stamina_gained) + "** stamina this turn!")

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
            # "GMRole","NPCRole","PlayerRole","GuildBankBalance","StartingHealth","StartingMana","StartingStamina","StartingAttack","StartingDefense","StartingMagicAttack","StartingAgility","StartingIntellect","StartingCharisma","HealthLevelAdd","ManaLevelAdd","StaminaLevelAdd","XPLevelRatio","HealthAutoHeal","ManaAutoHeal","StaminaAutoHeal"
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
        elif command == 'cheatsheet':
            if not parsed_string:
                await reply_message(message,
                                    "No cheatsheet specified! Please use **setup**, **spar** or **encounter.**")
                return

            embed = discord.Embed(title="Cheatsheet", description="Quick help for " + parsed_string)
            if parsed_string == 'setup':
                embed.add_field(name="Default Setup Command Reference",
                                value="=createroles\n=addadmin @UserMention\n=loaddefault\n")
                embed.add_field(name="Custom Setup Command Reference",
                                value="=setadminrole @AdminRoleMention\n=newsetup\n=setgmrole @GMRole\n=setnpcrole @NPCRole\n=setplayerrole @PlayerRole\n=listsetup\n=loaddefault (optional)")
            elif parsed_string == 'spar':
                embed.add_field(name="Sparring Command Quick Reference",
                                value="=spar1 @User1 @User2\n=yes/=no\n=spar2\n=spar3\n=weaponspar/=meleespar/=castspar\n=buff/=useitem\n")
            elif parsed_string == 'hunt':
                embed.add_field(name="Hunting Command Quick Reference",value="=hunt\n=castmonster/=weaponmonster/=meleemonster/=useitem/=buff")
            elif parsed_string == 'encounter':
                embed.add_field(name="Encounter Command Quick Reference",
                                value="**Game Moderator:**\n=monster1 @user1 @user2\n\n**Player:**\n=monster2\n\n**Game Moderator:**\n=monster3\n\n**Player:**\n=meleemonster/=weaponmonster/=castmonster\n=buff/=useitem\n\n**Game Moderator:**\n=monsterattack\n=abortencounter\n=disbandparty")
            elif parsed_string == 'player':
                embed.add_field(name="Character Command Quick Reference",
                                value="=create\n=change CharacterName\n=remove CharacterName\n=equip\n=unequip\n CharacterName\n=addstatpoints\n=profile\n=stats\n=active\n=inactive\n=daily")
                embed.add_field(name="Economy Command Quick Reference",
                                value="=buy\n=sell\n=buyarms\n=sellarms\n=trade\n=tradearms")
                embed.add_field(name="Inventory Command Quick Reference", value="=useitem\n=inventory CharacterName")
            elif parsed_string == 'admin':
                embed.add_field(name="Monsters", value="=newmonster/=editmonster/=deletemonster")
                embed.add_field(name="Items", value="=newitem/=edititem/=deleteitem/=giveitem/=takeitem")
                embed.add_field(name="Economy", value="=givecurrency/=takecurrency/=setbankbalance")
                embed.add_field(name="Vendors", value="=newvendor/=deletevendor/=addvendoritem/=deletevendoritem")
                embed.add_field(name="Armories", value="=newarmory/=deletearmory/=addarmoryitem/=deletearmoryitem")
                embed.add_field(name="Spells", value="=newspell/=editspell/=deletespell/=givespell/=takespell")
                embed.add_field(name="Melees", value="=newmelee/=editmelee/=deletemelee/=givemelee/=takemelee")
                embed.add_field(name="Buffs", value="=newbuff/=editbuff/=deletebuff/=givebuff/=takebuff")
                embed.add_field(name="Characters", value="=remove/=editstats/=givestatpoints")


            elif parsed_string == 'gm':
                embed.add_field(name="Items", value="=giveitem/=takeitem")
                embed.add_field(name="Economy", value="=givecurrency/=takecurrency")
                embed.add_field(name="Spells", value="=givespell/=takespell")
                embed.add_field(name="Melees", value="=givemelee/=takemelee")
                embed.add_field(name="Buffs", value="=givebuff/=takebuff")
                embed.add_field(name="Characters", value="=givestatpoints")
            else:
                await reply_message(message, "That isn't a valid cheatsheet category.")
                return
            await message.channel.send(embed=embed)
        elif command == 'mysparstats':
            if not mass_spar_event[message.guild.id]:
                await reply_message(message, "No spar currently progress!")
                return
            else:
                server_id = message.guild.id
                user_id = message.author.id
                embed = discord.Embed(title="Spar stats for " + message.author.display_name)
                embed.add_field(name="Character Name:", value=mass_spar_chars[server_id][user_id]["CharName"])
                embed.add_field(name="Attack:", value=str(mass_spar_chars[server_id][user_id]["Attack"]))
                embed.add_field(name="Defense", value=str(mass_spar_chars[server_id][user_id]["Defense"]))
                embed.add_field(name="MagicAttack:", value=str(mass_spar_chars[server_id][user_id]["MagicAttack"]))
                embed.add_field(name="Health", value=str(mass_spar_chars[server_id][user_id]["Health"]))
                embed.add_field(name="MaxHealth", value=str(mass_spar_chars[server_id][user_id]["MaxHealth"]))
                embed.add_field(name="Mana", value=str(mass_spar_chars[server_id][user_id]["Mana"]))
                embed.add_field(name="MaxMana:", value=str(mass_spar_chars[server_id][user_id]["MaxMana"]))
                embed.add_field(name="Level:", value=str(mass_spar_chars[server_id][user_id]["Level"]))
                embed.add_field(name="Experience:", value=str(mass_spar_chars[server_id][user_id]["Experience"]))
                embed.add_field(name="MaxStamina", value=str(mass_spar_chars[server_id][user_id]["MaxStamina"]))
                embed.add_field(name="Stamina", value=str(mass_spar_chars[server_id][user_id]["Stamina"]))
                embed.add_field(name="Agility", value=str(mass_spar_chars[server_id][user_id]["Agility"]))
                embed.add_field(name="Intellect", value=str(mass_spar_chars[server_id][user_id]["Intellect"]))
                embed.add_field(name="Charisma", value=str(mass_spar_chars[server_id][user_id]["Charisma"]))
                embed.add_field(name="ChardID:", value=str(mass_spar_chars[server_id][user_id]["CharId"]))
                await message.channel.send(embed=embed)
        elif command == 'showpending':
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
            if not mass_spar_event[server_id] and not server_encounters[server_id]:
                await reply_message(message, "Why are you casting Magic Missile? There's nothing to attack here!")
                return
            if mass_spar_event[server_id]:
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
                await reply_message(message, "<@" + str(
                    mass_spar[server_id][mass_spar_turn[server_id]].id) + ">, it is your turn!")
            elif server_encounters[server_id]:
                in_party = next((item for item in server_party[server_id] if item.id == user_id), None)
                if not in_party:
                    await reply_message(message, "You are not in the server party!")
                    return
                if message.author != list(server_party[server_id])[encounter_turn[server_id]]:
                    await reply_message(message, "It's not your turn!")
                    return
                if encounter_turn[server_id] > len(server_party[server_id]) - 2:
                    encounter_turn[server_id] = 0
                else:
                    encounter_turn[server_id] = encounter_turn[server_id] + 1
                await reply_message(message, "<@" + str(
                    server_party[server_id][encounter_turn[server_id]].id) + ">, it is your turn!")
        elif command == 'endspar':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to leave a spar!")
                return
            if mass_spar_event[server_id]:
                in_party = next((item for item in mass_spar[server_id] if item.id == user_id), None)                
                if not in_party:
                    await reply_message(message, "You are not in the spar group!")
                    return                
            mass_spar_chars[message.guild.id] = None
            mass_spar[message.guild.id] = None
            mass_spar_event[message.guild.id] = False
            await reply_message(message, "The spar has been ended! No XP or currency will be awarded!")
        elif command == 'roll':
            dice_re = re.compile(r"(\d+)d(\d+)")
            m = dice_re.match(parsed_string)
            if not m:
                await reply_message(message, "Invalid dice command!")
                return
            number_of_dice = m.group(1)
            dice_sides = m.group(2)
            if int(number_of_dice) > 100:
                await reply_message(message, "You can't specify more than 100 dice to roll!")
                return

            response = "**Dice roll:**\n\n"
            sum = 0
            for x in range(0, int(number_of_dice)):
                die_roll = random.randint(1, int(dice_sides))
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
            if len(mass_spar_chars[message.guild.id]) < 2:
                await reply_message(message,
                                    "Everyone has left the spar! Since no one can claim victory, the spar group is disbanded!")
                mass_spar_chars[message.guild.id] = {}
                mass_spar[message.guild.id] = {}
                mass_spar_event[message.guild.id] = False
        elif command == 'listprofiles':
            records = await select_sql(
                """SELECT CharacterName,Level,UserId FROM CharacterProfiles WHERE ServerId=%s;""",
                (str(message.guild.id),))
            if not records:
                await reply_message(message, "No characters found for this server!")
                return
            response = "**SERVER CHARACTER LIST**\n\n"
            for row in records:
                response = response + row[0] + ", level " + str(row[1]) + ", Player: `" + str(
                    message.guild.get_member(int(row[2]))) + "`\n"
            await reply_message(message, response)
        elif command == 'listuserchars':
            if not message.mentions:
                await reply_message(message, "You didn't specify a user!")
                return
            user = message.mentions[0]
            user_id = user.id
            records = await select_sql(
                """SELECT CharacterName,Level FROM CharacterProfiles WHERE ServerId=%s AND UserId=%s;""",
                (str(message.guild.id), str(user_id)))
            if not records:
                await reply_message(message, "No records found for that user!")
                return
            response = "**USER CHARACTER LIST**\n\n"
            for row in records:
                response = response + row[0] + " " + row[1] + ", level " + int(row[2]) + "\n"
            await reply_message(message, response)
        elif command == 'approve':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must have the admin role to approve a new character.")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'approve'
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterName", "Approval"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "UnapprovedCharacterProfiles", "CharacterName")

            response = "Please select a new character to approve by replying to this message with the ID below:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message,
                                "Please check your DMs for instructions on how to approve a character, <@" + str(
                                    message.author.id) + ">.")
        elif command == 'deny':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must have the admin role to deny a new character.")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'deny'
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterName", "Deny", "DenyReason", "Deletion"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "UnapprovedCharacterProfiles", "CharacterName")

            response = "Please select a new character to deny by replying to this message with the ID below:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to deny a character, <@" + str(
                message.author.id) + ">.")
        elif command == 'daily':
            current_time_obj = datetime.now()
            day = int(current_time_obj.strftime("%d"))
            try:
                daily[message.guild.id][message.author.id]
            except:
                daily[message.guild.id][message.author.id] = 0

            if daily[message.guild.id][message.author.id] == day:
                await reply_message(message, "You've already collected your daily!")
                return
            records = await select_sql(
                """SELECT Id,CharacterName,Currency,Experience FROM CharacterProfiles WHERE ServerId=%s AND UserId=%s;""",
                (str(message.guild.id), str(message.author.id)))
            if not records:
                await reply_message(message, "You have no characters!")
                return
            character_list = []
            character_name = []
            character_currency = []
            experience = []
            for row in records:
                character_list.append(row[0])
                character_name.append(row[1])
                character_currency.append(row[2])
                experience.append(row[3])
            lucky_char = random.randint(0, len(character_list) - 1)
            new_money = int(character_currency[lucky_char]) + 200
            new_xp = int(experience[lucky_char]) + 100
            result = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s,Experience=%s WHERE Id=%s;""",
                                      (str(new_money), str(new_xp), str(character_list[lucky_char])))
            if result:
                await reply_message(message, character_name[
                    lucky_char] + " is the lucky recipient of 200 currency and 100 XP today!")
                daily[message.guild.id][message.author.id] = day
            else:
                await reply_message(message, "Database error!")


        elif command == 'create':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must have the player role to create a new character.")
                return
            records = await select_sql("""SELECT Fields FROM CustomProfiles WHERE ServerId=%s;""",
                                       (str(message.guild.id),))
            if records:
                field_dict = {}
                for row in records:
                    fields = row[0].split(',')
                if message.author.id not in dm_tracker.keys():
                    await initialize_dm(message.author.id)
                dm_tracker[message.author.id]["currentcommand"] = 'newcustomchar'
                dm_tracker[message.author.id]["fieldlist"] = fields
                dm_tracker[message.author.id]["server_id"] = message.guild.id
                dm_tracker[message.author.id]["currentfield"] = 0
                dm_tracker[message.author.id]["commandchannel"] = message.channel
                await reply_message(message,
                                    "Please check your DMs for instructions on how to create a new character, <@" + str(
                                        message.author.id) + ">.")
                await direct_message(message,
                                     "Hello, you have requested to create a new character! Please start with the **name** of the character below in your reply!")
                return

            else:
                if message.author.id not in dm_tracker.keys():
                    await initialize_dm(message.author.id)
                dm_tracker[message.author.id]["currentcommand"] = 'newdefaultchar'
                dm_tracker[message.author.id]["fieldlist"] = ["CharacterName", "Age", "Race", "Gender", "Height",
                                                              "Weight", "Playedby", "Origin", "Occupation", "Class",
                                                              "PictureLink"]
                dm_tracker[message.author.id]["fieldmeans"] = ["Name of the character", "The age of the character",
                                                               "The race of the character (human, vampire, etc)",
                                                               "The gender, if known of the character (male, female, etc)",
                                                               "The usual height of the character, if known (5'5'', 10 cubits, etc)",
                                                               "The mass on the current world of the character (180 lbs, five tons, etc)",
                                                               "The name of the artist, human representation, actor, etc who is used to show what the character looks like (Angelina Jolie, Brad Pitt, etc)",
                                                               "The hometown or homeworld of the character (Texas, Earth, Antares, etc)",
                                                               "What the character does for a living, if applicable (blacksmith, mercenary, prince, etc)",
                                                               "The class of the character",
                                                               "A direct upload or http link to a publicly accessible picture on the Internet (None for no link). Google referral links don't always work"]
                dm_tracker[message.author.id]["currentfield"] = 0
                dm_tracker[message.author.id]["fielddict"] = []
                dm_tracker[message.author.id]["server_id"] = message.guild.id
                dm_tracker[message.author.id]["commandchannel"] = message.channel

                await reply_message(message,
                                    "Please check your DMs for instructions on how to create a new character, <@" + str(
                                        message.author.id) + ">.")

                await direct_message(message,
                                     "You have requested a new default character! Please type in the name you want, and then fill out the fields that appear.")
        elif command == 'randomprofile':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must have the player role to create a new random character.")
                return

            male_first_name_list = ["Ferris", "Redmond", "Raphael", "Orion", "Caspian", "Aramis", "Lucian", "Storm",
                                    "Percival", "Gawain", "Perseus", "Cormac", "Leon", "Patrick", "Robert", "Morgan",
                                    "Brandon", "Sven", "Roland", "Ronan", "Edmund", "Adam", "Edric", "Martin", "Odin",
                                    "Bayard", "Laurent", "Faramond", "Finn", "Edward", "Tristan", "Emil", "Zephyr",
                                    "Soren", "Arthur", "Robin", "Marcel", "Roman", "Beowulf"", ""Seth", "Tristan",
                                    "Arthur", "Edmund", "Percival", "Ronan", "Thor", "Leon", "Roman", "Adam", "Ferris",
                                    "Zephyr", "Gawain", "Perseus", "Cormac", "Lydan", "Syrin", "Ptorik", "Joz", "Varog",
                                    "Gethrod", "Hezra", "Feron", "Ophni", "Colborn", "Fintis", "Gatlin", "Jinto",
                                    "Hagalbar", "Krinn", "Lenox", "Revvyn", "Hodus", "Dimian", "Paskel", "Kontas",
                                    "Weston", "Azamarr ", "Jather ", "Tekren ", "Jareth", "Adon", "Zaden", "Eune ",
                                    "Graff", "Tez", "Jessop", "Gunnar", "Pike", "Domnhar", "Baske", "Jerrick", "Mavrek",
                                    "Riordan", "Wulfe", "Straus", "Tyvrik ", "Henndar", "Favroe", "Whit", "Jaris",
                                    "Renham", "Kagran", "Lassrin ", "Vadim", "Arlo", "Quintis", "Vale", "Caelan",
                                    "Yorjan", "Khron", "Ishmael", "Jakrin", "Fangar", "Roux", "Baxar", "Hawke",
                                    "Gatlen", "Barak", "Nazim", "Kadric", "Paquin", " ", "", "Kent", "Moki", "Rankar",
                                    "Lothe", "Ryven", "Clawsen", "Pakker", "Embre", "Cassian", "Verssek", "Dagfinn",
                                    "Ebraheim", "Nesso", "Eldermar", "Rivik", "Rourke", "Barton", "Hemm", "Sarkin",
                                    "Blaiz ", "Talon", "Agro", "Zagaroth", "Turrek", "Esdel", " ", "", "Lustros",
                                    "Zenner", "Baashar ", "Dagrod ", "Gentar", "Feston"]
            female_first_name_list = ["Ayrana", "Resha", "Varin", "Wren", "Yuni", "Talis", "Kessa", "Magaltie", "Aeris",
                                      "Desmina", "Krynna", "Asralyn ", "Herra", "Pret", "Kory", "Afia", "Tessel",
                                      "Rhiannon", "Zara", "Jesi", "Belen", "Rei", "Ciscra", "Temy", "Renalee ", "Estyn",
                                      "Maarika", "Lynorr", "Tiv", "Annihya", "Semet", "Tamrin", "Antia", "Reslyn",
                                      "Basak", "Vixra", "Pekka ", "Xavia", "Beatha ", "Yarri", "Liris", "Sonali",
                                      "Razra ", "Soko", "Maeve", "Everen", "Yelina", "Morwena", "Hagar", "Palra",
                                      "Elysa", "Sage", "Ketra", "Lynx", "Agama", "Thesra ", "Tezani", "Ralia", "Esmee",
                                      "Heron", "Naima", "Rydna ", "Sparrow", "Baakshi ", "Ibera", "Phlox", "Dessa",
                                      "Braithe", "Taewen", "Larke", "Silene", "Phressa", "Esther", "Anika", "Rasy ",
                                      "Harper", "Indie", "Vita", "Drusila", "Minha", "Surane", "Lassona", "Merula",
                                      "Kye", "Jonna", "Lyla", "Zet", "Orett", "Naphtalia", "Turi", "Rhays", "Shike",
                                      "Hartie", "Beela", "Leska", "Vemery ", "Lunex", "Fidess", "Tisette", "Partha"]
            unisex_first_name_list = []
            last_name_list = ["Starbringer", "Leafgreen", "Smith", "Thundershaw", "Dreamweaver", "McAle", "Hale",
                              "Zendor", "Zoaraster", "Horserider", "Stormwalker", "Abawi", "Allard", "Adara", "Abbott",
                              "Acampora", "Ackerman", "Ackroyd", "Abbington", "Axworthy", "Ainge", "Abernathy",
                              "Atkinson", "Abner", "Abella", "Agholor", "Allred", "Asola", "Abrams", "Acker", "Abrell",
                              "Acuff", "Archer", "Asterio", "Adair", "Albright", "Adelson", "Atwood", "Aguillar",
                              "Adler", "Arrowood", "Agnew", "Akuna", "Alcott", "Alstott", "Austin", "Algarotti",
                              "Alvarez", "Armani", "Anderson", "Amherst", "Adkins", "Ayesa", "Argento", "Arrowood",
                              "Andruzzi", "Abraham", "Angle", "Armstrong", "Attard", "Annenberg", "Arrhenius", "Acosta",
                              "Antrican", "Adderley", "Atwater", "Agassi", "Apatow", "Archeletta", "Averescu",
                              "Arrington", "Agrippa", "Aiken", "Albertson", "Alexander", "Amado", "Anders", "Armas",
                              "Akkad", "Aoki", "Aldrich", "Almond", "Alinsky", "Agnello", "Alterio", "Atchley", "Bynes",
                              "Bray", "Budreau", "Byrne", "Bragg", "Banner", "Bishop", "Burris", "Boggs", "Brembilla",
                              "Booth", "Bullard", "Booker", "Buckner", "Borden", "Breslin", "Bryant", "BIles", "Brunt",
                              "Brager", "Brandt", "Bosa", "Bradshaw", "Brubaker", "Berry", "Brooks", "Bandini",
                              "Bristow", "Barrick", "Biddle", "Brennan", "Brinkmann", "Benz", "Braddock", "Bright",
                              "Berman", "Bracco", "Bartley", "Briggs", "Bonanno", "Boyle", "Beeks", "Bernthal",
                              "Boldon", "Bowser", "Benwikere", "Bowman", "Bamberger", "Bowden", "Batch", "Blaustein",
                              "Blow", "Boulware", "Bezos", "Boulder", "Bauer", "Ballard", "Benton", "Bixby", "Bostwick",
                              "Biles", "Bobusic", "Belinski", "Blood", "Bisley", "Bettis", "Bensen", "Binion", "Bloch",
                              "Blixt", "Bellisario", "Botkin", "Benoit", "BInda", "Baldwin", "Bennett", "Bourland",
                              "Bester", "Bender", "Best", "Bald", "Bersa", "Belt", "Bourne", "Barks", "Beebe", "Banu",
                              "Bozzelli", "Bogaerts", "Cyrus", "Craggs", "Crisper", "Cotheran", "Curry", "Conard",
                              "Cutler", "Coggins", "Cates", "Crisp", "Curio ", "Creed", "Costner", "Cortse",
                              "Cunningham", "Cooper", "Cullen", "Castle", "Cugat", "Click", "Cassidy", "Crespo",
                              "Crusher", "Cooper", "Coates", "Crowley", "Creel", "Crassus", "Cogdill", "Cross",
                              "Crabtree", "Cranham", "Carver", "Cox", "Coltrane", "Chatwin", "Conklin", "Colt",
                              "Coulter", "Cleveland", "Coppens", "Coolidge", "Copeland", "Celino", "Coffin", "Cena",
                              "Conti ", "Coin", "Connelly", "Cents", "Carney", "Carmichael", "Coffey", "Carling",
                              "Christie", "Chadwick", "Cobo", "Clay", "Capra", "Candy", "Clancy", "Chalk", "Chambers",
                              "Callahan", "Cirque", "Cabrera-Bello", "Cherry", "Cannon", "Chung", "Cave", "Challenger",
                              "Cobb", "Calaway", "Chalut", "Cayce", "Cahill", "Cruz", "Cohen", "Caylor", "Cagle",
                              "Cline", "Crawford", "Cleary", "Cain", "Champ", "Cauley", "Claxton"    "Dubois", "Darby",
                              "Draper", "Dwyer", "Dixon", "Danton", "Devereaux", "Ditka", "Dominguez", "Decker",
                              "Dobermann", "Dunlop", "Dumont", "Dandridge", "Diamond", "Dobra ", "Dukas", "Dyer",
                              "Decarlo", "Delpy", "Dufner", "Driver", "Dalton", "Dark", "Dawkins", "Driskel",
                              "Derbyshire", "Davenport", "Dabney", "Dooley", "Dickerson", "Donovan", "Dallesandro",
                              "Devlin", "Donnelly", "Day", "Daddario", "Donahue", "Denver", "Denton", "Dodge",
                              "Dempsey", "Dahl", "Drewitt", "Earp", "Eberstark ", "Egan", "Elder", "Eldridge",
                              "Ellenburg", "Eslinger", "England", "Epps", "Eubanks", "Everhart", "Evert", "Eastwood",
                              "Elway", "Eslinger", "Ellerbrock", "Edge", "Endo", "Etter", "Ebersol", "Everson",
                              "Earwood", "Ekker", "Escobar", "Edgeworth", "Future", "Fitzpatrick", "Fontana", "Fenner",
                              "Furyk", "Finch", "Fullbright", "Fassbinder", "Flood", "Fong", "Fleetwood", "Fugger",
                              "Frost", "Fsik", "Fawcett", "Fishman", "Freeze", "Fissolo", "Foley", "Fairchild",
                              "Freeman", "Flanagan", "Freed", "Fogerty", "Foster", "Finn", "Fletcher", "Floris",
                              "Flynn", "Fairbanks", "Fawzi ", "Finau", "Floquet ", "Fleiss", "Ferguson", "Froning",
                              "Fitzgerald", "Fingermann", "Flagg", "Finchum", "Flair", "Ferber", "Fuller", "Farrell",
                              "Fenton", "Fangio", "Faddis", "Ferenz", "Farley", "Gundlach", "Gannon", "Goulding",
                              "Greenway", "Guest", "Gillis", "Gellar", "Gaither", "Griffith", "Grubbs", "Glass",
                              "Gotti", "Goodwin", "Grizzly", "Glover", "Grimes", "Gleason", "Gardner", "Geske",
                              "Griffo", "Glunt", "Golden", "Gardel", "Gribble", "Grell", "Gearey", "Grooms", "Glaser",
                              "Greer", "Geel", "Gallagher", "Glick", "Graber ", "Gore", "Gabbard", "Gelpi", "Gilardi",
                              "Goddard", "Gabel", "Hyde", "Hood", "Hull", "Hogan", "Hitchens", "Higgins", "Hodder",
                              "Huxx", "Hester", "Huxley", "Hess", "Hutton", "Hobgood", "Husher", "Hitchcock", "Huffman",
                              "Herrera", "Humber", "Hobbs", "Hostetler", "Henn", "Horry", "Hightower", "Hindley",
                              "Hitchens", "Holiday", "Holland", "Hitchcock", "Hoagland", "Hilliard", "Harvick",
                              "Hardison", "Hickey", "Heller", "Hartman", "Halliwell", "Hughes", "Hart", "Healy", "Head",
                              "Harper", "Hibben", "Harker", "Hatton", "Hawk", "Hardy", "Hadwin", "Hemmings", "Hembree",
                              "Helbig", "Hardin", "Hammer", "Hammond", "Haystack", "Howell", "Hatcher", "Hamilton",
                              "Halleck", "Hooper", "Hartsell", "Henderson", "Hale", "Hokoda", "Heers", "Homa",
                              "Hanifin", "Most Common Last Names Around the World", "Inch", "Inoki", "Ingram",
                              "Idelson", "Irvin", "Ives", "Ishikawa", "Irons", "Irwin", "Ibach", "Ivanenko",
                              "Ibara"    "Jurado", "Jammer", "Jagger", "Jackman", "Jishu", "Jingle", "Jessup",
                              "Jameson", "Jett", "Jackson", "Kulikov ", "Kellett", "Koo", "Kitt", "Keys", "Kaufman",
                              "Kersey", "Keating", "Kotek ", "Kuchar", "Katts", "Kilmer", "King", "Kubiak", "Koker",
                              "Kerrigan", "Kumara", "Knox", "Koufax", "Keagan", "Kestrel", "Kinder", "Koch", "Keats",
                              "Keller", "Kessler", "Kobayashi", "Klecko", "Kicklighter", "Kincaid", "Kershaw",
                              "Kaminsky", "Kirby", "Keene", "Kenny", "Keogh", "Kipps", "Salvador Dali",
                              "Salvador Dali"    "Litvak", "Lawler", "London", "Lynch", "Lacroix", "Ledford", "LeMay",
                              "Lovejoy", "Lombardo", "Lovecraft", "Laudermilk", "Locke", "Leishman", "Leary", "Lott",
                              "Ledger", "Lords", "Lacer", "Longwood", "Lattimore", "Laker", "Lecter", "Liston",
                              "Londos", "Lomax", "Leaves ", "Lipman", "Lambert", "Lesnar", "Lazenby", "Lichter",
                              "Lafferty", "Lovin", "Lucchesi", "Landis", "Lopez", "Lentz", "Murray", "Morrison",
                              "McKay", "Merchant", "Murillo", "Mooney", "Murdock", "Matisse", "Massey", "McGee",
                              "Minter", "Munson", "Mullard", "Mallory", "Meer ", "Mercer", "Mulder", "Malik", "Moreau ",
                              "Metz", "Mudd", "Meilyr", "Motter", "McNamara", "Malfoy", "Moses", "Moody", "Morozov",
                              "Mason", "Metcalf", "McGillicutty", "Montero", "Molinari", "Marsh", "Moffett", "McCabe",
                              "Manus", "Malenko", "Mullinax", "Morrissey", "Mantooth", "Mintz", "Messi", "Mattingly",
                              "Mannix", "Maker", "Montoya", "Marley", "McKnight", "Magnusson ", "Marino", "Maddox",
                              "Macklin", "Mackey", "Morikowa", "Mahan", "Necessary", "Nicely", "Nejem", "Nunn",
                              "Neiderman", "Naillon", "Nyland", "Novak", "Nygard", "Norwood", "Norris", "Namath",
                              "Nabor", "Nash", "Noonan", "Nolan ", "Nystrom", "Niles", "Napier", "Nunley", "Nighy",
                              "Overholt", "Ogletree", "Opilio ", "October", "Ozu", "O'Rourke", "Owusu", "Oduya", "Oaks",
                              "Odenkirk", "Ottinger", "O'Donnell", "Orton", "Oakley", "Oswald", "Ortega", "Ogle", "Orr",
                              "Ogden", "Onassis", "Olson", "Ollenrenshaw", "O'Leary", "O'Brien", "Oldman", "O'Bannon",
                              "Oberman", "O'Malley", "Otto", "Oshima", "Prado", "Prunk", "Piper", "Putnam", "Pittman",
                              "Post", "Price", "Plunkett", "Pitcher", "Pinzer", "Punch", "Paxton", "Powers", "Previn",
                              "Pulman", "Puller", "Peck", "Pepin", "Platt", "Powell", "Pawar", "Pinder", "Pickering",
                              "Pollock", "Perrin", "Pell", "Pavlov", "Patterson", "Perabo", "Patnick", "Panera",
                              "Prescott", "Portis", "Perkins", "Palmer", "Paisley", "Pladino", "Pope", "Posada",
                              "Pointer", "Poston", "Porter", "Quinn", "Quan", "Quaice", "Quaid", "Quirico", "Quarters",
                              "Quimby", "Qua", "Quivers", "Quall", "Quick", "Qugg", "Quint", "Quintero",
                              "Leonardo da Vinci", "Leonardo da Vinci"    "Rudd", "Ripperton", "Renfro", "Rifkin",
                              "Rand", "Root", "Rhodes", "Rowland", "Ramos", "Ryan", "Rafus", "Radiguet", "Ripley",
                              "Ruster", "Rush", "Race", "Rooney", "Russo", "Rude", "Roland", "Reader", "Renshaw",
                              "Rossi", "Riddle", "Ripa", "Richter", "Rosenberg", "Romo", "Ramirez", "Reagan",
                              "Rainwater", "Romirez", "Riker", "Riggs", "Redman", "Reinhart", "Redgrave", "Rafferty",
                              "Rigby", "Roman", "Reece", "Sutton", "Swift", "Sorrow", "Spinks", "Suggs", "Seagate",
                              "Story", "Soo", "Sullivan", "Sykes", "Skirth", "Silver", "Small", "Stoneking", "Sweeney",
                              "Surrett", "Swiatek", "Sloane", "Stapleton", "Seibert", "Stroud", "Strode", "Stockton",
                              "Scardino", "Spacek", "Spieth", "Stitchen", "Stiner", "Soria", "Saxon", "Shields",
                              "Stelly", "Steele", "Standifer", "Shock", "Simerly", "Swafford", "Stamper", "Sotelo",
                              "Smoker", "Skinner", "Shaver", "Shivers", "Savoy", "Small", "Skills", "Sinclair",
                              "Savage", "Sereno", "Sasai", "Silverman", "Silva", "Shippen", "Sasaki", "Sands", "Shute",
                              "Sabanthia", "Sheehan", "Sarkis", "Shea", "Santos", "Snedeker", "Stubbings", "Streelman",
                              "Skaggs", "Spears", "Twigg", "Tracy", "Truth", "Tillerson", "Thorisdottir ", "Tooms",
                              "Tripper", "Tway", "Taymor", "Tamlin", "Toller", "Tussac", "Turpin", "Tippett", "Tabrizi",
                              "Tanner", "Tuco", "Trumbo", "Tucker", "Theo", "Thain", "Trapp", "Trumbald ", "Trench",
                              "Terrella", "Tait", "Tanaka", "Tapp", "Tepper", "Trainor", "Turner", "Teague",
                              "Templeton", "Temple", "Teach", "Tam"    "Udder", "Uso", "Uceda", "Umoh", "Underhill",
                              "Uplinger", "Ulett", "Urtz", "Unger", "Vroman", "Vess", "Voight", "Vegas", "Vasher",
                              "Vandal", "Vader", "Volek", "Vega", "Vestine", "Vaccaro", "Vickers", "Witt", "Wolownik",
                              "Winding", "Wooten ", "Whitner", "Winslow", "Winchell", "Winters", "Walsh", "Whalen",
                              "Watson", "Wooster", "Woodson", "Winthrop", "Wall", "Wight", "Webb", "Woodard", "Wixx",
                              "Wong", "Whesker", "Wolfenstein", "Winchester", "Wire", "Wolf", "Wheeler", "Warrick",
                              "Walcott", "Wilde", "Wexler", "Wells", "Weeks", "Wainright", "Wallace", "Weaver",
                              "Wagner", "Wadd", "Withers", "Whitby", "Woodland", "Woody", "Xavier", "Xanders", "Xang",
                              "Ximinez", "Xie", "Xenakis", "Xu", "Xiang", "Xuxa", "Yearwood", "Yellen", "Yaeger",
                              "Yankovich", "Yamaguchi", "Yarborough", "Youngblood", "Yanetta", "Yadao", "Yale",
                              "Yasumoto", "Yates", "Younger", "Yoakum", "York", "Yount", "Zuckerberg", "Zeck",
                              "Zavaroni", "Zeller", "Zipser", "Zedillo", "Zook", "Zeigler", "Zimmerman", "Zeagler",
                              "Zale", "Zasso", "Zant", "Zappa", "Zapf", "Zahn", "Zabinski", "Zade", "Zabik", "Zader",
                              "Zukoff", "Zullo", "Zmich", "Zoller"]
            race_list = ["Human", "Elf", "Dwarf", "Gnome", "Troll", "Elemental", "Orc", "Angel", "Demon", "Vampire",
                         "Shadow walker", "Deity", "Xendorian", "Archangel", "Archdemon", "Undead", "Drow", "Ghost",
                         "Dragon", "Werewolf", "Fairy", "Dark Fairy", "Pixie", "Shifter", "Merperson",
                         "Sentient animal", "Goblin", "Halfling", "Kitsune", "Centaur", "Satyr", "Dryad", "Nightmare",
                         "Incarnate", "Death walker", "Yeti", "Wendigo", "Monster", "High Elf", "Wood Elf", "Dark Elf",
                         "Manticore", "Gryphon", "Phoenix", "Ent"]
            height_min_feet = 4
            height_max_feet = 6
            height_inches_max = 11
            weight_min = 90
            weight_max = 250
            age_min = 18
            age_max = 2000
            occupation_list = []
            occupation_list = ["Warrior", "Knight", "Hunter", "Blacksmith", "Noble", "Royalty", "Slave", "Mercenary",
                               "Caster", "Mage", "Wizard", "Warlock", "Protector", "Healer", "Medium", "Psychic",
                               "Assassin", "Swordsman", "Thief", "Cobbler", "Potion maker", "Preacher", "Priest",
                               "Paladin", "Witch", "Warlock", "Sorcerer", "Servant", "Escort", "Prostitute", "Solider",
                               "Bartender", "Merchant", "Sailor", "Pirate", "Archer", "Guard", "Slayer", "Alchemist",
                               "Apothecary", "Shopkeeper", "Trader", "Wizard", "Fighter", "Teacher", "Physician",
                               "Philosopher", "Farmer", "Shepherd", "Harbinger", "Messenger", "Horserider", "Chef",
                               "Night watch", "None", "Beggar", "Researcher", "Advisor", "Judge", "Executioner",
                               "Commander", "Captain", "Fisher", "Ranchhand", "Druid"]
            gender_list = ["Male", "Female", "Non-binary", "Genderfluid"]
            origin_list = ["Unknown", "Earth", "Rhydin", "Offworld"]
            powers_list = ["Psychic", "Lightning", "Light", "Healing", "Destruction", "Darkness", "Telepathy",
                           "Psychokinesis", "Flight", "Storms", "Water", "Air", "Wind", "Earth", "Fire",
                           "Talking to the dead", "Plane-walking", "Illusion", "Glamor", "Holy", "White Magic",
                           "Black Magic", "Seduction", "Speed", "Superhuman strength", "Immortality",
                           "Energy manipulation", "Reality warping", "Spaceflight", "Cloaking", "Shadow"]
            strengths_list = ["Melee combat", "Magic", "Physical strength", "Physical speed", "Highly intelligent",
                              "Expert swordfighter", "Martial arts", "Strategic", "Charismatic", "Highly perceptive",
                              "Expert with firearms", "Expert archer", "Resistant to magic"]
            weaknesses_list = ["Black magic", "Light", "Holy power", "Evil power", "Easily seduced", "Gullible",
                               "Socially manipulatable", "Low intelligence", "Fire", "Water", "Lightning", "Darkness",
                               "Shadow", "Astral attacks", "Weak physically", "Lost immortality", "Reduced powers",
                               "Trauma in past", "Phobias", "Anxiety", "Poor training", "Little magical capacity"]
            personality_list = ["Warm", "Cold", "Aloof", "Caring", "Gregarious", "Affable", "Talkative",
                                "Strong, silent type", "Brash", "Boisterous", "Lazy", "Shy", "Fearful",
                                "Happy-go-lucky", "Perky", "Perverted", "Sociopathic", "Formal", "Casual", "Creative",
                                "Nice", "Mean", "Rude", "Kind", "Gentle", "Harsh", "Asexual", "Wild in bed", "Stoic",
                                "Charismatic", "Charming", "Romantic", "Detached", "Depressed", "Worrywart",
                                "Troubled by their past", "Carries a grudge", "Loving", "Hateful", "Spiteful", "Angry",
                                "Short fuse", "Patient", "Passionate", "Empty"]
            skills_list = ["Archery", "Swordplay", "Reading", "Writing", "Science", "Technology", "Music",
                           "Telling jokes", "Lying when needed", "Magic", "Alchemy", "Healing", "Medicine", "Potions",
                           "Elixirs", "Chemistry", "Knowledge of the beyond", "Master illusionist", "Computers",
                           "Mixing drinks", "Telling stories", "Inspiring others", "Leading", "Fighting", "Organizing",
                           "Art", "Scuplting", "Crafts", "Metalworking", "Buidling structures", "Tinkering"]

            gender_picker = random.randint(1, 20)
            if gender_picker >= 1 and gender_picker <= 9:
                gender = "Male"
            elif gender_picker >= 10 and gender_picker <= 18:
                gender = "Female"
            else:
                gender = "Genderfluid"

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
                age = random.randint(18, 100)
            else:
                age = random.randint(age_min, age_max)

            origin = random.choice(origin_list)
            height_feet = random.randint(height_min_feet, height_max_feet)
            height_inches = random.randint(0, 11)
            weight = random.randint(weight_min, weight_max)

            number_of_strengths = random.randint(1, 5)
            strengths = ""
            for x in range(0, number_of_strengths):
                strengths = strengths + random.choice(strengths_list) + ", "
            number_of_weaknesses = random.randint(1, 5)
            weaknesses = ""
            for x in range(0, number_of_weaknesses):
                weaknesses = weaknesses + random.choice(weaknesses_list) + ", "
            powers = ""

            number_of_powers = random.randint(1, 3)
            for x in range(0, number_of_powers):
                powers = powers + random.choice(powers_list) + ", "
            number_of_skills = random.randint(1, 5)
            skills = ""
            for x in range(0, number_of_skills):
                skills = skills + random.choice(skills_list) + ", "
            personality = ""
            number_of_personality = random.randint(2, 6)
            for x in range(0, number_of_personality):
                personality = personality + random.choice(personality_list) + ", "

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'randomprofile'
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterName", "Age", "Race", "Gender", "Height", "Weight",
                                                          "Playedby", "Origin", "Occupation", "PictureLink", "Attack",
                                                          "Defense", "MagicAttack", "Health", "Mana", "Stamina",
                                                          "Agility", "Intellect", "Charisma", "Currency", "Level",
                                                          "Experience", "StatPoints","MaxHealth","MaxMana","MaxStamina"]

            dm_tracker[message.author.id]["currentfield"] = 0
            server_id = message.guild.id
            dm_tracker[message.author.id]["fielddict"] = [first_name + " " + last_name, str(age), race, gender,  str(height_feet) + "'" + str(height_inches) + r"\"", str(weight) + " lbs", "None", origin, occupation, "None", str(guild_settings[server_id]["StartingAttack"]), str(guild_settings[server_id]["StartingDefense"]),str(guild_settings[server_id]["StartingMagicAttack"]), str(guild_settings[server_id]["StartingHealth"]),   str(guild_settings[server_id]["StartingMana"]), str(guild_settings[server_id]["StartingStamina"]),  str(guild_settings[server_id]["StartingIntellect"]), str(guild_settings[server_id]["StartingCharisma"]), str(1000), str(1), str(0), str(0), str(guild_settings[server_id]["StartingHealth"]),  str(guild_settings[server_id]["StartingMana"]), str(guild_settings[server_id]["StartingStamina"])]

            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            counter = 0
            embed = discord.Embed(title="New Random Character",
                                  description="Reply to the DM to apply with this character.")

            response = "**RANDOM CHARACTER INFORMATION**\n\n"
            for field in dm_tracker[message.author.id]["fieldlist"]:
                embed.add_field(name=field, value=dm_tracker[message.author.id]["fielddict"][counter])
                response = response + "**" + field + ":** " + dm_tracker[message.author.id]["fielddict"][counter] + "\n"
                counter = counter + 1

            # await reply_message(message, response)
            await message.channel.send(embed=embed)

            await direct_message(message,
                                 "Would you like to add this character to the applicant characters list? Respond **YES** to apply, anything else to discard.")
        elif command == 'wallet':
            if not parsed_string:
                await reply_message(message, "You didn't specify a character!")
                return
            records = await select_sql(
                """SELECT Currency,PictureLink FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s;""",
                (str(message.guild.id), str(parsed_string)))
            if not records:
                await reply_message(message, "That character was not found!")
                return

            for row in records:
                currency = row[0]
                picture_link = row[1]

            embed = discord.Embed(title=parsed_string + "'s wallet")
            embed.add_field(name="Currency", value=currency)
            if re.search(r"http", picture_link):
                embed.set_thumbnail(url=picture_link)
            await message.channel.send(embed=embed)


        elif command == 'givestatpoints':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must have the GM role to give stat points.")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'givestatpoints'
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterId", "Points"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Please choose a character from the below to give available points to:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please see your DMs for instructions on how to give stat points, <@" + str(
                message.author.id) + ">.")
        elif command == 'givexp':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must have the GM role to give stat points.")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'givexp'
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterId", "XP"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Please choose a character from the below to give available points to:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please see your DMs for instructions on how to give stat points, <@" + str(
                message.author.id) + ">.")
        elif (command == 'stats'):

            char_name = parsed_string

            if not char_name:
                await reply_message(message, "No character name specified!")
                return
            get_character_profile = """SELECT CharacterName,IFNULL(Age,' '),IFNULL(Race,' '), IFNULL(Gender,' '), IFNULL(Height,' '), IFNULL(Weight,' '), IFNULL(PlayedBy,' '), IFNULL(Origin,' '), IFNULL(Occupation,' '), UserId,Attack,Defense,MagicAttack,Health,Mana,Level,Experience,Stamina,Agility,Intellect,Charisma,StatPoints,Currency,PictureLink,IFNULL(Class,' ') FROM CharacterProfiles WHERE CharacterName=%s  AND ServerId=%s;"""
            char_tuple = (char_name, str(message.guild.id))

            records = await select_sql(get_character_profile, char_tuple)
            if not records:
                await reply_message(message, "No character found by that name!")
                return
            embed = discord.Embed(title="Character Profile for " + char_name)
            embed2 = discord.Embed(title="Character Statistics for " + char_name)

            for row in records:
                if re.search(r"http", row[23]):
                    embed.set_thumbnail(url=row[23])
                char_id = row[24]
                attack = int(row[10])
                defense = int(row[11])
                magic_attack = int(row[12])
                agility = int(row[18])
                intellect = int(row[19])
                charisma = int(row[20])
                health = int(row[13])
                mana = int(row[14])
                stamina = int(row[15])
                stat_records = await select_sql(
                    """SELECT IFNULL(HeadId,'None'),IFNULL(ChestId,'None'),IFNULL(LeftHandId,'None'),IFNULL(RightHandId,'None'),IFNULL(FeetId,'None'),IFNULL(FormId,'None') FROM CharacterArmaments WHERE CharacterId=%s;""",
                    (str(char_id),))
                if stat_records:
                    for stat_row in stat_records:

                        for x in range(0, len(stat_row)):
                            item = stat_row[x]
                            if item != 'None':
                                arm_records = await select_sql(
                                    """SELECT MinimumLevel,Defense,StatMod,Modifier FROM Armaments WHERE Id=%s;""",
                                    (str(item),))
                                for arm_row in arm_records:
                                    if int(arm_row[0]) <= int(row[15]):
                                        if arm_row[2] == 'Attack':
                                            attack = attack + int(arm_row[3])
                                        elif arm_row[2] == 'Defense':
                                            defense = defense + int(arm_row[3])
                                        elif arm_row[2] == 'MagicAttack':
                                            magic_attack = magic_attack + int(arm_row[3])
                                        elif arm_row[2] == 'Intellect':
                                            intellect = intellect + int(arm_row[3])
                                        elif arm_row[2] == 'Charisma':
                                            charisma = charisma + int(arm_row[3])
                                        elif arm_row[2] == 'Agility':
                                            agility = agility + int(arm_row[3])
                                        elif arm_row[2] == 'Health':
                                            health = health + int(arm_row[3])
                                        elif arm_row[2] == 'Stamina':
                                            stamina = stamina + int(arm_row[3])
                                        elif arm_row[2] == 'Mana':
                                            mana = mana + int(arm_row[3])

                embed.add_field(name="Player:", value="<@" + str(row[9]) + ">")
                embed.add_field(name="Age:", value=str(row[1]))
                embed.add_field(name="Race:", value=row[2])
                embed.add_field(name="Gender:", value=row[3])
                embed.add_field(name="Height:", value=row[4])
                embed.add_field(name="Weight:", value=row[5])
                embed.add_field(name="PlayedBy:", value=row[6])
                embed.add_field(name="Origin:", value=row[7])
                embed.add_field(name="Occupation:", value=row[8])
                embed.add_field(name="Class:", value=row[24])

                embed2.add_field(name="Level:", value=str(row[15]))
                embed2.add_field(name="Experience:", value=str(row[16]))
                embed2.add_field(name="Health:", value=str(row[13]))
                embed2.add_field(name="Mana:", value=str(row[14]))
                embed2.add_field(name="Stamina:", value=str(row[17]))
                embed2.add_field(name="Melee Attack:", value=str(row[10]))
                embed2.add_field(name="Defense:", value=str(row[11]))
                embed2.add_field(name="Magic Attack:", value=str(row[12]))
                embed2.add_field(name="Agility:", value=str(row[18]))
                embed2.add_field(name="Intellect:", value=str(row[19]))
                embed2.add_field(name="Charisma:", value=str(row[20]))
                embed2.add_field(name="Currency:", value=str(row[22]))
                embed2.add_field(name="Stat Points:", value=str(row[21]))
                await log_message(str(embed2))

            temp_webhook = await message.channel.create_webhook(name='Chara-Tron')
            await temp_webhook.send(embeds=[embed2], username="RP Mastermind")
            await temp_webhook.delete()
        elif (command == 'profile'):

            char_name = parsed_string

            if not char_name:
                await reply_message(message, "No character name specified!")
                return
            #            get_character_profile = """SELECT CharacterName,IFNULL(Age,' '),IFNULL(Race,' '), IFNULL(Gender,' '), IFNULL(Height,' '), IFNULL(Weight,' '), IFNULL(PlayedBy,' '), IFNULL(Origin,' '), IFNULL(Occupation,' '), UserId,Attack,Defense,MagicAttack,Health,Mana,Level,Experience,Stamina,Agility,Intellect,Charisma, IFNULL(Biography,' '), IFNULL(Currency,' '), IFNULL(Description,' '), IFNULL(Personality,' '), IFNULL(Powers,' '), IFNULL(Strengths,' '), IFNULL(Weaknesses,' '), IFNULL(Skills,' '), IFNULL(PictureLink,' '),StatPoints,IFNULL(Status,'None'),Id,IFNULL(Class,' ') FROM CharacterProfiles WHERE CharacterName=%s  AND ServerId=%s;"""
            get_character_profile = """SELECT CharacterName,IFNULL(Age,' '),IFNULL(Race,' '), IFNULL(Gender,' '), IFNULL(Height,' '), IFNULL(Weight,' '), IFNULL(PlayedBy,' '), IFNULL(Origin,' '), IFNULL(Occupation,' '), UserId,Attack,Defense,MagicAttack,Health,Mana,Level,Experience,Stamina,Agility,Intellect,Charisma, IFNULL(PictureLink,' '),StatPoints,IFNULL(Status,'None'),Id,IFNULL(Class,'None'),Currency,MaxHealth,MaxStamina,MaxMana FROM CharacterProfiles WHERE CharacterName=%s  AND ServerId=%s;"""
            char_tuple = (char_name, str(message.guild.id))

            records = await select_sql(get_character_profile, char_tuple)
            if len(records) < 1:
                await reply_message(message, "No character found by that name!")
                return
            embed = discord.Embed(title="Character Profile for " + char_name)
            embed2 = discord.Embed(title="Character Statistics for " + char_name)

            for row in records:
                if re.search(r"http", row[21]):
                    embed.set_thumbnail(url=row[21])
                char_id = row[24]
                attack = int(row[10])
                defense = int(row[11])
                magic_attack = int(row[12])
                agility = int(row[18])
                intellect = int(row[19])
                charisma = int(row[20])
                health = int(row[13])
                mana = int(row[14])
                stamina = int(row[17])
                max_health = int(row[27])
                max_stamina = int(row[28])
                max_mana = int(row[29])
                stat_records = await select_sql(
                    """SELECT IFNULL(HeadId,'None'),IFNULL(ChestId,'None'),IFNULL(LeftHandId,'None'),IFNULL(RightHandId,'None'),IFNULL(FeetId,'None'),IFNULL(FormId,'None') FROM CharacterArmaments WHERE CharacterId=%s;""",
                    (str(char_id),))
                if stat_records:
                    for stat_row in stat_records:

                        for x in range(0, len(stat_row)):
                            item = stat_row[x]
                            if item != 'None':
                                arm_records = await select_sql(
                                    """SELECT MinimumLevel,Defense,StatMod,Modifier FROM Armaments WHERE Id=%s;""",
                                    (str(item),))
                                for arm_row in arm_records:
                                    if int(arm_row[0]) <= int(row[15]):
                                        if arm_row[2] == 'Attack':
                                            attack = attack + int(arm_row[3])
                                        elif arm_row[2] == 'MagicAttack':
                                            magic_attack = magic_attack + int(arm_row[3])
                                        elif arm_row[2] == 'Intellect':
                                            intellect = intellect + int(arm_row[3])
                                        elif arm_row[2] == 'Charisma':
                                            charisma = charisma + int(arm_row[3])
                                        elif arm_row[2] == 'Agility':
                                            agility = agility + int(arm_row[3])
                                        elif arm_row[2] == 'MaxHealth':
                                            max_health = max_health + int(arm_row[3])
                                        elif arm_row[2] == 'MaxStamina':
                                            max_stamina = max_stamina + int(arm_row[3])
                                        elif arm_row[2] == 'MaxMana':
                                            max_mana = max_mana + int(arm_row[3])
                                    defense = defense + int(arm_row[1])

                embed.add_field(name="Player:",
                                value="`" + discord.utils.get(message.guild.members, id=int(row[9])).name + "`")
                embed.add_field(name="Age:", value=str(row[1]))
                embed.add_field(name="Race:", value=row[2])
                embed.add_field(name="Class:", value=row[25])
                embed.add_field(name="Gender:", value=row[3])
                embed.add_field(name="Height:", value=row[4])
                embed.add_field(name="Weight:", value=row[5])
                embed.add_field(name="PlayedBy:", value=row[6])
                embed.add_field(name="Origin:", value=row[7])
                embed.add_field(name="Occupation:", value=row[8])

                embed2.add_field(name="Level:", value=str(row[15]))
                embed2.add_field(name="Experience:", value=str(row[16]))
                embed2.add_field(name="Health:", value=str(health) + "/" + str(max_health))
                embed2.add_field(name="Mana:", value=str(mana) + "/" + str(max_mana))
                embed2.add_field(name="Stamina:", value=str(stamina) + "/" + str(max_stamina))
                embed2.add_field(name="Melee Attack:", value=str(attack))
                embed2.add_field(name="Defense:", value=str(defense))
                embed2.add_field(name="Magic Attack:", value=str(magic_attack))
                embed2.add_field(name="Agility:", value=str(agility))
                embed2.add_field(name="Intellect:", value=str(intellect))
                embed2.add_field(name="Charisma:", value=str(charisma))
                embed2.add_field(name="Currency:", value=str(row[26]))
                embed2.add_field(name="Stat Points:", value=str(row[22]))
                embed2.add_field(name="Status:", value=str(row[23].split('=')[0]))
            #                embed3 = discord.Embed(title="Biography",description=row[21])
            #                embed4 = discord.Embed(title="Description",description=row[23])
            #                embed5 = discord.Embed(title="Personality",description=row[24])
            #                embed6 = discord.Embed(title="Powers",description=row[25])
            #               embed7 = discord.Embed(title="Strengths",description=row[26])
            #               embed8 = discord.Embed(title="Weaknesses",description=row[27])
            #                embed9 = discord.Embed(title="Skills",description=row[28])
            temp_webhook = await message.channel.create_webhook(name='Chara-Tron')
            await temp_webhook.send(embeds=[embed, embed2], username="RP Mastermind", avatar_url=client.user.avatar_url)
            await temp_webhook.delete()
            asyncio.sleep(1)
        #            await reply_message(message, "**Biography**:\n\n" + row[21] + "\n**Description:**\n\n" + row[23] + "\n**Personality:**\n\n" + row[24] + "\n**Powers:**\n\n" + row[25] + "\n**Strengths:**\n\n" + row[26] + "\n**Weaknesses:**\n\n" + row[27] + "\n**Skills:**\n\n" + row [28])
        #                await message.channel.send(embed=embed)
        #               await asyncio.sleep(1)
        #               await message.channel.send(embed=embed2)

        #                    response = "***CHARACTER PROFILE***\n\n**Mun:** <@" + str(row[9]) + ">\n**Name:** " + row[0] + "\n**Age:** " + str(row[1]) + "\n**Race:** "+ row[2] + "\n**Gender:** " +row[3] + "\n**Height:** " + row[4] +  "\n**Weight:** " + row[5] +  "\n**Played by:** " + row[6] + "\n**Origin:** " + row[7] + "\n**Occupation:** " + row[8] + "\n\n**STATS**\n\n**Health:** " + str(row[13]) + "\n**Mana:** " + str(row[14]) + "\n**Attack:** " + str(row[10]) + "\n**Defense:** " + str(row[11]) + "\n**Magic Attack Power:** " + str(row[12]) + "\n**Level:** " + str(row[15]) + "\n**Experience:** " + str(row[16]) + "\n**Stamina:** " + str(row[17]) + "\n**Agility:** " + str(row[18]) + "\n**Intellect:** " + str(row[19]) + "\n**Charisma:** " + str(row[20]) + "\n**Currency:** " + str(row[22])+  "\n\n**ADDITIONAL INFORMATION**\n\n**Biography:** " + row[21] + "\n**Description:**" + row[23] + "\n**Personality:** " + row[24] + "\n**Powers:** " + row[25] + "\n**Strengths:** " + row[26] + "\n**Weaknesses:** " + row[27] + "\n**Skills:** " + row[28] + "\n\n**PICTURE**\n\n" + row[29] + "\n"
        #                await reply_message(message, response)

        elif command == 'pending':
            char_name = parsed_string

            if not char_name:
                await reply_message(message, "No character name specified!")
                return
            #            get_character_profile = """SELECT CharacterName,IFNULL(Age,' '),IFNULL(Race,' '), IFNULL(Gender,' '), IFNULL(Height,' '), IFNULL(Weight,' '), IFNULL(PlayedBy,' '), IFNULL(Origin,' '), IFNULL(Occupation,' '), UserId,Attack,Defense,MagicAttack,Health,Mana,Level,Experience,Stamina,Agility,Intellect,Charisma, IFNULL(Biography,' '), IFNULL(Currency,' '), IFNULL(Description,' '), IFNULL(Personality,' '), IFNULL(Powers,' '), IFNULL(Strengths,' '), IFNULL(Weaknesses,' '), IFNULL(Skills,' '), IFNULL(PictureLink,' '),StatPoints,IFNULL(Status,'None'),Id,IFNULL(Class,' ') FROM CharacterProfiles WHERE CharacterName=%s  AND ServerId=%s;"""
            get_character_profile = """SELECT CharacterName,IFNULL(Age,' '),IFNULL(Race,' '), IFNULL(Gender,' '), IFNULL(Height,' '), IFNULL(Weight,' '), IFNULL(PlayedBy,' '), IFNULL(Origin,' '), IFNULL(Occupation,' '), UserId,Attack,Defense,MagicAttack,Health,Mana,Level,Experience,Stamina,Agility,Intellect,Charisma, IFNULL(PictureLink,' '),StatPoints,IFNULL(Status,'None'),Id,IFNULL(Class,' '),Currency FROM UnapprovedCharacterProfiles WHERE CharacterName=%s  AND ServerId=%s;"""
            char_tuple = (char_name, str(message.guild.id))

            records = await select_sql(get_character_profile, char_tuple)
            if len(records) < 1:
                await reply_message(message, "No character found by that name!")
                return
            embed = discord.Embed(title="Character Profile for " + char_name)
            embed2 = discord.Embed(title="Character Statistics for " + char_name)

            for row in records:
                if re.search(r"http", row[21]):
                    embed.set_thumbnail(url=row[21])
                char_id = row[24]
                attack = int(row[10])
                defense = int(row[11])
                magic_attack = int(row[12])
                agility = int(row[18])
                intellect = int(row[19])
                charisma = int(row[20])
                health = int(row[13])
                mana = int(row[14])
                stamina = int(row[15])
                stat_records = await select_sql(
                    """SELECT IFNULL(HeadId,'None'),IFNULL(ChestId,'None'),IFNULL(LeftHandId,'None'),IFNULL(RightHandId,'None'),IFNULL(FeetId,'None'),IFNULL(FormId,'None') FROM CharacterArmaments WHERE CharacterId=%s;""",
                    (str(char_id),))
                if stat_records:
                    for stat_row in stat_records:

                        for x in range(0, len(stat_row)):
                            item = stat_row[x]
                            if item != 'None':
                                arm_records = await select_sql(
                                    """SELECT MinimumLevel,Defense,StatMod,Modifier FROM Armaments WHERE Id=%s;""",
                                    (str(item),))
                                for arm_row in arm_records:
                                    if int(arm_row[0]) <= int(row[15]):
                                        if arm_row[2] == 'Attack':
                                            attack = attack + int(arm_row[3])
                                        elif arm_row[2] == 'Defense':
                                            defense = defense + int(arm_row[3])
                                        elif arm_row[2] == 'MagicAttack':
                                            magic_attack = magic_attack + int(arm_row[3])
                                        elif arm_row[2] == 'Intellect':
                                            intellect = intellect + int(arm_row[3])
                                        elif arm_row[2] == 'Charisma':
                                            charisma = charisma + int(arm_row[3])
                                        elif arm_row[2] == 'Agility':
                                            agility = agility + int(arm_row[3])
                                        elif arm_row[2] == 'Health':
                                            health = health + int(arm_row[3])
                                        elif arm_row[2] == 'Stamina':
                                            stamina = stamina + int(arm_row[3])
                                        elif arm_row[2] == 'Mana':
                                            mana = mana + int(arm_row[3])

                embed.add_field(name="Player:",
                                value="`" + discord.utils.get(message.guild.members, id=int(row[9])).name + "`")
                embed.add_field(name="Age:", value=str(row[1]))
                embed.add_field(name="Race:", value=row[2])
                embed.add_field(name="Class:", value=row[24])
                embed.add_field(name="Gender:", value=row[3])
                embed.add_field(name="Height:", value=row[4])
                embed.add_field(name="Weight:", value=row[5])
                embed.add_field(name="PlayedBy:", value=row[6])
                embed.add_field(name="Origin:", value=row[7])
                embed.add_field(name="Occupation:", value=row[8])

                embed2.add_field(name="Level:", value=str(row[15]))
                embed2.add_field(name="Experience:", value=str(row[16]))
                embed2.add_field(name="Health:", value=str(health))
                embed2.add_field(name="Mana:", value=str(mana))
                embed2.add_field(name="Stamina:", value=str(stamina))
                embed2.add_field(name="Melee Attack:", value=str(attack))
                embed2.add_field(name="Defense:", value=str(defense))
                embed2.add_field(name="Magic Attack:", value=str(magic_attack))
                embed2.add_field(name="Agility:", value=str(agility))
                embed2.add_field(name="Intellect:", value=str(intellect))
                embed2.add_field(name="Charisma:", value=str(charisma))
                embed2.add_field(name="Currency:", value=str(row[26]))
                embed2.add_field(name="Stat Points:", value=str(row[22]))
                embed2.add_field(name="Status:", value=str(row[23].split('=')[0]))
            #                embed3 = discord.Embed(title="Biography",description=row[21])
            #                embed4 = discord.Embed(title="Description",description=row[23])
            #                embed5 = discord.Embed(title="Personality",description=row[24])
            #                embed6 = discord.Embed(title="Powers",description=row[25])
            #               embed7 = discord.Embed(title="Strengths",description=row[26])
            #               embed8 = discord.Embed(title="Weaknesses",description=row[27])
            #                embed9 = discord.Embed(title="Skills",description=row[28])
            temp_webhook = await message.channel.create_webhook(name='Chara-Tron')
            await temp_webhook.send(embeds=[embed, embed2], username="RP Mastermind", avatar_url=client.user.avatar_url)
            await temp_webhook.delete()
            asyncio.sleep(1)
        #   await temp_webhook.delete()
        #               response = "***UNAPPROVED CHARACTER PROFILE***\n\n**Mun:** <@" + str(row[9]) + ">\n**Name:** " + row[0] + "\n**Age:** " + str(row[1]) + "\n**Race:** "+ row[2] + "\n**Gender:** " +row[3] + "\n**Height:** " + row[4] +  "\n**Weight:** " + row[5] +  "\n**Played by:** " + row[6] + "\n**Origin:** " + row[7] + "\n**Occupation:** " + row[8] + "\n\n**STATS**\n\n**Health:** " + str(row[13]) + "\n**Mana:** " + str(row[14]) + "\n**Attack:** " + str(row[10]) + "\n**Defense:** " + str(row[11]) + "\n**Magic Attack Power:** " + str(row[12]) + "\n**Level:** " + str(row[15]) + "\n**Experience:** " + str(row[16]) + "\n**Stamina:** " + str(row[17]) + "\n**Agility:** " + str(row[18]) + "\n**Intellect:** " + str(row[19]) + "\n**Charisma:** " + str(row[20]) + "\n**Currency:** " + str(row[22])+  "\n\n**ADDITIONAL INFORMATION**\n\n**Biography:** " + row[21] + "\n**Description:**" + row[23] + "\n**Personality:** " + row[24] + "\n**Powers:** " + row[25] + "\n**Strengths:** " + row[26] + "\n**Weaknesses:** " + row[27] + "\n**Skills:** " + row[28] + "\n\n**PICTURE**\n\n" + row[29] + "\n"
        #            await reply_message(message, response)
        elif command == 'change':
            user_id = message.author.id
            server_id = message.guild.id
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must have the player role to edit a character.")
                return
            if not parsed_string:
                await reply_message(message, "No character name specified!")
                return
            char_name = parsed_string
            current_fields = await select_sql(
                """SELECT Age,Race,Gender,Height,Weight,Playedby,Origin,Occupation,Class,PictureLink FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""",
                (str(message.guild.id), char_name))
            if not current_fields:
                await reply_message(message, "No character found by that name!")
                return
            records = await select_sql(
                """SELECT UserId FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s """,
                (str(message.guild.id), char_name))
            for row in records:
                char_user_id = int(row[0])
            if char_user_id != message.author.id:
                await reply_message(message, "This isn't your character!")
                return
            for row in current_fields:
                fields = row

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterName", "Age", "Race", "Gender", "Height", "Weight",
                                                          "Playedby", "Origin", "Occupation", "Class", "PictureLink"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["fielddict"].append(parsed_string)
            dm_tracker[message.author.id]["fieldmeans"] = ["Name of the character", "The age of the character",
                                                           "The race of the character (human, vampire, etc)",
                                                           "The gender, if known of the character (male, female, etc)",
                                                           "The usual height of the character, if known (5'5'', 10 cubits, etc)",
                                                           "The mass on the current world of the character (180 lbs, five tons, etc)",
                                                           "The name of the artist, human representation, actor, etc who is used to show what the character looks like (Angelina Jolie, Brad Pitt, etc)",
                                                           "The hometown or homeworld of the character (Texas, Earth, Antares, etc)",
                                                           "What the character does for a living, if applicable (blacksmith, mercenary, prince, etc)",
                                                           "The class of the character",
                                                           "A direct upload or http link to a publicly accessible picture on the Internet (None for no link). Google referral links don't always work"]
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

            await reply_message(message, "Please check your DMs for instructions on how to edit a character, <@" + str(
                message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested to edit the character **" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the character will be updated!\nThe first field is **" +
                                 dm_tracker[message.author.id]["fieldlist"][0] + "** and its current value is **" +
                                 dm_tracker[message.author.id]["fielddict"][0] + "**.")

        elif command == 'newcustomcommand':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to create new custom commands!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newcustomcommand'
            dm_tracker[message.author.id]["fieldlist"] = ["Command", "Responses"]
            dm_tracker[message.author.id]["fieldmeans"] = ["The command typed after the = prefix.",
                                                           "The responses for each random choice."]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            await reply_message(message,
                                "Please check your DMs for instructions on how to create a new custom command, <@" + str(
                                    message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested a new custom command! Please type in the name you want, and then fill out the fields that appear.")
        elif command == 'editcustomcommand':
            pass
        elif command == 'deletecustomcommand':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to delete new custom commands!")
                return
            if not parsed_string:
                await reply_message(message, "You didn't specify a custom command to delete!")
                return
            try:
                custom_commands[message.guild.id][parsed_string]
            except:
                await reply_message(message, "That command was not found!")
                return

            custom_commands[message.guild.id][parsed_string].clear()
            del custom_commands[message.guild.id][parsed_string]
            result = await commit_sql("""DELETE FROM CustomCommands WHERE ServerId=%s AND Command=%s;""",
                                      (str(message.guild.id), parsed_string))
            await reply_message(message, "Custom command " + parsed_string + " deleted.")

        elif command == 'listmychars':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must have the player role to list characters.")
                return
            records = await select_sql(
                """SELECT CharacterName,Level FROM CharacterProfiles WHERE ServerId=%s AND UserId=%s;""",
                (str(message.guild.id), str(message.author.id)))
            if not records:
                await reply_message(message, "You don't have any characters! Use =create to create a character!")
                return
            response = "**Characters for " + message.author.name + ":**\n\n"
            for row in records:
                response = response + row[0] + " Level: " + str(row[1]) + "\n"
            await reply_message(message, response)
        elif command == 'skills':
            if not parsed_string:
                await reply_message(message, "No character name specified!")
                return
            char_name = parsed_string
            embed = discord.Embed(title="Character Skills for " + char_name)

            response = "***CHARACTER SKILLS***\n\n**Character Name:** " + char_name + "\n\n**MAGIC SKILLS**\n\n"
            records = await select_sql("""SELECT Id FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""",
                                       (str(message.guild.id), char_name))
            if not records:
                await reply_message(message, "No character found with that name!")
                return
            for row in records:
                char_id = row[0]
            spells = ""
            records = await select_sql("""SELECT SpellId FROM MagicSkills WHERE CharacterId=%s;""", (char_id,))
            for row in records:
                spell_records = await select_sql("""SELECT SpellName FROM Spells WHERE Id=%s;""", (row[0],))
                for spell_row in spell_records:
                    spells = spells + spell_row[0] + "\n"
                    # response = response + spell_row[0] + "\n"
            if not records:
                spells = "None"
            embed.add_field(name="Spells", value=spells)
            response = response + "\n**MELEE SKILLS**\n\n"
            melees = ""
            records = await select_sql("""Select MeleeId FROM MeleeSkills WHERE CharacterId=%s""", (char_id,))
            for row in records:
                attack_records = await select_sql("""SELECT AttackName FROM Melee WHERE Id=%s""", (row[0],))
                for attack_row in attack_records:
                    melees = melees + attack_row[0] + "\n"
            #                   response = response + attack_row[0] + "\n"
            if not records:
                melees = "None"
            embed.add_field(name="Melee Skills", value=melees)
            response = response + "\n**BUFF SKILLS**\n\n"
            buffs = ""
            records = await select_sql("""Select BuffId FROM BuffSkills WHERE CharId=%s""", (char_id,))
            for row in records:
                attack_records = await select_sql("""SELECT BuffName FROM Buffs WHERE Id=%s""", (row[0],))
                for attack_row in attack_records:
                    response = response + attack_row[0] + "\n"
                    buffs = buffs + attack_row[0] + "\n"
            if not records:
                buffs = "None"
            embed.add_field(name="Buffs", value=buffs)
            await message.channel.send(embed=embed)

            # await reply_message(message, response)
        elif (command == 'editstats'):
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to modify character statistics!")
                return
            user_id = message.author.id
            server_id = message.guild.id

            char_name = parsed_string
            current_fields = await select_sql(
                """SELECT Attack,Defense,MagicAttack,Health,MaxHealth,Mana,MaxMana,Level,Experience,Stamina,MaxStamina,Agility,Intellect,Charisma FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""",
                (str(message.guild.id), char_name))
            if not current_fields:
                await reply_message(message, "No character found by that name!")
                return
            records = await select_sql(
                """SELECT UserId FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s """,
                (str(message.guild.id), char_name))
            for row in records:
                char_user_id = int(row[0])

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Attack", "Defense", "MagicAttack", "Health", "MaxHealth",
                                                          "Mana", "MaxMana", "Level",
                                                          "Experience", "Stamina", "MaxStamina", "Agility", "Intellect",
                                                          "Charisma"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["fieldmeans"] = [
                "The base number for melee combat damage. Multiplied by the melee damage multiplier",
                "The total defense against all damage the character has. Subtracted from damage",
                "The base number for spell damage. Multiplied by the spell damage multiplier",
                "The amount of health a character has. When this reaches zero during sparring or monster encounters, the player is out of the group. Can be restored by buffs or items",
                "The maximum health of the character.",
                "The amount of mana for spells. When this reaches zero, a character must pass, use melee attacks or an item",

                "The maximmum mana of the character.",
                "The character's current level, which determines health, mana and stamina. Also determines the experience gained by combat with characters or monsters of different levels",
                "The amount of experience a character has. To level up, a character must earn 20 times (default) their current level in experience points",
                "The amount of stamina a character has for melee combat. When this reaches zero, a chracter must pass or use a spell or item",
                "The maximum stamina of the character.",
                "How likely a character is to dodge an attack. Higher agility means greater speed", "The amount of defense against magic spells a character has.",
                "How likely a discount is from a vendor."]
            dm_tracker[message.author.id]["currentcommand"] = 'editstats'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(current_fields[0][counter])
                counter = counter + 1

            await reply_message(message,
                                "Please check your DMs for instructions on how to edit character stats, <@" + str(
                                    message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested to edit the character statistics of **" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the character will be updated!\nThe first field is **" +
                                 dm_tracker[message.author.id]["fieldlist"][0] + "** and its current value is **" + str(
                                     dm_tracker[message.author.id]["fielddict"][0]) + "**.")

        elif command == 'remove':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author) and not role_check(
                    guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be member of the player role to delete a character!")
                return

            if not parsed_string:
                await reply_message(message, "No character specified!")
                return

            char_name = parsed_string

            records = await select_sql(
                """SELECT UserId,Id FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""",
                (str(message.guild.id), char_name))
            if not records:
                await reply_message(message, "That character does not exist!")
                return
            for row in records:
                user_id = int(row[0])
                char_id = row[1]
            if user_id != message.author.id and not role_check(guild_settings[message.guild.id]["AdminRole"],
                                                               message.author):
                await reply_message(message, "You can't delete someone else's character! I'm telling! Hey <@&" + str(
                    guild_settings[message.guild.id]["AdminRole"]) + "> !!")
                return
            result = await commit_sql("""DELETE FROM CharacterProfiles WHERE Id=%s;""", (char_id,))
            if result:
                await reply_message(message, "Character " + char_name + " deleted from server!")
            else:
                await reply_message(message, "Database error!")

        elif command == 'setalt':
            if not role_check(guild_settings[message.guild.id]["NPCRole"], message.author):
                await reply_message(message, "You must be a member of the NPC role to set alt aliases!")
                return
            if not parsed_string:
                await reply_message(message, "No Alt shortcut specified!")
                return
            records = await select_sql("""SELECT UsersAllowed FROM Alts WHERE ServerId=%s AND Shortcut=%s;""",
                                       (str(message.guild.id), str(pasred_string)))
            if not records:
                await reply_message(message, "No alt with that shortcut exists!")
                return
            for row in records:
                if str(message.author.id) not in row[0]:
                    await reply_message(message,
                                        "<@" + str(message.author.id) + "> is not allowed to use Alt " + row[1] + "!")
                    return
            alt_aliases[message.guild.id][message.author.id][message.channel.id] = parsed_string
            result = await commit_sql(
                """INSERT INTO AltChannels (ServerId, UserId, ChannelId, Shortcut) VALUES (%s, %s, %s, %s);""",
                (str(message.guild.id), str(message.author.id), str(message.channel.id), parsed_string))
            await reply_message(message, "User <@" + str(
                message.author.id) + "> set alias to " + parsed_string + " in channel " + message.channel.name + ".")
        elif command == 'unsetalt':
            if not role_check(guild_settings[message.guild.id]["NPCRole"], message.author):
                await reply_message(message, "You must be a member of the NPC role to remove an alt alias!")
                return
            alt_aliases[message.guild.id][message.author.id][message.channel.id] = ""
            result = await commit_sql("""DELETE FROM AltChannels WHERE ServerId=%s AND UserId=%s AND ChannelId=%s;""",
                                      (str(message.guild.id), str(message.author.id), str(message.channel.id)))
            await reply_message(message, "User <@" + str(
                message.author.id) + "> cleared alias in channel " + message.channel.name + ".")
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
            dm_tracker[message.author.id]["fieldlist"] = ["CharName", "Shortcut", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = ["Alt Name", "The shortcut to use when posting as the alt",
                                                           "Direct upload or Internet http link for the alt"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = message.mentions
            allowed_ids[message.author.id] = []

            await reply_message(message, "Please check your DMs for instructions on how to create a new Alt, <@" + str(
                message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested a new Alt! Please type in the name you want, and then fill out the fields that appear.")
        elif command == 'newnpc':
            if not role_check(guild_settings[message.guild.id]["NPCRole"], message.author):
                await reply_message(message, "You must be a member of the NPC role to create NPCs!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newnpc'
            dm_tracker[message.author.id]["fieldlist"] = ["CharName", "Shortcut", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = ["NPC Name", "The shortcut to use when posting as the NPC",
                                                           "Direct upload or Internet http link for the NPC"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            await reply_message(message, "Please check your DMs for instructions on how to create a new NPC, <@" + str(
                message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested a new NPC! Please type in the name you want, and then fill out the fields that appear.")
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
        elif command == 'postnarr':
            await post_webhook(message.channel, "Narrator", parsed_string, narrator_url)
            await message.delete()
        elif command == 'enter':
            await post_webhook(message.channel, "Narrator", message.author.display_name + " has entered.", narrator_url)
            await message.delete()
        elif command == 'exit':
            await post_webhook(message.channel, "Narrator", message.author.display_name + " has exited.", narrator_url)
            await message.delete()
        elif command == 'listservers':
            if not await admin_check(message.author.id):
                await send_message(message, "Nope.")
                return
            response = "**SERVER LIST**\n\n"
            for guild in client.guilds:
                response = response + guild.name + "\n"
            await reply_message(message, response)
        elif command == 'changepresence':
            if not await admin_check(message.author.id):
                await send_message(message, "Nope.")
                return
            await client.change_presence(activity=discord.Game(name=parsed_string))
            await reply_message(message,"Presence set to " + parsed_string)
        elif command == 'setnarratorurl':
            narrator_url = message.attachments[0].url
            await reply_message(message, "Set narrator to " + narrator_url)
        elif command == 'postnpc':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to post as NonPlayerCharacters!")
                return
            shortcut = command_string[1]
            parsed_string = message.content.replace("=postnpc ", "").replace(shortcut, "")

            if not shortcut:
                await reply_message(message, "No NPC specified!")
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
                # pfp = requests.get(url = URL)

                #                await client.user.edit(avatar=pfp)
                #               await reply_message(message, response)
                temp_webhook = await message.channel.create_webhook(name='Chara-Tron')
                if URL.startswith('http'):
                    await temp_webhook.send(content=response, username=row[0], avatar_url=URL)
                else:
                    await temp_webhook.send(content=response, username=row[0])
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
            result = await commit_sql("""DELETE FROM NonPlayerCharacters WHERE ServerId=%s AND CharName=%s""",
                                      (str(message.guild.id), parsed_string))
            if result:
                await reply_message(message, "NPC " + parsed_string + " deleted.")
            else:
                await reply_message(message, "Database error!")
        elif command == 'editnpc':
            if not role_check(guild_settings[message.guild.id]["NPCRole"], message.author):
                await reply_message(message, "You must be a member of the NPC role to edit NonPlayerCharacters!")
                return

            records = await select_sql(
                """SELECT CharName,Shortcut,PictureLink FROM NonPlayerCharacters WHERE ServerId=%s AND CharName=%s;""",
                (str(message.guild.id), parsed_string))
            if not records:
                await reply_message(message, "No NPC found with that name!")
                return
            for row in records:
                fields = row
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'editnpc'
            dm_tracker[message.author.id]["fieldlist"] = ["CharName", "Shortcut", "PictureLink"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["fieldmeans"] = ["NPC Name", "The shortcut to use when posting as the NPC",
                                                           "Direct upload or Internet http link for the NPC"]
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = ""
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(fields[counter])
                counter = counter + 1

            await reply_message(message, "Please check your DMs for instructions on how to edit a NPC, <@" + str(
                message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested to edit the NPC **" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the spell will be updated!\nThe first field is **" +
                                 dm_tracker[message.author.id]["fieldlist"][0] + "** and its current value is **" +
                                 dm_tracker[message.author.id]["fielddict"][0] + "**.")
        elif command == 'postalt':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to post as Alts!")
                return
            shortcut = command_string[1]
            parsed_string = message.content.replace("=postalt ", "").replace(shortcut, "")

            if not shortcut:
                await reply_message(message, "No Alt specified!")
                return
            get_alt = """SELECT UsersAllowed, CharName, PictureLink FROM Alts WHERE ServerId=%s AND Shortcut=%s;"""
            alt_tuple = (str(message.guild.id), shortcut)
            records = await select_sql(get_alt, alt_tuple)
            if not records:
                await reply_message(message, "An alt with that shortcut does not exist!")
                return
            for row in records:
                if str(message.author.id) not in row[0]:
                    await reply_message(message,
                                        "<@" + str(message.author.id) + "> is not allowed to use Alt " + row[1] + "!")
                    return
                response = parsed_string
                current_pfp = await client.user.avatar_url.read()

                current_name = message.guild.me.name
                #                await message.guild.me.edit(nick=row[1])
                URL = row[2]
                # pfp = requests.get(url = URL)

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
            result = await commit_sql("""DELETE FROM Alts WHERE ServerId=%s AND CharName=%s""",
                                      (str(message.guild.id), parsed_string))
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
            records = await select_sql(
                """SELECT CharName,Shortcut,PictureLink FROM Alts WHERE ServerId=%s AND CharName=%s;""",
                (str(message.guild.id), re.sub(r"<.*>", "", parsed_string).strip()))
            if not records:
                await reply_message(message, "No Alt found with that name!")
                return
            for row in records:
                fields = row
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'editalt'
            dm_tracker[message.author.id]["fieldlist"] = ["CharName", "Shortcut", "PictureLink"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["fieldmeans"] = ["Alt Name", "The shortcut to use when posting as the alt",
                                                           "Direct upload or Internet http link for the alt"]
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = message.mentions
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(fields[counter])
                counter = counter + 1

            await reply_message(message, "Please check your DMs for instructions on how to edit a Alt, <@" + str(
                message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested to edit the alt **" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the spell will be updated!\nThe first field is **" +
                                 dm_tracker[message.author.id]["fieldlist"][0] + "** and its current value is **" +
                                 dm_tracker[message.author.id]["fielddict"][0] + "**.")

        elif command == 'listalts':
            response = "***CURRENT Alt LIST***\n\n__Alt Name__ - __Allowed Users__ __Shortcut__\n"
            embed = discord.Embed(title="Server Alt List", description="List of alternate names for this server")

            records = await select_sql("""SELECT CharName,UsersAllowed,Shortcut FROM Alts WHERE ServerId=%s;""",
                                       (str(message.guild.id),))
            name_re = re.compile(r"Member id=(.*?)name=")
            alts = ""
            name_list = []
            shortcuts = ""
            user_list = ""
            for row in records:
                m = name_re.findall(row[1])
                if m:
                    names = re.sub(r"[\[\]']", "", str(m))
                alts = alts + row[0] + "\n"
                name_list.append(names)

                for name in name_list:
                    user_list = user_list + discord.utils.get(message.guild.members, id=int(name)).name + ","
                shortcuts = shortcuts + row[2] + "\n"

                response = response + row[0] + " - " + str(names) + " - " + row[2] + "\n"

            embed.add_field(name="Alt Name", value=alts)
            embed.add_field(name="Allowed Users", value=user_list)
            embed.add_field(name="Shortcut", value=shortcuts)
            await message.channel.send(embed=embed)
            # await reply_message(message, response)
        elif command == 'randomspar':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to start a new random spar!")
                return
            if not parsed_string:
                await reply_message(message, "You didn't specify a level for the AI opponent!")
                return
            ai_level = int(parsed_string)
            await generate_random_ai_char(message, ai_level)
            await reply_message(message, "Please run the following commands:\n\n=yes\n=spar2\n=spar3")
            mass_spar[message.guild.id] = [message.author, client.user]
            user = message.author
            mass_spar_confirm[message.guild.id][user.id] = {}
            mass_spar_confirm[message.guild.id][client.user.id] = {}

            mass_spar_turn[message.guild.id] = 0
            mass_spar_confirm[message.guild.id][user.id]["Confirm"] = False
            mass_spar_confirm[message.guild.id][client.user.id]["Confirm"] = True
        elif command == 'listnpcs':
            response = "***CURRENT NPC LIST***\n\n__NPC Name__  __Shortcut__\n"
            embed = discord.Embed(title="Server NPC List", description="List of server non-player characters")
            names = ""
            shortcuts = ""
            records = await select_sql("""SELECT CharName,Shortcut FROM NonPlayerCharacters WHERE ServerId=%s;""",
                                       (str(message.guild.id),))
            name_re = re.compile(r"Member id=.*?name='(.+?)'")

            for row in records:
                response = response + row[0] + " - " + row[1] + "\n"
                names = names + row[0] + "\n"
                shortcuts = shortcuts + row[1] + "\n"
            embed.add_field(name="NPCs", value=response)
            await message.channel.send(embed=embed)
        #           await reply_message(message, response)
        elif command == 'newspell':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to create new spells!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newspell'
            dm_tracker[message.author.id]["fieldlist"] = ["SpellName", "ManaCost", "MinimumLevel", "DamageMultiplier",
                                                          "Description", "StatusChange", "StatusChangedBy",
                                                          "AllowedClasses", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = [
                "The name of the spell as it appears in combat or skill lists",
                "The amount of mana drained to perform the spell",
                "The mininum level required to use the spell. A character may know higher-level spells but cannot use them in combat",
                "The value by which MagicAttack is multiplied for total spell damage",
                "A free text description of the spell, such as what it looks like or its effects",
                "The character status effect field (None,Paralyzed,Stunned,Asleep,DisabledSpell,Delusional,Poison,ManaDrain,StaminaDrain)",
                "Stat change per turn or how many turns the effect lasts",
                "Classes allowed, separated by commas, or All for any class",
                "A picture of the spell (None for no link)"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            await reply_message(message,
                                "Please check your DMs for instructions on how to create a new spell, <@" + str(
                                    message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested a new spell! Please type in the name you want, and then fill out the fields that appear.")



        elif command == 'newmelee':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to create new melee attacks!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newmelee'
            dm_tracker[message.author.id]["fieldlist"] = ["AttackName", "StaminaCost", "MinimumLevel",
                                                          "DamageMultiplier", "Description", "StatusChange",
                                                          "StatusChangedBy", "AllowedClasses", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = [
                "The name of the melee attack as it appears in combat (punch, kick, body slam)",
                "How much stamina will be used to perform the attack",
                "The minimum level required for this attack. A character may know a technique at a lower level but cannot use it in combat",
                "How much to multiply the character's base attack power by for total damage",
                "A description of the attack (free text)",
                "The character status effect field (None,Paralyzed,Stunned,Asleep,DisabledSpell,Delusional,Poison,ManaDrain,StaminaDrain)",
                "Stat change per turn or how many turns the effect lasts",
                "Classes allowed, separated by commas, or All for any class",
                "A picture of the attack (None for no link)"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            await reply_message(message,
                                "Please check your DMs for instructions on how to create a new melee attack, <@" + str(
                                    message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested a new melee attack! Please type in the name you want, and then fill out the fields that appear.")
        elif command == 'newvendor':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to create new vendors!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newvendor'
            dm_tracker[message.author.id]["fieldlist"] = ["VendorName", "ItemList", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = ["VendorName", "ItemList", "PictureLink"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            await reply_message(message,
                                "Please check your DMs for instructions on how to create a new vendor, <@" + str(
                                    message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested a new vendor! Please type in the name you want, and then fill out the fields that appear.")
        elif command == 'addvendoritem':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to edit vendors!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'addvendoritem'
            dm_tracker[message.author.id]["fieldlist"] = ["VendorName", "ItemList"]
            dm_tracker[message.author.id]["fieldmeans"] = ["VendorName", "ItemList"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "Vendors", "VendorName")
            response = "Please select a vendor from the below list to edit:\n\n" + menu
            await reply_message(message,
                                "Please check your DMs for instructions on how to add items to a vendor, <@" + str(
                                    message.author.id) + ">.")
            await direct_message(message, response)
        elif command == 'deletevendor':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to delete vendors!")
                return
            if not parsed_string:
                await reply_message(message, "No vendor name specified!")
                return
            result = await commit_sql("""DELETE FROM Vendors WHERE ServerId=%s and VendorName=%s;""",
                                      (str(message.author.id), parsed_string))
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
            result = commit_sql("""DELETE FROM Armory WHERE ServerId=%s and ArmoryName=%s;""",
                                (str(message.author.id), parsed_string))
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
            dm_tracker[message.author.id]["fieldlist"] = ["VendorName", "ItemList"]
            dm_tracker[message.author.id]["fieldmeans"] = ["VendorName", "ItemList"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "Vendors", "VendorName")
            response = "Please select a vendor from the below list to edit:\n\n" + menu
            await reply_message(message,
                                "Please check your DMs for instructions on how to delete items from a vendor, <@" + str(
                                    message.author.id) + ">.")
            await direct_message(message, response)

        elif command == 'listvendor':
            if not parsed_string:
                await reply_message(message, "No vendor name specified!")
                return
            embed = discord.Embed(title="Vendor listing for " + parsed_string)
            items = ""
            vendor_name = parsed_string
            records = await select_sql("""SELECT ItemList,PictureLink FROM Vendors WHERE VendorName=%s;""",
                                       (vendor_name,))
            if not records:
                await reply_message(message, "No vendor found by that name!")
                return
            for row in records:
                items = row[0]
                if row[1].startswith('http'):
                    embed.set_thumbnail(url=row[1])

            response = ""
            item_list = items.split(',')
            for item in item_list:
                item_record = await select_sql("""SELECT EquipmentName,EquipmentCost FROM Equipment WHERE Id=%s""",
                                               (item,))

                for item_name in item_record:
                    response = response + item_name[0] + " - " + str(item_name[1]) + "\n"
            embed.add_field(name="Item Listing", value=response)
            await message.channel.send(embed=embed)
            # await reply_message(message, response + "\nPicture Link: " + row[1] + "\n")
        elif command == 'listvendors':
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            embed = discord.Embed(title="Server Vendor List")

            response = "**VENDORS**\n\n"
            menu = await make_simple_menu(message, "Vendors", "VendorName")
            embed.add_field(name="Vendors", value=menu)
            await message.channel.send(embed=embed)
            # await reply_message(message, response + menu)
        elif command == 'newarmory':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to create new armories!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newarmory'
            dm_tracker[message.author.id]["fieldlist"] = ["ArmoryName", "ArmamentList", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = ["The name of the armory", "List of armaments sold",
                                                           "Picture of the armory"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            await reply_message(message,
                                "Please check your DMs for instructions on how to create a new armory, <@" + str(
                                    message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested a new armory! Please type in the name you want, and then fill out the fields that appear.")
        elif command == 'addarmoryitem':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to edit armories!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'addarmoryitem'
            dm_tracker[message.author.id]["fieldlist"] = ["ArmoryName", "ItemList"]
            dm_tracker[message.author.id]["fieldmeans"] = ["ArmoryName", "ItemList"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "Armory", "ArmoryName")
            response = "Please select a armory from the below list to edit:\n\n" + menu
            await reply_message(message,
                                "Please check your DMs for instructions on how to add items to a armory, <@" + str(
                                    message.author.id) + ">.")
            await direct_message(message, response)
        elif command == 'deletearmoryitem':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to delete armories!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'deletearmoryitem'
            dm_tracker[message.author.id]["fieldlist"] = ["ArmoryName", "ItemList"]
            dm_tracker[message.author.id]["fieldmeans"] = ["ArmoryName", "ItemList"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "Armory", "ArmoryName")
            response = "Please select a armory from the below list to edit:\n\n" + menu
            await reply_message(message,
                                "Please check your DMs for instructions on how to delete items from a armory, <@" + str(
                                    message.author.id) + ">.")
            await direct_message(message, response)

        elif command == 'listarmory':
            if not parsed_string:
                await reply_message(message, "No armory name specified!")
                return
            armory_name = parsed_string
            embed = discord.Embed(title="Server Armory Listing for " + parsed_string)
            records = await select_sql("""SELECT ArmamentList,PictureLink FROM Armory WHERE ArmoryName=%s;""",
                                       (armory_name,))
            if not records:
                await reply_message(message, "No armory found by that name!")
                return
            for row in records:
                items = row[0]
                if row[1].startswith('http'):
                    embed.set_thumbnail(url=row[1])
            response = ""
            arms = ""
            item_list = items.split(',')
            for item in item_list:
                item_record = await select_sql("""SELECT ArmamentName,ArmamentCost FROM Armaments WHERE Id=%s""",
                                               (item,))
                for item_name in item_record:
                    response = response + item_name[0] + " - " + str(item_name[1]) + "\n"
            embed.add_field(name="Armaments for sale:", value=response)
            await message.channel.send(embed=embed)

            # await reply_message(message, response + "\nPicture Link: " + row[1] + "\n")
        elif command == 'listarmories':
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            response = "**ARMORIES**\n\n"
            menu = await make_simple_menu(message, "Armory", "ArmoryName")
            embed = discord.Embed(title="Server Armories")
            embed.add_field(name="Armory Names:", value=menu)
            await message.channel.send(embed=embed)
            # await reply_message(message, response + menu)
        elif command == 'listspell':
            if not parsed_string:
                await reply_message(message, "No spell name specified!")
                return
            records = await select_sql(
                """SELECT ManaCost,MinimumLevel,DamageMultiplier,Description,StatusChange,StatusChangedBy,PictureLink,AllowedClasses FROM Spells WHERE ServerId=%s AND SpellName=%s;""",
                (str(message.guild.id), parsed_string))
            if not records:
                await reply_message(message, "No spell found by that name!")
                return
            response = "**SPELL DETAILS**\n\nSpell Name: " + parsed_string + "\n"
            embed = discord.Embed(title="Spell Data for " + parsed_string)

            for row in records:
                if re.search(r"http", row[6]):
                    embed.set_thumbnail(url=row[6])
                embed.add_field(name="Mana Cost:", value=str(row[0]))
                embed.add_field(name="Minimum Level:", value=str(row[1]))
                embed.add_field(name="Damage Multiplier:", value=str(row[2]))
                embed.add_field(name="Description:", value=row[3])
                embed.add_field(name="Status Change:", value=row[4])
                embed.add_field(name="Status Changed By:", value=str(row[5]))
                embed.add_field(name="Allowed Classes:", value=str(row[7]))

            await message.channel.send(embed=embed)
            asyncio.sleep(1)
        #           await reply_message(message, response)
        elif command == 'listmelee':
            if not parsed_string:
                await reply_message(message, "No melee name specified!")
                return
            records = await select_sql(
                """SELECT StaminaCost,MinimumLevel,DamageMultiplier,Description,IFNULL(StatusChange,'None'),IFNULL(StatusChangedBy,0),PictureLink,AllowedClasses FROM Melee WHERE ServerId=%s AND AttackName=%s;""",
                (str(message.guild.id), parsed_string))
            if not records:
                await reply_message(message, "No melee found by that name!")
                return
            embed = discord.Embed(title="Melee Attack Listing for " + parsed_string)

            response = "**MELEE DETAILS**\n\nAttack Name: " + parsed_string + "\n"
            for row in records:
                if row[6].startswith('http'):
                    embed.set_thumbnail(url=row[6])
                embed.add_field(name="Stamina Cost:", value=str(row[0]))
                embed.add_field(name="Minimum Level:", value=str(row[1]))
                embed.add_field(name="Damage Multipler:", value=str(row[2]))
                embed.add_field(name="Description:", value=row[3])
                embed.add_field(name="Status Change:", value=row[4])
                embed.add_field(name="Status Changed By:", value=str(row[5]))
                embed.add_field(name="Allowed Classes:", value=str(row[7]))

                response = response + "Stamina Cost: " + str(row[0]) + "\nMinimum Level: " + str(
                    row[1]) + "\nDamage Multiplier: " + str(row[2]) + "\nDescription: " + row[3] + "\nPicture Link: " + \
                           row[4] + "\n"
            await message.channel.send(embed=embed)
            # await reply_message(message, response)
        elif command == 'newitem':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to create new equipment!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newitem'
            dm_tracker[message.author.id]["fieldlist"] = ["EquipmentName", "EquipmentDescription", "EquipmentCost",
                                                          "MinimumLevel", "StatMod", "Modifier", "StatusChange",
                                                          "StatusChangedBy", "AllowedClasses", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = [
                "The name of the item as it will appear in the inventory and vendor lists", "A description of the item",
                "How much currency a player must have to purchase the item",
                "The minimum level a character must be to use an item. A player may purchase a higher-level item but will not be able to use it until their level is the minimum or higher",
                "Which character statistic this item modifies (Health/MaxHealth, Stamina/MaxStamina, Mana/MaxMana, Attack, Defense, MagicAttack, Charisma, Agility)",
                "The value this item modifies the statistic by. A positive value increases the stat, a negative one decreases it. So a healing potion could be 100, and a cursed item -500",
                "The character status effect field (None,Paralyzed,Stunned,Asleep,DisabledSpell,Delusional,Poison,ManaDrain,StaminaDrain)",
                "Stat change per turn or how many turns the effect lasts",
                "Classes allowed, separated by commas, or All for any class",
                "A picture of the item (None for no link)"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            await reply_message(message, "Please check your DMs for instructions on how to create a new item, <@" + str(
                message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested a new item! Please type in the name you want, and then fill out the fields that appear.")
        elif command == 'newclass':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to create new classes!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newclass'
            dm_tracker[message.author.id]["fieldlist"] = ["Name", "Description", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = ["The name of the class", "A description of the class",
                                                           "A picture of the class (None for no link)"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            await reply_message(message,
                                "Please check your DMs for instructions on how to create a new class, <@" + str(
                                    message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested a new class! Please type in the name you want, and then fill out the fields that appear.")
        elif command == 'editrace':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to edit races!")
                return
            if not parsed_string:
                await reply_message(message, "No race name specified!")
                return
            user_id = message.author.id
            server_id = message.guild.id

            current_fields = await select_sql(
                """SELECT Name,Description, AttackBonus, DefenseBonus, MagicAttackBonus, HealthBonus, ManaBonus, StaminaBonus, IntellectBonus, CharismaBonus, AgilityBonus, PictureLink FROM Races WHERE ServerId=%s AND Name=%s;""",
                (str(message.guild.id), parsed_string))
            if not current_fields:
                await reply_message(message, "No race found by that name!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'editrace'
            dm_tracker[message.author.id]["fieldlist"] = ["Name", "Description", "AttackBonus", "DefenseBonus",
                                                          "MagicAttackBonus", "HealthBonus", "ManaBonus",
                                                          "StaminaBonus", "IntellectBonus", "CharismaBonus",
                                                          "AgilityBonus", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = ["The name of the race",
                                                           "A description of the race, such as typical features and traits",
                                                           "How much the attack is modified (positive or negative)",
                                                           "How much the defense is modified (positive or negative)",
                                                           "How much the magic attack (Magic Attack) is modified (positive or negative)",
                                                           "How much the health is modified (positive or negative)",
                                                           "How much the mana is modified (positive or negative)",
                                                           "How much the stamina is modified (positive or negative)",
                                                           "How much the intellect is modified (positive or negative)",
                                                           "How much the charisma is modified (positive or negative)",
                                                           "How much the agility is modified (positive or negative)",
                                                           "A sample picture of the race (None for no link)"]
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(current_fields[0][counter])
                counter = counter + 1

            await reply_message(message, "Please check your DMs for instructions on how to edit a race, <@" + str(
                message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested to edit the race **" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the race will be updated!\nThe first field is **" +
                                 dm_tracker[message.author.id]["fieldlist"][0] + "** and its current value is **" +
                                 dm_tracker[message.author.id]["fielddict"][0] + "**.")

        elif command == 'editclass':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to edit classes!")
                return
            if not parsed_string:
                await reply_message(message, "No class name specified!")
                return
            user_id = message.author.id
            server_id = message.guild.id

            current_fields = await select_sql(
                """SELECT Name,Description,PictureLink FROM Classes WHERE ServerId=%s AND Name=%s;""",
                (str(message.guild.id), parsed_string))
            if not current_fields:
                await reply_message(message, "No class found by that name!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'editclass'
            dm_tracker[message.author.id]["fieldlist"] = ["Name", "Description", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = ["The name of the class",
                                                           "A description of the class, such as typical items and armaments available",
                                                           "A sample picture of the class (None for no link)"]
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(current_fields[0][counter])
                counter = counter + 1

            await reply_message(message, "Please check your DMs for instructions on how to edit a class, <@" + str(
                message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested to edit the class **" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the class will be updated!\nThe first field is **" +
                                 dm_tracker[message.author.id]["fieldlist"][0] + "** and its current value is **" +
                                 dm_tracker[message.author.id]["fielddict"][0] + "**.")
        elif command == 'listrace':
            if not parsed_string:
                await reply_message(message, "No race name specified!")
                return
            records = await select_sql(
                """SELECT Description, AttackBonus, DefenseBonus, MagicAttackBonus, HealthBonus, ManaBonus, StaminaBonus, IntellectBonus, CharismaBonus, AgilityBonus, PictureLink FROM Races WHERE ServerId=%s AND Name=%s;""",
                (str(message.guild.id), parsed_string))
            if not records:
                await reply_message(message, "No race found with that name!")
                return
            embed = discord.Embed(title="Race data for " + parsed_string)

            for row in records:

                if row[10].startswith('http'):
                    embed.set_thumbnail(url=row[10])
                if int(row[1]) != 0:
                    embed.add_field(name="Attack Bonus", value=str(row[1]))
                if int(row[2]) != 0:
                    embed.add_field(name="Defense Bonus:", value=str(row[2]))
                if int(row[3]) != 0:
                    embed.add_field(name="Magic Attack Bonus:", value=row[3])
                if int(row[4]) != 0:
                    embed.add_field(name="Health Bonus:", value=str(row[4]))
                if int(row[5]) != 0:
                    embed.add_field(name="Mana Bonus:", value=str(row[5]))
                if int(row[6]) != 0:
                    embed.add_field(name="Stamina Bonus:", value=str(row[6]))
                if int(row[7]) != 0:
                    embed.add_field(name="Intellect Bonus:", value=str(row[7]))
                if int(row[9]) != 0:
                    embed.add_field(name="Agility Bonus:", value=str(row[9]))
                if int(row[8]) != 0:
                    embed.add_field(name="Charisma Bonus:", value=str(row[8]))

            await message.channel.send(embed=embed)
            await reply_message(message, "**Description:** " + row[0])
        elif command == 'listclass':
            if not parsed_string:
                await reply_message(message, "No class name specified!")
                return
            records = await select_sql(
                """SELECT Description, PictureLink FROM Classes WHERE ServerId=%s AND Name=%s;""",
                (str(message.guild.id), parsed_string))
            if not records:
                await reply_message(message, "No class found with that name!")
                return
            embed = discord.Embed(title="Class data for " + parsed_string)

            for row in records:
                if row[1].startswith('http'):
                    embed.set_thumbnail(url=row[1])
                embed.add_field(name="Description", value=row[0])

            await message.channel.send(embed=embed)

        elif command == 'newrace':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to create a new race!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newrace'
            dm_tracker[message.author.id]["fieldlist"] = ["Name", "Description", "AttackBonus", "DefenseBonus",
                                                          "MagicAttackBonus", "HealthBonus", "ManaBonus",
                                                          "StaminaBonus", "IntellectBonus", "CharismaBonus",
                                                          "AgilityBonus", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = ["The name of the race",
                                                           "A description of the race, such as typical features and traits",
                                                           "How much the attack is modified (positive or negative)",
                                                           "How much the defense is modified (positive or negative)",
                                                           "How much the magic attack (Magic Attack) is modified (positive or negative)",
                                                           "How much the health is modified (positive or negative)",
                                                           "How much the mana is modified (positive or negative)",
                                                           "How much the stamina is modified (positive or negative)",
                                                           "How much the intellect is modified (positive or negative)",
                                                           "How much the charisma is modified (positive or negative)",
                                                           "How much the agility is modified (positive or negative)",
                                                           "A sample picture of the race (None for no link)"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            await reply_message(message, "Please check your DMs for instructions on how to create a new race, <@" + str(
                message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested a new race! Please type in the name you want, and then fill out the fields that appear.")
        elif command == 'newarmament':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to create new armaments!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            # CREATE TABLE Armaments (Id int auto_increment, ArmamentName VARCHAR(100), ServerId VARCHAR(40), UserId VARCHAR(40), Description TEXT, Slot VARCHAR(20) MinimumLevel Int, DamageMin Int, DamageMax Int, Defense Int, StatMod VARCHAR(30), PRIMARY KEY(Id))
            dm_tracker[message.author.id]["currentcommand"] = 'newarmament'
            dm_tracker[message.author.id]["fieldlist"] = ["ArmamentName", "Description", "ArmamentCost", "Slot",
                                                          "MinimumLevel", "DamageMin", "DamageMax", "Defense",
                                                          "StatMod", "Modifier", "StatusChange", "StatusChangedBy",
                                                          "AllowedClasses", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = ["The display name of the armament",
                                                           "The free text description of the armament",
                                                           "How much currency the armament will sell for",
                                                           "The equippable slot for the armament (Hand, Head, Chest, Form or Feet [case sensitive])",
                                                           "The minimum level required to use the armament",
                                                           "The minimum damage the armament can do (zero for status only items)",
                                                           "The maximum amount of damage the armament can do (zero for status only items)",
                                                           "The amount of defense added by the armament (zero for non-defensive armaments)",
                                                           "The status field modified by the armament (Attack, MagicAttack, Charisma, Intellect or Agility)",
                                                           "The amount a statistic is modified by the armament (positive or negative)",
                                                           "The character status effect field (None,Paralyzed,Stunned,Asleep,DisabledSpell,Delusional,Poison,ManaDrain,StaminaDrain)",
                                                           "Stat change per turn or how many turns the effect lasts",
                                                           "Classes allowed, separated by commas, or All for any class",
                                                           "A picture of the armament (None for no link)"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            await reply_message(message,
                                "Please check your DMs for instructions on how to create a new armament, <@" + str(
                                    message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested a new armament! Please type in the name you want, and then fill out the fields that appear.")

        elif command == 'deletespell':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to delete spells!")
                return
            if not parsed_string:
                await reply_message(message, "No spell specified!")
                return
            result = await commit_sql("""DELETE FROM Spells WHERE ServerId=%s AND SpellName=%s;""",
                                      (str(message.guild.id), parsed_string))
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
            result = await commit_sql("""DELETE FROM Melee WHERE ServerId=%s AND AttackName=%s;""",
                                      (str(message.guild.id), parsed_string))
            if result:
                await reply_message(message, "Attack Name " + parsed_string + " deleted successfully.")
            else:
                await reply_message(message, "Database error!")
        elif command == 'listmelees':
            response = ""
            records = await select_sql("""SELECT AttackName FROM Melee WHERE ServerId=%s;""", (str(message.guild.id),))
            for row in records:
                response = response + row[0] + "\n"
            embed = discord.Embed(title="Server Melee Attack List")
            embed.add_field(name="Attack Names", value=response)
            await message.channel.send(embed=embed)
        #          await reply_message(message, response)
        elif command == 'listspells':
            response = ""
            records = await select_sql("""SELECT SpellName FROM Spells WHERE ServerId=%s;""", (str(message.guild.id),))
            for row in records:
                response = response + row[0] + "\n"
            embed = discord.Embed(title="Server Spell Listing")
            embed.add_field(name="Spell Names", value=response)
            await message.channel.send(embed=embed)

            # await reply_message(message, response)
        elif command == 'editmelee':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to edit melee attacks!")
                return
            if not parsed_string:
                await reply_message(message, "No melee name specified!")
                return
            user_id = message.author.id
            server_id = message.guild.id

            current_fields = await select_sql(
                """SELECT AttackName,Description,StaminaCost,MinimumLevel,DamageMultiplier,StatusChange,StatusChangedBy,AllowedClasses,PictureLink FROM Melee WHERE ServerId=%s AND AttackName=%s;""",
                (str(message.guild.id), parsed_string))
            if not current_fields:
                await reply_message(message, "No melee attack found by that name!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["AttackName", "Description", "StaminaCost", "MinimumLevel",
                                                          "DamageMultiplier", "StatusChange", "StatusChangedBy",
                                                          "AllowedClasses", "PictureLink"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'editmelee'
            dm_tracker[message.author.id]["fieldmeans"] = [
                "The name of the melee attack as it appears in combat (punch, kick, body slam)",
                "A description of the attack (free text)", "How much stamina will be used to perform the attack",
                "The minimum level required for this attack. A character may know a technique at a lower level but cannot use it in combat",
                "How much to multiply the character's base attack power by for total damage",
                "The character status effect field (None,Paralyzed,Stunned,Asleep,DisabledSpell,Delusional,Poison,ManaDrain,StaminaDrain)",
                "Stat change per turn or how many turns the effect lasts",
                "Classes allowed, separated by commas, or All for any class",
                "A picture of the attack (None for no link)"]
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(current_fields[0][counter])
                counter = counter + 1

            await reply_message(message, "Please check your DMs for instructions on how to edit an item, <@" + str(
                message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested to edit the item **" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the item will be updated!\nThe first field is **" +
                                 dm_tracker[message.author.id]["fieldlist"][0] + "** and its current value is **" +
                                 dm_tracker[message.author.id]["fielddict"][0] + "**.")
        elif command == 'editspell':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to edit spells!")
                return
            if not parsed_string:
                await reply_message(message, "No spell name specified!")
                return
            user_id = message.author.id
            server_id = message.guild.id

            current_fields = await select_sql(
                """SELECT SpellName,Description,ManaCost,MinimumLevel,DamageMultiplier,StatusChange,StatusChangedBy,AllowedClasses,PictureLink FROM Spells WHERE ServerId=%s AND SpellName=%s;""",
                (str(message.guild.id), parsed_string))
            if not current_fields:
                await reply_message(message, "No spell found by that name!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["SpellName", "Description", "ManaCost", "MinimumLevel",
                                                          "DamageMultiplier", "StatusChange", "StatusChangedBy",
                                                          "AllowedClasses", "PictureLink"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'editspell'
            dm_tracker[message.author.id]["fieldmeans"] = [
                "The name of the spell as it appears in combat or skill lists",
                "A free text description of the spell, such as what it looks like or its effects",
                "The amount of mana drained to perform the spell",
                "The mininum level required to use the spell. A character may know higher-level spells but cannot use them in combat",
                "The value by which MagicAttack is multiplied for total spell damage",
                "The character status effect field (None,Paralyzed,Stunned,Asleep,DisabledSpell,Delusional,Poison,ManaDrain,StaminaDrain)",
                "Stat change per turn or how many turns the effect lasts",
                "Classes allowed, separated by commas, or All for any class",
                "A picture of the spell (None for no link)"]
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(current_fields[0][counter])
                counter = counter + 1

            await reply_message(message, "Please check your DMs for instructions on how to edit a spell, <@" + str(
                message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested to edit the spell **" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the spell will be updated!\nThe first field is **" +
                                 dm_tracker[message.author.id]["fieldlist"][0] + "** and its current value is **" +
                                 dm_tracker[message.author.id]["fielddict"][0] + "**.")
        elif command == 'givemelee':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to give melee attacks!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Character", "Spell"]
            dm_tracker[message.author.id]["fieldmeans"] = ["Character", "Spell"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'givemelee'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Pick a character to add a melee attack to:\n\nPlease choose a character by selecting the IDs.\n" + menu
            await direct_message(message, response)
            await reply_message(message,
                                "Please check your DMs for instructions on how to give a melee attack, <@" + str(
                                    message.author.id) + ">.")

        elif command == 'givearmament':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to give melee attacks!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Character", "Armament"]
            dm_tracker[message.author.id]["fieldmeans"] = ["Character", "Armament"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'givearmament'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Pick a character to add a melee attack to:\n\nPlease choose a character by selecting the IDs.\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to give an armament, <@" + str(
                message.author.id) + ">.")

        elif command == 'giveitem':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to give melee attacks!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Character", "Item"]
            dm_tracker[message.author.id]["fieldmeans"] = ["Character", "Item"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'giveitem'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Pick a character to add an item to by replying with the IDs.\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to give an item, <@" + str(
                message.author.id) + ">.")

        elif command == 'givesummon':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to give monster summons!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Character", "Monster"]
            dm_tracker[message.author.id]["fieldmeans"] = ["Character", "Monster"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'givesummon'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Pick a character to give a summon to by replying with the IDs.\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to give a summon to, <@" + str(
                message.author.id) + ">.")
        elif command == 'givespell':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to give spells!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Character", "Spell"]
            dm_tracker[message.author.id]["fieldmeans"] = ["Character", "Spell"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'givespell'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Pick a character to add a spell to:\n\nPlease choose a character by selecting the IDs.\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to give a spell, <@" + str(
                message.author.id) + ">.")






        elif command == 'takemelee':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to take melee attacks!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Character", "Spell"]
            dm_tracker[message.author.id]["fieldmeans"] = ["Character", "Spell"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'takemelee'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Pick a character to add a spell to:\n\nPlease choose a character by selecting the IDs.\n" + menu
            await direct_message(message, response)
            await reply_message(message,
                                "Please check your DMs for instructions on how to take a melee attack, <@" + str(
                                    message.author.id) + ">.")

        elif command == 'takespell':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to take spells!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Character", "Spell"]
            dm_tracker[message.author.id]["fieldmeans"] = ["Character", "Spell"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'takespell'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Pick a character to take a spell from:\n\nPlease choose a character by selecting the IDs.\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to take a spell, <@" + str(
                message.author.id) + ">.")
        elif command == 'takeitem':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to take spells!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Character", "Item"]
            dm_tracker[message.author.id]["fieldmeans"] = ["Character", "Item"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'takeitem'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Pick a character to take an item from:\n\nPlease choose a character by selecting the IDs.\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to take an item, <@" + str(
                message.author.id) + ">.")

        elif command == 'takesummon':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to take spells!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Character", "Monster"]
            dm_tracker[message.author.id]["fieldmeans"] = ["Character", "Monster"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'takesummon'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Pick a character to add a spell to:\n\nPlease choose a character by selecting the IDs.\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to take a monster summon, <@" + str(
                message.author.id) + ">.")

        elif command == 'editarmament':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to edit armaments!")
                return
            if not parsed_string:
                await reply_message(message, "No armament name specified!")
                return
            user_id = message.author.id
            server_id = message.guild.id

            current_fields = await select_sql(
                """SELECT ArmamentName,Description,ArmamentCost,Slot,MinimumLevel,DamageMin,DamageMax,Defense,StatMod,Modifier,StatusChange,StatusChangedBy,AllowedClasses,PictureLink FROM Armaments WHERE ServerId=%s AND ArmamentName=%s;""",
                (str(message.guild.id), parsed_string))
            if not current_fields:
                await reply_message(message, "No armament found by that name!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["ArmamentName", "Description", "ArmamentCost", "Slot",
                                                          "MinimumLevel", "DamageMin", "DamageMax", "Defense",
                                                          "StatMod", "Modifier", "StatusChange", "StatusChangedBy",
                                                          "AllowedClasses", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = ["The display name of the armament",
                                                           "The free text description of the armament",
                                                           "How much currency the armament will sell for",
                                                           "The equippable slot for the armament (Left Hand, Right Hand, Head, Chest, Form or Feet [case sensitive])",
                                                           "The minimum level required to use the armament",
                                                           "The minimum damage the armament can do (zero for status only items)",
                                                           "The maximum amount of damage the armament can do (zero for status only items)",
                                                           "The amount of defense added by the armament (zero for non-defensive armaments)",
                                                           "The status field modified by the armament (Attack, MagicAttack, Charisma, Intellect or Agility)",
                                                           "The amount a statistic is modified by the armament (positive or negative)",
                                                           "The character status effect field (None,Paralyzed,Stunned,Asleep,DisabledSpell,Delusional,Poison,ManaDrain,StaminaDrain)",
                                                           "Stat change per turn or how many turns the effect lasts",
                                                           "Classes allowed, separated by commas, or All for any class",
                                                           "A picture of the armament (None for no link)"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'editarmament'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(current_fields[0][counter])
                counter = counter + 1

            await reply_message(message, "Please check your DMs for instructions on how to edit an armament, <@" + str(
                message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested to edit the armament **" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the armament will be updated!\nThe first field is **" +
                                 dm_tracker[message.author.id]["fieldlist"][0] + "** and its current value is **" +
                                 dm_tracker[message.author.id]["fielddict"][0] + "**.")
        elif command == 'edititem':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to edit equipment!")
                return
            if not parsed_string:
                await reply_message(message, "No item name specified!")
                return
            user_id = message.author.id
            server_id = message.guild.id

            current_fields = await select_sql(
                """SELECT EquipmentName,EquipmentDescription,EquipmentCost,MinimumLevel,StatMod,Modifier,StatusChange,StatusChangedBy,AllowedClasses,PictureLink FROM Equipment WHERE ServerId=%s AND EquipmentName=%s;""",
                (str(message.guild.id), parsed_string))
            if not current_fields:
                await reply_message(message, "No item found by that name!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'edititem'
            dm_tracker[message.author.id]["fieldlist"] = ["EquipmentName", "EquipmentDescription", "EquipmentCost",
                                                          "MinimumLevel", "StatMod", "Modifier", "StatusChange",
                                                          "StatusChangedBy", "AllowedClasses", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = [
                "The name of the item as it will appear in the inventory and vendor lists", "A description of the item",
                "How much currency a player must have to purchase the item",
                "The minimum level a character must be to use an item. A player may purchase a higher-level item but will not be able to use it until their level is the minimum or higher",
                "Which character statistic this item modifies (Health/MaxHelth, Stamina/MaxStamina, Mana/MaxMana, Attack, Defense, MagicAttack, Agility, Intellect, or Charisma)",
                "The value this item modifies the statistic by. A positive value increases the stat, a negative one decreases it. So a healing potion could be 100, and a cursed item -500",
                "The character status effect field (None,Paralyzed,Stunned,Asleep,DisabledSpell,Delusional,Poison,ManaDrain,StaminaDrain)",
                "Stat change per turn or how many turns the effect lasts",
                "Classes allowed, separated by commas, or All for any class",
                "A picture of the item (None for no link)"]
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(current_fields[0][counter])
                counter = counter + 1

            await reply_message(message, "Please check your DMs for instructions on how to edit an item, <@" + str(
                message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested to edit the item **" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the item will be updated!\nThe first field is **" +
                                 dm_tracker[message.author.id]["fieldlist"][0] + "** and its current value is **" +
                                 dm_tracker[message.author.id]["fielddict"][0] + "**.")


        elif command == 'deletearmament':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to delete armaments!")
                return
            if not parsed_string:
                await reply_message(message, "You didn't specify an armament name!")
                return
            records = await select_sql("""SELECT Id FROM Armaments WHERE ArmamentName=%s AND ServerId=%s;""",
                                       (parsed_string, str(message.guild.id)))

            if not records:
                await reply_message(message, "No armament found by that name!")
                return
            for row in records:
                item_id = row[0]

            result = await commit_sql("""DELETE FROM Armaments WHERE Id=%s;""", (item_id,))
            if result:
                result_remove = await commit_sql(
                    """DELETE FROM ArmamentInventory WHERE ServerId=%s AND ArmamentId=%s;""",
                    (str(message.guild.id), item_id))
                if result_remove:
                    await reply_message(message, "Armament removed from game and inventory successfully.")
                else:
                    await reply_message(message, "Database error!")
            else:
                await reply_message(message, "Database error!")
        elif command == 'deletecritter':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to delete critters!")
                return
            if not parsed_string:
                await reply_message(message, "You didn't specify a monser name!")
                return
            records = await select_sql("""SELECT Id FROM Critters WHERE CritterName=%s AND ServerId=%s;""",
                                       (parsed_string, str(message.guild.id)))

            if not records:
                await reply_message(message, "No critter found by that name!")
                return
            for row in records:
                item_id = row[0]

            result = await commit_sql("""DELETE FROM Critters WHERE Id=%s;""", (item_id,))
            if result:
                await reply_message(message, "Critter deleted successfully.")
            else:
                await reply_message(message, "Database error!")                    
        elif command == 'deletemonster':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to delete monsters!")
                return
            if not parsed_string:
                await reply_message(message, "You didn't specify a monser name!")
                return
            records = await select_sql("""SELECT Id FROM Monsters WHERE MonsterName=%s AND ServerId=%s;""",
                                       (parsed_string, str(message.guild.id)))

            if not records:
                await reply_message(message, "No monster found by that name!")
                return
            for row in records:
                item_id = row[0]

            result = await commit_sql("""DELETE FROM Monsters WHERE Id=%s;""", (item_id,))
            if result:
                await reply_message(message, "Monster deleted successfully.")
            else:
                await reply_message(message, "Database error!")                
        elif command == 'deleteitem':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to delete equipment!")
                return
            if not parsed_string:
                await reply_message(message, "You didn't specify an equipment name!")
                return
            records = await select_sql("""SELECT Id FROM Equipment WHERE EquipmentName=%s AND ServerId=%s;""",
                                       (parsed_string, str(message.guild.id)))

            if not records:
                await reply_message(message, "No item found by that name!")
                return
            for row in records:
                item_id = row[0]

            result = await commit_sql("""DELETE FROM Equipment WHERE Id=%s;""", (item_id,))
            if result:
                result_remove = await commit_sql("""DELETE FROM Inventory WHERE ServerId=%s AND EquipmentId=%s;""",
                                                 (str(message.guild.id), item_id))
                if result_remove:
                    await reply_message(message, "Item removed from game and inventory successfully.")
                else:
                    await reply_message(message, "Database error!")
            else:
                await reply_message(message, "Database error!")
        elif command == 'deleterace':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to delete races!")
                return
            if not parsed_string:
                await reply_message(message, "You didn't specify a race name!")
                return
            records = await select_sql("""SELECT Id FROM Races WHERE Name=%s AND ServerId=%s;""",
                                       (parsed_string, str(message.guild.id)))

            if not records:
                await reply_message(message, "No race found by that name!")
                return
            for row in records:
                item_id = row[0]

            result = await commit_sql("""DELETE FROM Races WHERE Id=%s;""", (item_id,))
            if result:
                await reply_message(message, "Race removed from game.")

            else:
                await reply_message(message, "Database error!")
        elif command == 'deleteclass':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to delete classes!")
                return
            if not parsed_string:
                await reply_message(message, "You didn't specify a class name!")
                return
            records = await select_sql("""SELECT Id FROM Classes WHERE Name=%s AND ServerId=%s;""",
                                       (parsed_string, str(message.guild.id)))

            if not records:
                await reply_message(message, "No class found by that name!")
                return
            for row in records:
                item_id = row[0]

            result = await commit_sql("""DELETE FROM Classes WHERE Id=%s;""", (item_id,))
            if result:
                await reply_message(message, "Class removed from game.")

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
            dm_tracker[message.author.id]["fieldlist"] = ["CharId", "VendorId", "ItemId"]
            dm_tracker[message.author.id]["fieldmeans"] = ["CharId", "VendorId", "ItemId"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            response = "**YOUR CHARACTERS**\n\n"
            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId",
                                               str(message.author.id))
            response = response + menu
            await direct_message(message,
                                 "Please select a character to purchase the item for by replying with the ID that is in bold.\n\n" + response)
            await reply_message(message, "Please check your DMs for instructions on how to buy an item, <@" + str(
                message.author.id) + ">.")
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
            dm_tracker[message.author.id]["fieldlist"] = ["CharId", "VendorId", "ItemId"]
            dm_tracker[message.author.id]["fieldmeans"] = ["CharId", "VendorId", "ItemId"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            response = "**YOUR CHARACTERS**\n\n"
            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId",
                                               str(message.author.id))
            response = response + menu
            await direct_message(message,
                                 "Please select a character to purchase the item for by replying with the ID that is in bold.\n\n" + response)
            await reply_message(message, "Please check your DMs for instructions on how to buy armaments, <@" + str(
                message.author.id) + ">.")


        elif command == 'myitems':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to check inventory!")
                return
            if not parsed_string:
                await reply_message(message, "You didn't specify a character!")
                return

            records = await select_sql(
                """SELECT Id,UserId FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""",
                (str(message.guild.id), char_name))
            if not records:
                await reply_message(message, "No character by that name found!")
                return
            for row in records:
                char_id = row[0]
                user_id = int(row[1])
            if user_id != message.author.id:
                await reply_message(message, "This isn't your character!")
                return
            records = await select_sql("""SELECT EquipmentId FROM Inventory WHERE CharacterId=%s;""", (char_id,))
            if not records:
                await reply_message(message, char_name + " doesn't have any items!")
                return
            response = "**INVENTORY**\n\n"
            for row in records:
                item_id = row[0]
                item_records = await select_sql("""SELECT EquipmentName FROM Equipment WHERE Id=%s;""", (item_id,))
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
            records = await select_sql(
                """SELECT Id,UserId FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""",
                (str(message.guild.id), parsed_string))
            if not records:
                await reply_message(message, "No character by that name found!")
                return
            for row in records:
                char_id = row[0]
                user_id = int(row[1])
            records = await select_sql("""SELECT EquipmentId FROM Inventory WHERE CharacterId=%s;""", (char_id,))
            if not records:
                await reply_message(message, parsed_string + " doesn't have any items!")
                return
            response = "**INVENTORY**\n\n"
            for row in records:
                item_id = row[0]
                item_records = await select_sql("""SELECT EquipmentName FROM Equipment WHERE Id=%s;""", (item_id,))
                for item in item_records:
                    response = response + item[0] + "\n"
            await reply_message(message, response)

        elif command == 'summons':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to check summons!")
                return
            if not parsed_string:
                await reply_message(message, "You didn't specify a character!")
                return
            records = await select_sql(
                """SELECT Id,UserId FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s ;""",
                (str(message.guild.id), parsed_string))
            if not records:
                await reply_message(message, "No character by that name found!")
                return
            for row in records:
                char_id = row[0]
                user_id = int(row[1])
            records = await select_sql("""SELECT MonsterId FROM SummonInventory WHERE CharacterId=%s;""", (char_id,))
            if not records:
                await reply_message(message, parsed_string + " doesn't have any summons!")
                return
            response = "**SUMMONS**\n\n"
            for row in records:
                item_id = row[0]
                item_records = await select_sql("""SELECT MonsterName FROM Monsters WHERE Id=%s;""", (item_id,))
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
            dm_tracker[message.author.id]["fieldlist"] = ["CharId", "ItemId", "TargetId"]
            dm_tracker[message.author.id]["fieldmeans"] = ["CharId", "ItemId", "TargetId"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId",
                                               str(message.author.id))

            await direct_message(message,
                                 "Please select a character to trade the item from by replying with the ID that is in bold.\n\n" + menu)
            await reply_message(message, "Please check your DMs for instructions on how to trade an item, <@" + str(
                message.author.id) + ">.")
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
            dm_tracker[message.author.id]["fieldlist"] = ["CharId", "ItemId", "TargetId"]
            dm_tracker[message.author.id]["fieldmeans"] = ["CharId", "ItemId", "TargetId"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId",
                                               str(message.author.id))

            await direct_message(message,
                                 "Please select a character to trade the item from by replying with the ID that is in bold.\n\n" + menu)
            await reply_message(message, "Please check your DMs for instructions on how to trade an item, <@" + str(
                message.author.id) + ">.")
        elif command == 'listitems':
            records = await select_sql("""SELECT EquipmentName FROM Equipment WHERE ServerId=%s;""",
                                       (str(message.guild.id),))
            if not records:
                await reply_message(message, "This server does not have any items yet!")
                return

            response = ""
            for row in records:
                response = response + row[0] + "\n"

            await reply_message(message, response)

        elif command == 'listraces':
            records = await select_sql("""SELECT Name FROM Races WHERE ServerId=%s;""", (str(message.guild.id),))
            if not records:
                await reply_message(message, "This server does not have any races yet!")
                return

            response = "**Server Race List**\n\n"
            for row in records:
                response = response + row[0] + "\n"

            await reply_message(message, response)
        elif command == 'listclasses':
            records = await select_sql("""SELECT Name FROM Classes WHERE ServerId=%s;""", (str(message.guild.id),))
            if not records:
                await reply_message(message, "This server does not have any classes yet!")
                return

            response = "**Server Class List**\n\n"
            for row in records:
                response = response + row[0] + "\n"

            await reply_message(message, response)
        elif command == 'listarmaments':
            records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE ServerId=%s;""",
                                       (str(message.guild.id),))
            if not records:
                await reply_message(message, "This server does not have any armaments yet!")
                return
            response = ""
            for row in records:
                response = response + row[0] + "\n"
            embed = discord.Embed(title="Server Armament Listing")
            embed.add_field(name="Armament Names", value=response)
            await message.channel.send(embed=embed)
        #            await reply_message(message, response)
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
            dm_tracker[message.author.id]["fieldlist"] = ["CharId", "VendorId", "ItemId"]
            dm_tracker[message.author.id]["fieldmeans"] = ["CharId", "VendorId", "ItemId"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            response = "**YOUR CHARACTERS**\n\n"
            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId",
                                               str(message.author.id))
            response = response + menu
            await direct_message(message,
                                 "Please select a character to sell the item for by replying with the ID that is in bold.\n\n" + response)
            await reply_message(message, "Please check your DMs for instructions on how to sell an item, <@" + str(
                message.author.id) + ">.")

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
            dm_tracker[message.author.id]["fieldlist"] = ["CharId", "VendorId", "ItemId"]
            dm_tracker[message.author.id]["fieldmeans"] = ["CharId", "VendorId", "ItemId"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            response = "**YOUR CHARACTERS**\n\n"
            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId",
                                               str(message.author.id))
            response = response + menu
            await direct_message(message,
                                 "Please select a character to sell the armament for by replying with the ID that is in bold.\n\n" + response)
            await reply_message(message, "Please check your DMs for instructions on how to sell an armament, <@" + str(
                message.author.id) + ">.")
        elif command == 'buff':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to use buffs!")
                return
            if not mass_spar_event[message.guild.id] and not server_encounters[message.guild.id]:
                await reply_message(message, "No encounter or spar in progress to use buffs for!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Character", "Buff", "Target"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'buff'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = ""
            characters = {}
            if mass_spar_event[message.guild.id]:
                characters[mass_spar_chars[message.guild.id][message.author.id]["CharId"]] = \
                    mass_spar_chars[message.guild.id][message.author.id]["CharName"]
            if server_encounters[message.guild.id]:
                characters[server_party_chars[message.guild.id][message.author.id]["CharId"]] = \
                    server_party_chars[message.guild.id][message.author.id]["CharName"]
            menu = "**CURRENT EVENT CHARACTERS**\n\n"
            for char in characters:
                menu = menu + "**" + str(char) + "** - " + characters[char] + "\n"

            await direct_message(message,
                                 "Select a character's buff to use by replying with their ID (the number in bold):\n" + menu)
            await reply_message(message, "<@" + str(message.author.id) + "> , check your DMs for how to use the buff.")
        elif command == 'newbuff':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to create new buffs!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newbuff'
            # BuffName VARCHAR(100), ManaCost Int, MinimumLevel Int, StatMod VARCHAR(30), Modifier Int, Description TEXT,
            dm_tracker[message.author.id]["fieldlist"] = ["BuffName", "ManaCost", "MinimumLevel", "StatMod", "Modifier",
                                                          "Description", "StatusChange", "StatusChangedBy",
                                                          "AllowedClasses", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = ["The name of the buff spell",
                                                           "The amount of mana drained to perform the buff",
                                                           "The minimum level required to use the buff",
                                                           "The status modified by the buff (Health, Mana, Stamina, Attack, Defense, MagicAttack, Charisma, Intellect or Agility)",
                                                           "The amount, positive or negative, of the buff's modification to the status",
                                                           "A free text description of the buff",
                                                           "The character status effect field (None,Paralyzed,Stunned,Asleep,DisabledSpell,Delusional,Poison,ManaDrain,StaminaDrain)",
                                                           "Stat change per turn or how many turns the effect lasts",
                                                           "Classes allowed, separated by commas, or All for any class",
                                                           "A picture of the buff (None for no link)"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            await reply_message(message, "Please check your DMs for instructions on how to create a new buff, <@" + str(
                message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested a new buff! Please type in the name you want, and then fill out the fields that appear.")
        elif command == 'editbuff':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to edit buffs!")
                return
            if not parsed_string:
                await reply_message(message, "No buff name specified!")
                return
            current_fields = await select_sql(
                """SELECT BuffName,ManaCost,MinimumLevel,StatMod,Modifier,Description,StatusChange,StatusChangedBy,AllowedClasses,PictureLink FROM Buffs WHERE ServerId=%s AND BuffName=%s;""",
                (str(message.guild.id), parsed_string))
            if not current_fields:
                await reply_message(message, "No buff found by that name!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)

            dm_tracker[message.author.id]["currentcommand"] = 'editbuff'
            # BuffName VARCHAR(100), ManaCost Int, MinimumLevel Int, StatMod VARCHAR(30), Modifier Int, Description TEXT,
            dm_tracker[message.author.id]["fieldlist"] = ["BuffName", "ManaCost", "MinimumLevel", "StatMod", "Modifier",
                                                          "Description", "StatusChange", "StatusChangedBy",
                                                          "AllowedClasses", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = ["The name of the buff spell",
                                                           "The amount of mana drained to perform the buff",
                                                           "The minimum level required to use the buff",
                                                           "The status modified by the buff (Health, Mana, Stamins, Attack, Defense, MagicAttack, Charisma, Intellect or Agility)",
                                                           "The amount, positive or negative, of the buff's modification to the status",
                                                           "A free text description of the buff",
                                                           "The character status effect field (None,Paralyzed,Stunned,Asleep,DisabledSpell,Delusional,Poison,ManaDrain,StaminaDrain)",
                                                           "Stat change per turn or how many turns the effect lasts",
                                                           "Classes allowed, separated by commas, or All for any class",
                                                           "A picture of the buff (None for no link)"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(current_fields[0][counter])
                counter = counter + 1

            await reply_message(message, "Please check your DMs for instructions on how to edit a buff, <@" + str(
                message.author.id) + ">.")

            await direct_message(message, "You have requested a buff edit! The first field is **" +
                                 dm_tracker[message.author.id]["fieldlist"][0] + "** and its value is **" +
                                 dm_tracker[message.author.id]["fielddict"][0] + "**!")
        elif command == 'deletebuff':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to delete buffs!")
                return
            if not parsed_string:
                await reply_message(message, "You didn't specify a buff name!")
                return
            records = await select_sql("""SELECT Id FROM EBuffs WHERE BuffName=%s AND ServerId=%s;""",
                                       (parsed_string, str(message.guild.id)))

            if not records:
                await reply_message(message, "No buff found by that name!")
                return
            for row in records:
                item_id = row[0]

            result = await commit_sql("""DELETE FROM Buffs WHERE Id=%s;""", (item_id,))
            if result:
                result_remove = await commit_sql("""DELETE FROM BuffSkills WHERE ServerId=%s AND BuffId=%s;""",
                                                 (str(message.guild.id), item_id))
                if result_remove:
                    await reply_message(message, "Buff removed from game successfully.")
                else:
                    await reply_message(message, "Database error!")
            else:
                await reply_message(message, "Database error!")
        elif command == 'changeowner':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to change character owners!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)

            dm_tracker[message.author.id]["currentcommand"] = 'changeowner'
            # BuffName VARCHAR(100), ManaCost Int, MinimumLevel Int, StatMod VARCHAR(30), Modifier Int, Description TEXT,
            dm_tracker[message.author.id]["fieldlist"] = ["Id", "UserId"]
            dm_tracker[message.author.id]["fieldmeans"] = ["Id", "UserId"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            await reply_message(message,
                                "Please check your DMs for instructions on how to change a character owner, <@" + str(
                                    message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested a character owner change! Please type in the response the **ID of the character**, and then enter each field as a reply to the DMs. When you have filled out all fields, the owner will be updated!\n\n" + menu)
        elif command == 'listbuffs':
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            menu = await make_simple_menu(message, "Buffs", "BuffName")
            response = ""
            response = response + menu
            embed = discord.Embed(title="Server Buff Listing")
            embed.add_field(name="Buff Names", value=response)
            await message.channel.send(embed=embed)
            #           await reply_message(message, response)
        elif command == 'givebuff':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to give buffs!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Character", "Buff"]
            dm_tracker[message.author.id]["fieldmeans"] = ["Character", "Buff"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'givebuff'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Pick a character to add a buff to:\n\nPlease choose a character by selecting the IDs.\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to give a buff, <@" + str(
                message.author.id) + ">.")
        elif command == 'takebuff':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to take spells!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["Character", "Spell"]
            dm_tracker[message.author.id]["fieldmeans"] = ["Character", "Spell"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'takebuff'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")
            response = "Pick a character to add a spell to:\n\nPlease choose a character by selecting the IDs.\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to take a spell, <@" + str(
                message.author.id) + ">.")
        elif command == 'listbuff':
            if not parsed_string:
                await reply_message(message, "You did not specify a buff!")
                return
            records = await select_sql(
                """SELECT BuffName,ManaCost,MinimumLevel,StatMod,Modifier,Description,StatusChange,StatusChangedBy,PictureLink,AllowedClasses FROM Buffs WHERE ServerId=%s AND BuffName=%s;""",
                (str(message.guild.id), str(parsed_string)))
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
                status_changed = row[6]
                status_changed_by = row[7]
                picture_link = row[8]
                allowed_classes =row[9]
            embed = discord.Embed(title="Buff Data for " + buff_name)
            if picture_link.startswith('http'):
                embed.set_thumbnail(url=picture_link)
            embed.add_field(name="Mana Cost:", value=mana_cost)
            embed.add_field(name="Minimum Level:", value=min_level)
            embed.add_field(name="Status Modified:", value=stat_mod)
            embed.add_field(name="Modified Value:", value=modifier)
            embed.add_field(name="Description:", value=description)
            embed.add_field(name="Status Change:", value=status_changed)
            embed.add_field(name="Status Changed By:", value=str(status_changed_by))
            embed.add_field(name="Allowed Classes:", value=str(allowed_classes))

            await message.channel.send(embed=embed)

            # response = "**BUFF DETAILS**\n\nName: " + buff_name + "\nMana Cost: " + mana_cost + "\nMinimum Level: " + min_level + "\nStatus Modified: " + stat_mod + "\nModified By: " + modifier + "\nDescription: " + description + "\nPicture Link: " + picture_link
            # await reply_message(message, response)

        elif command == 'useitem':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to use items!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = []
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'useitem1'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = ""

            records = await select_sql(
                """SELECT Id,CharacterName FROM CharacterProfiles WHERE ServerId=%s AND UserId=%s;""",
                (str(message.guild.id), str(message.author.id)))
            if not records:
                await reply_message(message, "No characters found for you!")
                return
            character_list = "**YOUR CHARACTERS**\n\n"
            for row in records:
                char_id = row[0]
                char_name = row[1]
                character_list = character_list + "**" + str(char_id) + "** " + char_name + "\n"

            await direct_message(message,
                                 "Select a character to use an item on by replying with their ID (the number in bold):\n" + character_list)
            await reply_message(message, "<@" + str(message.author.id) + "> , check your DMs for how to use the item.")


        elif command == 'equipped':
            char_name = parsed_string
            if not parsed_string:
                await reply_message(message, "No character name specified!")
                return
            records = await select_sql("""SELECT Id FROM CharacterProfiles WHERE CharacterName=%s AND ServerId=%s;""",
                                       (char_name, str(message.guild.id)))
            if not records:
                await reply_message(message, "No character found by that name!")
            for row in records:
                char_id = str(row[0])
            records = await select_sql(
                """SELECT IFNULL(HeadId,'0'), IFNULL(LeftHandId,'0'), IFNULL(RightHandId,'0'), IFNULL(ChestId,'0'), IFNULL(FeetId,'0'), IFNULL(FormId,'0') FROM CharacterArmaments WHERE CharacterId=%s;""",
                (char_id,))
            for row in records:
                head_id = row[0]
                left_id = row[1]
                right_id = row[2]
                chest_id = row[3]
                feet_id = row[4]
                form_id = row[5]
            if not records:
                await reply_message(message, "This character has nothing equipped!")
                return
            records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (head_id,))
            for row in records:
                head_name = row[0]
            try:
                head_name
            except:
                head_name = "None"
            records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (left_id,))
            for row in records:
                left_name = row[0]
            try:
                left_name
            except:
                left_name = "None"
            records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (right_id,))
            for row in records:
                right_name = row[0]
            try:
                right_name
            except:
                right_name = "None"
            records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (chest_id,))
            for row in records:
                chest_name = row[0]
            try:
                chest_name
            except:
                chest_name = "None"
            records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (feet_id,))
            for row in records:
                feet_name = row[0]
            try:
                feet_name
            except:
                feet_name = "None"
            records = await select_sql("""SELECT ArmamentName FROM Armaments WHERE Id=%s;""", (form_id,))
            for row in records:
                form_name = row[0]
            try:
                form_name
            except:
                form_name = "None"

            embed = discord.Embed(title="Current equipment for character " + parsed_string)
            embed.add_field(name="Head:", value=head_name)
            embed.add_field(name="Chest:", value=chest_name)
            embed.add_field(name="Left Hand:", value=left_name)
            embed.add_field(name="Right Hand:", value=right_name)
            embed.add_field(name="Feet:", value=feet_name)
            embed.add_field(name="Form:", value=form_name)

            await message.channel.send(embed=embed)

        # $            menu = "Current Armaments Equipped\n\nHead: **" +head_id + "** - " + head_name + "\nLeftHand: **" + left_id + "** - " + left_name + "\nRightHand: **" + right_id +  "** - " + right_name + "\nChest: **" + chest_id + "** - " + chest_name + "\nFeet: **" + feet_id + "** - " + feet_name +"\n"
        #           await reply_message(message, menu)

        elif command == 'lurk':
            if message.author.nick:
                name = message.author.nick
            else:
                name = message.author.name
            responses = [
                "*" + name + " lurks in the shadowy rafters with luminous orbs with parted tiers, trailing long digits through their platinum tresses.*",
                "**" + name + ":** ::lurk::", "*" + name + " flops on the lurker couch.*", name + ": *double lurk*",
                name + ": *luuuuuurk*", name + ": *posts that they are lurking so someone notices they are lurking*"]
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
            responses = ["flops on", "rolls around", "curls on", "lurks by", "farts near", "falls asleep on",
                         "throws Skittles at", "throws popcorn at", "huggles", "snugs", "hugs", "snuggles", "tucks in",
                         "watches", "stabs", "slaps", "sexes up", "tickles", "thwaps", "pinches", "smells",
                         "cries with", "laughs at", "fondles", "stalks", "leers at", "creeps by", "lays on", "glomps",
                         "clings to", "flirts with", "makes fun of", "nibbles on", "noms", "protects", "stupefies",
                         "snickers at"]
            usernames = message.guild.members
            user = random.choice(usernames)
            if message.mentions:
                user = message.mentions[0]
            response = "((*" + name + " " + random.choice(responses) + " " + str(user.display_name) + "*))"
            await reply_message(message, response)
            await message.delete()
        elif command == 'inactive':
            if active_chars[message.guild.id][message.author.id] is None:
                await reply_messsage(message, "You have no active character set!")
                return
            active_chars[message.guild.id][message.author.id] = None
            result = await commit_sql("""DELETE FROM ActiveChars WHERE ServerId=%s AND UserId=%s;""",
                                      (str(message.guild.id), str(message.author.id)))
            await reply_message(message, "Active character cleared for user " + message.author.display_name)
        elif command == 'active':
            char_name = parsed_string

            if not char_name:
                await reply_message(message, "No character name specified!")
                return
            #            get_character_profile = """SELECT CharacterName,IFNULL(Age,' '),IFNULL(Race,' '), IFNULL(Gender,' '), IFNULL(Height,' '), IFNULL(Weight,' '), IFNULL(PlayedBy,' '), IFNULL(Origin,' '), IFNULL(Occupation,' '), UserId,Attack,Defense,MagicAttack,Health,Mana,Level,Experience,Stamina,Agility,Intellect,Charisma, IFNULL(Biography,' '), IFNULL(Currency,' '), IFNULL(Description,' '), IFNULL(Personality,' '), IFNULL(Powers,' '), IFNULL(Strengths,' '), IFNULL(Weaknesses,' '), IFNULL(Skills,' '), IFNULL(PictureLink,' '),StatPoints,IFNULL(Status,'None'),Id,IFNULL(Class,' ') FROM CharacterProfiles WHERE CharacterName=%s  AND ServerId=%s;"""
            get_character_profile = """SELECT Id,UserId FROM CharacterProfiles WHERE CharacterName=%s  AND ServerId=%s;"""
            char_tuple = (char_name, str(message.guild.id))

            records = await select_sql(get_character_profile, char_tuple)
            if not records:
                await reply_message(message, "No character found by that name!")
                return
            for row in records:
                char_id = int(row[0])
                user_id = int(row[1])
            if user_id != message.author.id:
                await reply_message(message, "This isn't your character!")
                return
            active_chars[message.guild.id][message.author.id] = char_id
            records = await select_sql("""SELECT CharId FROM ActiveChars WHERE ServerId=%s AND UserId=%s;""",
                                       (str(message.guild.id), str(message.author.id)))
            if not records:
                result = await commit_sql(
                    """INSERT INTO ActiveChars (ServerId, UserId, CharacterId) VALUES (%s, %s, %s);""",
                    (str(message.guild.id), str(message.author.id), str(char_id)))
            else:
                result = await commit_sql("""UPDATE ActiveChars SET CharacterId=%s WHERE ServerId=%s AND UserId=%s;""",
                                          (str(char_id), str(message.guild.id), str(message.author.id)))
            await reply_message(message,
                                "User " + message.author.display_name + " set active character to " + char_name + "!")

        elif command == 'givecurrency':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to give currency!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'givecurrency'
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterId", "Currency"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")

            response = "Please select a character by replying to this DM with the character ID to give currency to:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to grant currency, <@" + str(
                message.author.id) + ">.")
        elif command == 'takecurrency':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to take currency!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'takecurrency'
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterId", "Currency"]
            dm_tracker[message.author.id]["fieldmeans"] = ["CharacterId", "Currency"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            menu = await make_simple_menu(message, "CharacterProfiles", "CharacterName")

            response = "Please select a character by replying to this DM with the character ID to give currency to:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "Please check your DMs for instructions on how to take currency, <@" + str(
                message.author.id) + ">.")
        elif command == 'equip':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the Plaer role to equip armaments!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'equip'
            dm_tracker[message.author.id]["fieldlist"] = ["CharacterId", "ArmamentId", "Slot"]
            dm_tracker[message.author.id]["fieldmeans"] = ["CharacterId", "ArmamentId", "Slot"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            records = await select_sql(
                """SELECT Id,CharacterName FROM CharacterProfiles WHERE ServerId=%s AND UserId=%s;""",
                (str(message.guild.id), str(message.author.id)))
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
            await reply_message(message, "Please check your DMs for instructions on how to equip armaments, <@" + str(
                message.author.id) + ">.")
        elif command == 'unequip':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the Player role to unequip armaments!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'unequip'
            dm_tracker[message.author.id]["fieldlist"] = []
            dm_tracker[message.author.id]["fieldmeans"] = []
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            records = await select_sql(
                """SELECT Id,CharacterName FROM CharacterProfiles WHERE ServerId=%s AND UserId=%s;""",
                (str(message.guild.id), str(message.author.id)))
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
            await reply_message(message, "Please check your DMs for instructions on how to equip armaments, <@" + str(
                message.author.id) + ">.")

        elif command == 'newmonster':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to create monsters!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newmonster'
            dm_tracker[message.author.id]["fieldlist"] = ["MonsterName", "Description", "Health", "Level", "Attack",
                                                          "Defense", "MagicAttack", "MaxCurrencyDrop", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = ["The name of the monster as appearing in encounters",
                                                           " A brief description of the monster physically, its temperament, and powers",
                                                           "The total health of the monster. When this reaches zero, the encounter ends. It does not restore",
                                                           "The level of the monster, used for calculating experience",
                                                           "The attack power of the monster. The monster's damage multiplier will be a random number between one and five",
                                                           "The defense against player damage the monster has",
                                                           "The Magic Attack of the monster, currently unused",
                                                           "The money the monster drops when the encounter ends.",
                                                           "A picture of the monster, either Internet link or direct Discord upload (None for no link)"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            await reply_message(message,
                                "Please check your DMs for instructions on how to create a new monster, <@" + str(
                                    message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested a new monster! Please type in the name you want, and then fill out the fields that appear.")
        elif command == 'newcritter':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to create critters!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentcommand"] = 'newcritter'
            dm_tracker[message.author.id]["fieldlist"] = ["CritterName", "Description", "Health", "Level", "Attack",
                                                          "Defense", "MagicAttack", "MaxCurrencyDrop", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = ["The name of the critter as appearing in encounters",
                                                           " A brief description of the critter physically, its temperament, and powers",
                                                           "The total health of the critter. When this reaches zero, the encounter ends. It does not restore",
                                                           "The level of the critter, used for calculating experience",
                                                           "The attack power of the critter. The critter's damage multiplier will be a random number between one and five",
                                                           "The defense against player damage the critter has",
                                                           "The Magic Attack of the critter, currently unused",
                                                           "The money the critter drops when the encounter ends.",
                                                           "A picture of the critter, either Internet link or direct Discord upload (None for no link)"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            await reply_message(message,
                                "Please check your DMs for instructions on how to create a new critter, <@" + str(
                                    message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested a new critter! Please type in the name you want, and then fill out the fields that appear.")
        #        elif command == 'changeinfo':
        #            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
        #                await reply_message(message, "You must be a member of the player role to edit character info!")
        #                return
        ##            if not parsed_string:
        #                await reply_message(message, "No character name specified!")
        #                return
        #            current_fields = await select_sql("""SELECT IFNULL(Biography,'None'),IFNULL(Skills,'None'),IFNULL(Strengths,'None'),IFNULL(Weaknesses,'None'),IFNULL(Powers,'None'),IFNULL(Personality,'None'),IFNULL(Description,'None') FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s;""", (str(message.guild.id), parsed_string))
        #            if not current_fields:
        #                await reply_message(message, "No character found by that name!")
        #                return
        #            for row in current_fields:
        #                fields = row
        #
        #            if message.author.id not in dm_tracker.keys():
        #               await initialize_dm(message.author.id)
        #           dm_tracker[message.author.id]["fieldlist"] = ["Biography","Skills","Strengths","Weaknesses","Powers","Personality","Description"]
        #           dm_tracker[message.author.id]["fieldmeans"] = ["Any information about the character's history (tragic past, family story, etc)","Any speciality skills the character has (ace sniper, expert in arcane arts, engineer PhD, etc)","Free text description of what the character is good at (drawing, melee combat, science, magic)", "Free text description of what weaknesses the character has (silver, light, Kryptonite, etc)", "The supernatural abilities the character has (such as magic, fire, telepathy)","Free text description of the character's personality (aloof, angry, intelligent)", "Free text physical description of the character, especially if no play by or picture link is provided, or a description of alternate forms (such as wolf form, final form, etc)"]
        #            dm_tracker[message.author.id]["currentfield"] = 0
        #            dm_tracker[message.author.id]["fielddict"]= []
        #            dm_tracker[message.author.id]["fielddict"] = []
        #            dm_tracker[message.author.id]["currentcommand"] = 'editinfo'
        #            dm_tracker[message.author.id]["server_id"] = message.guild.id
        #            dm_tracker[message.author.id]["commandchannel"] = message.channel
        #            dm_tracker[message.author.id]["parameters"] = parsed_string
        #           counter = 0
        #           for row in dm_tracker[message.author.id]["fieldlist"]:
        #               dm_tracker[message.author.id]["fielddict"].append(fields[counter])
        #               counter = counter + 1

        # await reply_message(message, "Please check your DMs for instructions on how to edit a character, <@" + str(message.author.id) + ">.")

        # await direct_message(message, "You have requested to edit the character**" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the character will be updated!\nThe first field is **" + dm_tracker[message.author.id]["fieldlist"][1] + "** and its current value is **" + dm_tracker[message.author.id]["fielddict"][1] + "**.")

        elif command == 'editmonster':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to edit monsters!")
                return
            if not parsed_string:
                await reply_message(message, "No monster name specified!")
                return
            current_fields = await select_sql(
                """SELECT Description,Health,Level,Attack,Defense,MagicAttack,IFNULL(MaxCurrencyDrop,0),IFNULL(PictureLink,'None') FROM Monsters WHERE ServerId=%s AND MonsterName=%s;""",
                (str(message.guild.id), parsed_string))
            if not current_fields:
                await reply_message(message, "No monster found by that name!")
                return
            for row in current_fields:
                fields = row

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["MonsterName", "Description", "Health", "Level", "Attack",
                                                          "Defense", "MagicAttack", "MaxCurrencyDrop", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = ["The name of the monster as appearing in encounters",
                                                           " A brief description of the monster physically, its temperament, and powers",
                                                           "The total health of the monster. When this reaches zero, the encounter ends. It does not restore",
                                                           "The level of the monster, used for calculating experience",
                                                           "The attack power of the monster. The monster's damage multiplier will be a random number between one and five",
                                                           "The defense against player damage the monster has",
                                                           "The Magic Attack of the monster, currently unused",
                                                           "The amount of money the monster drops when the encounter ends.",
                                                           "A picture of the monster, either Internet link or direct Discord upload (None for no link)"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
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

            await reply_message(message, "Please check your DMs for instructions on how to edit a monster, <@" + str(
                message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested to edit the monster **" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the monster will be updated!\nThe first field is **" +
                                 dm_tracker[message.author.id]["fieldlist"][0] + "** and its current value is **" +
                                 dm_tracker[message.author.id]["fielddict"][0] + "**.")
        elif command == 'editcritter':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to edit critters!")
                return
            if not parsed_string:
                await reply_message(message, "No critter name specified!")
                return
            current_fields = await select_sql(
                """SELECT Description,Health,Level,Attack,Defense,MagicAttack,IFNULL(MaxCurrencyDrop,0),IFNULL(PictureLink,'None') FROM Critters WHERE ServerId=%s AND CritterName=%s;""",
                (str(message.guild.id), parsed_string))
            if not current_fields:
                await reply_message(message, "No critter found by that name!")
                return
            for row in current_fields:
                fields = row

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["CritterName", "Description", "Health", "Level", "Attack",
                                                          "Defense", "MagicAttack", "MaxCurrencyDrop", "PictureLink"]
            dm_tracker[message.author.id]["fieldmeans"] = ["The name of the critter as appearing in encounters",
                                                           " A brief description of the critter physically, its temperament, and powers",
                                                           "The total health of the critter. When this reaches zero, the encounter ends. It does not restore",
                                                           "The level of the critter, used for calculating experience",
                                                           "The attack power of the critter. The critter's damage multiplier will be a random number between one and five",
                                                           "The defense against player damage the critter has",
                                                           "The Magic Attack of the critter, currently unused",
                                                           "The amount of money the critter drops when the encounter ends.",
                                                           "A picture of the critter, either Internet link or direct Discord upload (None for no link)"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["fielddict"].append(parsed_string)
            dm_tracker[message.author.id]["currentcommand"] = 'editcritter'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            counter = 0
            for row in dm_tracker[message.author.id]["fieldlist"]:
                dm_tracker[message.author.id]["fielddict"].append(fields[counter])
                counter = counter + 1
                if counter > len(dm_tracker[message.author.id]["fieldlist"]) - 2:
                    break

            await reply_message(message, "Please check your DMs for instructions on how to edit a critter, <@" + str(
                message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested to edit the critter **" + parsed_string + "**. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the critter will be updated!\nThe first field is **" +
                                 dm_tracker[message.author.id]["fieldlist"][0] + "** and its current value is **" +
                                 dm_tracker[message.author.id]["fielddict"][0] + "**.")
        elif command == 'listmonsters':
            records = await select_sql("""SELECT MonsterName FROM Monsters WHERE ServerId=%s;""",
                                       (str(message.guild.id),))
            if not records:
                await reply_message(message, "No monsters are on this server yet!")
                return
            response = ""
            for row in records:
                response = response + row[0] + "\n"
            embed = discord.Embed(title="Server Monster Listing")
            embed.add_field(name="Monster Names", value=response)
            await message.channel.send(embed=embed)
        elif command == 'listcritters':
            records = await select_sql("""SELECT CritterName FROM Critters WHERE ServerId=%s;""",
                                       (str(message.guild.id),))
            if not records:
                await reply_message(message, "No critters are on this server yet!")
                return
            response = ""
            for row in records:
                response = response + row[0] + "\n"
            embed = discord.Embed(title="Server Critter Listing")
            embed.add_field(name="Critter Names", value=response)
            await message.channel.send(embed=embed)            
            #           await reply_message(message, response)
        elif command == 'listmonster':
            if not parsed_string:
                await reply_message(message, "No monster name specified!")
                return
            records = await select_sql(
                """SELECT Description,Health,Level,Attack,Defense,MagicAttack,IFNULL(PictureLink,' '),MaxCurrencyDrop FROM Monsters WHERE ServerId=%s AND MonsterName=%s;""",
                (str(message.guild.id), parsed_string))
            if not records:
                await reply_message(message, "No monster found with that name!")
                return
            response = "**MONSTER DATA**\n\n"
            embed = discord.Embed(title="Monster data for " + parsed_string)

            for row in records:
                if re.search(r"http", row[6]):
                    embed.set_thumbnail(url=row[6])
                embed.add_field(name="Description:", value=row[0])
                embed.add_field(name="Health:", value=str(row[1]))
                embed.add_field(name="Level:", value=str(row[2]))
                embed.add_field(name="Melee Attack Power:", value=str(row[3]))
                embed.add_field(name="Defense:", value=str(row[4]))
                embed.add_field(name="Magic Attack Power:", value=str(row[5]))

            # await reply_message(message, response)
            await message.channel.send(embed=embed)
        elif command == 'listcritter':
            if not parsed_string:
                await reply_message(message, "No critter name specified!")
                return
            records = await select_sql(
                """SELECT Description,Health,Level,Attack,Defense,MagicAttack,IFNULL(PictureLink,' '),MaxCurrencyDrop FROM Critters WHERE ServerId=%s AND CritterName=%s;""",
                (str(message.guild.id), parsed_string))
            if not records:
                await reply_message(message, "No critter found with that name!")
                return
            response = "**CRITTER DATA**\n\n"
            embed = discord.Embed(title="Critter data for " + parsed_string)

            for row in records:
                if re.search(r"http", row[6]):
                    embed.set_thumbnail(url=row[6])
                embed.add_field(name="Description:", value=row[0])
                embed.add_field(name="Health:", value=str(row[1]))
                embed.add_field(name="Level:", value=str(row[2]))
                embed.add_field(name="Melee Attack Power:", value=str(row[3]))
                embed.add_field(name="Defense:", value=str(row[4]))
                embed.add_field(name="Magic Attack Power:", value=str(row[5]))

            # await reply_message(message, response)
            await message.channel.send(embed=embed)
        elif command == 'listitem':
            if not parsed_string:
                await reply_message(message, "No item name specified!")
                return
            records = await select_sql(
                """SELECT EquipmentDescription, EquipmentCost, MinimumLevel, StatMod, Modifier, StatusChange, StatusChangedBy, PictureLink, AllowedClasses FROM Equipment WHERE ServerId=%s AND EquipmentName=%s;""",
                (str(message.guild.id), parsed_string))
            if not records:
                await reply_message(message, "No item found with that name!")
                return
            response = "**ITEM DATA**\n\n"
            embed = discord.Embed(title="Item data for " + parsed_string)

            for row in records:
                if row[7].startswith('http'):
                    embed.set_thumbnail(url=row[7])
                embed.add_field(name="Description", value=row[0])
                embed.add_field(name="Price", value=str(row[1]))
                embed.add_field(name="Minimum Level:", value=str(row[2]))
                embed.add_field(name="Status Modified:", value=row[3])
                embed.add_field(name="Modified by value:", value=str(row[4]))
                embed.add_field(name="Status Change:", value=row[5])
                embed.add_field(name="Status Changed By:", value=str(row[6]))
                embed.add_field(name="Allowed Classes:", value=str(row[8]))

                response = response + "Name: " + parsed_string + "\nDescription: " + row[0] + "\nPrice: " + str(
                    row[1]) + "\nMinimum Level: " + str(row[2]) + "\nStat Modified: " + str(
                    row[3]) + "\nModifier Change: " + str(row[4]) + "\nPicture Link: " + row[5] + "\n"
            #           await reply_message(message, response)
            await message.channel.send(embed=embed)


        elif command == 'listcustomcommands':
            response = "**CUSTOM COMMANDS**\n\n"
            if len(custom_commands[message.guild.id]) < 1:
                await reply_message(message, "No custom commands defined!!")
                return
            for x in custom_commands[message.guild.id]:
                response = response + x + "\n"
            await reply_message(message, response)

        elif command == 'listcustomcommand':
            if not parsed_string:
                await reply_message(message, "You didn't specify a command to list!")
                return
            try:
                custom_commands[message.guild.id][parsed_string]
            except:
                await reply_message(message, "That command doesn't exist!")
                return
            response = "**Responses for " + parsed_string + "**\n\n"
            counter = 1
            for x in custom_commands[message.guild.id][parsed_string]:
                response = response + str(counter) + " - " + x + "\n"
                counter = counter + 1
            await reply_message(message, response)

        elif command == 'listarmament':
            if not parsed_string:
                await reply_message(message, "No armament name specified!")
                return
            records = await select_sql(
                """SELECT Description, ArmamentCost, MinimumLevel, StatMod, Modifier, Slot, DamageMin, DamageMax, Defense, StatusChange, StatusChangedBy, PictureLink,AllowedClasses FROM Armaments WHERE ServerId=%s AND ArmamentName=%s;""",
                (str(message.guild.id), parsed_string))
            if not records:
                await reply_message(message, "No armament found with that name!")
                return
            response = "**ARMAMENT DATA**\n\n"
            embed = discord.Embed(title="Armament data for " + parsed_string)

            for row in records:
                if row[11].startswith('http'):
                    embed.set_thumbnail(url=row[11])
                embed.add_field(name="Description:", value=row[0])
                embed.add_field(name="Price:", value=str(row[1]))
                embed.add_field(name="Minimum Level:", value=str(row[2]))
                embed.add_field(name="Status Modified:", value=row[3])
                embed.add_field(name="Modified by value:", value=str(row[4]))
                embed.add_field(name="Equipment Slot:", value=row[5])
                embed.add_field(name="Minimum Damage:", value=str(row[6]))
                embed.add_field(name="Maximum Damage:", value=str(row[7]))
                embed.add_field(name="Defense:", value=str(row[8]))
                embed.add_field(name="Status Change:", value=row[9])
                embed.add_field(name="Status Changed By:", value=str(row[10]))
                embed.add_field(name="Allowed Classes:", value=str(row[12]))

                response = response + "Name: " + parsed_string + "\nDescription: " + row[0] + "\nPrice: " + str(
                    row[1]) + "\nMinimum Level: " + str(row[2]) + "\nStat Modified: " + str(
                    row[3]) + "\nModifier Change: " + str(row[4]) + "\nSlot: " + row[5] + "\nMinimum Damage: " + str(
                    row[6]) + "\nMaximum Damage: " + str(row[7]) + "\nDefense: " + str(row[8]) + "\nPicture Link: " + \
                           row[9] + "\n"
            await message.channel.send(embed=embed)

            # await reply_message(message, response)

        elif command == 'monster3':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"],
                              message.author) and message.author != server_party[message.guild.id][0]:
                await reply_message(message, "You must be a member of the GM role to start an encounter!")
                return
            if server_encounters[message.guild.id]:
                await reply_message(message,
                                    "Monster encounter already in progress! There can only be one encounter active per server!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = ["MonsterName"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'monster3'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            menu = await make_simple_menu(message, "Monsters", "MonsterName")
            response = "Please select a monster from the list of monsters below by replying with the ID that is in bold:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "<@" + str(
                message.author.id) + "> , please see your DMs for instructions on how to choose a monster.")


        elif command == 'monster1':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to encounter a monster!")
                return
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"],
                              message.author) and message.mentions:
                await reply_message(message,
                                    "You must be a member of the player role to create a new server encounter party with others!")
                return

            if server_party[message.guild.id]:
                await reply_message(message, "Server party already exists!")
                return
            if message.mentions:
                server_party[message.guild.id] = message.mentions
            else:
                server_party[message.guild.id] = [message.author, ]
            await reply_message(message,
                                "Server party created successfully. Type =monster2 to set your encounter character, then =monster3 to select a monster for the encounter.")
        elif command == 'hunt':
        
            server_party[message.guild.id] = [message.author, ]
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to set an encounter character!")
                return
            if str(message.author.id) not in str(server_party[message.guild.id]):
                await reply_message(message, "You're not part of the server party!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = ["encounterchar"]
            dm_tracker[message.author.id]["currentcommand"] = 'hunt'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId",
                                               str(message.author.id))
            await direct_message(message,
                                 "Please reply to this message with the ID in bold of the character you wish to hunt with.\n\n**CHARACTER LIST**\n\n" + menu)
            await reply_message(message,
                                "Please check your DMs for instructions on how to choose a character, <@" + str(
                                    message.author.id) + "> .")            
            
        elif command == 'spar1':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to create a server spar group!")
                return
            if not message.mentions:
                await reply_message(message, "You didn't mention any spar members!")
                return
            mass_spar[message.guild.id] = message.mentions
            for user in mass_spar[message.guild.id]:
                mass_spar_confirm[message.guild.id][user.id] = {}
                mass_spar_confirm[message.guild.id][user.id]["Confirm"] = False
            await reply_message(message,
                                "Spar group created successfully. Mentioned members, please type **=yes** or **=no** to join or refuse the spar!")
        elif command == 'yes':
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
            await reply_message(message, "User <@" + str(
                message.author.id) + "> confirmed spar join! Type =spar2 to select a character for the spar!")
        elif command == 'no':
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
            await reply_message(message, "User <@" + str(
                message.author.id) + "> denied the spar and has been removed from the spar!")
            if len(mass_spar[message.guild.id]) <= 1:
                await reply_message(message, "The spar has one member or less, so the spar has been canceled!")
                mass_spar[message.guild.id] = {}
        elif command == 'spar3':
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
                    if not mass_spar_confirm[message.guild.id][user]["Confirm"]:
                        response = response + "<@" + str(user) + ">, "
                await reply_message(message, response)
                return
            all_players_setchar = True
            for user in mass_spar[message.guild.id]:
                try:
                    mass_spar_chars[message.guild.id][user.id]
                except:
                    all_players_setchar = False
            if not all_players_setchar:
                response = "Not all players have set a spar character. The following players need to set a spar character: "
                for user in mass_spar[message.guild.id]:
                    try:
                        mass_spar_chars[message.guild.id][user.id]
                    except:
                        response = response + "<@" + str(user.id) + ">, "
                await reply_message(message, response)
                return
            mass_spar_event[message.guild.id] = True
            if mass_spar_turn[message.guild.id] != 1:
                mass_spar_turn[message.guild.id] = 0
            await reply_message(message, "The spar has begun! <@" + str(
                mass_spar[message.guild.id][0].id) + "> gets first blood!")
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
            dm_tracker[message.author.id]["fieldlist"] = ["SpellId", "Target"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'castspar'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            menu = await make_menu(message, "MagicSkills", "Spells", "SpellId", "CharacterId", "SpellName",
                                   str(mass_spar_chars[server_id][user_id]["CharId"]))
            response = "Please select a spell from the list of your character's spells below by replying with the ID that is in bold:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "<@" + str(
                message.author.id) + "> , please see your DMs for instructions on how to cast a spell.")

        elif command == 'summonspar':
            server_id = message.guild.id
            user_id = message.author.id
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to summon monsters!")
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
            dm_tracker[message.author.id]["fieldlist"] = ["MonsterId", "Target"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'summonspar'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            menu = await make_menu(message, "SummonInventory", "Monsters", "MonsterId", "CharacterId", "MonsterName",
                                   str(mass_spar_chars[server_id][user_id]["CharId"]))
            response = "Please select a spell from the list of your character's summons below by replying with the ID that is in bold:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "<@" + str(
                message.author.id) + "> , please see your DMs for instructions on how to summon a monster.")
        elif command == 'armaments':
            char_name = parsed_string
            if not char_name:
                await reply_message(message, "No character specified!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["fieldlist"] = []
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            records = await select_sql("""SELECT Id FROM CharacterProfiles WHERE ServerId=%s AND CharacterName=%s;""",
                                       (str(message.guild.id), parsed_string))
            if not records:
                await reply_message(message, "No character found by that name!")
                return
            for row in records:
                char_id = row[0]
            menu = await make_menu(message, "ArmamentInventory", "Armaments", "ArmamentId", "CharacterId",
                                   "ArmamentName", str(char_id))
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
                await reply_message(message,
                                    "Why are you casting " + parsed_string + "? There's nothing to attack here!")
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
            dm_tracker[message.author.id]["fieldlist"] = ["AttackId", "Target"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'meleespar'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            menu = await make_menu(message, "MeleeSkills", "Melee", "MeleeId", "CharacterId", "AttackName",
                                   str(mass_spar_chars[server_id][user_id]["CharId"]))
            response = "Please select a spell from the list of your character's attacks below by replying with the ID that is in bold:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "<@" + str(
                message.author.id) + "> , please see your DMs for instructions on how to attack.")

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
            dm_tracker[message.author.id]["fieldlist"] = ["AttackId", "Target"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'weaponspar'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            records = await select_sql(
                "SELECT IFNULL(LeftHandId,'None'),IFNULL(RightHandId,'None') FROM CharacterArmaments Where CharacterId=%s;",
                (str(mass_spar_chars[server_id][user_id]["CharId"]),))
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
            try:
                left_name
            except:
                left_name = 'None'
            try:
                right_name
            except:
                right_name = 'None'
            menu = "Armaments Equipped:\n\n" + left_hand + " - " + left_name + "\n" + right_hand + " - " + right_name
            response = "Please select an armament from the list of your character's equipment below by replying with the ID that is in bold:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "<@" + str(
                message.author.id) + "> , please see your DMs for instructions on how to attack.")

        elif command == 'disarm':
            server_id = message.guild.id
            user_id = message.author.id
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to use disarming attacks!")
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
            dm_tracker[message.author.id]["fieldlist"] = ["CharId", "Disarmed"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'disarm'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            char_map = {}
            response = "Select a target:\n\n"
            for character in mass_spar_chars[server_id]:
                char_name = mass_spar_chars[server_id][character]["CharName"]
                char_id = mass_spar_chars[server_id][character]["CharId"]
                char_map[char_id] = character
                response = response + "**" + str(char_id) + "** - " + char_name + "\n"
            dm_tracker[message.author.id]["parameters"] = char_map
            await direct_message(message, response)

            await reply_message(message, "<@" + str(
                message.author.id) + "> , please see your DMs for instructions on how to disarm.")

        elif command == 'spar2':
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
            dm_tracker[message.author.id]["fielddict"] = ["sparchar"]
            dm_tracker[message.author.id]["currentcommand"] = 'spar2'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId",
                                               str(message.author.id))
            await direct_message(message,
                                 "Please reply to this message with the ID in bold of the character you wish to spar with.\n\n**CHARACTER LIST**\n\n" + menu)
            await reply_message(message,
                                "<@" + str(message.author.id) + "> , please check your DMs to select a character.")
        elif command == 'disbandparty':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to disband a party!")
                return
            if server_encounters[message.guild.id]:
                await reply_message(message, "There's a server encounter in progress. Cannot disband!")
                return
            server_party[message.guild.id].clear()
            server_party_chars[message.guild.id].clear()
            server_encounters[message.guild.id] = False
            server_monsters[message.guild.id].clear()
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
            server_party[message.guild.id] = {}
            server_party_chars[message.guild.id] = {}
            await reply_message(message, "Encounter aborted. No health will be deducted and no XP will be gained.")

        elif command == 'monster2':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to set an encounter character!")
                return
            if str(message.author.id) not in str(server_party[message.guild.id]):
                await reply_message(message, "You're not part of the server party!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = ["encounterchar"]
            dm_tracker[message.author.id]["currentcommand"] = 'monster2'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel

            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId",
                                               str(message.author.id))
            await direct_message(message,
                                 "Please reply to this message with the ID in bold of the character you wish to join the party with.\n\n**CHARACTER LIST**\n\n" + menu)
            await reply_message(message,
                                "Please check your DMs for instructions on how to choose a character, <@" + str(
                                    message.author.id) + "> .")


        elif command == 'monsterattack':
            if not role_check(guild_settings[message.guild.id]["GameModeratorRole"], message.author):
                await reply_message(message, "You must be a member of the GM role to attack with the monster!")
                return
            server_id = message.guild.id
            if not server_encounters[server_id]:
                await reply_message(message, "No encounter in progress!")
                return
            target = random.choice(list(server_party_chars[server_id].keys()))
            attack_text = " " + str(server_monsters[server_id]["MonsterName"]) + " attacks " + str(
                server_party_chars[server_id][target]["CharName"]) + "!"
            #           await post_webhook(message.channel, server_monsters[server_id]["MonsterName"], attack_text, server_monsters[server_id]["PictureLink"])
            embed = discord.Embed(title=attack_text)
            if server_monsters[server_id]["PictureLink"].startswith('http'):
                embed.set_thumbnail(url=server_monsters[server_id]["PictureLink"])
            await message.channel.send(embed=embed)

            asyncio.sleep(1)
            #          await reply_message(message, " " + str(server_monsters[server_id]["MonsterName"]) + " attacks " + str(server_party_chars[server_id][target]["CharName"]) + "!")
            dodge = await calculate_dodge(server_monsters[server_id]["Level"],
                                          server_party_chars[server_id][target]["Agility"])
            if dodge:
                dodge_text = server_party_chars[server_id][target]["CharName"] + " dodged the attack! No damage taken!"
                embed = discord.Embed(title=dodge_text)
                if server_party_chars[server_id][target]["PictureLink"].startswith('http'):
                    embed.set_thumbnail(url=server_party_chars[server_id][target]["PictureLink"])
                await message.channel.send(embed=embed)
                #                await post_webhook(message.channel, server_party_chars[server_id][target]["CharName"], dodge_text, server_party_chars[server_id][target]["PictureLink"])
                # await reply_message(message, server_party_chars[server_id][target]["CharName"] + " dodged the attack! No damage taken!")
                return
            else:
                damage = await calculate_damage(server_monsters[server_id]["Attack"],
                                                server_party_chars[server_id][target]["Defense"], random.randint(1, 5),
                                                server_monsters[server_id]["Level"],
                                                server_party_chars[server_id][target]["Level"])
                server_party_chars[server_id][target]["Health"] = int(
                    server_party_chars[server_id][target]["Health"] - damage)
                hit_text = server_party_chars[server_id][target]["CharName"] + " was hit by " + \
                           server_monsters[server_id]["MonsterName"] + " for " + str(
                    damage) + " points!\n\nHealth now at " + str(server_party_chars[server_id][target]["Health"]) + "!"
                embed = discord.Embed(title=hit_text)
                if server_party_chars[server_id][target]["PictureLink"].startswith('http'):
                    embed.set_thumbnail(url=server_party_chars[server_id][target]["PictureLink"])
                await message.channel.send(embed=embed)
                #                await post_webhook(message.channel, server_party_chars[server_id][target]["CharName"], hit_text, server_party_chars[server_id][target]["PictureLink"])
                #               await reply_message(message, server_party_chars[server_id][target]["CharName"] + " was hit by " + server_monsters[server_id]["MonsterName"] + " for " + str(damage) + " points!\n\nHealth now at " + str(server_party_chars[server_id][target]["Health"]))
                if server_party_chars[server_id][target]["Health"] < 1:
                    await reply_message(message, server_party_chars[server_id][target][
                        "CharName"] + " has no health left and is out of the fight!")
                    del server_party_chars[server_id][target]
                if len(server_party_chars[server_id]) < 1:
                    await reply_message(message, "The party has been vanquished! " + server_monsters[server_id][
                        "MonsterName"] + " wins! No experience will be awarded.")
                    server_encounters[server_id] = False

        elif command == 'castmonster':
            server_id = message.guild.id
            user_id = message.author.id
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to cast spells!")
                return
            if not server_encounters[server_id]:
                await reply_message(message,
                                    "Why are you casting " + parsed_string + "? There's nothing to attack here!")
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
            dm_tracker[message.author.id]["fieldlist"] = ["SpellId"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = ["castmonster"]
            dm_tracker[message.author.id]["currentcommand"] = 'castmonster'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            menu = await make_menu(message, "MagicSkills", "Spells", "SpellId", "CharacterId", "SpellName",
                                   str(server_party_chars[server_id][user_id]["CharId"]))
            response = "Please select a spell from the list of your character's spells below by replying with the ID that is in bold:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "<@" + str(
                message.author.id) + "> , please see your DMs for instructions on how to cast a spell.")

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
            dm_tracker[message.author.id]["fielddict"] = ["meleemonster"]
            dm_tracker[message.author.id]["currentcommand"] = 'meleemonster'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            menu = await make_menu(message, "MeleeSkills", "Melee", "MeleeId", "CharacterId", "AttackName",
                                   str(server_party_chars[server_id][user_id]["CharId"]))
            response = "Please select a melee attack from the list of your character's attacks below by replying with the ID that is in bold:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "<@" + str(
                message.author.id) + "> , please see your DMs for instructions on how to attack.")

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
            dm_tracker[message.author.id]["fielddict"] = ["weaponmonster"]
            dm_tracker[message.author.id]["currentcommand"] = 'weaponmonster'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            records = await select_sql(
                "SELECT IFNULL(LeftHandId,'None'),IFNULL(RightHandId,'None') FROM CharacterArmaments Where CharacterId=%s;",
                (str(server_party_chars[server_id][user_id]["CharId"]),))
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
            try:
                left_name
            except:
                left_name = 'None'
            try:
                right_name
            except:
                right_name = 'None'
            menu = "Armaments Equipped:\n\n" + left_hand + " - " + left_name + "\n" + right_hand + " - " + right_name
            response = "Please select an armament from the list of your character's equipment below by replying with the ID that is in bold:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "<@" + str(
                message.author.id) + "> , please see your DMs for instructions on how to attack.")

        elif command == 'addstatpoints':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to add stat points!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)

            dm_tracker[message.author.id]["fieldlist"] = ["CharacterName", "StatMod", "Modifier"]
            dm_tracker[message.author.id]["fieldmeans"] = ["Name of character", "Statistic to add points to",
                                                           "Points to use"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'addstatpoints'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId",
                                               str(message.author.id))
            response = "Please select a character to add points to from the list of your characters below by replying with the ID that is in bold:\n\n" + menu
            await direct_message(message, response)
            await reply_message(message, "<@" + str(
                message.author.id) + "> , please see your DMs for instructions on how to add stat points.")


        elif command == 'setgmrole':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to set other roles!")
                return
            if len(message.role_mentions) > 1:
                await reply_message(message, "Only one role can be defined as the GM role!")
                return
            role_id = message.role_mentions[0].id
            guild_settings[message.guild.id]["GameModeratorRole"] = role_id
            result = await commit_sql("""UPDATE GuildSettings SET GameModeratorRole=%s WHERE ServerId=%s;""",
                                      (str(role_id), str(message.guild.id)))
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
            result = await commit_sql("""UPDATE GuildSettings SET PlayerRole=%s WHERE ServerId=%s;""",
                                      (str(role_id), str(message.guild.id)))
            if result:
                await reply_message(message, "Player role successfully set!")
            else:
                await reply_message(message, "Database error!")

        elif command == 'setnpcrole':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to set other roles!")
                return
            if len(message.role_mentions) > 1:
                await reply_message(message, "Only one role can be defined as the NPC role!")
                return
            role_id = message.role_mentions[0].id
            guild_settings[message.guild.id]["NPCRole"] = role_id
            result = await commit_sql("""UPDATE GuildSettings SET NPCRole=%s WHERE ServerId=%s;""",
                                      (str(role_id), str(message.guild.id)))
            if result:
                await reply_message(message, "NPC role successfully set!")
            else:
                await reply_message(message, "Database error!")

        elif command == 'listroles':
            records = await select_sql(
                """SELECT IFNULL(AdminRole,'0'),IFNULL(GameModeratorRole,'0'),IFNULL(NPCRole, '0'),IFNULL(PlayerRole,'0') FROM GuildSettings WHERE ServerId=%s;""",
                (str(message.guild.id),))
            if not records:
                await reply_message(message, "Database error!")
                return
            for row in records:
                admin_role = message.guild.get_role(int(row[0]))
                gm_role = message.guild.get_role(int(row[1]))
                alt_role = message.guild.get_role(int(row[2]))
                player_role = message.guild.get_role(int(row[3]))
            response = "**Server Roles**\n\n**Admin Role:** " + str(admin_role) + "\n**Game Moderator Role:** " + str(
                gm_role) + "\n**NPC Role:** " + str(alt_role) + "\n**Player Role:** " + str(player_role) + "\n"
            await reply_message(message, response)

        elif command == 'loaddefault':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to set other roles!")
                return
            await reply_message(message, "Loading default data..")
            records = await select_sql(
                """SELECT SpellName, ManaCost, MinimumLevel, DamageMultiplier, Description, PictureLink,StatusChange,StatusChangedBy,AllowedClasses FROM Spells WHERE ServerId=%s;""",
                ('726969282012905484',))
            for row in records:
                result = await commit_sql(
                    """INSERT INTO Spells (ServerId, UserId, SpellName, ManaCost, MinimumLevel, DamageMultiplier, Description, PictureLink,StatusChange,StatusChangedBy,AllowedClasses) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);""",
                    (str(message.guild.id), str(message.author.id), row[0], row[1], str(row[2]), str(row[3]),
                     str(row[4]), row[5],row[6],row[7],row[8]))
            records = await select_sql(
                """SELECT AttackName, StaminaCost, MinimumLevel, DamageMultiplier, Description, PictureLink,StatusChange,StatusChangedBy,AllowedClasses FROM Melee WHERE ServerId=%s;""",
                ('726969282012905484',))
            for row in records:
                result = await commit_sql(
                    """INSERT INTO Melee (ServerId, UserId, AttackName, StaminaCost, MinimumLevel, DamageMultiplier, Description, PictureLink,StatusChange,StatusChangedBy,AllowedClasses) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);""",
                    (str(message.guild.id), str(message.author.id), row[0], row[1], str(row[2]), str(row[3]),
                     str(row[4]), row[5],row[6],row[7],row[8]))
            records = await select_sql(
                """SELECT EquipmentName, EquipmentDescription, EquipmentCost, MinimumLevel, StatMod, Modifier, PictureLink,StatusChange,StatusChangedBy,AllowedClasses FROM Equipment WHERE ServerId=%s;""",
                ('726969282012905484',))
            for row in records:
                result = await commit_sql(
                    """INSERT INTO Equipment (ServerId, UserId, EquipmentName, EquipmentDescription, EquipmentCost, MinimumLevel, StatMod, Modifier, PictureLink,StatusChange,StatusChangedBy,AllowedClasses) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);""",
                    (str(message.guild.id), str(message.author.id), row[0], row[1], str(row[2]), str(row[3]),
                     str(row[4]), row[5], row[6],row[7],row[8],row[9]))
            records = await select_sql(
                """SELECT ArmamentName, Description, ArmamentCost, Slot, MinimumLevel, DamageMin, DamageMax, Defense, StatMod, Modifier, PictureLink,StatusChange,StatusChangedBy,AllowedClasses FROM Armaments WHERE ServerId=%s;""",
                ('726969282012905484',))
            for row in records:
                result = await commit_sql(
                    """INSERT INTO Armaments (ServerId, UserId, ArmamentName, Description, ArmamentCost, Slot, MinimumLevel, DamageMin, DamageMax, Defense, StatMod, Modifier, PictureLink,StatusChange,StatusChangedBy,AllowedClasses) VALUES (%s,%s,%s,%s,%s,%s,%s,%s, %s,%s,%s,%s,%s,%s,%s,%s);""",
                    (str(message.guild.id), str(message.author.id), row[0], row[1], str(row[2]), str(row[3]),
                     str(row[4]), row[5], row[6], row[7], row[8], row[9], row[10], row[11],row[12],row[13]))
            records = await select_sql(
                """SELECT MonsterName, Description, Health, Level, Attack, Defense, MagicAttack, MaxCurrencyDrop, PictureLink FROM Monsters WHERE  ServerId=%s;""",
                ('726969282012905484',))
            for row in records:
                result = await commit_sql(
                    """INSERT INTO Monsters (ServerId, UserId, MonsterName, Description, Health, Level, Attack, Defense, MagicAttack, MaxCurrencyDrop, PictureLink) VALUES (%s,%s,%s,%s,%s,%s,%s,%s, %s,%s,%s);""",
                    (str(message.guild.id), str(message.author.id), row[0], row[1], str(row[2]), str(row[3]),
                     str(row[4]), row[5], row[6], row[7], row[8]))
            records = await select_sql(
                """SELECT BuffName, ManaCost, MinimumLevel, StatMod, Modifier, Description, IFNULL(PictureLink,'None'),StatusChange,StatusChangedBy,AllowedClasses FROM Buffs WHERE ServerId=%s;""",
                ('726969282012905484',))
            for row in records:
                result = await commit_sql(
                    """INSERT INTO Buffs (ServerId, UserId, BuffName, ManaCost, MinimumLevel, StatMod, Modifier, Description, PictureLink,StatusChange,StatusChangedBy,AllowedClasses) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);""",
                    (str(message.guild.id), str(message.author.id), str(row[0]), str(row[1]), str(row[2]), str(row[3]),
                     str(row[4]), str(row[5]), str(row[6]),row[7],row[8],row[9]))
            records = await select_sql("""SELECT Name, Description, AttackBonus, DefenseBonus, MagicAttackBonus,HealthBonus,ManaBonus,StaminaBonus,IntellectBonus,CharismaBonus,AgilityBonus,PictureLink FROM Races WHERE ServerId=%s;""",('726969282012905484',))
            
            for row in records:
                await log_message("Tuple: " + str(row))
                result = await commit_sql("""INSERT INTO Races (ServerId, UserId, Name, Description, AttackBonus, DefenseBonus, MagicAttackBonus,HealthBonus,ManaBonus,StaminaBonus,IntellectBonus,CharismaBonus,AgilityBonus,PictureLink) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);""",(str(message.guild.id),str(message.author.id), str(row[0]),str(row[1]), str(row[2]), str(row[3]), str(row[4]), str(row[5]), str(row[6]), str(row[7]), str(row[8]), str(row[9]), str(row[10]),str(row[11])))
            records = await select_sql("""SELECT Name, Description, PictureLink FROM Classes WHERE ServerId=%s;""",('726969282012905484',))
            for row in records:
                result = await commit_sql("""INSERT INTO Classes (ServerId, UserId, Name, Description, PictureLink) VALUES (%s, %s, %s, %s, %s);""",(str(message.guild.id),str(message.author.id),str(row[0]),str(row[1]),str(row[2])))
            records = await select_sql(
                """SELECT CritterName, Description, Health, Level, Attack, Defense, MagicAttack, MaxCurrencyDrop, PictureLink FROM Critters WHERE  ServerId=%s;""",
                ('726969282012905484',))
            for row in records:
                result = await commit_sql(
                    """INSERT INTO Critters (ServerId, UserId, CritterName, Description, Health, Level, Attack, Defense, MagicAttack, MaxCurrencyDrop, PictureLink) VALUES (%s,%s,%s,%s,%s,%s,%s,%s, %s,%s,%s);""",
                    (str(message.guild.id), str(message.author.id), row[0], row[1], str(row[2]), str(row[3]),
                     str(row[4]), row[5], row[6], row[7], row[8]))                
            
            await reply_message(message, "Done!")
        elif command == 'importcsv':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to import data!")
                return        
            if not parsed_string:
                await reply_message(message, "You didn't specify a table name!")
                return
            if not message.attachments:
                await reply_message(message, "You didn't attach a CSV file!")
                return
            table_name = parsed_string
            file_url = message.attachments[0].url
            file_name = message.attachments[0].filename
            await reply_message(message, "Downloading file " + file_name + "...")
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url) as resp:
 #           await send_message(message, "File saved to " + file_name + "!")
                    with open('/home/REDACTED/rpmmcsv/' + parsed_string.strip() + "." + re.sub(r".*\.(.*)",r"\1",file_name), 'wb') as file:
                        bytes = await resp.read()
                        
                        file.write(bytes)
                    with open('/home/REDACTED/rpmmcsv/' + parsed_string.strip() + "." + re.sub(r".*\.(.*)",r"\1",file_name)) as csv_file:
                        csv_reader = csv.reader(csv_file,delimiter = ',')
                        headers = []
                        sql_command = "INSERT INTO " + table_name + " (ServerId, UserId, "
                        header_list = next(csv_reader)
                        for header in header_list:
                            headers.append(header.strip())
                            sql_command = sql_command + header.strip() + ","
                        sql_command = sql_command.strip(',') + ") VALUES (%s, %s, "
                        sql_tuple = (str(message.guild.id),str(message.author.id))
                        rows = []
                        for row in csv_reader:
                            rows.append(row)
                        for row in rows:
                            row_command = sql_command
                            row_tuple = sql_tuple
                            for element in row:
                                row_command = row_command + "%s,"
                                row_tuple = row_tuple + (str(element.strip()),)
                            row_command = row_command.strip(',')
                            row_command = row_command + ");"
                            result = await commit_sql(row_command, row_tuple)
            await reply_message(message, "Import complete!")
                            
                                
                        
        elif command == 'setbank':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to set the bank assets!")
                return
            if not parsed_string:
                await reply_message(message, "You did not set a bank asset total!")
                return
            result = await commit_sql("""UPDATE GuildSettings SET GuildBankBalance=%s WHERE ServerId=%s""",
                                      (str(parsed_string), str(message.guild.id)))
            if result:
                await reply_message(message, "Guild bank balance set successfully!")
            else:
                await reply_message(message, "Database error!")


        elif command == 'listsetup':
            server_id = message.guild.id
            records = await select_sql(
                """SELECT ServerId,IFNULL(AdminRole,'0'),IFNULL(GameModeratorRole,'0'),IFNULL(NPCRole,'0'),IFNULL(PlayerRole,'0'),IFNULL(GuildBankBalance,'0'),IFNULL(StartingHealth,'0'),IFNULL(StartingMana,'0'),IFNULL(StartingStamina,'0'),IFNULL(StartingAttack,'0'),IFNULL(StartingDefense,'0'),IFNULL(StartingMagicAttack,'0'),IFNULL(StartingAgility,'0'),IFNULL(StartingIntellect,'0'),IFNULL(StartingCharisma,'0'),IFNULL(HealthLevelAdd,'0'),IFNULL(ManaLevelAdd,'0'),IFNULL(StaminaLevelAdd,'0'),IFNULL(XPLevelRatio,'0'),IFNULL(HealthAutoHeal,'0'),IFNULL(ManaAutoHeal,'0'),IFNULL(StaminaAutoHeal,'0'),IFNULL(AutoCharApproval,'0'),IFNULL(StatPointsPerLevel,'0'),IFNULL(CritterChannelId,'0') FROM GuildSettings WHERE ServerId=%s;""",
                (str(message.guild.id),))
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
                guild_settings[server_id]["HealthLevelAdd"] = int(row[15])
                guild_settings[server_id]["ManaLevelAdd"] = int(row[16])
                guild_settings[server_id]["StaminaLevelAdd"] = int(row[17])
                guild_settings[server_id]["XPLevelRatio"] = int(row[18])
                guild_settings[server_id]["HealthAutoHeal"] = float(row[19])
                guild_settings[server_id]["ManaAutoHeal"] = float(row[20])
                guild_settings[server_id]["StaminaAutoHeal"] = float(row[21])
                guild_settings[server_id]["AutoCharApproval"] = int(row[22])
                guild_settings[server_id]["StatPointsPerLevel"] = int(row[23])

            response = "**CURRENT SERVER SETTINGS**\n\n"
            embed = discord.Embed(title="Server Setup Parameters")
            for setting in list(guild_settings[server_id].keys()):
                if guild_settings[message.guild.id][setting] == 0:
                    setting_value = "Not set or 0"
                else:
                    setting_value = str(guild_settings[message.guild.id][setting])
                response = response + "**" + setting + ":** " + setting_value + "\n"
                if re.search(r"Role", setting):
                    embed.add_field(name=setting,
                                    value=discord.utils.get(message.guild.roles, id=int(setting_value)).name)
                else:
                    embed.add_field(name=setting, value=setting_value)
            await message.channel.send(embed=embed)
            # await reply_message(message, response)

        elif command == 'newsetup':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to perform initial setup!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)

            dm_tracker[message.author.id]["fieldlist"] = ["ServerId", "GuildBankBalance", "StartingHealth",
                                                          "StartingMana", "StartingStamina", "StartingAttack",
                                                          "StartingDefense", "StartingMagicAttack", "StartingAgility",
                                                          "StartingIntellect", "StartingCharisma", "HealthLevelAdd",
                                                          "ManaLevelAdd", "StaminaLevelAdd", "XPLevelRatio",
                                                          "HealthAutoHeal", "ManaAutoHeal", "StaminaAutoHeal",
                                                          "StatPointsPerLevel", "AutoCharApproval"]
            dm_tracker[message.author.id]["fieldmeans"] = ["Server ID",
                                                           "The total currency in the guild bank. Used for determining how much can be sold back to the guild or how much currency can be given by GMs",
                                                           " The amount of health new characters start with",
                                                           "The amount of mana new characters start with",
                                                           "The amount of stamina new characters start with",
                                                           "The amount of attack power new characters start with for melee",
                                                           "The amount of defense against total damage a character starts with",
                                                           "The amount of Magic Attack a new character starts with",
                                                           "The amount of agility a new character starts with",
                                                           "The amount of intellect a new character starts with",
                                                           "The amount of charisma a new character starts with",
                                                           "How much health is added when a new level is earned",
                                                           "How much mana is added when a new level is earned",
                                                           "How much stamina is added when a new level is earned",
                                                           "(Level * XP) needed to advance to next level",
                                                           "How much health is restored per turn during spars and encounters for characters as a multiplier of health. Set to zero for no restores, or less than 1 for partial autoheal (such as 0.1 for 10% per turn)",
                                                           "How much mana restores per turn.",
                                                           "How much stamina restores per turn",
                                                           "How many stat points should be granted upon leveling a character",
                                                           "Specify if characters should be automatically approved (1 for Yes, or 0 for NO)"]
            dm_tracker[message.author.id]["currentfield"] = 1
            dm_tracker[message.author.id]["fielddict"] = [str(message.guild.id), "1000000", "200", "100", "100", "10",
                                                          "5", "10", "10", "10", "10", "200", "100", "100", "200",
                                                          "0.05", "0.1", "0.1", "10", "1"]
            dm_tracker[message.author.id]["currentcommand"] = 'editsetup'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = message.guild.id

            await reply_message(message, "Please check your DMs for instructions on how to edit server setup, <@" + str(
                message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested to edit the server setup. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the server setup will be updated!\nThe first field is **" +
                                 dm_tracker[message.author.id]["fieldlist"][1] + "** and its current value is **" +
                                 dm_tracker[message.author.id]["fielddict"][1] + "**.")


        elif command == 'editsetup':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to edit setup!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)

            dm_tracker[message.author.id]["fieldlist"] = ["ServerId", "GuildBankBalance", "StartingHealth",
                                                          "StartingMana", "StartingStamina", "StartingAttack",
                                                          "StartingDefense", "StartingMagicAttack", "StartingAgility",
                                                          "StartingIntellect", "StartingCharisma", "HealthLevelAdd",
                                                          "ManaLevelAdd", "StaminaLevelAdd", "XPLevelRatio",
                                                          "HealthAutoHeal", "ManaAutoHeal", "StaminaAutoHeal",
                                                          "StatPointsPerLevel", "AutoCharApproval"]
            dm_tracker[message.author.id]["fieldmeans"] = ["Server ID",
                                                           "The total currency in the guild bank. Used for determining how much can be sold back to the guild or how much currency can be given by GMs",
                                                           " The amount of health new characters start with",
                                                           "The amount of mana new characters start with",
                                                           "The amount of stamina new characters start with",
                                                           "The amount of attack power new characters start with for melee",
                                                           "The amount of defense against total damage a character starts with",
                                                           "The amount of Magic Attack a new character starts with",
                                                           "The amount of agility a new character starts with",
                                                           "The amount of intellect a new character starts with",
                                                           "The amount of charisma a new character starts with",
                                                           "How much health is added when a new level is earned",
                                                           "How much mana is added when a new level is earned",
                                                           "How much stamina is added when a new level is earned",
                                                           "(Level * XP) needed to advance to next level",
                                                           "How much health is restored per turn during spars and encounters for characters as a multiplier of health. Set to zero for no restores, or less than 1 for partial autoheal (such as 0.1 for 10% per turn)",
                                                           "How much mana restores per turn.",
                                                           "How much stamina restores per turn",
                                                           "How many stat points should be granted upon leveling a character",
                                                           "Specify if characters should be automatically approved (1 for Yes, or 0 for NO)"]
            dm_tracker[message.author.id]["currentfield"] = 1
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'editsetup'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = message.guild.id

            records = await select_sql(
                """SELECT ServerId,GuildBankBalance,StartingHealth,StartingMana,StartingStamina,StartingAttack,StartingDefense,StartingMagicAttack,StartingAgility,StartingIntellect,StartingCharisma,HealthLevelAdd,ManaLevelAdd,StaminaLevelAdd,XPLevelRatio,HealthAutoHeal,ManaAutoHeal,StaminaAutoHeal,IFNULL(StatPointsPerLevel,'10'),IFNULL(AutoCharApproval,'0') FROM GuildSettings WHERE ServerId=%s;""",
                (str(message.guild.id),))
            counter = 0
            await log_message(str(len(dm_tracker[message.author.id]["fieldlist"])))
            for row in records:
                for field in dm_tracker[message.author.id]["fieldlist"]:
                    await log_message(str(field) + " " + str(counter) + str(dm_tracker[message.author.id]["fieldlist"]))
                    dm_tracker[message.author.id]["fielddict"].append(row[counter])
                    counter = counter + 1
                    if counter > len(dm_tracker[message.author.id]["fieldlist"]) - 1:
                        break

            await reply_message(message, "Please check your DMs for instructions on how to edit server setup, <@" + str(
                message.author.id) + ">.")

            await direct_message(message,
                                 "You have requested to edit the server setup. Please type in the response the answer to each field to update, or *skip* to leave as is. When you have filled out all fields, the  server setup will be updated!\nThe first field is **" + str(
                                     dm_tracker[message.author.id]["fieldlist"][
                                         1]) + "** and its current value is **" + str(
                                     dm_tracker[message.author.id]["fielddict"][1]) + "**.")


        elif command == 'sendcurrency':
            if not role_check(guild_settings[message.guild.id]["PlayerRole"], message.author):
                await reply_message(message, "You must be a member of the player role to send currency!")
                return

            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)

            dm_tracker[message.author.id]["fieldlist"] = ["CharacterId", "TargetId", "Currency"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = ["sendcurrency"]
            dm_tracker[message.author.id]["currentcommand"] = 'sendcurrency'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            menu = await make_less_simple_menu(message, "CharacterProfiles", "CharacterName", "UserId",
                                               str(message.author.id))
            await direct_message(message,
                                 "Please reply to this message with the ID in bold of the character you wish to send currency from.\n\n**CHARACTER LIST**\n\n" + menu)
            await reply_message(message, "Please check your DMs for instructions on how to send currency, <@" + str(
                message.author.id) + "> .")

        elif command == 'addplayer':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to add players!")
                return
            if not message.mentions:
                await reply_message(message, "You didn't specify any users to add!")
                return
            role = discord.utils.get(message.guild.roles, id=guild_settings[message.guild.id]["PlayerRole"])
            for user in message.mentions:
                try:
                    await user.add_roles(role)
                except discord.errors.Forbidden:
                    await reply_message(message, "Cannot add roles due to permissions!")
                    return
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
                try:
                    await user.add_roles(role)
                except discord.errors.Forbidden:
                    await reply_message(message, "Cannot add roles due to permissions!")
                    return
            await reply_message(message, "Users added to GM role!")


        elif command == 'addnpcuser':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to add Alt Managers!")
                return
            if not message.mentions:
                await reply_message(message, "You didn't specify any users to add!")
                return
            role = discord.utils.get(message.guild.roles, id=guild_settings[message.guild.id]["NPCRole"])
            for user in message.mentions:
                try:
                    await user.add_roles(role)
                except discord.errors.Forbidden:
                    await reply_message(message, "Cannot add roles due to permissions!")
                    return
            await reply_message(message, "Users added to NPC role!")


        elif command == 'addadmin':
            if not message.author.guild_permissions.manage_guild:
                await reply_message(message, "You must have manage server permissions to set the admin role!")
                return
            if not message.mentions:
                await reply_message(message, "You didn't specify any users to add!")
                return
            role = discord.utils.get(message.guild.roles, id=guild_settings[message.guild.id]["AdminRole"])
            for user in message.mentions:
                try:
                    await user.add_roles(role)
                except discord.errors.Forbidden:
                    await reply_message(message, "Cannot add roles due to permissions!")
                    return
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
                try:
                    await user.remove_roles(role)
                except discord.errors.Forbidden:
                    await reply_message(message, "Cannot remove roles due to permissions!")
                    return
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
                try:
                    await user.remove_roles(role)
                except discord.errors.Forbidden:
                    await reply_message(message, "Cannot remove roles due to permissions!")
                    return
            await reply_message(message, "Users removed from GM role!")


        elif command == 'deletenpcuser':
            if not role_check(guild_settings[message.guild.id]["AdminRole"], message.author):
                await reply_message(message, "You must be a member of the admin role to remove NPC Managers!")
                return
            if not message.mentions:
                await reply_message(message, "You didn't specify any users to remove!")
                return
            role = discord.utils.get(message.guild.roles, id=guild_settings[message.guild.id]["NPCRole"])
            for user in message.mentions:
                try:
                    await user.remove_roles(role)
                except discord.errors.Forbidden:
                    await reply_message(message, "Cannot remove roles due to permissions!")
                    return
            await reply_message(message, "Users removed from NPC role!")

        elif command == 'deleteadmin':
            if not message.author.guild_permissions.manage_guild:
                await reply_message(message, "You must have manage server permissions to set the admin role!")
                return
            if not message.mentions:
                await reply_message(message, "You didn't specify any users to remove!")
                return
            role = discord.utils.get(message.guild.roles, id=guild_settings[message.guild.id]["AdminRole"])
            for user in message.mentions:
                try:
                    await user.remove_roles(role)
                except discord.errors.Forbidden:
                    await reply_message(message, "Cannot remove roles due to permissions!")
                    return
            await reply_message(message, "Users removed from admin role!")

        elif command == 'setxpchannel':
            server_id = message.guild.id
            if not message.channel_mentions:
                await reply_message(message, "You didn't mention an XP channel!")
                return
            guild_settings[server_id]["XPChannel"] = message.channel_mentions[0]
            result = await commit_sql("""UPDATE GuildSettings SET XPChannelId=%s WHERE ServerId=%s;""",
                                      (str(guild_settings[server_id]["XPChannel"].id), str(message.guild.id)))
            await reply_message(message,
                                "Channel for XP messages set to " + guild_settings[server_id]["XPChannel"].name + "!")
        elif command == 'setcritterchannel':
            server_id = message.guild.id
            if not message.channel_mentions:
                await reply_message(message, "You didn't mention a critter channel!")
                return
            guild_settings[server_id]["CritterChannel"] = message.channel_mentions[0]
            result = await commit_sql("""UPDATE GuildSettings SET CritterChannelId=%s WHERE ServerId=%s;""",
                                      (str(guild_settings[server_id]["CritterChannel"].id), str(message.guild.id)))
            await reply_message(message,
                                "Channel for critter messages set to " + guild_settings[server_id]["CritterChannel"].name + "!")                                

        elif command == 'resetserver':
            if not message.author.guild_permissions.manage_guild:
                await reply_message(message, "You must have manage server permissions to reset the server!")
                return
            if message.author.id not in dm_tracker.keys():
                await initialize_dm(message.author.id)

            dm_tracker[message.author.id]["fieldlist"] = ["Confirm"]
            dm_tracker[message.author.id]["currentfield"] = 0
            dm_tracker[message.author.id]["fielddict"] = []
            dm_tracker[message.author.id]["currentcommand"] = 'resetserver'
            dm_tracker[message.author.id]["server_id"] = message.guild.id
            dm_tracker[message.author.id]["commandchannel"] = message.channel
            dm_tracker[message.author.id]["parameters"] = parsed_string
            await reply_message(message,
                                "**WARNING! THIS WILL WIPE ALL SERVER SETTINGS, INCLUDING CHARACTERS, ITEMS, VENDORS, SPELLS, MONSTERS, MELEE ATTACKS, AND SERVER SETTINGS FROM THE BOT! PLEASE REPLY TO THE DM WITH** ```CONFIRM``` **TO PROCEED.**")
            await direct_message(message,
                                 "**WARNING! THIS WILL WIPE ALL SERVER SETTINGS, INCLUDING CHARACTERS, ITEMS, VENDORS, SPELLS, MONSTERS, MELEE ATTACKS, AND SERVER SETTINGS FROM THE BOT! PLEASE REPLY TO THE DM WITH** ```CONFIRM``` **TO PROCEED.**\n\nAre you sure you want to do this?")
        elif command == 'invite':
            await reply_message(message,
                                "`Click here to invite RP Mastermind:` https://discord.com/api/oauth2/authorize?client_id=691353869841596446&permissions=805432384&scope=bot")
        else:
            pass

            # Experience for posting
    if not message.content.startswith("=") and not message.guild.id == 264445053596991498:
        critter_spawn[message.guild.id] = critter_spawn[message.guild.id] - 1
        if critter_spawn[message.guild.id] < 1:
            if server_encounters[message.guild.id]:
                return
            critter_spawn[message.guild.id] = random.randint(1,50)
            records = await select_sql(
                """SELECT IFNULL(Description,'None'),Health,Level,Attack,Defense,MagicAttack,IFNULL(PictureLink,' '),IFNULL(MaxCurrencyDrop,20),CritterName FROM Critters WHERE ServerId=%s ORDER BY RAND ( ) LIMIT 1;""",
                (str(message.guild.id),))
            if not records:
                return  
            server_id = message.guild.id
            for row in records:
                server_monsters[server_id]["MonsterName"] = row[8]
                monster_name = row[8]
                server_monsters[server_id]["Description"] = row[0]
                server_monsters[server_id]["Health"] = int(row[1])
                server_monsters[server_id]["Level"] = int(row[2])
                server_monsters[server_id]["Attack"] = int(row[3])
                server_monsters[server_id]["Defense"] = int(row[4])
                server_monsters[server_id]["Agility"] = server_monsters[server_id]["Level"] * random.randint(3, 7)
                server_monsters[server_id]["MagicAttack"] = int(row[5])
                server_monsters[server_id]["PictureLink"] = row[6]
                if not row[6].startswith('http'):
                    server_monsters[server_id]["PictureLink"] = narrator_url
                server_monsters[server_id]["MaxCurrencyDrop"] = int(row[7])
                monster_health[server_id] = int(row[1])

            await guild_settings[message.guild.id]["CritterChannel"].send("A critter has been sighted! If you'd like to hunt the " + monster_name + " type =hunt!")
            embed = discord.Embed(title="Critter sighted!",
                                  description="A **" + monster_name + "** has appeared in " + str(
                                    guild_settings[message.guild.id]["CritterChannel"].name) + "!")
            if server_monsters[server_id]["PictureLink"].startswith('http'):
                embed.set_thumbnail(url=server_monsters[server_id]["PictureLink"])
            embed.add_field(name="Critter Level:", value=str(server_monsters[server_id]["Level"]))
            embed.add_field(name="Critter Description:", value=server_monsters[server_id]["Description"])
            await guild_settings[message.guild.id]["CritterChannel"].send(embed=embed)
        if active_chars[message.guild.id][message.author.id] is not None:
            records = await select_sql(
                """SELECT Id,CharacterName,Currency,Experience,Level FROM CharacterProfiles WHERE Id=%s;""",
                (str(active_chars[message.guild.id][message.author.id]),))
            if not records:
                return

            for row in records:
                character_list = row[0]
                character_name = row[1]
                character_currency = row[2]
                experience = row[3]
                levels = row[4]
            new_money = int(character_currency) + 1
            new_xp = int(experience) + 2
            await log_message("granted " + character_name + " XP and currency.")
            server_id = message.guild.id
            if new_xp > (guild_settings[server_id]["XPLevelRatio"] * int(levels)):
                level = int(levels) + 1
                records = await select_sql(
                    """SELECT StatPoints,Health,Mana,Stamina FROM CharacterProfiles WHERE Id=%s;""",
                    (str(active_chars[message.guild.id][message.author.id]),))
                for row in records:
                    stat_points = int(row[0])
                    old_stamina = int(row[3])
                    old_mana = int(row[2])
                    old_health = int(row[1])

                available_points = guild_settings[server_id]["StatPointsPerLevel"] + stat_points
                response = "<@" + str(message.author.id) + "> **" + character_name + "** LEVELED UP TO LEVEL **" + str(
                    level) + "!**\nYou have " + str(
                    available_points) + " stat points to spend!\n\n"
                total_xp = 0
                health = old_health + guild_settings[server_id]["HealthLevelAdd"]
                stamina = old_stamina + guild_settings[server_id]["StaminaLevelAdd"]
                mana = old_mana + guild_settings[server_id]["ManaLevelAdd"]
                result = await commit_sql(
                    """UPDATE CharacterProfiles SET Level=%s,Experience=%s,Health=%s,Stamina=%s,Mana=%s,StatPoints=%s WHERE Id=%s;""",
                    (str(level), str(total_xp), str(health), str(stamina), str(mana), str(available_points),
                     str(active_chars[message.guild.id][message.author.id])))
                await guild_settings[server_id]["XPChannel"].send(response)
            else:
                result = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s,Experience=%s WHERE Id=%s;""",
                                          (str(new_money), str(new_xp),
                                           str(active_chars[message.guild.id][message.author.id])))
                try:
                    await guild_settings[server_id]["XPChannel"].send(
                        ">>> granted " + character_name + " XP and currency.")
                except:
                    pass
        else:
            records = await select_sql(
                """SELECT Id,CharacterName,Currency,Experience,Level FROM CharacterProfiles WHERE ServerId=%s AND UserId=%s;""",
                (str(message.guild.id), str(message.author.id)))
            if not records:
                return
            character_list = []
            character_name = []
            character_currency = []
            experience = []
            levels = []
            for row in records:
                character_list.append(row[0])
                character_name.append(row[1])
                character_currency.append(row[2])
                experience.append(row[3])
                levels.append(row[4])
            lucky_char = random.randint(0, len(character_list) - 1)
            new_money = int(character_currency[lucky_char]) + 1
            new_xp = int(experience[lucky_char]) + 2
            await log_message("granted " + character_name[lucky_char] + " XP and currency.")
            server_id = message.guild.id
            if new_xp > (guild_settings[server_id]["XPLevelRatio"] * int(levels[lucky_char])):
                level = int(levels[lucky_char]) + 1
                records = await select_sql(
                    """SELECT StatPoints,Health,Mana,Stamina FROM CharacterProfiles WHERE Id=%s;""",
                    (str(character_list[lucky_char]),))
                for row in records:
                    stat_points = int(row[0])
                    old_stamina = int(row[3])
                    old_mana = int(row[2])
                    old_health = int(row[1])

                available_points = guild_settings[server_id]["StatPointsPerLevel"] + stat_points
                response = "<@" + str(message.author.id) + "> **" + character_name[
                    lucky_char] + "** LEVELED UP TO LEVEL **" + str(level) + "!**\nYou have " + str(
                    available_points) + " stat points to spend!\n\n"
                total_xp = 0
                health = old_health + guild_settings[server_id]["HealthLevelAdd"]
                stamina = old_stamina + guild_settings[server_id]["StaminaLevelAdd"]
                mana = old_mana + guild_settings[server_id]["ManaLevelAdd"]
                result = await commit_sql(
                    """UPDATE CharacterProfiles SET Level=%s,Experience=%s,Health=%s,Stamina=%s,Mana=%s,StatPoints=%s WHERE Id=%s;""",
                    (str(level), str(total_xp), str(health), str(stamina), str(mana), str(available_points),
                     str(character_list[lucky_char])))
                await guild_settings[server_id]["XPChannel"].send(response)
            else:
                result = await commit_sql("""UPDATE CharacterProfiles SET Currency=%s,Experience=%s WHERE Id=%s;""",
                                          (str(new_money), str(new_xp), str(character_list[lucky_char])))
                try:
                    await guild_settings[server_id]["XPChannel"].send(
                        ">>> granted " + character_name[lucky_char] + " XP and currency.")
                except:
                    pass


client.run('REDACTED')

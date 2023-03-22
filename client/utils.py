import os
import database
import subprocess
import shlex
import io
import requests
import random
from discord.opus import Encoder
from translate import Translator
import discord

class FFmpegPCMAudioBytesIO(discord.AudioSource):
    def __init__(self, source, *, executable='ffmpeg', pipe=False, stderr=None, before_options=None, options=None):
        stdin = None if not pipe else source
        args = [executable]
        if isinstance(before_options, str):
            args.extend(shlex.split(before_options))
        args.append('-i')
        args.append('-' if pipe else source)
        args.extend(('-f', 's16le', '-ar', '48000', '-ac', '2', '-loglevel', 'error'))
        if isinstance(options, str):
            args.extend(shlex.split(options))
        args.append('pipe:1')
        self._process = None
        try:
            self._process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr)
            self._stdout = io.BytesIO(
                self._process.communicate(input=stdin)[0]
            )
        except FileNotFoundError:
            raise discord.ClientException(executable + ' was not found.') from None
        except subprocess.SubprocessError as exc:
            raise discord.ClientException('Popen failed: {0.__class__.__name__}: {0}'.format(exc)) from exc
    def read(self):
        ret = self._stdout.read(Encoder.FRAME_SIZE)
        if len(ret) != Encoder.FRAME_SIZE:
            return b''
        return ret
    def cleanup(self):
        proc = self._process
        if proc is None:
            return
        proc.kill()
        if proc.poll() is None:
            proc.communicate()

        self._process = None

dbms = database.Database(database.SQLITE, dbname='client.sqlite3')
database.create_db_tables(dbms)

def translate(guildid: str, text: str):
  tolang=database.select_guildconfig(dbms, guildid, value = "en")
  fromlang='en'
  if tolang == fromlang:
    return text
  cached = database.select_translation(dbms, fromlang, tolang, text)
  if cached is not None:
    return cached
  else:
    translation = requests.get(os.environ.get("API_URL") + os.environ.get("API_PATH_TEXT") + "/" + from_lang + "/" + to_lang + "/" + text + "/" + guildid)
    if (translation.text != "Internal Server Error" and translation.status_code == 200):
      database.insert_translation(dbms, fromlang, tolang, text, translation)
      return translation
    else:
      return text

def insert_new_guild(guildid: str, language: str):
    database.insert_guildconfig(dbms, guildid, language)

def update_guild(guildid: str, language: str):
    database.update_guildconfig(dbms, guildid, language)

def get_guild_language(guildid: str):
    return database.select_guildconfig(dbms, guildid, value = "en")

def check_exists_guild(guildid: str):
    value = database.select_guildconfig(dbms, guildid, value = None)
    if value is None:
      database.insert_guildconfig(dbms, guildid, "en")

def random_boolean():
    return bool(random.getrandbits(1))
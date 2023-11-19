import os
import sqlite3
import pymongo
import datetime
import logging
import sys

from io import BytesIO
from dotenv import load_dotenv
from os.path import dirname
from os.path import join
from pathlib import Path
from exceptions import AudioLimitException
from pydub import AudioSegment

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=int(os.environ.get("LOG_LEVEL")),
        datefmt='%Y-%m-%d %H:%M:%S')
log = logging.getLogger('werkzeug')
log.setLevel(int(os.environ.get("LOG_LEVEL")))

GUILD_ID = os.environ.get("GUILD_ID") 


#sqlite_create_audio_query = """ CREATE TABLE IF NOT EXISTS Audio(
#            id INTEGER PRIMARY KEY,
#            name VARCHAR(500) NOT NULL,
#            chatid VARCHAR(50) NOT NULL,
#            data BLOB NULL,
#            voice VARCHAR(50) NOT NULL,
#            is_correct INTEGER DEFAULT 1 NOT NULL,
#            language VARCHAR(2) NOT NULL,
#            counter INTEGER DEFAULT 1 NOT NULL,
#            duration INTEGER DEFAULT 0 NOT NULL,
#            user VARCHAR(500) NULL,
#            tms_insert DATETIME DEFAULT CURRENT_TIMESTAMP,
#            tms_update DATETIME DEFAULT CURRENT_TIMESTAMP,
#            UNIQUE(name,chatid,voice,language)
#        ); """

def insert(name: str, chatid: str, filesave, voice: str, language: str, is_correct=1, duration=0):
  try:
    dbfile = chatid + "-db"
    myclient = pymongo.MongoClient('mongodb://'+os.environ.get("MONGO_HOST")+':'+os.environ.get("MONGO_PORT")+'/')
    chatbotdb = myclient[dbfile]
    audiotable = chatbotdb["audio"]

    record = { "name": name, 
               "chatid": chatid, 
               "file": filesave,
               "voice": voice,
               "is_correct": is_correct,
               "language": language,
               "counter": 0,
               "duration": duration,
               "user": None,
               "tms_insert": datetime.datetime.now(),
               "tms_update": datetime.datetime.now() }
    
    audiotable.insert_one(record)

  except Exception as e:
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    logging.error("%s %s %s", exc_type, fname, exc_tb.tb_lineno, exc_info=1)



def select_count_by_name_chatid_voice_language(name: str, chatid: str, voice: str, language: str):
  count = 0
  try:
    
    dbfile = chatid + "-db"
    myclient = pymongo.MongoClient('mongodb://'+os.environ.get("MONGO_HOST")+':'+os.environ.get("MONGO_PORT")+'/')
    chatbotdb = myclient[dbfile]
    audiotable = chatbotdb["audio"]


    count = len(list(audiotable.find({
                        "chatid": chatid,
                        "voice": voice,
                        "name": name,
                        "language": language                        
                      })))

  except Exception as e:
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    logging.error("%s %s %s", exc_type, fname, exc_tb.tb_lineno, exc_info=1)
  return count
  

def insert_or_update(name: str, chatid: str, filesave: str, voice: str, language: str, is_correct=1, duration=0, user=None):
  try:
    dbfile = chatid + "-db"
    myclient = pymongo.MongoClient('mongodb://'+os.environ.get("MONGO_HOST")+':'+os.environ.get("MONGO_PORT")+'/')
    chatbotdb = myclient[dbfile]
    audiotable = chatbotdb["audio"]

    count = select_count_by_name_chatid_voice_language(name, chatid, voice, language)

    if count > 0:

      query = { "chatid": chatid,
                "voice": voice,
                "name": name,
                "language": language
              }

      record = { "$set": {"name": name, 
                          "chatid": chatid, 
                          "file": filesave,
                          "voice": voice,
                          "is_correct": is_correct,
                          "language": language,
                          "counter": 0,
                          "duration": duration,
                          "user": user,
                          "tms_update": datetime.datetime.now() }
                  }
      audiotable.update_one(query, record)

    else:

      record = {"name": name, 
                "chatid": chatid, 
                "file": filesave,
                "voice": voice,
                "is_correct": is_correct,
                "language": language,
                "counter": 0,
                "duration": duration,
                "user": user,
                "tms_insert": datetime.datetime.now(),
                "tms_update": datetime.datetime.now() }
      
      audiotable.insert_one(record)

  except Exception as e:
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    logging.error("%s %s %s", exc_type, fname, exc_tb.tb_lineno, exc_info=1)



def select_by_name_chatid_voice_language(name: str, chatid: str, voice: str, language: str):
  memoryBuff = None
  try:
    dbfile = chatid + "-db"
    myclient = pymongo.MongoClient('mongodb://'+os.environ.get("MONGO_HOST")+':'+os.environ.get("MONGO_PORT")+'/')
    chatbotdb = myclient[dbfile]
    audiotable = chatbotdb["audio"]
    
    query = { "chatid": chatid,
              "voice": voice,
              "name": name,
              "language": language,
              "is_correct": 1,
              "file": {
                "$nin": [None, ""]
              }
            }

    records = audiotable.find(query)

    for row in records:
      file = row["file"]
      duration = row["duration"]
      if duration > int(os.environ.get("MAX_TTS_DURATION")) :
        raise AudioLimitException
      sound = AudioSegment.from_mp3(file)
      memoryBuff = BytesIO()
      sound.export(memoryBuff, format='mp3', bitrate="256")
      memoryBuff.seek(0)


  except Exception as e:
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    logging.error("%s %s %s", exc_type, fname, exc_tb.tb_lineno, exc_info=1)

  return memoryBuff

def update_is_correct(name: str, chatid: str, voice: str, language: str, is_correct=1):
  try:
    sqliteConnection = sqlite3.connect("./config/audiodb.sqlite3")
    cursor = sqliteConnection.cursor()

    sqlite_insert_audio_query = """UPDATE Audio
                          SET is_correct = ?, tms_update = CURRENT_TIMESTAMP
                           WHERE 
                          name = ? and chatid = ? and voice = ? and language = ? """

    data_audio_tuple = (is_correct,
                        name, 
                        chatid, 
                        voice,
                        language,)

    cursor.execute(sqlite_insert_audio_query, data_audio_tuple)


    sqliteConnection.commit()
    cursor.close()
  except sqlite3.Error as error:
    logging.error("Failed to Execute SQLITE Query", exc_info=1)
  finally:
    if sqliteConnection:
        sqliteConnection.close()



def update_is_correct_by_word(text: str, chatid: str, is_correct: int, use_like: bool):
  try:
    text = text.strip()
    sqliteConnection = sqlite3.connect("./config/audiodb.sqlite3")
    cursor = sqliteConnection.cursor()

    logging.info('Updating word is_correct to %s for text: "%s"', str(is_correct), text)

    if use_like: 
      sqlite_query = "UPDATE Audio SET is_correct = ? WHERE is_correct != ? and chatid = ? and data is not null and duration <= ? and (trim(name) like ? OR trim(name) like ? OR trim(name) LIKE ? OR trim(name) = ?) COLLATE NOCASE"
      data_audio_tuple = (is_correct,is_correct,chatid,int(os.environ.get("MAX_TTS_DURATION")),text+"%","%"+text,"%"+text+"%",text,)
    else: 
      sqlite_query = "UPDATE Audio SET is_correct = ? WHERE is_correct != ? and chatid = ? and data is not null and duration <= ? and trim(name) = ? COLLATE NOCASE"
      data_audio_tuple = (is_correct,is_correct,chatid,int(os.environ.get("MAX_TTS_DURATION")),text,)

    cursor.execute(sqlite_query, data_audio_tuple)


    sqliteConnection.commit()
    cursor.close()
  except sqlite3.Error as error:
    logging.error("Failed to Execute SQLITE Query", exc_info=1)
  finally:
    if sqliteConnection:
        sqliteConnection.close()

def update_is_correct_if_not_none(chatid: str, is_correct: int):
  try:
    sqliteConnection = sqlite3.connect("./config/audiodb.sqlite3")
    cursor = sqliteConnection.cursor()

    sqlite_query = "UPDATE Audio SET is_correct = ? WHERE chatid = ? and data is not null and duration <= ?"

    data_audio_tuple = (is_correct,chatid,int(os.environ.get("MAX_TTS_DURATION")),)

    cursor.execute(sqlite_query, data_audio_tuple)


    sqliteConnection.commit()
    cursor.close()
  except sqlite3.Error as error:
    logging.error("Failed to Execute SQLITE Query", exc_info=1)
  finally:
    if sqliteConnection:
        sqliteConnection.close()

def increment_counter(name: str, chatid: str, voice: str, language: str, counter_limit: int):
  try:
    sqliteConnection = sqlite3.connect("./config/audiodb.sqlite3")
    cursor = sqliteConnection.cursor()

    counter = select_counter_by_name_chatid_voice_language(name, chatid, voice, language)
    
    sqlite_insert_audio_query = """UPDATE Audio
                            SET counter = ?, tms_update = CURRENT_TIMESTAMP
                            WHERE 
                            name = ? and chatid = ? and voice = ? and language = ? and is_correct = ?"""

    data_audio_tuple = (counter + 1,
                        name, 
                        chatid, 
                        voice,
                        language,
                        1 if counter < counter_limit else 0)

    cursor.execute(sqlite_insert_audio_query, data_audio_tuple)



    sqliteConnection.commit()
    cursor.close()

  except sqlite3.Error as error:
    logging.error("Failed to Execute SQLITE Query", exc_info=1)
  finally:
    if sqliteConnection:
        sqliteConnection.close()


def select_list_by_chatid(chatid=GUILD_ID):
  records = None
  try:
    sqliteConnection = sqlite3.connect("./config/audiodb.sqlite3")
    cursor = sqliteConnection.cursor()
    sqlite_select_query = " SELECT DISTINCT * from Audio WHERE chatid = ? AND is_correct = 1 AND counter > 0 ORDER BY name, voice"
    cursor.execute(sqlite_select_query, (chatid,))
    records = cursor.fetchall()

    cursor.close()

  except sqlite3.Error as error:
    logging.error("Failed to Execute SQLITE Query", exc_info=1)
  finally:
    if sqliteConnection:
      sqliteConnection.close()
  return records

def select_by_chatid(chatid=GUILD_ID):
  records = None
  try:
    sqliteConnection = sqlite3.connect("./config/audiodb.sqlite3")
    cursor = sqliteConnection.cursor()
    sqlite_select_query = " SELECT DISTINCT * from Audio WHERE chatid = ?"
    cursor.execute(sqlite_select_query, (chatid,))
    records = cursor.fetchall()

  except sqlite3.Error as error:
    logging.error("Failed to Execute SQLITE Query", exc_info=1)
  finally:
    if sqliteConnection:
      sqliteConnection.close()
  return records

def select_data_name_voice_by_chatid(chatid: str):
  records = None
  try:
    sqliteConnection = sqlite3.connect("./config/audiodb.sqlite3")
    cursor = sqliteConnection.cursor()
    sqlite_select_query = " SELECT DISTINCT data, name, voice from Audio WHERE chatid = ? AND is_correct = 1 AND counter > 0 and data is not null"
    cursor.execute(sqlite_select_query, (chatid,))
    records = cursor.fetchall()

    cursor.close()

  except sqlite3.Error as error:
    logging.error("Failed to Execute SQLITE Query", exc_info=1)
  finally:
    if sqliteConnection:
      sqliteConnection.close()
  return records

def select_counter_by_name_chatid_voice_language(name: str, chatid: str, voice: str, language: str):
  if chatid == "X":
    return None
  else:
    counter = 0
    try:
      sqliteConnection = sqlite3.connect("./config/audiodb.sqlite3")
      cursor = sqliteConnection.cursor()

      sqlite_select_query = """SELECT counter from Audio WHERE name = ? AND chatid = ? AND voice = ? AND language = ?"""
      cursor.execute(sqlite_select_query, (name, chatid, voice, language,))
      records = cursor.fetchall()

      for row in records:
        counter   =  row[0]

      cursor.close()

    except sqlite3.Error as error:
      logging.error("Failed to Execute SQLITE Query", exc_info=1)
    finally:
      if sqliteConnection:
        sqliteConnection.close()
    return counter

def select_voice_by_name_chatid_language(name: str, chatid: str, language: str):
  if chatid == "X":
    return None
  else:
    voice = None
    try:
      sqliteConnection = sqlite3.connect("./config/audiodb.sqlite3")
      cursor = sqliteConnection.cursor()

      sqlite_select_query = """SELECT voice from Audio WHERE name = ? AND chatid = ? AND language = ? ORDER BY RANDOM() LIMIT 1; """
      cursor.execute(sqlite_select_query, (name, chatid, language,))
      records = cursor.fetchall()

      for row in records:
        voice   =  row[0]

      cursor.close()

    except sqlite3.Error as error:
      logging.error("Failed to Execute SQLITE Query", exc_info=1)
    finally:
      if sqliteConnection:
        sqliteConnection.close()
    return voice



def select_distinct_language_by_name_chatid(name: str, chatid: str):
  if chatid == "X":
    return None
  else:
    lang = None
    try:
      sqliteConnection = sqlite3.connect("./config/audiodb.sqlite3")
      cursor = sqliteConnection.cursor()

      sqlite_select_query = """SELECT DISTINCT language from Audio WHERE name = ? AND chatid = ? """
      cursor.execute(sqlite_select_query, (name, chatid,))
      records = cursor.fetchall()

      for row in records:
        lang   =  str(row[0])

      cursor.close()

    except sqlite3.Error as error:
      logging.error("Failed to Execute SQLITE Query", exc_info=1)
    finally:
      if sqliteConnection:
        sqliteConnection.close()
    return lang

def select_by_chatid_voice_language_random(chatid: str, voice:str, language:str, text:str):
  if chatid == "X":
    return None
  else:
    audio = None
    name = None
    try:
      sqliteConnection = sqlite3.connect("./config/audiodb.sqlite3")
      cursor = sqliteConnection.cursor()

      sqlite_select_query="SELECT data, name, duration from Audio WHERE chatid = ? AND language = ? AND is_correct = 1 AND counter > 0 and data is not null"
      params=None
      params=(chatid,language,)

      if voice != "random":
        sqlite_select_query = sqlite_select_query + " and voice = ?"
        params=(chatid,language,voice,)
        

      if text is None:
        sqlite_select_query = sqlite_select_query + " ORDER BY RANDOM() LIMIT 1;"
      elif text is not None:
        params = params + (text+"%","%"+text,"%"+text+"%",text,)
        sqlite_select_query = sqlite_select_query + " and (name like ? OR name like ? OR name LIKE ? OR name =?) COLLATE NOCASE ORDER BY RANDOM() LIMIT 1;"

      cursor.execute(sqlite_select_query, params )
      records = cursor.fetchall()

      name = False

      for row in records:
        data = row[0]
        duration = row[2]
        cursor.close()
        if duration > int(os.environ.get("MAX_TTS_DURATION")):
          sqliteConnection.close()
          raise AudioLimitException
        audio = BytesIO(data)
        audio.seek(0)
        name = row[1]

      cursor.close()

    except sqlite3.Error as error:
      logging.error("Failed to Execute SQLITE Query", exc_info=1)
    finally:
      if sqliteConnection:
        sqliteConnection.close()
    return audio, name

def select_audio_by_id(id: int):
  audio = None
  try:
    sqliteConnection = sqlite3.connect("./config/audiodb.sqlite3")
    cursor = sqliteConnection.cursor()

    sqlite_select_query = """SELECT data from Audio WHERE id = ? """
    cursor.execute(sqlite_select_query, (id,))
    records = cursor.fetchall()

    for row in records:
      data   =  row[0]
      cursor.close()
      audio = BytesIO(data)
      audio.seek(0)

    cursor.close()

  except sqlite3.Error as error:
    logging.error("Failed to Execute SQLITE Query", exc_info=1)
  finally:
    if sqliteConnection:
      sqliteConnection.close()
  if audio is None:
    raise Exception("Audio not found")
  else:
    return audio

def select_count_by_text_chatid_voice(text: str, chatid: str, voice: str):
  count = 0
  try:
    sqliteConnection = sqlite3.connect("./config/audiodb.sqlite3")
    cursor = sqliteConnection.cursor()

    sqlite_select_query = """SELECT count(id) from Audio WHERE name = ? and chatid = ? and voice = ?"""
    cursor.execute(sqlite_select_query, (text, chatid, voice,))
    records = cursor.fetchall()

    for row in records:
      count = row[0]

    cursor.close()
  except sqlite3.Error as error:
    logging.error("Failed to Execute SQLITE Query", exc_info=1)
    return count
  finally:
    if sqliteConnection:
      sqliteConnection.close()
    return count

def select_count_by_text_chatid(text: str, chatid: str):
  count = 0
  try:
    sqliteConnection = sqlite3.connect("./config/audiodb.sqlite3")
    cursor = sqliteConnection.cursor()

    sqlite_select_query = """SELECT count(id) from Audio WHERE name = ? and chatid = ?"""

    cursor.execute(sqlite_select_query, (text, chatid))
    records = cursor.fetchall()

    for row in records:
      count = row[0]

    cursor.close()
  except sqlite3.Error as error:
    logging.error("Failed to Execute SQLITE Query", exc_info=1)
    return count
  finally:
    if sqliteConnection:
      sqliteConnection.close()
    return count

def select_count_by_chatid_voice(chatid: str, voice: str):
  count = 0
  try:
    sqliteConnection = sqlite3.connect("./config/audiodb.sqlite3")
    cursor = sqliteConnection.cursor()

    sqlite_select_query = """SELECT count(id) from Audio WHERE chatid = ? and voice = ?"""
    cursor.execute(sqlite_select_query, (chatid, voice,))
    records = cursor.fetchall()

    for row in records:
      count = row[0]

    cursor.close()
  except sqlite3.Error as error:
    logging.error("Failed to Execute SQLITE Query", exc_info=1)
    return count
  finally:
    if sqliteConnection:
      sqliteConnection.close()
    return count


def delete_by_name(name: str, chatid: str):
  try:
    sqliteConnection = sqlite3.connect("./config/audiodb.sqlite3")
    cursor = sqliteConnection.cursor()

    sqlite_delete_query = """DELETE from Audio 
                          WHERE chatid = ?
                          AND (name like ?
                          OR name like ?
                          OR name = ?)"""


    data_tuple = (chatid,
                  name+'%', 
                  '%'+name, 
                  name) 
    cursor.execute(sqlite_delete_query, data_tuple)

    sqliteConnection.commit()
    cursor.close()

  except Exception as e:
    logging.error("Failed to Execute SQLITE Query", exc_info=1)
    raise Exception(e)
  finally:
    if sqliteConnection:
      sqliteConnection.close()



def clean_old_limited_audios(limit: int):
  try:
    sqliteConnection = sqlite3.connect("./config/audiodb.sqlite3")
    cursor = sqliteConnection.cursor()

    sqlite_delete_audio_query = """DELETE from audio where data is null and duration > 0 and duration < ?"""

    data_audio_tuple = (limit,)

    cursor.execute(sqlite_delete_audio_query, data_audio_tuple)


    sqliteConnection.commit()
    cursor.close()
  except sqlite3.Error as error:
    logging.error("Failed to Execute SQLITE Query", exc_info=1)
  finally:
    if sqliteConnection:
        sqliteConnection.close()

def vacuum():
  try:
    sqliteConnection = sqlite3.connect("./config/audiodb.sqlite3")
    cursor = sqliteConnection.cursor()

    cursor.execute("VACUUM")

    cursor.close()
  except sqlite3.Error as error:
    logging.error("Failed to Execute VACUUM", exc_info=1)
  finally:
    if sqliteConnection:
      sqliteConnection.close()
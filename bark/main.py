import os
import voice
import logging
import voice
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import Flask, request, send_file, Response, jsonify, make_response, after_this_request, g
from flask_restx import Api, Resource, reqparse
from flask_caching import Cache
from os.path import join, dirname
from dotenv import load_dotenv
from time import strftime


dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=int(os.environ.get("LOG_LEVEL")),
        datefmt='%Y-%m-%d %H:%M:%S')
log = logging.getLogger('werkzeug')
log.setLevel(int(os.environ.get("LOG_LEVEL")))

TMP_DIR = os.environ.get("TMP_DIR")

app = Flask(__name__)
class Config:    
    CACHE_TYPE = os.environ['CACHE_TYPE']
    CACHE_REDIS_HOST = os.environ['CACHE_REDIS_HOST']
    CACHE_REDIS_PORT = os.environ['CACHE_REDIS_PORT']
    CACHE_REDIS_DB = os.environ['CACHE_REDIS_DB']
    CACHE_REDIS_URL = os.environ['CACHE_REDIS_URL']
    CACHE_DEFAULT_TIMEOUT = os.environ['CACHE_DEFAULT_TIMEOUT']
    SCHEDULER_API_ENABLED = False

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],
    storage_uri="memory://",
)

app.config.from_object(Config())

    
@app.after_request
def after_request(response):
  if not request.path.startswith('/utils/healthcheck'):
    timestamp = strftime('[%Y-%b-%d %H:%M]')
    logging.info('%s %s %s %s %s %s', timestamp, request.remote_addr, request.method, request.scheme, request.full_path, response.status)
  return response

cache = Cache(app)
api = Api(app)

nsvoice = api.namespace('voice', 'Bark Voice APIs')

@nsvoice.route('/clone/<string:output>')
class CloneClass(Resource):
  @cache.cached(timeout=5, query_string=True)
  def get (self, output: str):
    try:
      voice.voice_clone(output)
      return make_response("Cloned!", 200)
    except Exception as e:
      g.request_error = str(e)
      @after_this_request
      def clear_cache(response):
        cache.delete_memoized(CloneClass.get, self, str)
        return make_response(g.get('request_error'), 500)

@nsvoice.route('/talk/<string:model>/<string:text>')
class TalkClass(Resource):
  @cache.cached(timeout=5, query_string=True)
  def get (self, model: str, text: str):
    try:
      tts_out = voice.talk(model, text)
      filename = "audio.mp3"
      response = send_file(tts_out, attachment_filename=filename, mimetype='audio/mpeg')
      response.headers['X-Generated-Text'] = text.encode('utf-8').decode('latin-1')
      if voice is not None:
        response.headers['X-Generated-Voice'] = voice.encode('utf-8').decode('latin-1')
      return response
    except Exception as e:
      g.request_error = str(e)
      @after_this_request
      def clear_cache(response):
        cache.delete_memoized(TalkClass.get, self, str)
        return make_response(g.get('request_error'), 500)
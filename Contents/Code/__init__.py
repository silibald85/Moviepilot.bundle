# Moviepilot metadata agent for Plex
# Adds German titles, summaries and posters from www.moviepilot.de to movies

import re

BASE_URL = 'http://www.moviepilot.de'
API_KEY = '734xthw33clipcnv6nqdtnq3em3rmj'
MOVIE_INFO_BY_IMDB = '%s/movies/imdb-id-%%s.json?api_key=%s' % (BASE_URL, API_KEY)
MOVIE_INFO_BY_TITLE = '%s/movies/%%s.json?api_key=%s' % (BASE_URL, API_KEY)
CAST_INFO_BY_IMDB = '%s/movies/imdb-id-%%s/casts.json?api_key=%s' % (BASE_URL, API_KEY)

def Start():
  HTTP.CacheTime = CACHE_1DAY
  HTTP.Headers['User-agent'] = 'Plex/Nine'

def get_json(url):
  try:
    return JSON.ObjectFromURL(url)
  except:
    return None

class MoviepilotAgent(Agent.Movies):
  name = 'Moviepilot'
  languages = ['de']
  primary_provider = False
  contributes_to = ['com.plexapp.agents.imdb']

  def search(self, results, media, lang):
    # Use the IMDB id found by the primary metadata agent (IMDB/Freebase)
    results.Append(MetadataSearchResult(id = media.primary_metadata.id.lstrip('t0'), score = 100))

  def update(self, metadata, media, lang):
    movie = get_json(MOVIE_INFO_BY_IMDB % (metadata.id))

    if movie != None:
      metadata.title = movie['display_title']
      metadata.year = int( movie['production_year'] )

      summary = Summary(metadata.id)
      metadata.summary = re.sub('\[\[(.+?)\]\]', summary, movie['short_description']) # Replace linked movie titles and names with full title or name
      metadata.summary = String.StripTags(metadata.summary) # Strip HTML tags
      metadata.summary = re.sub('(\r)?\n((\r)?\n)+', '\n\n', metadata.summary).strip() # Replace 2+ newlines with 2 newlines

      metadata.rating = float( movie['average_community_rating'] )/10 # Convert score of 0-100 to 0-10
      metadata.duration = int( movie['runtime'] ) * 60000 # Convert minutes to milliseconds

      metadata.genres.clear()
      genres = movie['genres_list'].split(',')
      for genre in genres:
        metadata.genres.add( genre.strip() )

      try:
        poster_url = ''.join([movie['poster']['base_url'], movie['poster']['photo_id'], '/', movie['poster']['file_name_base'], '.', movie['poster']['extension']])
        if poster_url not in metadata.posters:
          img = HTTP.Request(poster_url)
          metadata.posters[poster_url] = Proxy.Preview(img)
      except:
        pass

class Summary(object):
  def __init__(self, metadata_id):
    self.metadata_id = metadata_id

  def __call__(self, matchobj):
    type = matchobj.group(1)[0:1]
    name = matchobj.group(1)[2:-2]

    if type == 's':
      full_name = ''
      cast = get_json(CAST_INFO_BY_IMDB % (self.metadata_id))

      if cast != None:
        for people in cast['movies_people']:
          if people['person']['restful_url'].find(name) != -1:
            full_name = people['person']['first_name'] + ' ' + people['person']['last_name']
            break
          else:
            continue
      return full_name
    elif type == 'm':
      title = ''
      movie = get_json(MOVIE_INFO_BY_TITLE % (name))
      if movie != None:
        title = movie['display_title']
      return title

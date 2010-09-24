# Moviepilot metadata agent for Plex
# Adds German titles and summaries to movies

import re

BASE_URL = 'http://www.moviepilot.de'
API_KEY = '734xthw33clipcnv6nqdtnq3em3rmj'
MOVIE_INFO = '%s/movies/imdb-id-%%d.json?api_key=%s' % (BASE_URL, API_KEY)

def Start():
  HTTP.CacheTime = CACHE_1DAY

class MoviepilotAgent(Agent.Movies):
  name = 'Moviepilot'
  languages = ['de']
  primary_provider = False
  contributes_to = ['com.plexapp.agents.imdb']

  def search(self, results, media, lang):
    results.Append(MetadataSearchResult(id = media.primary_metadata.id.lstrip('t0'), score = 100))

  def update(self, metadata, media, lang):
    try:
      response = JSON.ObjectFromURL(MOVIE_INFO % ( int(metadata.id) ))

      metadata.title = response['display_title']
      metadata.year = int( response['production_year'] )
      summary = String.StripTags( response['short_description'] )
      metadata.summary = re.sub('\(\[\[.+?\]\]\)\s', '', summary)
      metadata.rating = float( response['average_community_rating'] )/10
      metadata.duration = int( response['runtime'] ) * 60000

      metadata.genres.clear()
      genres = response['genres_list'].split(',')
      for genre in genres:
        metadata.genres.add( genre.strip() )

      try:
        poster_url = ''.join([response['poster']['base_url'], response['poster']['photo_id'], '/', response['poster']['file_name_base'], '.', response['poster']['extension']])
        if poster_url not in metadata.posters:
          img = HTTP.Request(poster_url)
          metadata.posters[poster_url] = Proxy.Preview(img)
      except:
        pass

    except:
      pass

# Moviepilot metadata agent for Plex
# Adds German titles, summaries and posters from www.moviepilot.de to movies

import datetime, re, time

BASE_URL = 'http://www.moviepilot.de'
API_KEY = '734xthw33clipcnv6nqdtnq3em3rmj'
SEARCH_MOVIES = '%s/searches/movies.json?q=%%s&api_key=%s' % (BASE_URL, API_KEY)
MOVIE_INFO = '%s/movies/%%s.json?api_key=%s' % (BASE_URL, API_KEY)
CAST_INFO = '%s/movies/%%s/casts.json?api_key=%s' % (BASE_URL, API_KEY)

GOOGLE_JSON_URL = 'http://ajax.googleapis.com/ajax/services/search/web?v=1.0&rsz=large&q=allintitle:%%22%s%%22+Film+site:moviepilot.de%%2Fmovies'

def Start():
  HTTP.CacheTime = CACHE_1DAY
  HTTP.Headers['User-agent'] = 'Plex/Nine'

class MoviepilotAgent(Agent.Movies):
  name = 'Moviepilot'
  languages = ['de']


  def search(self, results, media, lang):
    try:
      searchResult = JSON.ObjectFromURL(SEARCH_MOVIES % (String.Quote(media.name, usePlus=True)))
      if ['total_entries'] == 0:
        searchResult = None
    except:
      Log('Error while retrieving data from the Moviepiot API.')
      searchResult = None

    self.parseSearchResult(results, media, lang, searchResult)


  def update(self, metadata, media, lang):
    movie = JSON.ObjectFromURL(MOVIE_INFO % (metadata.id))

    metadata.title = movie['display_title'].replace('&#38;', '&')
    if movie['production_year'] != None:
      metadata.year = int(movie['production_year'])

    summary = Summary(metadata.id)
    metadata.summary = re.sub('\[\[(.+?)\]\]', summary, movie['short_description']) # Replace linked movie titles and names with full title or name
    metadata.summary = String.StripTags(metadata.summary) # Strip HTML tags
    metadata.summary = re.sub(r'\*([^\s].+?[^\s])\*', r'\1', metadata.summary)
    metadata.summary = re.sub('(\r)?\n((\r)?\n)+', '\n\n', metadata.summary).strip() # Replace 2+ newlines with 2 newlines

    metadata.rating = float( movie['average_community_rating'] )/10 # Convert score of 0-100 to 0-10
    if movie['runtime'] != None:
      metadata.duration = int( movie['runtime'] ) * 60 * 1000 # Convert minutes to milliseconds

    metadata.genres.clear()
    genres = movie['genres_list'].split(',')
    for genre in genres:
      metadata.genres.add( genre.strip() )

    # Director(s), writer(s) and cast
    cast = JSON.ObjectFromURL(CAST_INFO % (metadata.id))
    directors = []
    writers = []
    actors = []
    for people in cast['movies_people']:
      # First or last name *can* be missing
      first_name = people['person']['first_name']
      if first_name == None:
        first_name = ''

      last_name = people['person']['last_name']
      if last_name == None:
        last_name = ''

      full_name = ' '.join([first_name, last_name]).strip()
      role = people['function_restful_url'].rsplit('/',1)[1]

      if role == 'director':
        directors.append(full_name)
      elif role == 'screenplay':
        writers.append(full_name)
      elif role == 'actor':
        actors.append('|'.join([full_name, people['character']]))

    metadata.directors.clear()
    directors = list(set(directors)) # Remove duplicates
    directors.sort()
    for director in directors:
      metadata.directors.add(director)

    metadata.writers.clear()
    writers = list(set(writers)) # Remove duplicates
    writers.sort()
    for writer in writers:
      metadata.writers.add(writer)

    metadata.roles.clear()
    actors = list(set(actors)) # Remove duplicates
    actors.sort()
    for actor in actors:
      role = metadata.roles.new()
      role.role = actor.split('|')[1]
      role.actor = actor.split('|')[0]

    try:
      poster_url = ''.join([movie['poster']['base_url'], movie['poster']['photo_id'], '/', movie['poster']['file_name_base'], '.', movie['poster']['extension']])
      if poster_url not in metadata.posters:
        img = HTTP.Request(poster_url)
        metadata.posters[poster_url] = Proxy.Preview(img)
    except:
      pass


  def parseSearchResult(self, results, media, lang, searchResult):
    # Process the movie info found on Moviepilot
    score = 90

    if searchResult != None:
      for movie in searchResult['movies']:
        id = movie['restful_url'].rsplit('/',1)[1]
        title = movie['display_title'].replace('&#38;', '&')
        year = movie['production_year']
        finalScore = score - self.scoreResultPenalty(media, year, title)

        results.Append(MetadataSearchResult(id=id, name=title, year=year, lang=lang, score=finalScore))

    # Process the movie info found on Google
    score = 110 # Google title searches are more accurate, give those a higher score
    try:
      time.sleep(0.5)
      searchResult = JSON.ObjectFromURL(GOOGLE_JSON_URL % (String.Quote(media.name, usePlus=True)))
    except:
      Log('Error while retrieving data from Google.')
      searchResult = None

    if searchResult != None and searchResult['responseStatus'] == 200:
      for movie in searchResult['responseData']['results']:
        id = re.search('\/movies\/([^/]+)', movie['unescapedUrl']).group(1)
        title = movie['titleNoFormatting'].split('| Film |',1)[0].strip()
        year = re.search('\(([0-9]{4})\):', movie['content']).group(1)
        finalScore = score - self.scoreResultPenalty(media, year, title)

        results.Append(MetadataSearchResult(id=id, name=title, year=year, lang=lang, score=finalScore))

    # Remove duplicate entries.
    results.Sort('score', descending=True)
    toWhack = []
    resultMap = {}
    for result in results:
      if not resultMap.has_key(result.id):
        resultMap[result.id] = True
      else:
        toWhack.append(result)

    for dupe in toWhack:
      results.Remove(dupe)

    # Just for log
    for result in results:
      Log(' ==> ' + result.name + ' | year = ' + str(result.year) + ' | id = ' + result.id + ' | score = ' + str(result.score))


  def scoreResultPenalty(self, media, year, title):
    scorePenalty = 0

    # Penalty for movies from the future
    if int(year) > datetime.datetime.now().year:
      scorePenalty += 25

    # Give penalties based on the difference in years
    if media.year:
      scorePenalty += abs(int(year) - int(media.year)) * 3

    # Use 'clean' titles for the next checks
    title1 = re.sub('[^a-z]+', '', title.lower())      # Title we found on Moviepilot/Google
    title2 = re.sub('[^a-z]+', '', media.name.lower()) # Title from filename/foldername

    Log(title1)
    Log(title2)

    # Calculate Levenshtein distance...
    nameDist = Util.LevenshteinDistance(title1, title2)
    # ...but only give penalies based on this difference to movies where the years don't match
    if media.year != year:
      scorePenalty += nameDist

    # Bonus for exact title matches
    if nameDist == 0:
      scorePenalty += -25

    # Give bonus for movies where a 'shorter' title is found within the longer, official title
    # Example:
    # Title found on Moviepilot/Google: Wall-E - Der Letzte räumt die Erde auf
    # Title from filename/foldername:   Wall-E

    if title1.find(title2) != -1:
      scorePenalty += -10

    return scorePenalty


class Summary(object):
  def __init__(self, metadata_id):
    self.metadata_id = metadata_id

  def __call__(self, matchobj):
    type = matchobj.group(1)[0:1]
    name = matchobj.group(1)[2:-2]

    if type == 's':
      cast = JSON.ObjectFromURL(CAST_INFO % (self.metadata_id))
      for people in cast['movies_people']:
        if people['person']['restful_url'].find(name) != -1:
          # First or last name *can* be missing
          first_name = people['person']['first_name']
          if first_name == None:
            first_name = ''

          last_name = people['person']['last_name']
          if last_name == None:
            last_name = ''

          full_name = ' '.join([first_name, last_name]).strip()
          break
        else:
          continue
      return full_name
    elif type == 'm':
      movie = JSON.ObjectFromURL(MOVIE_INFO % (name))
      title = movie['display_title']
      return title

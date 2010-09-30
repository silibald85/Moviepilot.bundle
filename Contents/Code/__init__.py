# Moviepilot metadata agent for Plex
# Adds German titles, summaries and posters from www.moviepilot.de to movies

import datetime, re, time

# Moviepilot
MP_BASE_URL = 'http://www.moviepilot.de'
MP_API_KEY = '734xthw33clipcnv6nqdtnq3em3rmj'
MP_SEARCH_MOVIES = '%s/searches/movies.json?q=%%s&api_key=%s' % (MP_BASE_URL, MP_API_KEY)
MP_MOVIE_INFO = '%s/movies/%%s.json?api_key=%s' % (MP_BASE_URL, MP_API_KEY)
MP_CAST_INFO = '%s/movies/%%s/casts.json?api_key=%s' % (MP_BASE_URL, MP_API_KEY)

# TMDB
TMDB_API_KEY = '3ee878f19cf07186c8dc4111fb37b4a6'
TMDB_GETINFO_IMDB = 'http://api.themoviedb.org/2.1/Movie.imdbLookup/de/json/%s/%%s' % (TMDB_API_KEY)

# Google
GOOGLE_JSON_URL = 'http://ajax.googleapis.com/ajax/services/search/web?v=1.0&rsz=large&q=allintitle:%%22%s%%22+Film+site:moviepilot.de%%2Fmovies'

def Start():
  HTTP.CacheTime = CACHE_1DAY
  HTTP.Headers['User-agent'] = 'Plex/Nine'

class MoviepilotAgent(Agent.Movies):
  name = 'Moviepilot'
  languages = ['de']


  def search(self, results, media, lang):
    normalizedName = String.StripDiacritics(media.name).lower()
    searchResult = JSON.ObjectFromURL(MP_SEARCH_MOVIES % (String.Quote(normalizedName, usePlus=True)))
    if 'movies' not in searchResult:
      if 'suggestions' in searchResult:
        Log(' --> Search suggestions (not used at the moment, as Google finds missing titles):')
        for s in searchResult['suggestions']:
          Log(' --> ' + s)
      searchResult = None

    self.parseSearchResult(results, media, lang, searchResult)


  def update(self, metadata, media, lang):
    movie = JSON.ObjectFromURL(MP_MOVIE_INFO % (metadata.id))

    metadata.title = movie['display_title'].replace('&#38;', '&').replace('&#39;', '’')
    if movie['production_year'] and str(movie['production_year']).strip() != '':
      metadata.year = int(movie['production_year'])

    summary = Summary(metadata.id) # Create an instance of the callable class Summary and make the metadata.id available in it
    metadata.summary = re.sub('\[\[(.+?)\]\]', summary, movie['short_description']) # Replace linked movie titles and names with full title or name
    metadata.summary = String.StripTags(metadata.summary) # Strip HTML tags
    metadata.summary = re.sub(r'\*([^\s].+?[^\s])\*', r'\1', metadata.summary) # Strip asterisks from movie titles
    metadata.summary = re.sub('(\r)?\n((\r)?\n)+', '\n\n', metadata.summary).strip() # Replace 2+ newlines with 2 newlines

    metadata.rating = float( movie['average_community_rating'] )/10 # Convert score of 0-100 to 0-10
    if movie['runtime']:
      metadata.duration = int( movie['runtime'] ) * 60 * 1000 # Convert minutes to milliseconds

    metadata.genres.clear()
    genres = movie['genres_list'].split(',')
    for genre in genres:
      metadata.genres.add( genre.strip() )

    # Director(s), writer(s) and cast
    cast = JSON.ObjectFromURL(MP_CAST_INFO % (metadata.id))
    directors = []
    writers = []
    actors = []
    for people in cast['movies_people']:
      # First or last name *can* be missing
      first_name = people['person']['first_name']
      if not first_name:
        first_name = ''

      last_name = people['person']['last_name']
      if not last_name:
        last_name = ''

      full_name = ' '.join([first_name, last_name]).strip()
      role = people['function_restful_url']
      if not role:
        role = ''
      else:
        role = people['function_restful_url'].rsplit('/',1)[1]

      if role == 'director':
        directors.append(full_name)
      elif role == 'screenplay':
        writers.append(full_name)
      elif role == 'actor':
        if not people['character']:
          character = ''
        else:
          character = people['character']
        actors.append('|'.join([full_name, character]))

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

    # Get the poster from Moviepilot if it is available
    p_i = 0
    try:
      poster_url = ''.join([movie['poster']['base_url'], movie['poster']['photo_id'], '/', movie['poster']['file_name_base'], '.', movie['poster']['extension']])
      if poster_url not in metadata.posters:
        p_i += 1
        img = HTTP.Request(poster_url)
        metadata.posters[poster_url] = Proxy.Preview(img, sort_order = p_i)
    except:
      pass

    # Get backdrops and (more) posters from TMDB if we know the IMDB id
    if movie['alternative_identifiers'] and 'imdb' in movie['alternative_identifiers']:
      imdbId = movie['alternative_identifiers']['imdb']
      imdbId = ''.join(['tt', imdbId.zfill(7)])
      tmdb_dict = JSON.ObjectFromURL(TMDB_GETINFO_IMDB % (imdbId))[0]

      # Backdrops
      b_i = 0
      for b in tmdb_dict['backdrops']:
        if b['image']['size'] == 'original':
          b_i += 1
          if b['image']['url'] not in metadata.art:
            b_id = b['image']['id']

            # Find a thumbnail
            for t in tmdb_dict['backdrops']:
              if t['image']['id'] == b_id and t['image']['size'] == 'poster':
                thumb = HTTP.Request(t['image']['url'], cacheTime=CACHE_1WEEK)
                break
            try:
              metadata.art[b['image']['url']] = Proxy.Preview(thumb, sort_order = b_i)
            except:
              pass

      # Posters
      for p in tmdb_dict['posters']:
        if p['image']['size'] == 'original':
          p_i += 1 # Variable p_i already initiated when trying to retrieve poster from Moviepilot
          if p['image']['url'] not in metadata.posters:
            p_id = p['image']['id']

            # Find a thumbnail
            for t in tmdb_dict['posters']:
              if t['image']['id'] == p_id and t['image']['size'] == 'mid':
                thumb = HTTP.Request(t['image']['url'], cacheTime=CACHE_1WEEK)
                break
            try:
              metadata.posters[p['image']['url']] = Proxy.Preview(thumb, sort_order = p_i)
            except:
              pass


  def parseSearchResult(self, results, media, lang, searchResult):
    # Process the movie info found on Moviepilot
    score = 90

    if searchResult:
      for movie in searchResult['movies']:
        if movie['restful_url'] and movie['display_title']:
          id = movie['restful_url'].rsplit('/',1)[1]
          title = movie['display_title'].replace('&#38;', '&')
          year = None
          if movie['production_year'] and str(movie['production_year']).strip() != '':
            year = int(movie['production_year'])
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

    if searchResult and searchResult['responseStatus'] == 200:
      for movie in searchResult['responseData']['results']:
        title = movie['titleNoFormatting']
        if title.find('| Film') != -1:
          title = title.split('| Film',1)[0].strip()
          id = re.search('\/movies\/([^/]+)', movie['unescapedUrl']).group(1)
          try:
            year = re.search('\(.*([0-9]{4}).*\)', movie['content']).group(1)
          except:
            year = None
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
      Log(' --> ' + result.name + ' | year = ' + str(result.year) + ' | id = ' + result.id + ' | score = ' + str(result.score))


  def scoreResultPenalty(self, media, year, title):
    scorePenalty = 0

    if year:
      # Penalty for movies from the future
      if int(year) > datetime.datetime.now().year:
        scorePenalty += 30

      # Give penalties based on the difference in years
      if media.year:
        scorePenalty += abs(int(year) - int(media.year)) * 3

    # Use 'clean' titles for the next checks
    # Strip 'The ' from the beginning of titles
    title1 = re.sub( '^The\s', '', title, re.IGNORECASE )
    title2 = re.sub( '^The\s', '', media.name, re.IGNORECASE )

    title1 = re.sub( '[^a-z0-9]+', '', String.StripDiacritics(title1.lower()) ) # Title we found on Moviepilot/Google
    title2 = re.sub( '[^a-z0-9]+', '', String.StripDiacritics(title2.lower()) ) # Title from filename/foldername

    Log(' --> Title we found on Moviepilot/Google = ' + title1)
    Log(' --> Title from filename/foldername      = ' + title2)

    # Calculate Levenshtein distance...
    nameDist = Util.LevenshteinDistance(title1, title2)
    # ...but only give penalies based on this difference to movies where the years don't match
    if media.year != year:
      scorePenalty += nameDist

    # Bonus for exact title matches
    if nameDist == 0:
      scorePenalty += -25

    # Bonus for movies where a shorter title is found within the longer (official) title
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
      full_name = ''
      try:
        cast = JSON.ObjectFromURL(MP_CAST_INFO % (self.metadata_id))
        for people in cast['movies_people']:
          if people['person']['restful_url'].find(name) != -1:
            # First or last name *can* be missing
            first_name = people['person']['first_name']
            if not first_name:
              first_name = ''

            last_name = people['person']['last_name']
            if not last_name:
              last_name = ''

            full_name = ' '.join([first_name, last_name]).strip()
            break
      except:
        pass
      return full_name
    elif type == 'm':
      try:
        movie = JSON.ObjectFromURL(MP_MOVIE_INFO % (name))
        title = movie['display_title']
      except:
        title = ''
      return title

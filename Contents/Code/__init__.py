MOVIE_URL = 'http://www.moviepilot.de/movies/imdb-id-%s'
RE_FSK = Regex('FSK (0|6|12|16|18)')
RE_POSTER_URL = Regex('background-image: url\(/(.+)_person\.jpg')

####################################################################################################
def Start():

	HTTP.CacheTime = CACHE_1WEEK
	HTTP.Headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:19.0) Gecko/20100101 Firefox/19.0'

####################################################################################################
class MoviepilotAgent(Agent.Movies):

	name = 'Moviepilot'
	languages = [Locale.Language.German]
	primary_provider = False
	contributes_to = ['com.plexapp.agents.imdb']


	def search(self, results, media, lang):

		# Use the IMDB id found by the primary metadata agent (Freebase)
		results.Append(MetadataSearchResult(
			id = media.primary_metadata.id.lstrip('t0'),
			score = 100
		))


	def update(self, metadata, media, lang):

		# Use data from Moviepilot only if the user has set the language for this section to German
		if lang == Locale.Language.German:
			try:
				html = HTML.ElementFromURL(MOVIE_URL % metadata.id, sleep=1.0)
			except:
				Log('Error fetching page for %s' % metadata.id)

			if html:
				# Title
				metadata.title = html.xpath('//h1[@itemprop="name"]/text()')[0].strip()

				# Original title
				original_title = html.xpath('//h2/span/text()')[0].rsplit('(',1)[0].strip()

				if original_title != metadata.title:
					metadata.original_title = original_title

				# Summary
				paragraphs = html.xpath('//div[@itemprop="description"]/p|//div[@itemprop="description"]/div/p')

				for p in paragraphs:
					if len(p.xpath('./strong|./b')) > 0 and len(p.xpath('./text()')) == 0:
						continue
					break

				metadata.summary = String.StripTags(p.text_content()).strip()

				# Poster
				poster = html.xpath('//div[@class="poster"]/@style')

				if len(poster) > 0:
					poster = RE_POSTER_URL.search(poster[0])

					if poster:
						poster_url = 'http://www.moviepilot.de/%s.jpg' % poster.group(1)

						if poster_url not in metadata.posters:
							img = HTTP.Request(poster_url)
							metadata.posters[poster_url] = Proxy.Preview(img)

				# FSK
				fsk = html.xpath('//h2//span[contains(text(), "FSK ")]')[0].text
				fsk = RE_FSK.search(fsk)

				if fsk:
					metadata.content_rating = 'de/%s' % fsk.group(1)

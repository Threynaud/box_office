import requests
import string
import re
import logging
import dateutil.parser
import pickle
import urllib
import json

from bs4 import BeautifulSoup
from tqdm import tqdm


logging.basicConfig(level=logging.DEBUG)


def url_to_page(url):
    ''' url: str, url of the page to scrap
        page: str, DOM of the page scrapped
    '''
    response = requests.get(url)

    page = response.text
    return page


def soup_DOM(page):
    ''' page: str, DOM of the page scrapped
        soup: bs4.BeautifulSoup object corresponding to the page scrapped
    '''
    soup = BeautifulSoup(page, "lxml")
    return soup


def get_all_movies():
    ''' Returns all the movie urls from boxofficemojo.com in a list'''

    # Alphabet loop for how movies are indexed including
    # movies that start with a special character or number
    index = ["NUM"] + list(string.ascii_uppercase)

    # List of movies urls
    movies_list = []

    # Loop through the pages for each letter
    for letter in tqdm(index):

        # Loop through the pages within each letter
        for num in range(1, 20):
            url = ("http://www.boxofficemojo.com/movies/alphabetical.htm?"
                   "letter=" + letter + "&page=" + str(num))
            try:
                page = url_to_page(url)
                soup = soup_DOM(page)
                rows = soup.find(id="body").find("table").find("table").find_all(
                    "table")[1].find_all("tr")

                # skip index row
                if len(rows) > 1:
                    counter = 1
                    for row in rows:

                        # skip index row
                        if counter > 1:
                            link = row.td.font.a['href']

                            # don't add duplicates
                            if link not in movies_list:
                                movies_list.append(link)
                        counter += 1
            except Exception as e:
                logging.exception(e)
    return movies_list


def pickle_movie(url):
    ''' url: str like '/movies/?id=<nameofthefilm>.htm' '''

    home = "http://www.boxofficemojo.com"
    page = url_to_page(home + url)
    soup = soup_DOM(page)

    pickle.dump(soup, open(url[len('/movies/?id='):-len('.htm')], "wb"))


def get_movie_value(soup, field_name):
    '''Grab a value from boxofficemojo HTML

    Takes a string attribute of a movie on the page and
    returns the string in the next sibling object
    (the value for that attribute)
    or None if nothing is found.
    '''
    obj = soup.find(text=re.compile(field_name))
    if not obj:
        return None
    # this works for most of the values
    next_sibling = obj.findNextSibling()
    if next_sibling:
        return next_sibling.text
    else:
        return None


def to_date(datestring):
    ''' datestring: str
        date: datetime object
    '''

    date = dateutil.parser.parse(datestring)
    return date


def money_to_int(moneystring):
    ''' moneystring: str
    '''

    moneystring = moneystring.replace('$', '').replace(',', '')
    return int(moneystring)


def runtime_to_minutes(runtimestring):
    ''' runtimestring: str
        minutes: int, number of minutes
    '''

    runtime = runtimestring.split()
    try:
        minutes = int(runtime[0]) * 60 + int(runtime[2])
        return minutes
    except:
        return


def get_title(soup):
    ''' soup: bs4.BeautifulSoup object
        title: str
    '''

    title_string = soup.find('title').text
    title = title_string.split('(')[0].strip()
    return title


def remove_non_numeric(s):
    ''' s: str with non numeric characters
        return: int
    '''
    return int(re.sub("[^0-9]", "", s))


def get_movie_infos(soup):
    ''' Return dict with needed infos about a movie '''
    try:
        # Release date
        raw_release_date = get_movie_value(soup, 'Release Date')
        release_date = to_date(raw_release_date)
    except Exception:
        release_date = None

    try:
        # Domestic total gross
        raw_domestic_total_gross = get_movie_value(soup, 'Domestic Total')
        domestic_total_gross = money_to_int(raw_domestic_total_gross)
    except Exception:
        domestic_total_gross = None

    try:
        # Budget
        budget = get_movie_value(soup, 'Production Budget')
    except Exception:
        budget = None

    try:
        # Runtime (mins)
        raw_runtime = get_movie_value(soup, 'Runtime')
        runtime = runtime_to_minutes(raw_runtime)
    except Exception:
        runtime = None

    try:
        # Title
        title = get_title(soup)
    except Exception:
        title = None

    try:
        # Rating
        rating = get_movie_value(soup, 'MPAA Rating')
    except Exception:
        rating = None

    try:
        # Genre
        genre = soup.find(text=re.compile('Genre:')).findNextSibling().text
    except Exception:
        genre = None

    try:
        # Director
        director = getpeople(soup, 'Director')
    except Exception:
        director = None

    try:
        # Actors
        actors = getpeople(soup, 'Actor')
    except Exception:
        actors = None

    try:
        # Producers
        producer = getpeople(soup, 'Producer')
    except Exception:
        producer = None

    try:
        # Writers
        writers = getpeople(soup, 'Writer')
    except Exception:
        writers = None

    try:
        # Cinematographer
        cinematographer = getpeople(soup, 'Cinematographer')
    except Exception:
        cinematographer = None

    try:
        # Composer
        composer = getpeople(soup, 'Composer')
    except Exception:
        composer = None

    headers = ['movie title', 'domestic total gross', 'budget',
               'release date', 'runtime', 'rating', 'genre', 'director', 'actors', 'producer', 'writers', 'cinematographer', 'composer']

    movie_dict = dict(zip(headers, [title,
                                    domestic_total_gross,
                                    budget,
                                    release_date,
                                    runtime,
                                    rating,
                                    genre,
                                    director,
                                    actors,
                                    producer,
                                    writers,
                                    cinematographer,
                                    composer]))
    return movie_dict


def soupstrainer(temp):
    '''temp: str to clean'''
    temp = temp.replace('\n', '')
    temp = temp.replace(':', ':,')
    temp = temp.replace('  ', '')
    temp = temp.replace('*', '')
    temp = temp.replace(')', '),')
    temp = temp.replace('Denotes minor role', '')
    temp = re.sub(r"(\w)([A-Z])", r"\1,\2", temp)
    temp = re.sub(r"(\WMc,)", r" Mc", temp)

    return temp.split(',')


def getpeople(soup, temp):
    '''temp: str, like 'Actors', 'Directors', etc.'''

    toggle = False
    people = []
    words = []

    for i in range(0, len(soup.find_all(class_='mp_box_content'))):
        if (temp or temp + 's') in soup.find_all(class_='mp_box_content')[i].text:
            words = soupstrainer(
                soup.find_all(class_='mp_box_content')[i].text)
# .encode('utf-8'))
    if words == '':
        return None

    for word in words:
        if ':' in word and toggle:
            toggle = not toggle
        if temp in word:
            toggle = not toggle
            continue
        if toggle:
            people.append(word)

    return people


def omdbapi_to_json(title, year="", tomatoes="true", typ="movie"):
    ''' title: str, title of the movie
        year: str, release year
    '''
    base_url = "http://www.omdbapi.com/?"
    params = {'t': title, 'y': year, 'tomatoes': tomatoes, 'type': typ}
    url = base_url + urllib.parse.urlencode(params)
    response = url_to_page(url)
    data = json.loads(response)
    return data


def complete_line_df(movie, df):
    '''movie: tuple, item of df.iterrows '''

    title = movie[1]["movie title"]
    year = movie[1]["release date"].year
    data = omdbapi_to_json(title, year=year)

    if data["Response"] == 'True':
        if movie[1]["rating"] == "Unrated":
            try:
                df.set_value(movie[0], 'rating', data["Rated"])
            except:
                pass

        try:
            df.set_value(movie[0], 'genre', data["Genre"])
        except:
            pass

        if movie[1]["director"] == []:
            try:
                df.set_value(movie[0], 'director', data["Director"])
            except:
                pass

        if movie[1]["actors"] == []:
            try:
                df.set_value(movie[0], 'actors', data["Actors"])
            except:
                pass

        try:
            df.set_value(movie[0], 'imdb_rating', data["imdbRating"])
        except:
            pass

        try:
            df.set_value(movie[0], 'imdb_votes', data["imdbVotes"])
        except:
            pass

        try:
            df.set_value(movie[0], 'tomato_meter', data["tomatoMeter"])
        except:
            pass

        try:
            df.set_value(movie[0], 'tomato_rating', data["tomatoRating"])
        except:
            pass

        try:
            df.set_value(movie[0], 'tomato_rotten', data["tomatoRotten"])
        except:
            pass

        try:
            df.set_value(
                movie[0], 'tomato_user_rating', data["tomatoUserRating"])
        except:
            pass

        try:
            df.set_value(
                movie[0], 'tomato_user_reviews', data["tomatoUserReviews"])
        except:
            pass

        try:
            df.set_value(movie[0], 'meta_score', data["Metascore"])
        except:
            pass

        try:
            df.set_value(movie[0], 'tomato_consensus', data["tomatoConsensus"])
        except:
            pass

    else:
        data = omdbapi_to_json(title)
        if data["Response"] == 'True':
            if movie[1]["rating"] == "Unrated":
                try:
                    df.set_value(movie[0], 'rating', data["Rated"])
                except:
                    pass

            try:
                df.set_value(movie[0], 'genre', data["Genre"])
            except:
                pass

            if movie[1]["director"] == []:
                try:
                    df.set_value(movie[0], 'director', data["Director"])
                except:
                    pass

            if movie[1]["actors"] == []:
                try:
                    df.set_value(movie[0], 'actors', data["Actors"])
                except:
                    pass

            try:
                df.set_value(movie[0], 'imdb_rating', data["imdbRating"])
            except:
                pass

            try:
                df.set_value(movie[0], 'imdb_votes', data["imdbVotes"])
            except:
                pass

            try:
                df.set_value(movie[0], 'tomato_meter', data["tomatoMeter"])
            except:
                pass

            try:
                df.set_value(movie[0], 'tomato_rating', data["tomatoRating"])
            except:
                pass

            try:
                df.set_value(movie[0], 'tomato_rotten', data["tomatoRotten"])
            except:
                pass

            try:
                df.set_value(
                    movie[0], 'tomato_user_rating', data["tomatoUserRating"])
            except:
                pass

            try:
                df.set_value(
                    movie[0], 'tomato_user_reviews', data["tomatoUserReviews"])
            except:
                pass

            try:
                df.set_value(movie[0], 'meta_score', data["Metascore"])
            except:
                pass

            try:
                df.set_value(
                    movie[0], 'tomato_consensus', data["tomatoConsensus"])
            except:
                pass

import requests
from enum import Enum
from bs4 import BeautifulSoup
import re
import tasks


class UserNotFoundError(Exception):
    def __init__(self, user_id):
        self.user_id = user_id


class RecipeNotFoundError(Exception):
    def __init__(self, recipe_id):
        self.recipe_id = recipe_id


class LoginException(Exception):
    def __init__(self, username):
        self.username = username


class OrderBy(Enum):
    relevance = 2
    rating = 3
    difficulty = 4
    max_time_needed = 5
    date = 6
    random = 7
    daily_shuffle = 8


class ChefkochApi:
    """An API Wrapper for www.chefkoch.com"""

    def __init__(self, username="", password=""):
        if username and password:
            self.session = self.login(username, password)
            self.is_logged_in = True
        else:
            self.session = requests.session()
            self.is_logged_in = False

    def login(self, username, password):
        """Login user with username and password"""
        session = requests.Session()
        login_url = "https://www.chefkoch.de/benutzer/authentifizieren"
        login_data = {
            "username": username,
            "password": password,
            "remember_me": "on",
            "context": "login/init"
        }
        res = session.post(login_url, login_data)

        # They send 200 even if the authentication failed...
        if res.url == "https://www.chefkoch.de/benutzer/einloggen":
            raise LoginException(username)

        return session

    def get_recipe(self, recipe_id):
        """Returns a recipe as a dict for a given recipe_id"""
        url = "https://api.chefkoch.de/v2/recipes/%s" % recipe_id
        res = self.session.get(url)
        if res.status_code is not 200:
            raise RecipeNotFoundError(recipe_id)
        else:
            return res.json()

    def search_recipe(self, query='',
                      offset=0,
                      limit=50,
                      minimum_rating=0,
                      maximum_time=0,
                      order_by=OrderBy.relevance,
                      descend_categories=1,
                      order=0):
        """Returns a list of recipes that match the given search tearms"""
        payload = {
            "query": query,
            "limit": limit,
            "offset": offset,
            "minimumRating": minimum_rating,
            "maximumTime": maximum_time,
            "orderBy": order_by,
            "descendCategories": descend_categories,
            "order": order
        }
        res = self.session.get("https://api.chefkoch.de/v2/recipes", params=payload)
        if res.status_code is not 200:
            raise ConnectionError("Response is not 200")
        else:
            return res.json()

    def get_user(self, user_id):
        url = 'http://www.chefkoch.de/user/profil/' + user_id
        r = self.session.get(url)
        response = r.content.decode("utf-8")
        soup = BeautifulSoup(response, 'html.parser')

        title = soup.select(".page-title")
        if len(title) >= 1:
            if "Keine oder ungültige User-ID" in title[0].text.strip():
                raise UserNotFoundError(user_id)

        user_details = soup.select("#user-details tr")

        user = {
            'id': user_id,
            '_id': user_id,
            'friends': [],
            'Schritt-für-Schritt-Anleitungen': []
        }

        if len(soup.select('.username')) >= 0:
            user['username'] = soup.select('.username')[0].text.strip(),

        for entry in user_details:
            td = entry.select("td")
            if td[0].text.strip() != '':
                img = td[1].select("img")
                if not img:
                    user[td[0].text.strip().replace(':', '')] = td[1].text.strip()
                else:
                    user[td[0].text.strip().replace(':', '')] = img[0].attrs['alt']

        profile_sections = soup.select(".slat__title")

        for section in profile_sections:

            if section.text.strip().find('Über mich') >= 0:
                user['aboutme'] = soup.select("#user-about")[0].text.strip().replace("\r", "")

            if section.text.strip().strip().find('Freunde') >= 0:
                user['Freunde'] = re.findall(r'\d+', section.text.strip())[0]
                user['friends'] = self.get_friends_of_user(user_id)

            # Anzahl der Rezepte
            if section.text.strip().find('Rezepte') >= 0:
                user['Anzahl_Rezepte'] = re.findall(r'\d+', section.text.strip())[0]

            # Anzahl der Rezeptsammlungen
            if section.text.strip().find('Rezeptsammlungen') >= 0:
                user['AnzahlRezeptsammlungen'] = re.findall(r'\d+', section.text.strip())[0]

            # Rezeptsammlungen + Anzahl der Rezepte pro Sammlung
            user['Rezeptsammlungen'] = []
            for row in soup.select('#table-recipe-collections tr'):
                for link in row.select('a'):
                    url = link.get('href')
                    count = re.findall(r'\d+', row.text)[0]
                    user['Rezeptsammlungen'].append({'url': url, 'nrOfRecipes': count})

            if section.text.strip().find('Schritt-für-Schritt-Anleitungen') >= 0:
                user['Anzahl-Schritt-für-Schritt-Anleitungen'] = re.findall(r'\d+', section.text.strip())[0]
                user['Schritt-für-Schritt-Anleitungen'] = self.get_step_by_step_guides(user_id)

            if section.text.strip().find('Fotoalben') >= 0:
                user['Fotoalben'] = re.findall(r'\d+', section.text.strip())[0]

            if section.text.strip().find('Forenthemen') >= 0:
                user['Forenthemen'] = re.findall(r'\d+', section.text.strip())[0]

            if section.text.strip().find('Gruppen') >= 0:
                user['Gruppen'] = re.findall(r'\d+', section.text.strip())[0]

            # Gruppen (Name + url)
            user['Gruppen'] = []
            for row in soup.select('#user-groups li'):
                name_of_group = row.text.strip()
                link = row.select('a')[0]
                url = link.get('href')
                user['Gruppen'].append({'url': url, 'Gruppenname': name_of_group})
        return user

    def get_friends_of_user(self, user_id):
        """Returns a list of friends for a given user_id"""
        url = 'http://www.chefkoch.de/user/freunde/%s/' % user_id
        response = self.session.get(url).text
        soup = BeautifulSoup(response, 'html.parser')

        friends = []

        for buddy in soup.select('li.user-buddies__buddy'):
            friend = {'username': buddy.text.strip()}
            if buddy.select('a'):
                friend['link'] = buddy.select('a')[0].get('href')
                regex = r"/user/profil/(.*)/.*.html"
                friend['id'] = re.findall(regex, friend['link'])[0]
            friends.append(friend)
        return friends

    def get_rating_by_recipe_id(self, recipe_id, db):
        url = 'http://www.chefkoch.de/rezepte/wertungen/' + recipe_id + '/'
        r = self.session.get(url)
        response = r.content.decode("utf-8")

        soup = BeautifulSoup(response, 'html.parser')

        recipe_rating = {}
        recipe_rating['_id'] = recipe_id

        voting_table = soup.select(".voting-table tr")

        if not voting_table:
            recipe_rating["rating"] = []
            return recipe_rating

        voting_table.pop(0)

        votings = []
        for entry in voting_table:
            td = entry.select("td")

            voting_by_user = {}
            voting_by_user["voting"] = re.findall(r'\d+', td[0].select("span span")[0].get("class")[1])[0]
            voting_by_user["name"] = td[1].text.strip()

            # check if user account was removed from chefkoch.de
            if td[1].select("a"):
                voting_by_user["id"] = td[1].select("a")[0].get("href").split('/')[3]
                # adds user to db
                # TODO: This logic should be in tasks.py
                self.add_unknown_user(voting_by_user["id"], db)
            else:
                voting_by_user["id"] = "unbekannt"
                print(voting_by_user)
                print(recipe_id)
                print(entry.text.strip())

            voting_by_user["date"] = td[2].text.strip()

            votings.append(voting_by_user)

        recipe_rating["rating"] = votings

        return recipe_rating

    def get_step_by_step_guides(self, user_id):
        url = 'http://www.chefkoch.de/community/profil/%s/anleitungen' % user_id
        response = self.session.get(url).text
        soup = BeautifulSoup(response, 'html.parser')
        guides = []
        for row in soup.select('.theme-community .without-footer'):
            link = row.select('a')
            if link[1]:
                url = link[1].get('href')
                guides.append({'url': url, 'Titel': link[1].text.strip()})
        return guides

    # TODO: This should also be in tasks.py
    def add_unknown_user(self, id, db):
        user_found = False

        db_user = db.users.find({"_id": id})

        for user in db_user:
            user_found = True

        if not user_found:
            tasks.crawl_single_user.delay(id)

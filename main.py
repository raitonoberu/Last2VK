import requests
import os
from time import sleep

try:
    from fp.fp import FreeProxy

    _fp_available = True
except ImportError:
    _fp_available = False

# https://vkhost.github.io
vk_token = os.getenv("VK_TOKEN")

# https://www.last.fm/api/account/create
lastfm_key = os.getenv("LASTFM_KEY")

# Your last.fm username
lastfm_username = os.getenv("LASTFM_USERNAME")

# Time between updating status (in secs)
refresh_delay = int(os.getenv("REFRESH_DELAY")) if os.getenv("REFRESH_DELAY") else 20

# "true" or "false"
debug = os.getenv("DEBUG") or "false"
retry_without_artist = os.getenv("RETRY_WITHOUT_ARTIST") or "true"
use_proxies = os.getenv("USE_PROXIES") or "true"


if not _fp_available:
    if use_proxies == "true":
        print("If you want to use proxies, please install 'free-proxy' package:")
        print("  $ pip install free-proxy\n")
        use_proxies = "false"


def main():
    session = requests.session()
    lastfm = LastFmApi(session, lastfm_key, lastfm_username)
    vk = VkApi(session, vk_token)

    while True:
        sleep(refresh_delay)
        try:
            try:
                track = lastfm.get_status()
            except LastFmException as e:
                if e.code not in (8, 16, 29):
                    # not related to timeout, server issues, etc.
                    raise
                continue

            if track is None:
                continue
            track_name = track[0] + " " + track[1]
            if debug == "true":
                print(track_name)
            result = vk.search(track_name)
            if result is None:
                if retry_without_artist != "true":
                    if debug == "true":
                        print("Not found")
                    continue
                result = vk.search(track[1])
                if result is None:
                    if debug == "true":
                        print("Not found")
                    continue
            vk.set_status(result)
        except Exception as e:
            if debug == "true":
                raise
            print(e)
            lastfm.now_playing = None


class Proxifier(object):
    proxy = None

    def get_proxy(self):
        if self.proxy is None:
            self.update_proxy()
        return self.proxy

    def update_proxy(self):
        self.proxy = FreeProxy(country_id=["RU"]).get()
        if debug == "true":
            print("[DEBUG] New proxy:", self.proxy)


class VkApi(object):
    def __init__(self, session, token):
        self.session = session
        self.token = token
        if use_proxies == "true":
            self.proxifier = Proxifier()

    def _get(self, url, params={}):
        if use_proxies == "true":
            proxy = self.proxifier.get_proxy()
            if proxy is None:
                proxy = {}
            else:
                proxy = {"http": proxy}
        else:
            proxy = {}

        try:
            return self.session.get(url, params=params, proxies=proxy)
        except:  # TODO: catch only proxy-related exceptions
            if use_proxies == "true":
                self.proxifier.update_proxy()
                return self._get(url, params)
            raise

    def search(self, q):
        params = {
            "q": q,
            "auto_complete": "1",
            "count": "1",
            "access_token": self.token,
            "v": "5.100",
        }
        json = self._get(
            "https://api.vk.com/method/audio.search", params=params
        ).json()["response"]
        if json["count"] == 0:
            return None
        result = json["items"][0]
        return str(result["owner_id"]) + "_" + str(result["id"])

    def set_status(self, track_id):
        params = {
            "audio": track_id,
            "access_token": self.token,
            "v": "5.100",
        }
        self._get("https://api.vk.com/method/audio.setBroadcast", params=params)


class LastFmException(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return "Error (" + str(self.code) + "): " + self.message


class LastFmApi(object):
    now_playing = None

    def __init__(self, session, api_key, username):
        self.session = session
        self.api_key = api_key
        self.username = username

    def get_status(self):
        params = {
            "method": "user.getrecenttracks",
            "limit": 1,
            "user": self.username,
            "api_key": self.api_key,
            "format": "json",
        }
        json = self.session.get(
            "http://ws.audioscrobbler.com/2.0/", params=params
        ).json()
        if "recenttracks" not in json:
            if "error" in json:
                raise LastFmException(json["error"], json["message"])
            print(json)
        json = json["recenttracks"]["track"]

        if (
            len(json) > 0
            and "@attr" in json[0]
            and json[0]["@attr"]["nowplaying"] == "true"
        ):
            track = (json[0]["artist"]["#text"], json[0]["name"])
            if track != self.now_playing:
                # return every track only once
                self.now_playing = track
                return track
            return None
        self.now_playing = None
        return None


if __name__ == "__main__":
    main()

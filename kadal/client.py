from typing import Union, List

from kadal.query import MEDIA_SEARCH, MEDIA_BY_ID, MEDIA_PAGED, USER_SEARCH, USER_BY_ID
from kadal.media import Media
from kadal.user import User


URL = 'https://graphql.anilist.co'


class KadalError(Exception):
    def __init__(self, message, status):
        self.message = message
        self.status = status


class MediaNotFound(KadalError):
    pass


class Client:
    def __init__(self, session=None, *, lib='asyncio', loop=None):
        if lib not in ('asyncio', 'multio'):
            raise ValueError("lib must be of type `str` and be either `asyncio` or `multio`, "
                             "not `{}`".format(lib if isinstance(lib, str) else lib.__class__.__name__))
        self._lib = lib
        if lib == 'asyncio':
            import asyncio
            loop = loop or asyncio.get_event_loop()
        self.session = session or self._make_session(lib, loop)

    @staticmethod
    def _make_session(lib, loop=None) -> Union['aiohttp.ClientSession', 'asks.Session']:
        if lib == 'asyncio':
            try:
                import aiohttp
            except ImportError:
                raise ImportError("To use Kadal in asyncio mode, it requires the `aiohttp` module.")
            return aiohttp.ClientSession(loop=loop)
        try:
            import asks
        except ImportError:
            raise ImportError("To use Kadal in curio/trio mode, it requires the `asks` module.")
        return asks.Session()

    async def _request(self, query, **variables) -> dict:
        r = await self.session.post(URL, json={"query": query, "variables": variables})
        if self._lib == 'asyncio':
            data = await r.json()
        else:
            data = r.json()
        if data.get('errors'):
            self.handle_error(data['errors'][0])
        return data

    async def _paged_request(self, page=1, perPage=50, **variables) -> List[dict]:
        """Depending on the value passed for 'sort' variable you can sort by whatever you want.
        search Media Sort here https://anilist.github.io/ApiV2-GraphQL-Docs/
        ex: await yourkadalclient.paged_request(**{"type":"ANIME","sort":"SCORE_DESC"})"""
        data = await self._request(MEDIA_PAGED, page=page, perPage=perPage, **variables)
        lst = data['data']['Page']['media']
        if not lst:
            raise MediaNotFound("Not Found.", 404)
        return lst

    @staticmethod
    def handle_error(error):
        msg = error['message']
        status = error['status']
        if status == 404:
            raise MediaNotFound(msg, status)
        else:
            raise KadalError(msg, status)

    async def get_anime(self, id) -> Media:
        data = await self._request(MEDIA_BY_ID, id=id, type='ANIME')
        return Media(data)

    async def get_manga(self, id) -> Media:
        data = await self._request(MEDIA_BY_ID, id=id, type='MANGA')
        return Media(data)

    async def get_user(self, id) -> User:
        data = await self._request(USER_BY_ID, id=id)
        return User(data)
    
    async def custom_paged_search(self, page=1, perPage=50, **variables) -> List[Media]:  
        return [Media(media_data, page=True) for media_data in await self._paged_request(page=page, perPage=perPage, **variables)]

    async def search_anime(self, query, *, popularity=False, allow_adult=False) -> Media:
        variables = {
            "search": query,
            "type": "ANIME",
        }
        if not allow_adult:
            variables['isAdult'] = False

        if popularity:
            data = (await self._paged_request(**variables))[0]
        else:
            data = await self._request(MEDIA_SEARCH, **variables)
        return Media(data, page=popularity)

    async def search_manga(self, query, *, popularity=False, include_novels=False, allow_adult=False) -> Media:
        exclude = "NOVEL" if not include_novels else None
        variables = {
            "search": query,
            "type": "MANGA",
            "exclude": exclude,
        }
        if not allow_adult:
            variables['isAdult'] = False

        if popularity:
            data = (await self._paged_request(**variables))[0]
        else:
            data = await self._request(MEDIA_SEARCH, **variables)
        return Media(data, page=popularity)

    async def search_user(self, query) -> User:
        data = await self._request(USER_SEARCH, search=query)
        return User(data)

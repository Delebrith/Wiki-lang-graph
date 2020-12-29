from __future__ import annotations

__all__ = ["Page", "PageKey", "PageKeySet"]

import asyncio
import logging
from collections import Coroutine
from collections import Generator
from collections import Iterable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any
from typing import Optional

import httpx

from scripts.wikilanggraph.base_set import BaseSet
from scripts.wikilanggraph.mergedicts import mergedicts
from scripts.wikilanggraph.multiton import multiton

logger = logging.getLogger(__name__)

Seconds = int


@multiton("title", "language")
class Page:
    _instances = {}

    def __init__(self: Page, *, language: str, title: str) -> None:
        self._aliases: set[str] = set()
        self._title: str = title
        self._language: str = language
        self._wikibase_item: Optional[str] = None
        self._displaytitle: Optional[str] = None
        self._links: PageKeySet[PageKey] = PageKeySet()
        self._langlinks: PageKeySet[PageKey] = PageKeySet()
        self._fetched: bool = False
        self._valid: bool = True
        self._revisions: set[int] = set()

    def __repr__(self: Page) -> str:
        return (
            f"Page(title={self._title}, displaytitle={self._displaytitle},"
            f" lang={self._language}, wikibase_item={self._wikibase_item})"
        )

    @property
    def language(self: Page) -> str:
        return self._language

    @property
    def title(self: Page) -> str:
        return self._title

    @property
    def wikibase_item(self: Page) -> str:
        return self._wikibase_item

    @property
    def links(self: Page) -> Generator[Page, None, None]:
        return self._links.pages

    @property
    def langlinks(self: Page) -> Generator[Page, None, None]:
        return self._langlinks.pages

    @property
    def all_language_versions(self: Page) -> set[Page]:
        return {self} | set(self.langlinks)

    @property
    def links_as_graph_nodes(
        self: Page,
    ) -> Generator[Any, None, None]:
        return self._links.graph_nodes_generator()

    @property
    def langlinks_as_graph_nodes(
        self: Page,
    ) -> Generator[Any, None, None]:
        return self._langlinks.graph_nodes_generator()

    @property
    def links_as_graph_edges(self: Page) -> Generator[Any, None, None]:
        return self._links.graph_edges_generator(from_node=self.wikibase_item)

    def to_pagekey(self: Page) -> PageKey:
        return PageKey(language=self.language, title=self.title)

    async def fetch_langlinks(
        self: Page,
        client: httpx.AsyncClient,
        languages: Optional[Iterable[str]] = None,
        make_unique: bool = False,
    ) -> None:
        if not self._fetched:
            await self.fetch_page(client=client)
        if languages is not None:
            self._langlinks.filter_languages(languages=languages)
        coroutines = await self._langlinks.fetch_pages_coroutines(
            client=client, make_unique=make_unique
        )
        await asyncio.gather(*coroutines)
        self._langlinks.remove_nonexistent()

    async def fetch_links(
        self: Page, client: httpx.AsyncClient, avoid: str = ":"
    ) -> None:
        if not self._fetched:
            await self.fetch_page(client=client)
        self._links.filter_titles(avoid=avoid)
        coroutines = await self._links.fetch_pages_coroutines(client=client)
        await asyncio.gather(*coroutines)
        self._links.remove_nonexistent()

    async def fetch_page(
        self: Page, client: httpx.AsyncClient, make_unique: bool = False
    ) -> None:
        if self._fetched:
            logger.warning(
                'Page "%s" has already been fetched once, and will not fetched be again',
                self.title,
            )
            return
        self._fetched = True

        data = await self._fetch(client, links=make_unique, revisions=make_unique)
        while "continue" in data:
            extra_params = data.pop("continue")
            logger.debug(
                'Continue fetching for page "%s": %s', self.title, extra_params
            )
            new_data = await self._fetch(
                client, links=make_unique, revisions=make_unique, **extra_params
            )
            data = dict(mergedicts(data, new_data))

        page_number, page_data = data["query"]["pages"].popitem()
        if page_number == "-1":
            logger.warning(
                'Linked page "%s" does not exist and will be removed', self.title
            )
            self._valid = False
            return
        self._parse_page_data(data=page_data, add_language_to_wikibase_item=make_unique)
        self._add_aliases_to_class_instances()

    def _parse_page_data(
        self: Page, data: dict[str, Any], add_language_to_wikibase_item: bool = False
    ) -> None:
        self._displaytitle = data["displaytitle"]
        with suppress(KeyError):
            self._links = PageKeySet(
                PageKey(language=self._language, title=link["title"])
                for link in data["links"]
            )
        with suppress(KeyError):
            self._langlinks = PageKeySet(
                PageKey(language=langlink["lang"], title=langlink["*"])
                for langlink in data["langlinks"]
            )
        with suppress(KeyError):
            self._aliases = {alias["title"] for alias in data["redirects"]}
        try:
            self._wikibase_item = data["pageprops"]["wikibase_item"]
        except KeyError:
            logger.error("No wikibase item %s", self)
        with suppress(KeyError):
            self._revisions = data["revisions"]
        if add_language_to_wikibase_item:
            self._wikibase_item += f"__{self.language}"
        if self.wikibase_item is None:
            logger.error("No wikibase: %s, %s", self.title, self.wikibase_item)

    async def _fetch(
        self: Page,
        client: httpx.AsyncClient,
        links: bool = False,
        revisions: bool = False,
        **extra_params: Any,
    ) -> dict:
        base_url = f"https://{self.language}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "prop": "info|langlinks|pageprops|redirects",
            "titles": self.title,
            "redirects": 1,
            "rdlimit": "max",
            "inprop": "displaytitle",
            "llprop": "autonym|langname|url",
            "lllimit": "max",
            "ppprop": "wikibase_item",
        }
        if links:
            params["prop"] += "|links"
            params["pllimit"] = ("max",)

        if revisions:
            params["prop"] += "|revisions"
            params["rvlimit"] = "max"
            params["rvprop"] = "ids|flags|timestamp|roles|flagged"

        response: Optional[httpx.Response] = None
        sleep_time: Seconds = 2
        while not response:
            try:
                response = await client.get(base_url, params=params | extra_params)
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
                logger.error(
                    '%s while fetching "%s" - waiting at least %i seconds before another try',
                    e.__class__.__name__,
                    self.title,
                    sleep_time,
                    exc_info=False,
                )
                await asyncio.sleep(sleep_time)
                sleep_time *= 4

        return response.json()

    def _add_aliases_to_class_instances(self: Page) -> None:
        for alias in self._aliases:
            Page._instances[(alias, self.language)] = self


@dataclass(frozen=True, eq=True)
class PageKey:
    title: str
    language: str


class PageKeySet(BaseSet):
    @property
    def pages(self: PageKeySet) -> Generator[Page, None, None]:
        return (Page(**page_key.__dict__) for page_key in self.data)

    @property
    def wikibase_items(self: PageKeySet) -> Generator[str, None, None]:
        return (page.wikibase_item for page in self.pages)

    def remove_nonexistent(self: PageKeySet) -> None:
        self.data = {
            page_key for page_key in self.data if Page(**page_key.__dict__)._valid
        }

    def filter_languages(self: PageKeySet, languages: Iterable[str]) -> None:
        self.data = {
            page_key for page_key in self.data if page_key.language in languages
        }

    def filter_titles(self: PageKeySet, avoid: str) -> None:
        if avoid:
            self.data = {
                page_key for page_key in self.data if avoid not in page_key.title
            }

    def graph_nodes_generator(
        self: PageKeySet,
    ) -> Generator[tuple[str, dict[str, Page]], None, None]:
        return ((page.wikibase_item, {"page": page}) for page in self.pages)

    async def fetch_pages_coroutines(
        self: Page, client: httpx.AsyncClient, *args: Any, **kwargs: Any
    ) -> Generator[Coroutine, Any, None]:
        return (page.fetch_page(client, *args, **kwargs) for page in self.pages)

    def graph_edges_generator(
        self: PageKeySet, from_node: str
    ) -> Generator[tuple[str, str]]:
        return ((from_node, to_node) for to_node in self.wikibase_items)

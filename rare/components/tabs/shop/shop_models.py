import datetime
import random
from dataclasses import dataclass

from rare.utils.utils import get_lang


class ImageUrlModel:
    def __init__(self, front_tall: str = "", offer_image_tall: str = "",
                 thumbnail: str = "", front_wide: str = "", offer_image_wide: str = ""):
        self.front_tall = front_tall
        self.offer_image_tall = offer_image_tall
        self.thumbnail = thumbnail
        self.front_wide = front_wide
        self.offer_image_wide = offer_image_wide

    @classmethod
    def from_json(cls, json_data: list):
        tmp = cls()
        for item in json_data:
            if item["type"] == "Thumbnail":
                tmp.thumbnail = item["url"]
            elif item["type"] == "DieselStoreFrontTall":
                tmp.front_tall = item["url"]
            elif item["type"] == "DieselStoreFrontWide":
                tmp.front_wide = item["url"]
            elif item["type"] == "OfferImageTall":
                tmp.offer_image_tall = item["url"]
            elif item["type"] == "OfferImageWide":
                tmp.offer_image_wide = item["url"]
        return tmp


class ShopGame:
    # TODO: Copyrights etc
    def __init__(self, title: str = "", image_urls: ImageUrlModel = None, social_links: dict = None,
                 langs: list = None, reqs: dict = None, publisher: str = "", developer: str = "",
                 original_price: str = "", discount_price: str = "", tags: list = None, namespace: str = "",
                 offer_id: str = ""):
        self.title = title
        self.image_urls = image_urls
        self.links = []
        if social_links:
            for item in social_links:
                if item.startswith("link"):
                    self.links.append(tuple((item.replace("link", ""), social_links[item])))
        else:
            self.links = []
        self.languages = langs
        self.reqs = reqs
        self.publisher = publisher
        self.developer = developer
        self.price = original_price
        self.discount_price = discount_price
        self.tags = tags
        self.namespace = namespace
        self.offer_id = offer_id

    @classmethod
    def from_json(cls, api_data: dict, search_data: dict):
        if isinstance(api_data, list):
            for product in api_data:
                if product["_title"] == "home":
                    api_data = product
                    break
        if "pages" in api_data.keys():
            api_data = api_data["pages"][0]
        tmp = cls()
        tmp.title = search_data.get("title", "Fail")
        tmp.image_urls = ImageUrlModel.from_json(search_data["keyImages"])
        links = api_data["data"]["socialLinks"]
        tmp.links = []
        for item in links:
            if item.startswith("link"):
                tmp.links.append(tuple((item.replace("link", ""), links[item])))
        tmp.available_voice_langs = api_data["data"]["requirements"].get("languages", "Failed")
        tmp.reqs = {}
        for i, system in enumerate(api_data["data"]["requirements"].get("systems", [])):
            try:
                tmp.reqs[system["systemType"]] = {}
            except KeyError:
                continue
            for req in system["details"]:
                try:
                    tmp.reqs[system["systemType"]][req["title"]] = (req["minimum"], req["recommended"])
                except KeyError:
                    pass
        tmp.publisher = api_data["data"]["meta"].get("publisher", "")
        tmp.developer = api_data["data"]["meta"].get("developer", "")
        if not tmp.developer:
            for i in search_data["customAttributes"]:
                if i["key"] == "developerName":
                    tmp.developer = i["value"]
        tmp.price = search_data['price']['totalPrice']['fmtPrice']['originalPrice']
        tmp.discount_price = search_data['price']['totalPrice']['fmtPrice']['discountPrice']
        tmp.tags = [i.replace("_", " ").capitalize() for i in api_data["data"]["meta"].get("tags", [])]
        tmp.namespace = search_data["namespace"]
        tmp.offer_id = search_data["id"]

        return tmp


@dataclass
class BrowseModel:
    category: str = "games/edition/base|bundles/games|editors|software/edition/base"
    count: int = 30
    locale: str = get_lang()
    keywords: str = ""
    sortDir: str = "DESC"
    start: int = 0
    tag: str = ""
    withMapping: bool = True
    withPrice: bool = True
    date: str = f"[,{datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%dT%X')}.{str(random.randint(0, 999)).zfill(3)}Z]"
    price: str = ""
    onSale: bool = False

    @property
    def __dict__(self):
        payload = {"category": self.category,
                   "count": self.count,
                   "country": self.locale.upper(),
                   "keywords": self.keywords,
                   "locale": self.locale,
                   "sortDir": self.sortDir,
                   "allowCountries": self.locale.upper(),
                   "start": self.start,
                   "tag": self.tag,
                   "withMapping": self.withMapping,
                   "withPrice": self.withPrice,
                   "releaseDate": self.date,
                   "effectiveDate": self.date,
                   }

        if self.price == "free":
            payload["freeGame"] = True
        elif self.price.startswith("<price>"):
            payload["priceRange"] = self.price.replace("<price>", "")
        if self.onSale:
            payload["onSale"] = True
        return payload

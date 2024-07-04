import datetime
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel
from pymongo import UpdateOne

from mongo.database import DataBase, db_logger
from scraping.car_parser import CarAdvShortInfo


class CarForGroup(BaseModel):
    id: Optional[str]
    link: Optional[str]
    img_src: Optional[str]
    make: str
    model: str
    year: int
    price: int
    engine_power: int
    engine_capacity: int

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
        }


class CarRepository:

    def __init__(self, db: DataBase):
        self.db = db

    async def save_car(self, car_details: dict):
        await self.db.car_collection.replace_one(
            filter={'ad_number': car_details['ad_number']},
            replacement=car_details,
            upsert=True
        )
        db_logger.debug('Saved new car, ad #%s', car_details['ad_number'])

    @staticmethod
    def car_from_mongo(document: dict) -> CarForGroup:
        document["id"] = str(document.pop("_id"))
        document['options'] = [option for option in document.get('options', []) if option is not None]
        try:
            return CarForGroup(**document)
        except Exception as e:
            print(e)

    async def get_car(self, ad_number: int) -> dict:
        return await self.db.car_collection.find_one({'ad_number': ad_number})

    async def get_grouped_data(self, group_by: list, data_filter: dict, min_count: int = 1):
        group_id = {field: f"${field}" for field in group_by}
        pipeline = []
        if data_filter:
            pipeline.append({"$match": data_filter})
        pipeline.extend([
            {
                "$group": {
                    "_id": group_id,
                    "count": {"$sum": 1},
                    "cars": {"$push": "$$ROOT"}
                }
            },
            {
                "$match": {
                    "count": {"$gte": min_count}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    **{field: f"$_id.{field}" for field in group_by},
                    "count": 1,
                    "cars": 1
                }
            }
        ])
        grouped_data = []
        async for group in self.db.car_collection.aggregate(pipeline):
            group["cars"] = [self.car_from_mongo(car) for car in group["cars"]]
            grouped_data.append(group)
        return grouped_data

    async def get_makes_and_models(self) -> dict[str, list[str]]:
        pipeline = [
            {
                "$group": {
                    "_id": "$make",
                    "models": {"$addToSet": "$model"}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "make": "$_id",
                    "models": 1
                }
            }
        ]

        aggregation_result = await self.db.car_collection.aggregate(pipeline).to_list(length=None)

        result = {item['make']: item['models'] for item in aggregation_result}
        return result

    async def update_short_car_info(self, old_car_ads: list[CarAdvShortInfo], db: DataBase):
        operations = []
        for car_ad in old_car_ads:
            filter_query = {"ad_number": car_ad.ad_number}
            update_query = {
                "$set": {
                    "ad_link": car_ad.ad_link,
                    "updatedAt": datetime.datetime.now(datetime.timezone.utc)
                }
            }
            operations.append(UpdateOne(filter_query, update_query, upsert=False))

        if operations:
            result = await self.db.car_collection.bulk_write(operations)
            db_logger.debug('Updated %s records', len(operations))
            return result.bulk_api_result

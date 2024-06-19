from typing import Optional, AsyncGenerator

from bson import ObjectId
from pydantic import BaseModel, Field

from mongo.database import DataBase


class Car(BaseModel):
    id: Optional[str]
    link: Optional[str]
    img_src: Optional[str]
    condition: str
    make: str
    model: str
    year: int
    mileage: int
    body_type: str
    fuel_type: str
    engine_capacity: int
    engine_power: int
    fixed_price: str
    price: int
    exchange: str
    ad_number: int | str
    emission_class: str
    drive: str
    transmission: str
    doors: str
    seats: str
    steering_side: str
    climate_control: str
    color: str
    interior_material: str | None
    interior_color: str | None
    registered_until: str
    origin: str
    damage: str
    import_country: Optional[str] = None
    options: Optional[list[str]] = Field(default_factory=list)
    details: Optional[list[str]] = None

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

    @staticmethod
    def car_from_mongo(document: dict) -> Car:
        document["id"] = str(document.pop("_id"))
        document['options'] = [option for option in document.get('options', []) if option is not None]
        try:
            return Car(**document)
        except Exception as e:
            print(e)

    async def get_car(self, link: str) -> dict:
        return await self.db.car_collection.find_one({'link': link})

    async def get_cars(self, filters: dict) -> AsyncGenerator[dict, None]:
        async for car_doc in self.db.car_collection.find(filters):
            yield car_doc

    async def delete_car(self, link: str):
        await self.db.car_collection.delete_one({'link': link})

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

import re
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse, parse_qs

from bson import ObjectId
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

from main import update_page_number, scrape_cars, scrape_all_pages
from mongo.specifications import DecimalRangeParameter, SubSetParameter, OneOfParameter, SimpleParameter, MakeParameter
from scraping.translation import safety_features_translation, additional_options_translation, condition_translation, \
    body_type_codes, fuel_type_codes, gearbox_codes, wheel_side_codes

app = FastAPI()

origins = [
    "http://localhost:63342",  # Добавьте другие разрешенные источники при необходимости
    "http://0.0.0.0:8000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MONGO_DETAILS = "mongodb://localhost:27017"
client = AsyncIOMotorClient(MONGO_DETAILS)
database = client.car_database
car_collection = database.get_collection("cars")


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
    ad_number: str
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
    options: Optional[List[str]] = Field(default_factory=list)
    details: Optional[List[str]] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
        }


def car_from_mongo(document: Dict[str, Any]) -> Car:
    document["id"] = str(document.pop("_id"))
    document['options'] = [option for option in document.get('options', []) if option is not None]
    try:
        return Car(**document)
    except Exception as e:
        print(e)


# Helper function to retrieve cars from the database
async def retrieve_cars(filters: Dict[str, Any]):
    cars = []
    async for car in car_collection.find(filters):
        cars.append(car_from_mongo(car))
    return cars


async def group_cars(group_by: List[str], min_count: int = 1, data_filter: dict = None):
    # Validate group_by fields
    valid_fields = {"make", "model", "year"}
    if not all(field in valid_fields for field in group_by):
        raise HTTPException(status_code=400, detail=f"Invalid group_by fields. Valid fields are: {valid_fields}")

    # Build the _id object for grouping
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
    async for group in car_collection.aggregate(pipeline):
        group["cars"] = [car_from_mongo(car) for car in group["cars"]]
        grouped_data.append(group)
    return grouped_data


@app.get("/cars/grouped", response_model=List[Dict[str, Any]])
async def get_grouped_cars(
        group_by: List[str] = Query(..., description="Fields to group by: make, model, year"),
        min_count: Optional[int] = Query(1),
        search_url: Optional[str] = Query(description="Search bar field from polovni automobili")
):
    parsed_url = urlparse(search_url)
    query = _get_mongo_query_from_url(parsed_url)
    grouped_data = await group_cars(group_by, min_count, data_filter=query)
    return grouped_data


@app.get("/cars", response_model=List[Car])
async def get_cars(
        make: str | None = Query(None),
        model: Optional[str] = Query(None),
        year: Optional[int] = Query(None)
):
    filters = {}
    if make:
        filters["make"] = make
    if model:
        filters["model"] = model
    if year:
        filters["year"] = year

    cars = await retrieve_cars(filters)
    return cars


class ScrapeBody(BaseModel):
    search_url: str
    start_page: int = 1
    max_pages: int = 1


def _to_snake_case(param: str) -> str:
    if '_' not in param:
        return re.sub(r'(?<!^)(?=[A-Z])', '_', param).lower()
    return param


@app.post("/ads", response_model=str)
async def scrape_ads_from_url(body: ScrapeBody):
    total_cars = await scrape_all_pages(body.search_url)
    return f"cars saved: {total_cars}"


@app.post("/test_ads", response_model=str)
async def scrape_ads_from_url(body: ScrapeBody):
    total_cars = 0
    for i in range(body.start_page, body.max_pages + 1):
        updated_url = update_page_number(body.search_url, i)
        total_cars += scrape_cars(updated_url)
    return f"cars saved: {total_cars}"


def _get_mongo_query_from_url(parsed_url):
    if not parsed_url.query:
        return None
    query_params = dict((k, v if len(v) > 1 or k.endswith('[]') else v[0])
                        for k, v in parse_qs(parsed_url.query).items())
    query_params = {_to_snake_case(param): value for param, value in query_params.items()}

    price = DecimalRangeParameter('price', query_params.get('price_from'), query_params.get('price_to'))
    year = DecimalRangeParameter('year', query_params.get('year_from'), query_params.get('year_to'))

    power_kw = DecimalRangeParameter('power', query_params.get('power_from'), query_params.get('power_to'))

    engine_capacity = DecimalRangeParameter('engine_capacity', query_params.get('engine_volume_from'),
                                            query_params.get('engine_volume_to'))
    mileage = DecimalRangeParameter('mileage', query_params.get('mileage_from'), query_params.get('mileage_to'))

    safety = [param for param in query_params if
              param in safety_features_translation.values()]
    safety = SubSetParameter('safety', safety)

    options = [param for param in query_params if
               param in additional_options_translation.values()]
    options = SubSetParameter('options', options)

    condition = [param for param in query_params if
                 param in condition_translation.values()]
    condition = SubSetParameter('details', condition)

    body_types = [body_type_codes.get(int(chassis)) for chassis in query_params.get('chassis[]', [])]
    body_types = OneOfParameter("body_type", body_types)

    fuel_type = [fuel_type_codes.get(int(fuel)) for fuel in query_params.get('fuel[]', [])]
    fuel_type = OneOfParameter("fuel_type", fuel_type)

    gearbox = [gearbox_codes.get(int(gearbox)) for gearbox in query_params.get('gearbox[]', [])]
    gearbox = OneOfParameter("transmission", gearbox)

    wheel_side = (wheel_side_codes.get(int(query_params.get('wheel_side')[0]))
                  if query_params.get('wheel_side') else None)
    wheel_side = SimpleParameter('wheel_side', wheel_side)
    car_1_make, car_1_model = query_params.get('brand'), query_params.get('model[]')
    car_2_make, car_2_model = query_params.get('brand2'), query_params.get('model2[]')
    make = MakeParameter({car_1_make: car_1_model, car_2_make: car_2_model})

    # todo: implement additional parameters for condition, ac type, door count
    model_filter = {price, year, power_kw, engine_capacity, mileage, safety, options, condition, body_types, fuel_type,
                    gearbox, wheel_side, make}
    query = {}
    for spec in model_filter:
        try:
            spec_query = spec.to_query()
        except ValueError:
            continue
        for key, value in spec_query.items():
            if key in query:
                if isinstance(query[key], dict) and isinstance(value, dict):
                    query[key].update(value)
                elif isinstance(query[key], list) and isinstance(value, list):
                    query[key].extend(value)
            else:
                query[key] = value
    return query


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

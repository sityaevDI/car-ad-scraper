from typing import List, Optional, Dict, Any

from bson import ObjectId
from fastapi import FastAPI, Query, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

from main import update_page_number, scrape_cars

app = FastAPI()

MONGO_DETAILS = "mongodb://localhost:27017"
client = AsyncIOMotorClient(MONGO_DETAILS)
database = client.car_database
car_collection = database.get_collection("cars")


class Car(BaseModel):
    id: Optional[str]
    link: str
    img_src: Optional[str]
    condition: str
    make: str
    model: str
    year: int
    mileage: int
    body_type: str
    fuel_type: str
    engine_capacity: int
    engine_power: str
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
    return Car(**document)


# Helper function to retrieve cars from the database
async def retrieve_cars(filters: Dict[str, Any]):
    cars = []
    async for car in car_collection.find(filters):
        cars.append(car_from_mongo(car))
    return cars


async def group_cars(group_by: List[str], min_count: int = 1):
    # Validate group_by fields
    valid_fields = {"make", "model", "year"}
    if not all(field in valid_fields for field in group_by):
        raise HTTPException(status_code=400, detail=f"Invalid group_by fields. Valid fields are: {valid_fields}")

    # Build the _id object for grouping
    group_id = {field: f"${field}" for field in group_by}

    pipeline = [
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
    ]
    grouped_data = []
    async for group in car_collection.aggregate(pipeline):
        group["cars"] = [car_from_mongo(car) for car in group["cars"]]
        grouped_data.append(group)
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


@app.get("/cars/grouped", response_model=List[Dict[str, Any]])
async def get_grouped_cars(
        group_by: List[str] = Query(..., description="Fields to group by: make, model, year"),
        min_count: Optional[int] = Query(1)
):
    grouped_data = await group_cars(group_by, min_count)
    return grouped_data


class ScrapeBody(BaseModel):
    search_url: str
    start_page: int = 1
    max_pages: int


@app.post("/ads", response_model=str)
async def scrape_ads_from_url(body: ScrapeBody):
    total_cars = 0
    for i in range(body.start_page, body.max_pages):
        updated_url = update_page_number(body.search_url, i)
        total_cars += scrape_cars(updated_url.format(page=i))
    return f"cars saved: {total_cars}"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

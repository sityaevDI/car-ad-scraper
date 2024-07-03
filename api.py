import asyncio
import json
import re
from typing import List, Optional, Dict, Any, Iterable
from urllib.parse import urlparse, parse_qs

from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from main import scrape_all_pages
from mongo.car_repo import CarRepository
from mongo.database import get_database, DataBase
from mongo.specifications import DecimalRangeParameter, SubSetParameter, OneOfParameter, SimpleParameter, MakeParameter, \
    Specification
from scraping.translation import safety_features_translation, additional_options_translation, condition_translation, \
    body_type_codes, fuel_type_codes, gearbox_codes, wheel_side_codes, ac_type_codes, condition_codes, \
    emission_class_codes, interior_material_codes

app = FastAPI()

origins = [
    "http://localhost:63342",
    "http://0.0.0.0:8000",
    "http://localhost:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def group_cars(group_by: List[str], db: DataBase, min_count: int = 1, data_filter: dict = None, ):
    # Validate group_by fields
    valid_fields = {"make", "model", "year"}
    if not all(field in valid_fields for field in group_by):
        raise HTTPException(status_code=400, detail=f"Invalid group_by fields. Valid fields are: {valid_fields}")

    # Build the _id object for grouping
    car_repo = CarRepository(db)
    results = await car_repo.get_grouped_data(group_by, data_filter, min_count)
    return results


@app.get('/cars/makes', response_model=dict[str, list[str]])
async def get_car_makes(db: DataBase = Depends(get_database)):
    repo = CarRepository(db)
    data = await repo.get_makes_and_models()
    return data


@app.get("/cars/grouped", response_model=List[Dict[str, Any]], )
async def get_grouped_cars(
        group_by: List[str] = Query(..., description="Fields to group by: make, model, year"),
        min_count: Optional[int] = Query(1),
        search_url: Optional[str] = Query(None, description="Search bar field from polovni automobili"),
        makes_to_include: Any = '{}',
        makes_to_exclude: Any = '{}',
        db: DataBase = Depends(get_database)):
    parsed_url = urlparse(search_url)
    if parsed_url.query:
        query_params = dict((k, v if len(v) > 1 or k.endswith('[]') else v[0])
                            for k, v in parse_qs(parsed_url.query).items())
    else:
        query_params = {}
    query_params.update(
        {'makes_to_include': json.loads(makes_to_include),
         'makes_to_exclude': json.loads(makes_to_exclude)})
    specifications = _uri_params_to_specs(query_params)
    query = _mongo_query_from_specs(specifications)
    grouped_data = await group_cars(db=db, group_by=group_by, min_count=min_count, data_filter=query)
    return grouped_data


class ScrapeBody(BaseModel):
    search_url: str
    start_page: int = 1
    max_pages: int = 1


def _to_snake_case(param: str) -> str:
    if '_' not in param:
        return re.sub(r'(?<!^)(?=[A-Z])', '_', param).lower()
    return param


@app.post("/ads", response_model=str, )
async def scrape_ads_from_url(
        body: ScrapeBody,
        db: DataBase = Depends(get_database)):
    task = await asyncio.create_task(scrape_all_pages(body.search_url, db))
    if task.exception():
        print(task.exception())
    # todo: feature request - create task id with possibility to track scrape completion
    return "Scrape search started with id {}"


def _uri_params_to_specs(query_params: dict) -> set[Specification] | None:
    query_params = {_to_snake_case(param): value for param, value in query_params.items()}

    price = DecimalRangeParameter('price', query_params.get('price_from'), query_params.get('price_to'))
    year = DecimalRangeParameter('year', query_params.get('year_from'), query_params.get('year_to'))

    power_kw = DecimalRangeParameter('engine_power', query_params.get('power_from'), query_params.get('power_to'))

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

    wheel_side = (wheel_side_codes.get(int(query_params.get('wheel_side')))
                  if query_params.get('wheel_side') else None)
    wheel_side = SimpleParameter('steering_side', wheel_side)
    car_1_make, car_1_models = query_params.get('brand'), query_params.get('model[]')
    car_2_make, car_2_models = query_params.get('brand2'), query_params.get('model2[]')
    query_params.get('makes_to_include').update({car_1_make: car_1_models, car_2_make: car_2_models})
    make = MakeParameter(query_params.get('makes_to_include'), query_params.get('makes_to_exclude'))

    ac_type = [ac_type_codes.get(int(ac_code)) for ac_code in query_params.get('air_condition[]', [])]
    ac_type = OneOfParameter('climate_control', ac_type)

    damage = [condition_codes.get(int(condition_code)) for condition_code in query_params.get('damaged[]', [])]
    damage = OneOfParameter('damage', damage)

    emission_class = (emission_class_codes.get(int(query_params.get('emission_class')))
                      if query_params.get('emission_class') else None)
    emission_class = SimpleParameter('emission_class', emission_class)

    interior_material = [interior_material_codes.get(int(int_m_code)) for int_m_code in
                         query_params.get('interior_material[]', [])]
    interior_material = OneOfParameter('interior_material', interior_material)
    # todo: implement additional parameters for door count
    model_filter = {price, year, power_kw, engine_capacity, mileage, safety, options, condition, body_types, fuel_type,
                    gearbox, wheel_side, make, ac_type, damage, emission_class, interior_material}
    return model_filter


def _mongo_query_from_specs(specifications: Iterable[Specification]):
    query = {}
    for spec in specifications:
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

import os

from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URL = os.getenv("MONGODB_URL", "")  # deploying without docker-compose

if not MONGODB_URL:
    MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
    MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
    MONGO_USER = os.getenv("MONGO_USER", )
    MONGO_PASS = os.getenv("MONGO_PASSWORD", )
    MONGO_DB = os.getenv("MONGO_DB", "car_database")

    if MONGO_PASS:
        MONGODB_URL = f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}"
    else:
        MONGODB_URL = f"mongodb://{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}"


class DataBase:
    def __init__(self, mongodb_url: str):
        self.car_collection = None
        self.database = None
        self.client: AsyncIOMotorClient = None
        self.mongodb_url = mongodb_url

    async def connect(self):
        self.client = AsyncIOMotorClient(self.mongodb_url)
        self.database = self.client.car_database
        self.car_collection = self.database.get_collection("cars")
        await self.car_collection.create_index('createdAt', expireAfterSeconds=3 * 24 * 60 * 60)

    async def disconnect(self):
        self.client.close()


db = DataBase(MONGODB_URL)


async def get_database() -> DataBase:
    if db.client is None:
        await db.connect()
    return db

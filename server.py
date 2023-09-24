import json
from sqlalchemy.exc import IntegrityError
from models import Session, Advertising, engine, Base
from aiohttp import web


app = web.Application()

async def context_orm(app: web.Application):
    print("START")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    print("STOP")


@web.middleware
async def session_middleware(request: web.Request, handler):
    async with Session() as session:
        request["session"] = session
        response = await handler(request)
        return response


app.cleanup_ctx.append(context_orm)
app.middlewares.append(session_middleware)

def get_http_error(error_class, description: str):
    return error_class(
        text=json.dumps({"status": "error", "description": description}),
        content_type="application/json",
    )



async def get_ad(session, id):
    ad = await session.get(Advertising, id)
    if ad is None:
        raise get_http_error(404, "Advertising not found")
    return ad

async def add_ads(ad, session):
    try:
        session.add(ad)
        await session.commit()
    except IntegrityError as er:
        raise get_http_error(web.HTTPConflict, "User already exists")
    return ad

class AdvertisingView(web.View):
    @property
    def session(self):
        return self.request["session"]

    @property
    def id(self):
        return int(self.request.match_info["id"])

    async def get(self):
        ad = await get_ad(self.session, self.id)
        return web.json_response(
                    {
                        "id": ad.id,
                        "header": ad.header,
                        "description": ad.description,
                        "creation_time": ad.creation_time.isoformat(),
                        'owner': ad.owner
                    }
                )

    async def post(self):

        validated_json = await self.request.json()
        ad = Advertising(**validated_json)
        ad = await add_ads(ad, self.session)
        return web.json_response({'id': ad.id},)



    async def delete(self):
        ad = await get_ad(self.session, self.id)
        await self.session.delete(ad)
        await self.session.commit()
        return web.json_response({"status": "success"},)


app.add_routes(
    [
        web.post("/ad", AdvertisingView),
        web.get("/ad/{id:\d+}", AdvertisingView),
        web.delete("/ad/{id:\d+}", AdvertisingView),
    ]
)
if __name__ == "__main__":
    web.run_app(app)

import asyncio
from http import HTTPStatus

from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core.integration import aiohttp_error_middleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.ms_teams.bot import MSTeamsBot
from src.auth.manager import AuthManager
from src.auth.middleware import AuthMiddleware
from src.sync.sync_manager import SynchronizerManager
from src.config.settings import Settings, get_settings

SETTINGS: Settings = get_settings()

# Create Synchronizer and Scheduler
SYNC: SynchronizerManager = SynchronizerManager()

async def run_daily_sync(synchronizer_manager: SynchronizerManager = SYNC) -> None:
    await asyncio.to_thread(synchronizer_manager.run_synchronization)

# Create Authentication Middleware
AUTH_MANAGER: AuthManager = AuthManager(SETTINGS.users_path)
AUTH_MIDDLEWARE: AuthMiddleware = AuthMiddleware(AUTH_MANAGER)

# Create the Bot
BOT: MSTeamsBot = MSTeamsBot(AUTH_MANAGER, AUTH_MIDDLEWARE)

# Simple endpoint for testing
async def welcome(req: Request) -> Response:
    return Response(text="MaIA - Concept")

# Listen for incoming requests on /api/messages.
async def messages(req: Request) -> Response:
    if "application/json" in req.headers["Content-Type"]:
        body = await req.json()
    else:
        return Response(status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)

    auth_header = req.headers["Authorization"] if "Authorization" in req.headers else ""

    response = await BOT.process_activity(body, auth_header)
    if response:
        return json_response(data=response.body, status=response.status)
    
    return Response(status=HTTPStatus.OK)

# Create App
APP = web.Application(middlewares=[aiohttp_error_middleware])

# Add the start function to the application's startup
async def start_background_tasks(app):
    app['scheduler'] = AsyncIOScheduler()
    app['scheduler'].add_job(run_daily_sync, 'cron', hour=SETTINGS.sync_hour, minute=SETTINGS.sync_min)
    app['scheduler'].start()

APP.on_startup.append(start_background_tasks)

# Add a function to stop the scheduler when the app closes
async def cleanup_background_tasks(app):
    app['scheduler'].shutdown()

APP.on_cleanup.append(cleanup_background_tasks)

# Add routes
APP.router.add_get("/", welcome)
APP.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    try:
        web.run_app(APP, host=SETTINGS.host, port=SETTINGS.port)
    except Exception as error:
        raise error
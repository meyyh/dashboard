from quart import Quart, send_from_directory
import os
import json
import asyncio
import uvicorn
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.oauth import validate_token
from twitchAPI.oauth import refresh_access_token
from twitchAPI.type import AuthScope

TOKEN_FILE = "tokens.json"
live_users_cache = ["ff"]
twitch = None

# Function to save tokens to file
async def save_tokens(access_token, refresh_token):
    with open(TOKEN_FILE, "w") as file:
        json.dump({"access_token": access_token, "refresh_token": refresh_token}, file)

# Function to load tokens from file
async def load_tokens():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as file:
            return json.load(file)
    return None

app = Quart(__name__)
app.config['STATIC_FOLDER'] = 'static'

async def init_twitch():
    app_id = os.getenv('TWITCH_APP_ID')
    app_secret = os.getenv('TWITCH_APP_SECRET')

    if not app_id or not app_secret:
        print("Can't get app_id or app_secret")
        exit()

    global twitch
    twitch = await Twitch(app_id, app_secret)
    target_scope = [AuthScope.USER_READ_FOLLOWS]

    tokens = await load_tokens()

    if tokens:
        validate = await validate_token(tokens['access_token'])

        if "status" in validate and validate["status"] == 401:
            print("tokens were invalid\n")

            newAccess, newRefresh = await refresh_access_token(
                tokens['refresh_token'], app_id, app_secret
            )

            await save_tokens(newAccess, newRefresh)
            tokens = await load_tokens()

            await twitch.set_user_authentication(
                tokens['access_token'], target_scope, tokens['refresh_token']
            )
        else:
            await twitch.set_user_authentication(
                tokens['access_token'], target_scope, tokens['refresh_token']
            )
    else:
        # Authenticate and save new tokens
        auth = UserAuthenticator(twitch, target_scope, force_verify=False)
        token, refresh_token = await auth.authenticate()
        await twitch.set_user_authentication(token, target_scope, refresh_token)
        await save_tokens(token, refresh_token)

# Fetch live users from Twitch
async def fetch_live_users():
    user_info = [i async for i in twitch.get_users()][0].to_dict()

    live_users = []
    async for stream in twitch.get_followed_streams(user_info['id'], None, 100):
        stream_dict = stream.to_dict()
        async for user in twitch.get_users(stream_dict["user_id"]):
            user_data = user.to_dict()
            live_users.append({
                "display_name": user_data["display_name"],
                "profile_image_url": user_data["profile_image_url"],
                "game_name": stream_dict["game_name"],
                "title": stream_dict["title"],
                "viewer_count": stream_dict["viewer_count"]
            })
    return live_users

# Function to update live users every 5 minutes
async def update_live_users():
    global live_users_cache
    print("Starting live user update task.")  # Add a start print for debugging
    while True:
        try:
            live_users_cache = await fetch_live_users()
            
            print("Live users updated.")
        except Exception as e:
            print(f"Error fetching live users: {e}")
        await asyncio.sleep(240)  # Update every 4 minutes

# Run tasks on app startup
@app.before_serving
async def on_startup():
    # Run init_twitch() to initialize Twitch API
    await init_twitch()
    # Run update_live_users every 5 minutes in the background
    asyncio.create_task(update_live_users())

@app.route('/')
async def home():
    return await send_from_directory(app.config['STATIC_FOLDER'], 'index.html')

# New route to access live users data
@app.route('/api/live-users')
async def live_users():
    return json.dumps(live_users_cache)

if __name__ == '__main__':
    # Run the app with Uvicorn to handle async operations
    uvicorn.run(app, host="0.0.0.0", port=5000)



# idea for getting system info

# import psutil

# cpu_perc = psutil.cpu_percent(interval=1)
# # gives an object with many fields
# psutil.virtual_memory()

# # you can convert that object to a dictionary
# dict(psutil.virtual_memory()._asdict())

# # you can have the percentage of used RAM
# ram_perc = psutil.virtual_memory().percent

# # you can calculate percentage of available memory
# psutil.virtual_memory().available * 100 / psutil.virtual_memory().total


# print(cpu_perc)
# print(ram_perc)
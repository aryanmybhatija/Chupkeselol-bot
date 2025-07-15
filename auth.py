import json
import os
import logging
from dotenv import load_dotenv

load_dotenv()
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", ""))

# Setup logging for auth module
file_handler = logging.FileHandler('auth.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logger = logging.getLogger("terabox_bot")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)

# ফাইল পাথ
AUTHORIZED_USERS_FILE = os.path.abspath("authorized_users.json")
logger.info(f"Authorized users file path: {AUTHORIZED_USERS_FILE}")

# ইউজার লোড
if os.path.exists(AUTHORIZED_USERS_FILE):
    try:
        with open(AUTHORIZED_USERS_FILE, "r") as f:
            AUTHORIZED_USERS = json.load(f)
        logger.info(f"Loaded authorized users: {AUTHORIZED_USERS}")
    except Exception as e:
        AUTHORIZED_USERS = []
        logger.warning(f"Failed to load users: {str(e)}. Initializing empty list.")
else:
    AUTHORIZED_USERS = []
    logger.info("No user file found, initializing empty list")

"""
def add_authorized_user(user_id: int) -> bool:
    if user_id in AUTHORIZED_USERS:
        logger.info(f"User {user_id} already authorized")
        return False
    AUTHORIZED_USERS.append(user_id)
    return save_users()
"""
def add_authorized_user(user_id: int) -> bool:
    user_id = int(user_id)  # Ensure it's stored as integer
    if user_id in AUTHORIZED_USERS:
        logger.info(f"User {user_id} already authorized")
        return False
    AUTHORIZED_USERS.append(user_id)
    return save_users()

def remove_authorized_user(user_id: int) -> bool:
    if user_id not in AUTHORIZED_USERS:
        logger.info(f"User {user_id} not found in list")
        return False
    AUTHORIZED_USERS.remove(user_id)
    return save_users()

def save_users() -> bool:
    try:
        with open(AUTHORIZED_USERS_FILE, "w") as f:
            json.dump(AUTHORIZED_USERS, f)
        logger.info("✅ User list saved successfully")
        logger.info(f"✅ Saved to path: {AUTHORIZED_USERS_FILE}")  # ⬅️ এই লাইনটি যোগ করো
        return True
    except Exception as e:
        logger.error(f"❌ Error saving user list: {str(e)}")
        return False

def is_authorized(user_id: int) -> bool:
    return user_id == BOT_OWNER_ID or user_id in AUTHORIZED_USERS

def get_authorized_users() -> list:
    logger.info(f"Returning authorized users: {AUTHORIZED_USERS}")
    return AUTHORIZED_USERS

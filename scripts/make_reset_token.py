import asyncio, hashlib, os, secrets, sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient
EMAIL = "delivered+sihha-reset@resend.dev"


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    user = await db.users.find_one({"email": EMAIL}, {"_id": 0, "user_id": 1})
    raw = secrets.token_urlsafe(32)
    await db.password_reset_tokens.insert_one({
        "token_hash": hashlib.sha256(raw.encode()).hexdigest(), "user_id": user["user_id"], "email": EMAIL,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=60), "used_at": None,
        "created_at": datetime.now(timezone.utc).isoformat()})
    print(raw)

asyncio.run(main())

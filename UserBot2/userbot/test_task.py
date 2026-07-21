import redis
import json
import uuid

# Connect to Redis
# Since running from host (Windows), use localhost
# Ensure 6379 is exposed in docker-compose (it is)
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

task = {
  "task_id": str(uuid.uuid4()),
  "action": "send_message",
  "target_chat_id": "me", # Special Telegram 'me' (Saved Messages)
  "message": "👋 Hello! This is a test message from your Redis-powered Userbot worker.",
  "delay_range": [1, 2] 
}

print(f"🚀 Pushing task {task['task_id']} to userbot:queue...")
r.lpush("userbot:queue", json.dumps(task))
print("✅ Task pushed! Check your Telegram 'Saved Messages'.")
print("   Also check docker logs: docker logs -f userbot-userbot-1")

import redis
import json
import uuid
import time

# Connect to Redis
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

def push_task(action, data):
    task = {
        "task_id": str(uuid.uuid4()),
        "action": action,
        **data
    }
    print(f"🚀 Pushing action '{action}'...")
    r.lpush("userbot:queue", json.dumps(task))
    print(f"✅ Task pushed! ID: {task['task_id']}")

def test_send_message():
    """Test 1: Send a simple message to Saved Messages"""
    print("\n--- Test 1: Send Message ---")
    data = {
        "target_chat_id": "me", 
        "message": "Hello! This is a simple send test.",
        "delay_range": [1, 2]
    }
    push_task("send_message", data)

def test_forward_message():
    """Test 2: Forward a message (requires a real message ID)"""
    print("\n--- Test 2: Forward Message ---")
    # You need a valid message ID from a chat. 
    # For demo, we'll try to forward the last message from 'me' to 'me' 
    # BUT since we don't know the ID, this might fail or need a real ID.
    # We'll use a dummy ID 12345, likely to fail if not exists, but shows flow.
    print("NOTE: You need to replace 'message_id' with a real one for this to work perfectly.")
    data = {
        "source_chat_id": "me",
        "target_chat_id": "me",
        "message_id": 12345, 
        "delay_range": [1, 2]
    }
    push_task("forward_message", data)

def test_safe_gcast():
    """Test 3: Safe Broadcast (Gcast)"""
    print("\n--- Test 3: Safe Gcast ---")
    # Gcast attempts to send to a list of users.
    # Safety guards will BLOCK if they are not in your contacts.
    # Use your own ID or a friend in your contacts.
    my_user_id = 123456789 # REPLACE THIS with your numeric user ID
    
    print(f"NOTE: Sending Gcast to ID {my_user_id}. Ensure this is valid/safe.")
    
    data = {
        "message": "📢 This is a Safe Broadcast test.",
        "recipients": [
            {"type": "user", "id": my_user_id} # sending to self is also safe/allowed by guard
        ],
        "limits": {"per_hour": 5},
        "delay_range": [5, 10] # Longer delay for gcast
    }
    push_task("safe_gcast", data)

def test_monitor():
    print("\n--- Test 4: Monitor ---")
    print("To test monitoring:")
    print("1. Send a message to any chat the bot is currently in (e.g. Saved Messages).")
    print("2. Check the logs: docker logs -f userbot-userbot-1")
    print("3. You should see 'Monitored message pushed to Redis'.")
    print("4. Check Redis list 'userbot:monitor_events' to see the captured data.")

if __name__ == "__main__":
    print("Select a feature to test:")
    print("1. Send Message")
    print("2. Forward Message")
    print("3. Safe Gcast")
    print("4. Explain Monitor")
    
    choice = input("Enter number (1-4): ")
    
    if choice == '1':
        test_send_message()
    elif choice == '2':
        test_forward_message()
    elif choice == '3':
        test_safe_gcast()
    elif choice == '4':
        test_monitor()
    else:
        print("Invalid choice.")

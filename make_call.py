import os
import certifi

# Fix for macOS SSL Certificate errors - MUST be before other imports
os.environ['SSL_CERT_FILE'] = certifi.where()

import argparse
import asyncio
import random
import json
import logging
from dotenv import load_dotenv
# 1️⃣ Imported ExcelService below dotenv
from excel_service import ExcelService
from livekit import api

# Load environment variables
load_dotenv(".env")

async def main():
    parser = argparse.ArgumentParser(description="Make an outbound call via LiveKit Agent.")
    parser.add_argument("--to", required=True, help="The phone number to call (e.g., +91...)")
    args = parser.parse_args()

    # 1. Validation
    phone_number = args.to.strip()
    if not phone_number.startswith("+"):
        print("Error: Phone number must start with '+' and country code.")
        return

    if len(phone_number) < 8:
        print(f"Error: Phone number '{phone_number}' looks too short.")
        return

    # 2️⃣ Excel data validation for customer existence
    customer = ExcelService.find_customer(phone_number)
    if customer is None:
        print(f"\n❌ Customer not found in customers.xlsx : {phone_number}")
        return

    url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not (url and api_key and api_secret):
        print("Error: LiveKit credentials missing in .env.local")
        return

    # 2. Setup API Client
    lk_api = api.LiveKitAPI(url=url, api_key=api_key, api_secret=api_secret)

    # 🌟 CRITICAL FIX: call_id pehle generate hoga taaki customer_data me add ho sake
    call_id = random.randint(100000, 999999)
    room_name = f"sfl-call-{call_id}"

    # 3️⃣ Replaced hardcoded customer_data dict with the Excel data dynamic copy
    customer_data = customer.copy()
    customer_data["call_id"] = call_id  # Ab call_id crash nahi karega!
    customer_data["voice_id"] = "anushka"
    customer_data["model_provider"] = "groq"

    # 4️⃣ Branded Prints updated to use customer.get() safely
    print("=" * 60)
    print("SUNITA FINLEASE AI CALL")
    print("=" * 60)
    print(f"Call ID       : {call_id}")
    print(f"Customer      : {customer.get('customer_name')}")
    print(f"Phone         : {phone_number}")
    print(f"Loan Type     : {customer.get('loan_type')}")
    print(f"Campaign      : {customer.get('campaign')}")
    print(f"Room          : {room_name}")
    print("=" * 60)

    print(f"Initiating call to {phone_number}...")

    try:
        # 4. Dispatch the Agent with the dynamic customer data payload
        dispatch_request = api.CreateAgentDispatchRequest(
            agent_name="outbound-caller", # Must match agent.py
            room=room_name,
            metadata=json.dumps(customer_data)
        )
        
        dispatch = await lk_api.agent_dispatch.create_dispatch(dispatch_request)

        print("\n✅ Call Dispatched Successfully!")
        print(f"Dispatch ID: {dispatch.id}")
        print("-" * 60)
        print("The agent is now joining the room and will dial the number.")
        print("Check your agent terminal for logs.")
        
    except Exception as e:
        print(f"\n❌ Error dispatching call: {e}")
    
    finally:
        await lk_api.aclose()

if __name__ == "__main__":
    asyncio.run(main())

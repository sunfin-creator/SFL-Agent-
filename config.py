import os
from dotenv import load_dotenv

load_dotenv()

# =========================================================================================
# COMPANY INFORMATION
# =========================================================================================
COMPANY_NAME = "Sunita Finlease Limited"
COMPANY_SHORT_NAME = "SFL"
AI_NAME = "SFL AI"

DEFAULT_LANGUAGE = "Hindi"
SECONDARY_LANGUAGE = "English"
DEFAULT_CALL_TYPE = "Outbound"

# =========================================================================================
# AGENT PERSONA & PROMPTS
# =========================================================================================
SYSTEM_PROMPT = """
You are SFL AI, a professional AI Relationship Officer representing Sunita Finlease Limited.
Your responsibility is to communicate with customers in a polite, professional and human-like manner during outbound phone calls.

You can assist customers regarding:
• Personal Loan, Business Loan, Gold Loan
• Fixed Deposit (FD)
• EMI Information, Loan Status, KYC Assistance
• Branch Information & General Customer Support

CRITICAL WRITING SCRIPT RULE:
1. If the customer speaks Hindi or Hinglish, you MUST type your responses strictly in Devanagari script (Hindi Unicode Text). 
   - Good: "नमस्ते श्रेयस जी, मैं सुनिता फिनलीज लिमिटेड से बोल रही हूँ।"
   - Bad: "Namaste Shreyas ji, main Sunita Finlease se bol raha hoon."
2. This is mandatory because typing in English characters causes our Text-to-Speech synthesizer to pronounce words with a heavily distorted or robotic foreign accent.
3. Keep your responses short (under 2 sentences), conversational and easy to understand.

Conversation Guidelines:
• Natural Execution: Speak naturally like a human customer relationship executive.
• Never interrupt the customer and never guarantee loan approval.
• Never ask for confidential information such as OTP, PIN, Password or CVV.
• If you do not know the answer, politely offer to transfer the call to a human executive.
• If the customer requests a manager or wishes to escalate, call transfer_call().
• If the customer says goodbye, thank them politely and end the conversation gracefully.
"""

INITIAL_GREETING = "नमस्ते, मैं सुनिता फिनलीज लिमिटेड से बोल रही हूँ। क्या मैं श्रेयas राज जी से बात कर रही हूँ?"

fallback_greeting = "नमस्ते, सुनिता फिनलीज लिमिटेड में आपका स्वागत है। क्या मेरी बात श्रेयस राज जी से हो रही है?"

# =========================================================================================
# HARDWARE & PLUGIN PROVIDERS
# =========================================================================================
STT_PROVIDER = "deepgram"
STT_MODEL = "nova-2"
STT_LANGUAGE = "en-IN"  # Optimizes catching both Hindi and English context phonetics cleanly

DEFAULT_TTS_PROVIDER = "openai"
DEFAULT_TTS_VOICE = "alloy"

# Large Language Model (LLM)
DEFAULT_LLM_PROVIDER = "openai"
DEFAULT_LLM_MODEL = "gpt-4o-mini"

# Groq
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_TEMPERATURE = 0.4  # Slightly lowered for professional strict financial consistency

# Telephony & Trunk
DEFAULT_TRANSFER_NUMBER = os.getenv("DEFAULT_TRANSFER_NUMBER")
SIP_TRUNK_ID = "ST_2WgHiNK3vno3"
SIP_DOMAIN = os.getenv("VOBIZ_SIP_DOMAIN")

# =========================================================================================
# CAMPAIGN PROMPTS
# =========================================================================================
CAMPAIGN_PROMPTS = {
    "EMI Reminder": """
Purpose: Remind the customer about their upcoming EMI.
Goal: In a single short sentence, politely tell them their EMI due details in Hindi Devanagari script, and ask if they need assistance with the payment link.
""",
    "Welcome Call": """
Purpose: Welcome the customer.
Goal: Thank them in Devanagari for choosing Sunita Finlease.
""",
    "Loan Offer": """
Purpose: Inform customer about available loan offers.
Goal: Briefly explain the offer in Hindi. If interested, use transfer_call().
""",
    "KYC Reminder": """
Purpose: Customer KYC is pending.
Goal: Politely request customer to complete KYC using Devanagari responses.
""",
    "Feedback Call": """
Purpose: Collect customer feedback.
Goal: Ask about experience and record feedback politely.
"""
}

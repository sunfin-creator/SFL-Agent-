import os
import certifi
import asyncio  

# Fix for macOS SSL Certificate errors - MUST be before other imports
os.environ['SSL_CERT_FILE'] = certifi.where()

import logging
import json
from dotenv import load_dotenv
import time
from dataclasses import dataclass, field

from livekit import agents, api  # type: ignore
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.agents import llm
from livekit.plugins import (
    openai,
    deepgram,
    noise_cancellation,
    silero,
)
from typing import Optional

# Load environment variables
load_dotenv(".env")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outbound-agent")

import config
from excel_service import ExcelService
# 🌟 INTEGRATION WORK: SFL prompt engine imported directly
from prompt_manager import generate_sfl_runtime_prompt


def print_call_banner(customer_context):
    print("\n" + "=" * 70)
    print("        SUNITA FINLEASE VOICE PLATFORM (SFL-OS)")
    print("=" * 70)
    print(f"📞 Call ID     : {customer_context.get('call_id', '-')}")
    print(f"👤 Customer     : {customer_context.get('customer_name', '-')}")
    print(f"📱 Phone        : {customer_context.get('phone_number', '-')}")
    print(f"🏦 Loan Type    : {customer_context.get('loan_type', '-')}")
    print(f"🎯 Campaign     : {customer_context.get('campaign', '-')}")
    print(f"📍 Branch       : {customer_context.get('branch', '-')}")
    print("=" * 70)


def _build_llm(config_provider: str = None):
    """Configure the LLM provider strictly targeting Groq default performance."""
    provider = (config_provider or os.getenv("LLM_PROVIDER", config.DEFAULT_LLM_PROVIDER)).lower()

    if provider == "groq":
        logger.info("Using Groq LLM Engine")
        return openai.LLM(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.getenv("GROQ_API_KEY"),
            model=os.getenv("GROQ_MODEL", config.GROQ_MODEL),
            temperature=float(os.getenv("GROQ_TEMPERATURE", str(config.GROQ_TEMPERATURE))),
        )
    
    logger.info("Using OpenAI LLM Engine")
    return openai.LLM(model="gpt-4o-mini")


@dataclass
class ConversationState:
    transcript: list = field(default_factory=list)
    summary: str = ""
    disposition: str = "CONNECTED"
    callback_date: str = ""
    customer_response: str = ""
    transferred: bool = False


BRANCHES = {
    "Raipur": "Sunita Finlease Limited, Raipur Branch.",
    "Bilaspur": "Sunita Finlease Limited, Bilaspur Branch.",
    "Durg": "Sunita Finlease Limited, Durg Branch."
}


class TransferFunctions(llm.ToolContext):
    def __init__(
        self,
        ctx: agents.JobContext,
        phone_number: str = None,
        customer_context: dict = None,
    ):
        super().__init__(tools=[])
        self.ctx = ctx
        self.phone_number = phone_number
        self.customer_context = customer_context or {}
        self.call_result = {
            "disposition": "CONNECTED",
            "summary": "",
            "callback_date": "",
            "customer_response": "",
        }

    @llm.function_tool(description="Look up user details by phone number.")
    async def lookup_user(self, phone: str) -> str:
        logger.info(f"Looking up user: {phone}")
        return f"User found: {self.customer_context.get('customer_name')}. Status: Verified SFL Borrower Account."

    @llm.function_tool(description="Transfer the call to a human support agent or another phone number.")
    async def transfer_call(self, destination: Optional[str] = None):
        dest = destination or config.DEFAULT_TRANSFER_NUMBER
        if "@" not in dest and config.SIP_DOMAIN:
            dest = f"sip:{dest.replace('tel:', '').replace('sip:', '')}@{config.SIP_DOMAIN}"
        else:
            if not dest.startswith("tel:") and not dest.startswith("sip:"):
                 dest = f"tel:{dest}"
        
        logger.info(f"Transferring call to {dest}")
        participant_identity = f"sip_{self.phone_number}" if self.phone_number else None

        if not participant_identity:
            for p in self.ctx.room.remote_participants.values():
                participant_identity = p.identity
                break
        
        if not participant_identity:
            return "Failed to transfer: could not identify the caller."

        try:
            await self.ctx.api.sip.transfer_sip_participant(
                api.TransferSIPParticipantRequest(
                    room_name=self.ctx.room.name,
                    participant_identity=participant_identity,
                    transfer_to=dest,
                    play_dialtone=False
                )
            )
            self.call_result["disposition"] = "TRANSFERRED"
            self.call_result["summary"] = "Call successfully transferred to human executive desk."
            return "Transfer initiated successfully."
        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            return f"Error executing transfer: {e}"

    @llm.function_tool(description="Schedule a callback for the customer.")
    async def schedule_callback(self, callback_date: str, callback_time: str, reason: str = "") -> str:
        self.call_result["disposition"] = "CALLBACK"
        self.call_result["callback_date"] = f"{callback_date} {callback_time}"
        self.call_result["summary"] = f"Customer requested callback on {callback_date} at {callback_time}."

        ExcelService.save_callback(
            customer=self.customer_context,
            callback_date=callback_date,
            callback_time=callback_time,
            reason=reason,
        )
        return f"Callback scheduled successfully for {callback_date} at {callback_time}."

    @llm.function_tool(description="Create a support ticket for customer complaints.")
    async def create_support_ticket(self, issue: str) -> str:
        ticket = ExcelService.create_support_ticket(self.customer_context, issue)
        self.call_result["disposition"] = "COMPLAINT"
        self.call_result["summary"] = f"Customer reported an issue. Support ticket generated: {ticket}"
        return f"Support ticket {ticket} has been created successfully."

    @llm.function_tool(description="Provide branch information.")
    async def get_branch_information(self, branch_name: str) -> str:
        return BRANCHES.get(branch_name, "Branch information is currently unavailable.")

    @llm.function_tool(description="Politely end the current call.")
    async def end_call(self, reason: str = "") -> str:
        logger.info(f"Ending call : {reason}")
        self.call_result["disposition"] = "COMPLETED"
        self.call_result["summary"] = reason if reason else "Conversation completed successfully."
        return "The conversation has been completed successfully. Politely thank the customer and end the call."


class OutboundAssistant(Agent):
    def __init__(self, tools: list, customer_context: dict) -> None:
        # 🌟 INTEGRATION WORK: Real-time generation of custom SFL context prompt template
        super().__init__(
            instructions=generate_sfl_runtime_prompt(customer_context),
            tools=tools,
        )


async def entrypoint(ctx: agents.JobContext):
    logger.info("Connecting to SFL custom orchestration framework room...")
    call_start_time = time.time()
    conversation = ConversationState()

    phone_number = None
    config_dict = {}
    call_id = None
    
    # Updated fail-safe pipeline logic
    if not phone_number:
        phone_number = "+917667131255" # Fail-safe pipeline
        customer_context = {
            "customer_name": "Shreyas Raj", 
            "phone_number": phone_number,
            "campaign": "Loan Offer",  # <--- CHNAGED: Bypassed EMI, locked on Loan Offer
            "branch": "Raipur"
        }
    else:
        customer_context = {
            "call_id": call_id,
            "phone_number": phone_number,
            "customer_id": None,
            "customer_name": None,
            "loan_type": None,
            "loan_number": None,
            "emi_amount": None,
            "due_date": None,
            "branch": "Raipur",
            "preferred_language": "Hindi",
            "campaign": "Welcome Call",
        }
    
    try:
        if ctx.job.metadata:
            data = json.loads(ctx.job.metadata)
            phone_number = data.get("phone_number")
            config_dict = data
            call_id = data.get("call_id")
            customer_context.update(data)
    except Exception:
        pass
        
    try:
        if ctx.room.metadata:
            data = json.loads(ctx.room.metadata)
            if data.get("phone_number"):
                phone_number = data.get("phone_number")
            config_dict.update(data)
            customer_context.update(data)
    except Exception:
        logger.warning("No valid metadata parsing available in Room context.")

    customer_context["phone_number"] = phone_number
    print_call_banner(customer_context)
    fnc_ctx = TransferFunctions(ctx, phone_number, customer_context)

    # 🌟 CORE BYPASS PIPELINE DEFINED (SFL PLATFORM LOCK)
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model=config.STT_MODEL, language=config.STT_LANGUAGE),
        llm=_build_llm(config_dict.get("model_provider")),
        tts=deepgram.TTS(model="aura-athena-en"),  # Custom clear dialect accent
    )

    await session.start(
        room=ctx.room,
        agent=OutboundAssistant(
            tools=list(fnc_ctx.function_tools.values()),
            customer_context=customer_context,
        ),
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVCTelephony(),
            close_on_disconnect=True,
        ),
    )

    should_dial = False
    if phone_number:
        user_already_here = False
        for p in ctx.room.remote_participants.values():
            if f"sip_{phone_number}" in p.identity or "sip_" in p.identity:
                user_already_here = True
                break
        
        if not user_already_here:
            should_dial = True

    if should_dial:
        logger.info(f"Initiating outbound trunk SIP connection to {phone_number}...")
        try:
            await ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=ctx.room.name,
                    sip_trunk_id=config.SIP_TRUNK_ID,  
                    sip_call_to=phone_number,
                    participant_identity=f"sip_{phone_number}",
                    wait_until_answered=True,
                )
            )
            logger.info("Trunk call successfully handshaked! Listening stream...")
            
            await asyncio.sleep(2)
            await session.generate_reply(instructions=config.INITIAL_GREETING)
            
            conversation.transcript.append({
                "speaker": "AI",
                "text": "Initial greeting sent."
            })
            
            while ctx.room.remote_participants:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Failed to place outbound call process: {e}")
            ctx.shutdown()
            
        finally:
            duration = round(time.time() - call_start_time)
            transferred_flag = "Yes" if fnc_ctx.call_result["disposition"] == "TRANSFERRED" else "No"
            try:
                ExcelService.save_call_history(
                    call_id=customer_context.get("call_id"),
                    customer=customer_context,
                    call_status=fnc_ctx.call_result["disposition"],
                    duration=f"{duration} sec",
                    ai_summary=fnc_ctx.call_result["summary"],
                    disposition=fnc_ctx.call_result["disposition"],
                    customer_response=fnc_ctx.call_result["customer_response"],
                    callback_date=fnc_ctx.call_result["callback_date"],
                    transferred=transferred_flag,
                    recording_url="",
                    transcript=json.dumps(conversation.transcript),
                )
                logger.info("SFL Master analytics storage cataloged row execution successfully.")
            except Exception as e:
                logger.error(f"Failed to catalog excel log execution: {e}")

            print("\n" + "=" * 70)
            print("✅ CALL PROCESS COMPLETED")
            print("=" * 70)
    else:
        logger.info("Detecting standard room inbound presence...")
        await session.generate_reply(instructions=config.fallback_greeting)


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="outbound-caller", 
        )
    )

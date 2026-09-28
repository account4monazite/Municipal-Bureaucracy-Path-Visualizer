from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from groq.types.chat import ChatCompletionMessageParam
from app.core.settings import get_settings
from app.models import ChatMessage, TaskState
from app.services.nlp_service import NLPService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a civic task navigator assistant for India.
Your role is to help citizens understand what steps they need to take to complete government procedures.

RULES:
1. You are task-oriented — stay focused on identifying the civic task and gathering essential details.
2. Ask ONLY the next most important missing piece of information. Do not ask multiple questions at once.
3. NEVER invent government forms, fees, office names, URLs, eligibility criteria, or deadlines.
4. If you are unsure, say you will look it up from official sources.
5. Be conversational, concise, and reassuring.
6. Once you have (intent + location), confirm and offer to generate the step-by-step roadmap.

REQUIRED INFORMATION (gather in order of priority):
- What civic task does the user want to accomplish? (e.g. register a business, get a passport)
- Which city/state are they in? (needed for jurisdiction-specific requirements)

After gathering minimum required info, say something like:
"Great! I have enough to generate your step-by-step roadmap for [task] in [city]."

DONT'T ASK ANY FOLLOW UP QUESTION FOR CLARIFICATION IF YOU HAVE THE [task] and [city/state.
ALSO DON'T ASK IS THIS CORRECT, SHALL I PROCEED?, nothing like that.
NO QUESTIONS SHOULD BE ASKED FOLLOW WHAT IS GIVEN.

7. ALWAYS reply in English, even if the user speaks in Hindi or another language. This is critical for the text-to-speech system to work.
"""


class ChatbotService:
    """
    Manages task-oriented conversations.

    The LLM is used only for conversational flow and intent understanding.
    Government facts come exclusively from the NLP/scraping service.
    """

    def __init__(self, nlp_service: NLPService) -> None:
        self._nlp = nlp_service
        self._settings = get_settings()
        self._llm_client = None
        self._llm_available = False
        self._init_llm()

    def _init_llm(self) -> None:
        self._llm_available = True
        logger.info("ChatbotService: Ollama initialized (model=%s, url=%s)", self._settings.ollama_model, self._settings.ollama_api_url)

    # ── Public interface ──────────────────────────────────────────────────────

    async def process_message(
        self,
        state: TaskState,
        user_message: str,
        is_voice: bool = False,
    ) -> tuple[str, TaskState]:
        """
        Process a single user message given the current task state.

        Returns:
            (assistant_reply, updated_task_state)
        """
        # 1. Add user message to history
        state.conversation_history.append(
            ChatMessage(role="user", content=user_message)
        )

        # 2. Extract structured info from the message
        extracted = await self._nlp.extract_task(user_message)
        state = self._merge_extracted(state, extracted)

        # 3. Generate reply
        reply = await self._generate_reply(state, user_message, is_voice)

        # 4. Re-check what's missing after extraction
        state.missing_information = self._compute_missing(state)

        # 5. Store assistant reply in history
        state.conversation_history.append(
            ChatMessage(role="assistant", content=reply)
        )
        state.updated_at = datetime.now(timezone.utc)

        return reply, state

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _merge_extracted(self, state: TaskState, extracted: Dict[str, Any]) -> TaskState:
        """Merge NLP-extracted fields into existing task state (non-destructive)."""
        extracted_intent = extracted.get("intent")
        if extracted_intent and str(extracted_intent).lower() != "unknown":
            state.intent = extracted_intent

        loc = extracted.get("location") or {}
        if isinstance(loc, dict):
            if loc.get("city") and not state.location.city:
                state.location.city = loc["city"]
            if loc.get("state") and not state.location.state:
                state.location.state = loc["state"]
            if loc.get("district") and not state.location.district:
                state.location.district = loc["district"]

        details = extracted.get("details") or {}
        if isinstance(details, dict):
            for k, v in details.items():
                if k not in state.details or not state.details[k]:
                    state.details[k] = v

        return state

    def _compute_missing(self, state: TaskState) -> List[str]:
        """Return a list of required fields that are still missing."""
        missing = []
        if not state.intent or state.intent.lower() == "unknown":
            missing.append("civic_task")
        if not state.location.city and not state.location.state:
            missing.append("location")
        return missing

    async def _generate_reply(self, state: TaskState, user_message: str, is_voice: bool = False) -> str:
        """Generate the chatbot reply using LLM or rule-based fallback."""
        if self._llm_available:
            return await self._llm_reply(state, user_message, is_voice)
        return self._rule_based_reply(state, is_voice)

    async def _llm_reply(self, state: TaskState, user_message: str, is_voice: bool = False) -> str:
        """Generate a reply using Ollama chat completions."""
        context_note = self._build_context_note(state)
        system_message = SYSTEM_PROMPT
        if context_note:
            system_message += f"\n\nCurrent task state:\n{context_note}"
        
        if is_voice:
            # Prevent conflicting instructions by explicitly replacing the question prompts
            system_message = system_message.replace(
                '"Great! I have enough to generate your step-by-step roadmap for [task] in [city]. Shall I proceed?"',
                '"Great! I have enough information. I am now looking up the step-by-step procedure for [task] in [city]."'
            ).replace(
                "6. Once you have (intent + location), confirm and offer to generate the step-by-step roadmap.",
                "6. Once you have (intent + location), confirm that you are generating the step-by-step roadmap (do NOT ask a question)."
            ).replace(
                "2. Ask ONLY the next most important missing piece of information. Do not ask multiple questions at once.",
                "2. Do NOT ask for any missing information. Accept whatever the user provided."
            ).replace(
                "- Any task-specific details (e.g. business type for registration)",
                ""
            )
            system_message += "\n\nCRITICAL INSTRUCTION: The user provided this input via voice. You MUST NOT ask any follow-up questions for clarification (e.g. do NOT ask for license type, business type, etc). Just acknowledge the intent and location, confirm you understood, and state what is happening next."

        messages = [
            {"role": "system", "content": system_message},
        ]
        for message in state.conversation_history[:-1]:
            if message.role == "assistant":
                messages.append(
                    {"role": "assistant", "content": message.content}
                )
            elif message.role == "user":
                messages.append({"role": "user", "content": message.content})

        messages.append({"role": "user", "content": user_message})

        model = self._settings.ollama_model.strip()
        try:
            logger.info("Sending chat completion request to Ollama (model=%s)", model)
            import httpx
            payload = {
                "model": model,
                "messages": messages,
                "stream": False
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self._settings.ollama_api_url, json=payload)
                response.raise_for_status()
                data = response.json()
            
            reply = data.get("message", {}).get("content")
            return reply or self._rule_based_reply(state)
        except Exception:
            logger.exception("Ollama reply generation failed (model=%s)", model)
            return self._rule_based_reply(state)

    def _rule_based_reply(self, state: TaskState, is_voice: bool = False) -> str:
        """Simple rule-based fallback when the LLM is unavailable."""
        missing = self._compute_missing(state)

        if "civic_task" in missing:
            if is_voice:
                return "I'm here to help you navigate government procedures. I still need to know what you would like to accomplish, for example, registering a business or applying for a passport."
            return (
                "Hello! I'm here to help you navigate government procedures. "
                "What would you like to accomplish? For example: register a business, "
                "apply for a passport, or get a driving license?"
            )

        if "location" in missing:
            task_display = (state.intent or "your task").replace("_", " ").title()
            if is_voice:
                return f"I can help you with {task_display}. I still need to know which city or state you are in to find the right offices and requirements."
            return (
                f"I can help you with {task_display}. "
                "Which city or state are you in? This helps me find the right offices and requirements for you."
            )

        # We have enough info
        city = state.location.city or state.location.state or "your area"
        task_display = (state.intent or "your task").replace("_", " ").title()
        
        if is_voice:
            return f"Great! I have enough information to generate your roadmap for {task_display} in {city}. I am generating it now."
            
        return (
            f"Great! I have enough information to generate your roadmap for "
            f"{task_display} in {city}. "
            "Shall I proceed? You can call the /api/roadmap/generate endpoint or just say 'yes'."
        )

    def _build_context_note(self, state: TaskState) -> str:
        """Build a concise context note for the LLM."""
        parts = []
        if state.intent:
            parts.append(f"Identified task: {state.intent}")
        if state.location.city or state.location.state:
            loc = ", ".join(filter(None, [state.location.city, state.location.state]))
            parts.append(f"Location: {loc}")
        if state.details:
            parts.append(f"Additional details: {state.details}")
        missing = self._compute_missing(state)
        if missing:
            parts.append(f"Still needed: {', '.join(missing)}")
        return "\n".join(parts) if parts else ""

    def create_initial_state(self, session_id: str) -> TaskState:
        """Create a fresh task state for a new session."""
        return TaskState(session_id=session_id)

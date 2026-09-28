import asyncio
from app.services.nlp_service import NLPService
from app.services.chatbot_service import ChatbotService
from app.models import TaskState

async def test_chatbot():
    nlp = NLPService()
    chatbot = ChatbotService(nlp)
    
    # We pass a brand new session id to ensure no old history is pulled from the DB
    state = TaskState(session_id="test_new_session")
    
    # Send user message
    user_msg = "Senior citizen card apply Mumbai Maharashtra"
    print(f"USER: {user_msg}")
    
    reply, updated_state = await chatbot.process_message(state, user_msg)
    
    print(f"BOT: {reply}")
    print(f"STATE INTENT: {updated_state.intent}")
    print(f"STATE LOCATION: {updated_state.location}")

if __name__ == "__main__":
    asyncio.run(test_chatbot())

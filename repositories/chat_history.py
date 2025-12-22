from typing import List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from services.rabbitmq import rabbitmq_service
import json

def get_messages(user_id: int, lesson_id: int, limit: int = 50) -> List[BaseMessage]:
    """
    Retrieve chat history via RabbitMQ RPC (Server-side fetch)
    """
    try:
        payload = {
            "userId": user_id,
            "lessonId": lesson_id,
            "limit": limit
        }
        
        # Call RPC
        response = rabbitmq_service.rpc_call("GET_CHAT_HISTORY", payload)
        
        messages = []
        if response and response.get("success"):
            chat_list = response.get("messages", [])
            
            # Convert to LangChain messages
            for msg in chat_list:
                role = msg.get("role")
                # Handle value/content field mapping
                content = msg.get("value") or msg.get("content") or ""
                
                if role == 'user':
                    messages.append(HumanMessage(content=content))
                elif role == 'assistant' or role == 'ai':
                    messages.append(AIMessage(content=content))
                    
        return messages
                    
    except Exception as e:
        print(f"❌ Error fetching chat history via RPC: {e}")
        return []

def add_message(user_id: int, lesson_id: int, role: str, content: str):
    """
    Save a message via RabbitMQ Event (Fire & Forget)
    Pattern: SAVE_CHAT_MESSAGES
    """
    # Map role
    db_role = 'user'
    if role == 'ai' or role == 'assistant':
        db_role = 'assistant'
    
    try:
        # Payload matching Course Service DTO
        payload = {
            "lessonId": lesson_id,
            "userId": user_id,
            "messages": [
                {
                    "role": db_role,
                    "value": content
                }
            ]
        }
        
        # Publish
        rabbitmq_service.publish_event("SAVE_CHAT_MESSAGES", payload)
        
    except Exception as e:
        print(f"❌ Error publishing chat message: {e}")

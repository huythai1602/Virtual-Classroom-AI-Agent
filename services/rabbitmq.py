
import os
import json
import pika
import uuid
import time
import threading
from typing import Dict, Any, Optional
from config.settings import settings

class RabbitMQService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RabbitMQService, cls).__new__(cls)
                cls._instance.connection = None
                cls._instance.channel = None
            return cls._instance

    def connect(self):
        """Establish connection to RabbitMQ"""
        if not settings.RABBITMQ_URL:
            print("⚠️ RabbitMQ URL not set. Skipping connection.")
            return

        try:
            params = pika.URLParameters(settings.RABBITMQ_URL)
            self.connection = pika.BlockingConnection(params)
            self.channel = self.connection.channel()
            
            # Declare queues ensuring they exist
            self.channel.queue_declare(queue=settings.RABBITMQ_OUT_QUEUE, durable=True)
            self.channel.queue_declare(queue=settings.RABBITMQ_IN_QUEUE, durable=True)
            
            print(f"✅ Connected to RabbitMQ at {settings.RABBITMQ_URL.split('@')[-1]}")
            print(f"   - Out Queue: {settings.RABBITMQ_OUT_QUEUE}")
            print(f"   - In Queue: {settings.RABBITMQ_IN_QUEUE}")

        except Exception as e:
            print(f"❌ Failed to connect to RabbitMQ: {str(e)}")
            self.connection = None

    def ensure_connection(self):
        """Check and reconnect if necessary"""
        if not self.connection or self.connection.is_closed:
            self.connect()

    def publish_event(self, pattern: str, payload: Dict[str, Any]):
        """
        Fire-and-forget message publishing
        Used for: SAVE_CHAT_MESSAGES
        """
        self.ensure_connection()
        if not self.channel:
            print("⚠️ RabbitMQ channel not available. Message dropped.")
            return

        try:
            properties = pika.BasicProperties(
                delivery_mode=2,  # make message persistent
                content_type='application/json',
                headers={'pattern': pattern}
            )
            
            # NestJS Compatibility: Wrap payload in packet structure
            packet = {
                "pattern": pattern,
                "data": payload
            }
            
            self.channel.basic_publish(
                exchange='',
                routing_key=settings.RABBITMQ_OUT_QUEUE,
                body=json.dumps(packet),
                properties=properties
            )
            print(f"📤 Published Event [{pattern}] to {settings.RABBITMQ_OUT_QUEUE}")
        except Exception as e:
            print(f"❌ Failed to publish event: {str(e)}")

    def rpc_call(self, pattern: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Make a synchronous RPC call over RabbitMQ
        Used for: GET_QUIZ_DATA, GET_LESSON_TRANSCRIPT, GET_CHAT_HISTORY
        """
        self.ensure_connection()
        if not self.connection:
            raise Exception("RabbitMQ unavailable")

        # Create a temporary callback queue for this request
        callback_queue_name = None # Initialize to avoid UnboundLocalError
        response = None
        corr_id = str(uuid.uuid4())
        
        def on_response(ch, method, props, body):
            nonlocal response
            if props.correlation_id == corr_id:
                response = json.loads(body)

        try:
            # Setup temporary queue
            # Note: We create a throwaway channel for the consumer to avoid blocking the main one? 
            # Or just use the main channel but be careful. 
            # For simplicity in this synchronous blocking call, we can use the existing channel 
            # but we need to consume. 
            
            # Better approach for RPC in blocking pika:
            # Declare a temporary exclusive queue
            result = self.channel.queue_declare(queue='', exclusive=True)
            callback_queue_name = result.method.queue
            
            self.channel.basic_consume(
                queue=callback_queue_name,
                on_message_callback=on_response,
                auto_ack=True
            )

            # Send request
            properties = pika.BasicProperties(
                reply_to=callback_queue_name,
                correlation_id=corr_id,
                content_type='application/json',
                headers={'pattern': pattern}
            )
            
            # NestJS Compatibility: Wrap payload in packet structure if needed, 
            # OR just ensure headers are correct. 
            # But the 'Pattern: undefined' error strongly suggests NestJS is looking for the pattern in the deserialized packet.
            # Standard NestJS Microservice packet: { pattern: string, data: any, id: string }
            packet = {
                "pattern": pattern,
                "data": payload,
                "id": corr_id
            }

            self.channel.basic_publish(
                exchange='',
                routing_key=settings.RABBITMQ_OUT_QUEUE, # Send request to Course Service
                body=json.dumps(packet), # Send wrapped packet
                properties=properties
            )
            
            print(f"🔄 RPC Call [{pattern}] sent. Waiting for reply...")
            
            # Wait for response with timeout
            start_time = time.time()
            while response is None:
                self.connection.process_data_events()
                if time.time() - start_time > settings.RABBITMQ_TIMEOUT:
                    raise TimeoutError("RPC request timed out")
                time.sleep(0.05)
                
            # Unwrap response if it comes back wrapped (NestJS reply structure)
            # NestJS reply: { response: ..., isDisposed: true }
            if isinstance(response, dict) and "response" in response:
                 return response["response"]
                
            return response

        except Exception as e:
            print(f"❌ RPC Call failed: {str(e)}")
            return None
        finally:
            # Cleanup can be tricky with shared channel, but exclusive queue auto-deletes when connection closes.
            # Explicit delete is better if we keep connection open.
            if callback_queue_name and self.channel:
                 try:
                     self.channel.queue_delete(queue=callback_queue_name)
                 except:
                     pass

rabbitmq_service = RabbitMQService()

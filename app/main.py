import base64
import json
import os
import uuid
import paho.mqtt.client as mqtt
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from app.services.speech_recognition import SpeechRecognitionService
from app.services.children_dialogue import DeepSeekChildrenDialogue
from app.services.speech_synthesis import SpeechSynthesisService
from app.settings import settings
from app.utils.audio_converter import convert_to_pcm
from app.utils.logger import setup_logging

load_dotenv(".env")

logger = setup_logging()

app = FastAPI()

# Initialize service instances
recognizer = SpeechRecognitionService()
synthesizer = SpeechSynthesisService()
DIALOGUE_CACHE = {}  # Session cache {session_id: dialogue_instance}

# MQTT setup
MQTT_BROKER = "localhost"  # Local broker
MQTT_PORT = 1883
MQTT_TOPIC_IN = "chat/audio/in"
MQTT_TOPIC_OUT = "chat/audio/out"
MQTT_CLIENT_ID = f"chatbot-{uuid.uuid4()}"


mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)


# Connect to the MQTT broker
mqtt_client.connect(MQTT_BROKER, MQTT_PORT)


class ChatResponse(BaseModel):
    session_id: str
    text_response: str
    audio_url: str
    timestamp: str


# MQTT callbacks
def on_connect(client, userdata, flags, rc):
    """Callback when the MQTT client connects."""
    print(f"Connected with result code {rc}")
    client.subscribe(MQTT_TOPIC_IN)


def on_message(client, userdata, msg):
    """Callback when a message is received from MQTT."""
    try:
        payload = msg.payload.decode('utf-8')
        message = json.loads(payload)
        audio_data_base64 = message.get("audio_data")
        metadata = message.get("metadata")
        audio_input_name = metadata.get("filename")
        audio_input_size = metadata.get("size")

        session_id = str(uuid.uuid4())  # Generate new session ID
        audio_input_path = os.path.join(settings.File_PATH, f"{session_id}_input.wav").replace(os.sep, '/')

        audio_input_data = base64.b64decode(audio_data_base64)
        # Save the incoming audio message to a file
        with open(audio_input_path, "wb") as f:
            f.write(audio_input_data)

        # Convert audio format (if needed)
        audio_pcm_path = os.path.join(settings.File_PATH, f"{session_id}_pcm.wav").replace(os.sep, '/')
        pcm_flag = convert_to_pcm(input_path=audio_input_path, output_path=audio_pcm_path)
        if not pcm_flag:
            raise Exception("Failed to convert audio format")
        else:
            if os.path.exists(audio_input_path):
                os.remove(audio_input_path)

        # Recognize text from audio
        text_input = recognizer.recognize(audio_input=audio_pcm_path)

        if os.path.exists(audio_pcm_path):
            os.remove(audio_pcm_path)

        # Generate dialogue response
        dialogue_service = get_dialogue_service(session_id)
        text_reply = dialogue_service.chat(text_input)

        print(text_reply)

        # Synthesize speech from text
        audio_output_filename = f"{session_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp3"
        audio_output_path = os.path.join(settings.File_PATH, audio_output_filename).replace(os.sep, '/')

        synthesizer.synthesis(text=text_reply, output_path=audio_output_path)

        # Read the generated audio file and publish it via MQTT
        with open(audio_output_path, "rb") as f:
            audio_output_data = f.read()

        response = {
            "session_id": session_id,
            "filename": audio_output_filename,
            "audio_reply": base64.b64encode(audio_output_data).decode('utf-8'),
            "text_reply": text_reply
        }
        client.publish(MQTT_TOPIC_OUT, json.dumps(response))

        if os.path.exists(audio_output_path):
            os.remove(audio_output_path)

    except Exception as e:
        print(f"Error processing message: {e}")


# MQTT client setup
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message


# Start the MQTT client loop in the background
def start_mqtt_loop():
    """Start the MQTT client loop to listen for messages."""
    mqtt_client.loop_start()


@app.on_event("startup")
async def startup():
    """Start MQTT loop on FastAPI startup."""
    start_mqtt_loop()


@app.on_event("shutdown")
async def shutdown():
    """Stop MQTT loop on FastAPI shutdown."""
    mqtt_client.loop_stop()


def get_dialogue_service(session_id: str) -> DeepSeekChildrenDialogue:
    """Get or create a dialogue service instance for the given session."""
    if session_id not in DIALOGUE_CACHE:
        DIALOGUE_CACHE[session_id] = DeepSeekChildrenDialogue(
            temperature=0.95,
            max_history=5
        )
    return DIALOGUE_CACHE[session_id]


@app.post("/chat", response_model=ChatResponse)
async def chat_reply(background_tasks: BackgroundTasks, session_id: str, text_input: str):
    """Endpoint to interact with the chatbot via HTTP requests."""
    try:
        # Get or create dialogue service instance
        dialogue_service = get_dialogue_service(session_id)

        # Generate dialogue response
        text_reply = dialogue_service.chat(text_input)

        audio_output_filename = f"{session_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp3"
        audio_output_path = os.path.join(settings.File_PATH, audio_output_filename).replace(os.sep, '/')
        synthesizer.synthesis(text=text_reply, output_path=audio_output_path)

        audio_url = f"/audio/{audio_output_filename}"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        return ChatResponse(
            session_id=session_id,
            text_response=text_reply,
            audio_url=audio_url,
            timestamp=timestamp
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {e}")

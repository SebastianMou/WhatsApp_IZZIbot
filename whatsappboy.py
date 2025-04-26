from openai import OpenAI
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import os
import json
import logging
import threading
import time

load_dotenv()

openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
twilio_client = Client(account_sid, auth_token)

app = Flask(__name__)

conversation_history = {}

manual_mode = {}

first_message_sent = {}

last_message_time = {}

pending_responses = {}

DEBUG_MODE = True

image_library = {
    "paquetes_principales": {
        "description": "Paquetes principales IZZI (2P y 3P)",
        "url": "https://tinyurl.com/3bcdnps4" 
    },
    "promociones_adicionales": {
        "description": "Todas las promociones y paquetes adicionales",
        "url": "https://tinyurl.com/ABR-2025-IZZI"
    }
}

SECRET_KEYWORD = "/-"
RESUME_KEYWORD = "/--"

HISTORY_FILE = "conversation_history.json"
MANUAL_MODE_FILE = "manual_mode.json"
FIRST_MESSAGE_FILE = "first_message_sent.json"

RESPONSE_DELAY = 10

def debug_print(msg):
    if DEBUG_MODE:
        print(f"DEBUG: {msg}")

# Load existing conversation history from file if it exists
def load_conversation_history():
    global conversation_history, manual_mode, first_message_sent
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as file:
                conversation_history = json.load(file)
            debug_print(f"Loaded conversation history for {len(conversation_history)} users")
        if os.path.exists(MANUAL_MODE_FILE):
            with open(MANUAL_MODE_FILE, 'r') as file:
                manual_mode = json.load(file)
        if os.path.exists(FIRST_MESSAGE_FILE):
            with open(FIRST_MESSAGE_FILE, 'r') as file:
                first_message_sent = json.load(file)
    except Exception as e:
        debug_print(f"Error loading data: {e}")
        conversation_history = {}
        manual_mode = {}
        first_message_sent = {}

# Save data to files
def save_data():
    try:
        with open(HISTORY_FILE, 'w') as file:
            json.dump(conversation_history, file)
        with open(MANUAL_MODE_FILE, 'w') as file:
            json.dump(manual_mode, file)
        with open(FIRST_MESSAGE_FILE, 'w') as file:
            json.dump(first_message_sent, file)
        debug_print("Data saved successfully")
    except Exception as e:
        debug_print(f"Error saving data: {e}")

# Safe function to send messages that won't crash your server
def safe_send_message(to, body):
    debug_print(f"Attempting to send message to {to}: {body[:50]}...")
    try:
        message = twilio_client.messages.create(
            from_='whatsapp:+5274458564815',
            body=body,
            to=to
        )
        debug_print(f"Message sent successfully to {to}")
        return True, message.sid
    except TwilioRestException as e:
        debug_print(f"Twilio error sending to {to}: {str(e)}")
        return False, str(e)
    except Exception as e:
        debug_print(f"Unexpected error sending to {to}: {str(e)}")
        return False, str(e)

def get_system_instruction():
    return """
    ## Instrucciones Chatbot Ventas IZZI

    ### Identidad
    - Eres un asesor de internet amigable y conversacional llamado Sebastian Mauricio.
    - Tu objetivo es vender servicios IZZI por WhatsApp de forma natural y efectiva.

    ### Estilo de comunicación
    - Mensajes cortos (1-3 oraciones máximo).
    - Tono casual y humano, nunca robótico.
    - Usa 1-2 emojis ocasionales (no en cada mensaje).
    - Evita listas, viñetas o formatos complejos.

    ### Paquetes principales
    - **2P (3 meses promoción):** 40MB (+60MB adicionales) $349, 60MB (+80MB adicionales) $419, 80MB (+100MB adicionales) $439, 150MB (+200MB adicionales) $509, 200MB (+500MB adicionales) $569, 500MB (+1000MB adicionales) $689, 1000MB $889
    - **3P (6 meses promoción):** 40MB (+60MB adicionales) $499, 60MB (+80MB adicionales) $599, 80MB (+100MB adicionales) $619, 150MB (+200MB adicionales) $689, 200MB (+500MB adicionales) $749, 500MB (+1000MB adicionales) $869, 1000MB $1,069

    ### Promociones importantes
    - Instalación GRATIS
    - MAX gratis por 12 meses (activar primeros 3 meses)
    - Apple TV+ incluido en paquetes 200MB+
    - Domizzilia: $50 descuento mensual de por vida
    - Sin plazos forzosos disponible (seguro de exención)

    ### Proceso de venta
    1. Saluda de forma casual y pregunta si actualmente tiene algún servicio de internet contratado.
    2. Si responde, DEBES solicitar su ubicación EXACTA usando el mapa de WhatsApp:
       - Pídele específicamente que comparta su ubicación en tiempo real usando la función de mapa de WhatsApp
       - Explica que esto es necesario para verificar la cobertura con precisión
       - Dile cómo compartir su ubicación: "Por favor, presiona el clip (📎) y selecciona 'Ubicación' para compartir tu ubicación actual"
    3. Cuando recibas un mensaje que dice [UBICACIÓN COMPARTIDA], confirma que has recibido la ubicación y agradece al usuario por compartirla.
    4. DESPUÉS de recibir la ubicación, DEBES hacer más preguntas para entender sus necesidades:
       - ¿Cuántos dispositivos conectarán al internet?
       - ¿Qué tipo de uso le darán? (streaming, videollamadas, juegos, trabajo desde casa, etc.)
       - ¿Cuántas personas usarán el servicio?
       - ¿Tienen un presupuesto específico en mente?
       - ¿Les interesa algún servicio adicional como TV o streaming?
    5. Basado en toda esta información, recomienda el paquete más adecuado con su precio específico y beneficios.
    6. IMPORTANTE: Cuando el cliente acepte un paquete específico y esté listo para proceder, NO solicites documentación.
       En su lugar, envía el siguiente mensaje EXACTO y luego termina la conversación:
       "¡Perfecto! Déjame verificar la cobertura exacta en tu zona. Dame un momento mientras confirmo la disponibilidad del servicio... ⏳"
       
    ### REGLA CRÍTICA PARA TERMINAR LA CONVERSACIÓN
    - NUNCA pidas INE, comprobante de domicilio o información personal
    - Cuando el cliente acepte un paquete específico, ÚNICAMENTE envía el mensaje sobre verificar cobertura
    - NO continúes la conversación después de enviar ese mensaje
    - NO pidas documentación
    - NO hables sobre códigos de verificación
    - NO expliques siguientes pasos o procesos

    ### Ejemplos de respuestas

    **Primer mensaje al iniciar conversación:**
    "¡Hola! 👋 ¿Actualmente cuentas con una compañía o servicio de internet?"

    **Solicitud de ubicación por WhatsApp:**
    "Para verificar la cobertura exacta en tu zona, ¿podrías compartirme tu ubicación usando el mapa de WhatsApp? Solo presiona el clip (📎), selecciona 'Ubicación' y envíame tu ubicación actual. 📍"

    **Confirmación de ubicación recibida:**
    "¡Gracias por compartir tu ubicación! 👍 Ahora verificaré si tenemos cobertura exacta en esa zona. ¿Cuántos dispositivos conectarás al internet?"

    **Pregunta sobre precios:**
    "Tenemos internet desde $399 (40 megas) por 3 meses. El más popular es 60 megas a $469 con internet ilimitado. ¿Qué velocidad necesitas?"

    **Cuando el cliente acepta un paquete:**
    "¡Perfecto! Déjame verificar la cobertura exacta en tu zona. Dame un momento mientras confirmo la disponibilidad del servicio... ⏳"
    [NO ENVÍES MÁS MENSAJES DESPUÉS DE ESTO]

    ### Restricciones
    - No ofrecer servicios fuera de paquetes oficiales
    - SIEMPRE verificar cobertura mediante la ubicación exacta del mapa de WhatsApp
    - No aceptar solo nombres de colonias o calles, INSISTIR en la ubicación por mapa
    - No compartir precios incorrectos
    - No crear promociones no autorizadas
    - NUNCA solicitar documentación personal (INE, comprobante de domicilio)
    - DETENER la conversación después del mensaje de verificación de cobertura
"""

# Define add_image_if_needed outside the delayed_response function
def add_image_if_needed(ai_response, is_first_message=False):
    """Add at most one image to the response based on content or if it's the first message"""
    
    # Check if we're explicitly discussing packages/prices
    discussing_packages = any(term in ai_response.lower() for term in [
        "paquete", "precio", "costo", "tarifa", "megas", 
        "internet", "velocidad", "mb", "plan", "oferta", "promoción"
    ])
    
    # Add image only in specific situations:
    # 1. First message from the bot after location is shared
    # 2. When specifically discussing packages/prices AND the user is asking about them
    if is_first_message or (discussing_packages and not "ya te compartí" in ai_response.lower()):
        # Don't send the same image twice in a short period
        data = image_library["paquetes_principales"]
        # Only add if the image URL isn't already in the response
        if data['url'] not in ai_response:
            ai_response += f"\n\n📸 {data['description']}:\n{data['url']}"
    
    return ai_response

def delayed_response(sender, incoming_msg):
    global last_message_time, pending_responses, conversation_history, first_message_sent
    
    debug_print(f"Starting delayed response for {sender}, will wait {RESPONSE_DELAY} seconds")
    
    # Sleep for the configured delay time
    time.sleep(RESPONSE_DELAY)
    
    # After waiting, check if we received any new messages during the delay
    current_time = time.time()
    if sender in last_message_time and (current_time - last_message_time[sender]) < RESPONSE_DELAY:
        debug_print(f"Aborting response to older message from {sender} - newer message received")
        return
    
    debug_print(f"Processing delayed response for {sender} after waiting")
    
    # Make sure the conversation exists for this sender
    if sender not in conversation_history:
        # Initialize with system instruction
        conversation_history[sender] = [{"role": "system", "content": get_system_instruction()}]
        debug_print(f"Initialized new conversation for {sender}")
    
    # Check if this is the first message
    is_first_message = not first_message_sent.get(sender, False)
    debug_print(f"Is first message for {sender}? {is_first_message}")
    
    # If this is the first message from this user, respond with the specific question
    if is_first_message:
        # Mark that we've sent the first message to this user
        first_message_sent[sender] = True
        
        # Standard first message to always ask
        first_response = "¡Hola! 👋 ¿Actualmente cuenta con una compañía o servicio de internet?"
        debug_print(f"Sending first message to {sender}: {first_response}")
        
        # Add our fixed first response to conversation history
        conversation_history[sender].append({"role": "assistant", "content": first_response})
        
        # Save updated conversation history
        save_data()
        
        # Send the fixed first response using safe method
        success, result = safe_send_message(sender, first_response)
        debug_print(f"First message sent result: {success}, {result}")
        
        # Clear this sender from pending responses
        if sender in pending_responses:
            del pending_responses[sender]
            
        return
    
    # Not first message, generate AI response
    debug_print(f"Generating AI response for {sender}")
    
    # Get AI response using the conversation history
    # Get AI response using the conversation history
    try:
        debug_print(f"Sending request to OpenAI with conversation history of {len(conversation_history[sender])} messages")
        
        # Print last few messages for context
        for i, msg in enumerate(conversation_history[sender][-3:]):
            debug_print(f"  Message {i}: {msg['role']} - {msg['content'][:50]}...")
        
        # If this message is resuming from manual mode, add a system instruction to analyze the conversation
        messages_to_send = conversation_history[sender].copy()
        if incoming_msg == "AI assistance resumed":
            debug_print("Adding instruction to analyze conversation after manual mode")
            analyze_instruction = {
                "role": "system", 
                "content": "The conversation was temporarily in manual mode (handled by a human). Review the recent messages and provide an appropriate response that acknowledges any questions or issues raised during that time."
            }
            messages_to_send.append(analyze_instruction)
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages_to_send
        )
        
        ai_response = response.choices[0].message.content
        debug_print(f"Got AI response: {ai_response[:100]}...")

        # Special handling for location acknowledgment
        if "[UBICACIÓN COMPARTIDA]" in incoming_msg and not "gracias" in ai_response.lower():
            debug_print("Adding location acknowledgment to response")
            ai_response = "¡Gracias por compartir tu ubicación! 👍 Verificaré si tenemos cobertura en esa zona exacta. " + ai_response


        # Add this check in your delayed_response function after generating the AI response:
        if "déjame verificar la cobertura exacta" in ai_response.lower() and "dame un momento" in ai_response.lower():
            # Switch to manual mode after sending this message
            manual_mode[sender] = True
            debug_print(f"Automatically switched to manual mode for {sender} after coverage verification message")
            save_data()

        # Check if we've recently sent an image to this user
        last_few_messages = conversation_history[sender][-3:]  # Get last 3 messages
        recently_sent_image = False
        for msg in last_few_messages:
            if msg.get("role") == "assistant" and any(img['url'] in msg.get("content", "") for img in image_library.values()):
                recently_sent_image = True
                break

        # Only add image if we haven't recently sent one
        if not recently_sent_image:
            ai_response = add_image_if_needed(ai_response, is_first_message)
        else:
            # Skip adding an image if we recently sent one
            debug_print("Skipping image - recently sent one")
        
        # Add AI response to conversation history
        conversation_history[sender].append({"role": "assistant", "content": ai_response})
        save_data()
        
        # Actually send the message to the user
        debug_print(f"Sending AI response to {sender}: {ai_response[:50]}...")
        success, result = safe_send_message(sender, ai_response)
        debug_print(f"AI response sent result: {success}, {result}")
        
    except Exception as e:
        debug_print(f"Error generating response: {e}")
        import traceback
        traceback.print_exc()
    
    # Clear this sender from pending responses
    if sender in pending_responses:
        del pending_responses[sender]
        debug_print(f"Cleared pending response for {sender}")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.route("/webhook", methods=['POST'])
def webhook():
    global last_message_time, pending_responses, conversation_history
    
    try:
        all_values = request.values.to_dict()
        debug_print(f"RECEIVED REQUEST: {all_values}")
        
        incoming_msg = request.values.get('Body', '').strip()
        sender = request.values.get('From', '')
        
        debug_print(f"Received message from {sender}: {incoming_msg}")
        
        last_message_time[sender] = time.time()
        
        if not incoming_msg:
            media_count = request.values.get('NumMedia', '0')
            media_content_type = request.values.get('MediaContentType0', '')
            
            # Check specifically for audio messages
            if 'audio' in media_content_type.lower():
                # Mark as voice message
                incoming_msg = "[AUDIO_MESSAGE]"
                debug_print("Detected voice message")
            # Check for location
            elif 'Latitude' in request.values:
                incoming_msg = "[UBICACIÓN COMPARTIDA]"
                debug_print("Detected location share")
            # Any other media
            elif media_count != '0' or 'MediaUrl' in request.values:
                incoming_msg = "[MEDIA_CONTENT]"
                debug_print("Detected other media content")
        
        if "[AUDIO_MESSAGE]" in incoming_msg:
            debug_print("Adding voice message response")
            ai_response = "Disculpa, estoy en un lugar con mucho ruido y no puedo escuchar bien los mensajes de voz. ¿Podrías enviarme tu consulta por texto? Así podré ayudarte mejor. 😊"
            
            conversation_history[sender].append({"role": "assistant", "content": ai_response})
            save_data()
            
            success, result = safe_send_message(sender, ai_response)
            debug_print(f"Voice message response sent result: {success}, {result}")
            
            if sender in pending_responses:
                del pending_responses[sender]
                
            return "Audio message handled"

        if incoming_msg == SECRET_KEYWORD:
            debug_print(f"Secret keyword detected from {sender}")
            if sender in manual_mode:
                manual_mode[sender] = not manual_mode.get(sender, False)
            else:
                manual_mode[sender] = True
            
            debug_print(f"Manual mode for {sender} set to {manual_mode.get(sender, False)}")
            
            if sender in pending_responses:
                del pending_responses[sender]
            
            save_data()
            return "Mode changed"
        elif incoming_msg == RESUME_KEYWORD:
            debug_print(f"Resume keyword detected from {sender}")
            if sender in manual_mode and manual_mode[sender]:
                manual_mode[sender] = False
                debug_print(f"Manual mode disabled for {sender}, AI will resume")
                
                # Start a delayed response to allow AI to analyze the conversation and respond
                response_thread = threading.Thread(target=delayed_response, args=(sender, "AI assistance resumed"))
                response_thread.daemon = True
                response_thread.start()
                
                # Store the thread reference
                pending_responses[sender] = response_thread
                
                save_data()
                return "AI assistance resumed"
            return "Not in manual mode"
         
        if manual_mode.get(sender, False):
            debug_print(f"User {sender} is in manual mode, message will not be processed")
            
            if sender in pending_responses:
                del pending_responses[sender]
                
            return "Message received in manual mode"
        
        if sender not in conversation_history:
            debug_print(f"Initializing new conversation for {sender}")
            conversation_history[sender] = [{"role": "system", "content": get_system_instruction()}]
        
        debug_print(f"Adding user message to conversation history for {sender}")
        conversation_history[sender].append({"role": "user", "content": incoming_msg})
        
        if len(conversation_history[sender]) > 21:  # 1 system message + 20 conversation messages
            conversation_history[sender] = [conversation_history[sender][0]] + conversation_history[sender][-20:]
            debug_print(f"Trimmed conversation history for {sender} to 21 messages")
        
        # Save the updated conversation history
        save_data()
        
        # Cancel any existing pending response for this user
        if sender in pending_responses:
            debug_print(f"Cancelling pending response for {sender} - new message received")
            # We don't actually need to cancel the thread - it will check the message time and cancel itself
        
        # Start a new delayed response thread
        debug_print(f"Starting new response thread for {sender}")
        response_thread = threading.Thread(target=delayed_response, args=(sender, incoming_msg))
        response_thread.daemon = True  # Make sure thread doesn't prevent app from exiting
        response_thread.start()
        
        # Store the thread reference
        pending_responses[sender] = response_thread
        
        return "Message received, will respond after delay"
        
    except Exception as e:
        debug_print(f"Error in webhook: {e}")
        import traceback
        traceback.print_exc()
        return "Error processing request", 500

@app.route("/debug", methods=['GET'])
def debug_state():
    return jsonify({
        "conversation_count": len(conversation_history),
        "manual_mode_count": len(manual_mode),
        "first_message_sent_count": len(first_message_sent),
        "pending_responses_count": len(pending_responses),
        "twilio_account_sid": account_sid[-4:] if account_sid else "None",
        "has_twilio_auth": bool(auth_token),
        "has_openai_key": bool(os.environ.get('OPENAI_API_KEY')),
        "response_delay": RESPONSE_DELAY
    })

@app.route("/status", methods=['GET'])
def status():
    return "Bot is running"

with app.app_context():
    load_conversation_history()
    debug_print("Application initialized and ready")

if __name__ == "__main__":
    debug_print("Starting server on port 7000")
    app.run(debug=True, port=7000)
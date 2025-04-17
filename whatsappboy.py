from openai import OpenAI
from twilio.rest import Client
from dotenv import load_dotenv
from flask import Flask, request
import os
import json
import logging

load_dotenv()

# Set up OpenAI client
openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

# Set up Twilio client
account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
twilio_client = Client(account_sid, auth_token)

# Flask app for webhook
app = Flask(__name__)

# Dictionary to store conversation history for each user
conversation_history = {}

# Dictionary to track which conversations are in manual mode
manual_mode = {}

# NEW: Dictionary to track if first message has been sent to each user
first_message_sent = {}

# === IMAGE DICTIONARY START ===
image_library = {
    "2P 60MB promo": {
        "description": "Paquete de 60MB con promoción 3 meses",
        "url": "https://tinyurl.com/ABR-2025-IZZI"
    },
    "3P 200MB promo": {
        "description": "Paquete 3P con 200MB y Apple TV+ incluido",
        "url": "https://tinyurl.com/IZZI-3P-200MB"
    },
    "coverage map": {
        "description": "Mapa de cobertura IZZI",
        "url": "https://tinyurl.com/IZZI-Cobertura"
    }
    # Puedes agregar más imágenes aquí
}

# Your phone number to receive notifications
YOUR_PHONE_NUMBER = 'whatsapp:+527445055734'  # Reemplaza con tu número de WhatsApp

# Secret keyword to toggle manual mode
SECRET_KEYWORD = "CONTROL123"  # Cambia esto a tu palabra clave secreta

# File to persist conversation history
HISTORY_FILE = "conversation_history.json"
MANUAL_MODE_FILE = "manual_mode.json"
FIRST_MESSAGE_FILE = "first_message_sent.json"  # NEW: File to track first message status

# Load existing conversation history from file if it exists
def load_conversation_history():
    global conversation_history, manual_mode, first_message_sent
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as file:
                conversation_history = json.load(file)
        if os.path.exists(MANUAL_MODE_FILE):
            with open(MANUAL_MODE_FILE, 'r') as file:
                manual_mode = json.load(file)
        if os.path.exists(FIRST_MESSAGE_FILE):  # NEW: Load first message status
            with open(FIRST_MESSAGE_FILE, 'r') as file:
                first_message_sent = json.load(file)
    except Exception as e:
        print(f"Error loading data: {e}")
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
        with open(FIRST_MESSAGE_FILE, 'w') as file:  # NEW: Save first message status
            json.dump(first_message_sent, file)
    except Exception as e:
        print(f"Error saving data: {e}")

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.route("/webhook", methods=['POST'])
def webhook():
    # Get incoming message
    incoming_msg = request.values.get('Body', '').strip()
    sender = request.values.get('From', '')
    
    # Check if this is the secret keyword to toggle manual mode
    if incoming_msg == SECRET_KEYWORD:
        print(f"Secret keyword detected from {sender}!")
        # Toggle manual mode for this conversation
        if sender in manual_mode:
            manual_mode[sender] = not manual_mode.get(sender, False)
        else:
            manual_mode[sender] = True
        
        # Notify you that manual mode has been toggled
        notification_msg = f"Manual mode {'ACTIVATED' if manual_mode.get(sender, False) else 'DEACTIVATED'} for {sender}"
        twilio_client.messages.create(
            from_='whatsapp:+14155238886',
            body=notification_msg,
            to=YOUR_PHONE_NUMBER
        )
        
        # Save the updated manual mode status
        save_data()
        
        # Don't respond to the user for the secret keyword
        return "Mode changed"
    
    # If in manual mode, forward this message to you
    if manual_mode.get(sender, False):
        # Forward the message to you
        twilio_client.messages.create(
            from_='whatsapp:+14155238886',
            body=f"Message from {sender}: {incoming_msg}",
            to=YOUR_PHONE_NUMBER
        )
        
        # Add a route to handle your responses
        return "Message forwarded"
    
    # Normal bot mode - continue with existing logic
    
    # System instruction for AI
    system_instruction = """
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
        - **2P (3 meses promoción):** 40MB $399, 60MB $469, 80MB $489, 150MB $559, 200MB $619
        - **3P (6 meses promoción):** 40MB $549, 60MB $649, 80MB $669, 150MB $739, 200MB $799

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
        3. Identifica sus necesidades (velocidad, tipo de uso, número de dispositivos, etc).
        4. Ofrece el paquete más adecuado con precio específico y explica beneficios.
        5. Solicita documentación: INE y comprobante domicilio.
        6. Explica verificación por WhatsApp y código.

        ### Ejemplos de respuestas

        **Pregunta sobre cobertura:**
        "¿En qué colonia vives? Verifico si tenemos cobertura ahí. Asegúrate de que el usuario lo envíe por WhatsApp usando la función de mapa para obtener coordenadas precisas."

        **Pregunta sobre precios:**
        "Tenemos internet desde $399 (40 megas) por 3 meses. El más popular es 60 megas a $469 con internet ilimitado. ¿Qué velocidad necesitas?"

        **Para cerrar venta:**
        "¡Perfecto! Para avanzar, envíame tu INE y comprobante de domicilio al 55 2401 6069. Luego te daré un código para confirmar."

        ### Restricciones
        - No ofrecer servicios fuera de paquetes oficiales
        - Verificar cobertura antes de prometer instalación
        - No compartir precios incorrectos
        - No crear promociones no autorizadas
    """
    
    # NEW: Check if this is a new user or first message
    is_new_user = sender not in conversation_history
    is_first_message = not first_message_sent.get(sender, False)
    
    # Initialize conversation for new users
    if is_new_user:
        conversation_history[sender] = [{"role": "system", "content": system_instruction}]
    
    # NEW: If this is the first message from this user, respond with the specific question
    if is_first_message:
        # Mark that we've sent the first message to this user
        first_message_sent[sender] = True
        
        # Standard first message to always ask
        first_response = "¡Hola! 👋 ¿Actualmente cuenta con una compañía o servicio de internet?"
        
        # Add user message to conversation history
        conversation_history[sender].append({"role": "user", "content": incoming_msg})
        
        # Add our fixed first response to conversation history
        conversation_history[sender].append({"role": "assistant", "content": first_response})
        
        # Save updated conversation history
        save_data()
        
        # Send the fixed first response
        message = twilio_client.messages.create(
            from_='whatsapp:+14155238886',
            body=first_response,
            to=sender
        )
        
        return "First message sent"
    
    # Add user message to conversation history
    conversation_history[sender].append({"role": "user", "content": incoming_msg})
    
    # Limit conversation history to prevent token limit issues (keep last 20 messages)
    if len(conversation_history[sender]) > 21:  # 1 system message + 20 conversation messages
        conversation_history[sender] = [conversation_history[sender][0]] + conversation_history[sender][-20:]
    
    logger.info(f"Conversation with {sender}")
    for msg in conversation_history[sender]:
        role = msg["role"]
        content_preview = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
        logger.info(f"  {role}: {content_preview}")
    
    logger.info("Sending request to OpenAI API...")

    # Get AI response using the conversation history
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=conversation_history[sender]
    )
    
    ai_response = response.choices[0].message.content

    keywords = ["60mb", "200mb", "apple tv", "cobertura"]
    for key, data in image_library.items():
        print("AI Response:", ai_response)
        for kw in keywords:
            if kw in ai_response.lower():
                ai_response += f"\n\n📸 {data['description']}:\n{data['url']}"
                break

    logger.info(f"  assistant response: {ai_response[:100]}..." if len(ai_response) > 100 else ai_response)

    # Add AI response to conversation history
    conversation_history[sender].append({"role": "assistant", "content": ai_response})
    
    # Save updated conversation history
    save_data()
    
    # Send AI response back via WhatsApp
    message = twilio_client.messages.create(
        from_='whatsapp:+14155238886',
        body=ai_response,
        to=sender
    )
    
    return "Message sent"

# Add a new route to handle your responses to forwarded messages
@app.route("/send_manual", methods=['POST'])
def send_manual():
    # This endpoint would be called from a simple web interface where you can respond
    recipient = request.form.get('recipient')
    message_text = request.form.get('message')
    
    # Send your response to the user
    twilio_client.messages.create(
        from_='whatsapp:+14155238886',
        body=message_text,
        to=recipient
    )
    
    return "Manual message sent"

# In newer Flask versions, we handle initialization differently
with app.app_context():
    load_conversation_history()

if __name__ == "__main__":
    app.run(debug=True, port=7000)
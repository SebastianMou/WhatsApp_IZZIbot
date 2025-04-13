import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set your API key properly
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

system_instruction = """
    act like a cool human
"""
prompt = input("Enter something: ")

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": prompt},
    ]
)

print(response.choices[0].message.content)
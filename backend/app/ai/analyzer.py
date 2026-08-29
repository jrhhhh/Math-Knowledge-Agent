import json
import os

from openai import OpenAI
from dotenv import load_dotenv

from app.ai.prompts import SYSTEM_PROMPT


load_dotenv()


client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


def analyze_problem(problem: str):

    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": problem
            }
        ],
        response_format={
            "type": "json_object"
        }
    )

    text = response.choices[0].message.content

    return json.loads(text)
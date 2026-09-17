import json
import os

from openai import OpenAI
from dotenv import load_dotenv

from app.ai.prompts import SYSTEM_PROMPT


load_dotenv()


primary_api_key = os.getenv("DEEPSEEK_API_KEY")
primary_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
primary_model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
try:
    primary_timeout = max(1.0, float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "20")))
except (TypeError, ValueError):
    primary_timeout = 20.0

client = OpenAI(
    api_key=primary_api_key,
    base_url=primary_base_url,
    timeout=primary_timeout,
    max_retries=0,
)

# 可选的 OpenAI 兼容备用服务。未配置时完全不启用，保持现有部署兼容。
backup_api_key = os.getenv("MATH_AGENT_BACKUP_API_KEY")
backup_base_url = os.getenv("MATH_AGENT_BACKUP_BASE_URL")
backup_model = os.getenv("MATH_AGENT_BACKUP_MODEL", "gpt-4o-mini")
backup_client = OpenAI(api_key=backup_api_key, base_url=backup_base_url, timeout=30.0, max_retries=0) if backup_api_key and backup_base_url else None


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

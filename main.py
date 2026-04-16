from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx
import os
import json
from anthropic import Anthropic

app = FastAPI()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

client = Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """
Ты — строгий модератор чата. 
Анализируй сообщение и возвращай ТОЛЬКО JSON без всякого другого текста.

JSON должен быть:
{
  "action": "delete" | "reply" | "nothing",
  "reason": "короткое объяснение на русском",
  "reply_text": "текст ответа, если action=reply"
}

Правила:
- Удаляй спам, рекламу, ссылки на другие каналы, мат, оскорбления
- Удаляй сообщения с криптой, казино, "заработай", "инвестиции"
- На оффтоп можно ответить или ничего не делать
"""

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    print("Получено сообщение:", json.dumps(data, ensure_ascii=False)[:500])

    try:
        message = data.get("message") or data.get("edited_message")
        if not message:
            return JSONResponse({"status": "ok"})

        chat_id = message["chat"]["id"]
        message_id = message["message_id"]
        text = message.get("text") or ""

        # Отправляем в Claude Haiku
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=300,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Сообщение: {text}"}]
        )

        result = json.loads(response.content[0].text.strip())

        if result["action"] == "delete":
            await httpx.AsyncClient().post(f"{TELEGRAM_API}/deleteMessage", json={
                "chat_id": chat_id,
                "message_id": message_id
            })
            print(f"Удалено: {result['reason']}")

        elif result["action"] == "reply" and result.get("reply_text"):
            await httpx.AsyncClient().post(f"{TELEGRAM_API}/sendMessage", json={
                "chat_id": chat_id,
                "text": result["reply_text"],
                "reply_to_message_id": message_id
            })
            print(f"Ответил: {result['reply_text']}")

    except Exception as e:
        print("Ошибка:", str(e))

    return JSONResponse({"status": "ok"})


@app.get("/")
async def root():
    return {"status": "Модератор работает!"}

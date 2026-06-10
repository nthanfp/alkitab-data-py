import json

import httpx

from app.core.config import settings

SYSTEM_PROMPT = """Kamu adalah ahli Alkitab. Kamu menerima teks ayat Alkitab dari pengguna.
Tugasmu: identifikasi referensi Alkitab dari teks tersebut.

Kembalikan JSON dengan format:
{"references": [{"book": "nama kitab", "chapter": angka, "verse": angka}]}

Aturan:
- Kembalikan maksimal 3 referensi, urutkan dari yang paling cocok.
- Gunakan nama kitab lengkap dalam Bahasa Indonesia (contoh: "Yesaya", "Mazmur", "Roma").
- Jika tidak bisa mengidentifikasi, kembalikan {"references": []}.
- JANGAN penjelasan tambahan, hanya JSON murni.
"""


def _parse_json_from_text(text: str) -> list[dict]:
    content = text.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0]

    brace_start = content.find('{')
    brace_end = content.rfind('}')
    if brace_start == -1 or brace_end == -1:
        return []

    json_str = content[brace_start:brace_end + 1]
    try:
        parsed = json.loads(json_str)
        return parsed.get("references", [])
    except json.JSONDecodeError:
        return []


async def extract_references(text: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.LLM_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0.0,
                },
            )
            resp.raise_for_status()
            response_text = resp.text

            try:
                data = json.loads(response_text)
            except json.JSONDecodeError:
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                if start != -1 and end > start:
                    data = json.loads(response_text[start:end])
                else:
                    return []

            message = data.get("choices", [{}])[0].get("message", {})
            content = message.get("content", "")
            if not content:
                content = message.get("reasoning_content", "")

            return _parse_json_from_text(content)
    except Exception:
        return []

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
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            import json
            parsed = json.loads(content)
            return parsed.get("references", [])
    except Exception:
        return []

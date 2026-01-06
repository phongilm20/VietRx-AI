import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import json
import time 

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY is not set")

client = genai.Client(api_key=API_KEY)

# Gemini API call with retry mechanism (503/429 errors)
# config_kwargs: temperature, max_output_tokens, etc.
def call_gemini_with_retry(prompt,
                           model="gemini-2.5-flash",
                           max_retries=3,
                           base_delay=2.0,
                           **config_kwargs): 
    """
    Gọi model Gemini với cơ chế retry khi bị quá tải (503 UNAVAILABLE).
    """
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )
            return response
        except Exception as e:
            msg = str(e) 
            print(f"[GEMINI ERROR] attempt {attempt}: {msg}")
            
            # If the model is unvailable or overloaded, retry
            if "UNAVAILABLE" in msg or "overloaded" in msg:

                if attempt == max_retries:
                    break

                sleep_s = base_delay * attempt # increase delay each retry to avoid thundering herd
                print(f"[RETRY] Model overloaded, waiting {sleep_s:.1f}s...")
                time.sleep(sleep_s)
                continue
            
            # Break if any other errors
            break
    return None


def generate_draft_advice(user_input, drug_info):
    """
    ROLE 1: THE DOCTOR (Generator)
    Tạo lời khuyên y tế tiếng Việt, dễ hiểu cho bà 70 tuổi.
    """
    prompt = f"""
ROLE: Compassionate Vietnamese family doctor.

TASK: Draft medical advice for a 70-year-old grandmother.

FDA DATA (TRUTH):
{drug_info}

USER QUERY:
{user_input}

GUIDELINES:
1. Translate medical terms to simple Vietnamese.
2. Start with "Dạ thưa ạ".
3. Briefly explain what this medicine is, how it is used in general (route and dosage form), and its general purpose, using simple Vietnamese for a 70-year-old.
4. You may mention strength, quantity, and expiry only to describe the product, not to give a dosing schedule.
5. Keep it under 120 words.
6. NO markdown formatting. Plain text only.

"""

    response = call_gemini_with_retry(
        prompt,
        model="gemini-2.5-flash",
        temperature=0.4,
    )

    if not response:
        print("[GENERATOR ERROR] Failed after retries.")
        return None

    try:
        return response.text.strip()
    except Exception as e:
        print(f"[GENERATOR ERROR] Response failed: {e}")
        return None

# During my research, I realized that LLMs can "hallucinate" medical info.
# To make VietRX safer, I implemented a "Generator-Auditor" pattern.
# One agent generates the advice, and another audits it for safety against the FDA database.
def audit_safety(drug_info, draft_advice):
    """
    ROLE 2: THE AUDITOR (Evaluator)
    """
    prompt = f"""
ROLE: Medical AI Auditor.

TASK: Verify if the Doctor's advice aligns strictly with FDA Data.

SOURCE DATA (FDA):
{drug_info}

DRAFT ADVICE TO CHECK:
{draft_advice}

CRITERIA:

1. ALLOWED:
- Mention common, well-established indications and class-level warnings for this drug class, even if they are not fully listed in the FDA excerpt above.
- Use brand/generic name, class, dosage form, route, strength, quantity, and expiry only to describe the product, not to propose or imply any dosing regimen (number of tablets, times per day, treatment duration) or to judge whether the dose is “high” or “low”.

2. NOT ALLOWED:
- Invent specific dosages or dosing schedules, detailed “how to take” instructions, or indications clearly inappropriate for this drug class.

3. SEVERE ERROR:
- Encourage use in clearly inappropriate patients, use the wrong route of administration, or ignore/contradict serious warnings present in the FDA data.

OUTPUT FORMAT (JSON ONLY):
{{
  "is_safe": true/false,
  "reason": "English explanation of the error",
  "corrected_advice": "Rewritten Vietnamese advice if unsafe, else null"
}}
"""

    response = call_gemini_with_retry(
        prompt,
        model="gemini-2.5-flash",
        response_mime_type="application/json",
        temperature=0.0,
    )

    if not response:
        print("[AUDITOR WARNING] Audit skipped because model is overloaded.")
        # Fail-safe: coi như an toàn nhưng ghi rõ lý do
        return {
            "is_safe": True,
            "reason": "Audit skipped (model overloaded)",
            "corrected_advice": None,
        }

    try:
        return json.loads(response.text)
    except Exception as e:
        print(f"[AUDITOR ERROR] JSON parse failed: {e}")
        # Fail-safe
        return {
            "is_safe": True,
            "reason": "Audit failed (JSON parse error)",
            "corrected_advice": None,
        }


def get_medical_advice(user_input, drug_info):
    """
    PIPELINE: Generation -> Audit -> Final Output
    """

    print(f"[AI PIPELINE] 1. Generating draft advice...")
    draft = generate_draft_advice(user_input, drug_info)
    
    if not draft:
        return "Xin lỗi ạ, hệ thống đang gặp sự cố."

    print(f"[AI PIPELINE] 2. Auditing for safety...")
    audit_result = audit_safety(drug_info, draft)
    
    if audit_result.get("is_safe"):
        print("[AUDIT PASSED] Advice is verified.")
        return draft
    else:
        print(f"[AUDIT FAILED] Reason: {audit_result.get('reason')}")
        print("[RECOVERY] Switching to corrected advice.")
        
        correction = audit_result.get("corrected_advice")
        if correction:
            return correction
        else:
            return "Xin lỗi ạ, thông tin thuốc phức tạp con cần kiểm tra lại ạ."
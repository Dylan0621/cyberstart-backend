from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import json
# import google.generativeai as genai  ← COMENTADO, era Gemini
from openai import OpenAI
from dotenv import load_dotenv
from supabase import create_client, Client
from pydantic import BaseModel



load_dotenv()
# genai.configure(api_key=os.getenv('GEMINI_API_KEY'))  ← COMENTADO

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()


# --- CURRICULUM DB (Single Source of Truth) ---
CURRICULUM_DB = {
    "boot_process": """
    Tema: El Proceso de Arranque (Boot Process). 
    Secuencia estricta: 1. Electricidad a tarjeta madre. 2. Firmware (UEFI en PC, PBL en Android, Secure ROM en iPhone). 3. POST. 4. Búsqueda de SO en disco. 5. CPU ejecuta instrucciones. 6. Kernel carga en RAM.
    Conceptos: Señal eléctrica a binario (bits). Kernel como intermediario crítico.
    """,
    "memory_hierarchy": """
    Tema: Jerarquía de Memoria.
    Secuencia de velocidad (rápido a lento): 1. Registros de CPU. 2. Memoria Caché (L1/L2/L3). 3. Memoria RAM. 4. Almacenamiento SSD/HDD. 5. Almacenamiento en Nube.
    Conceptos: Volatilidad (RAM es volátil, SSD es persistente). Latencia (distancia física a la CPU determina la velocidad). Cache Hit vs Cache Miss.
    """
}

origins = [
    "http://localhost:5173",
    "https://cyberstart-frontend.pages.dev"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "cyberstart-core"}

@app.get("/api/curriculum")
def get_curriculum():
    # Retorna la lista dinámica de lecciones disponibles en el backend
    return [
        {
            "id": "boot_process", 
            "title": "Lección 1: El Proceso de Arranque", 
            "description": "Secuencia determinista de hardware a software."
        },
        {
            "id": "memory_hierarchy", 
            "title": "Lección 2: Jerarquía de Memoria", 
            "description": "Latencia, RAM, Caché y almacenamiento persistente."
        }
    ]

@app.get("/api/lessons/{lesson_id}")
def get_lesson(lesson_id: str):
    context_data = CURRICULUM_DB.get(lesson_id, f"Tema genérico: {lesson_id}")
    system_prompt = f'''Eres un Senior Software Engineer. Genera una lección estructurada en JSON estricto basada EXCLUSIVAMENTE en este contenido:
    {context_data}
    El JSON devuelto DEBE cumplir exactamente esta estructura de claves y arrays (recreando el formato de este Data Schema):
    {{
      "course": "Fundamentos de Ingeniería de Software",
      "lesson": "Lección 1: El Proceso de Arranque",
      "completion_message": "String (Párrafo de felicitación resumiendo lo aprendido en este tema exacto)",
      "completion_tags": ["String (tag_1)", "String (tag_2)", "String (tag_3)"],
      "nodes": [
        {{
          "id": "node_0",
          "type": "context",
          "ui": "Character Dialogue / Intro Card",
          "visual": "mentor_avatar_engineer",
          "mentor_message": "String (explicación del mentor)",
          "learning_objective": "String",
          "cta": "Iniciar Diagnóstico",
          "next": "exercise_1_1"
        }},
        {{
          "id": "exercise_1_1",
          "type": "ordering",
          "concept_tag": "boot_sequence_flow",
          "prompt": "String (instrucción del ejercicio)",
          "items": [
            {{"id": "s1", "label": "String (paso de la secuencia)", "correct_pos": 1}}
          ],
          "feedback": {{"correct": "String", "incorrect": "String"}},
          "next": "exercise_1_2"
        }},
        {{
          "id": "exercise_1_2",
          "type": "fill_blanks",
          "concept_tag": "platform_firmware_discrimination",
          "prompt": "String",
          "sentences": [
            {{
              "id": "b1",
              "before": "String (texto antes del espacio)",
              "blank_id": "fw_pc",
              "after": "String (texto después del espacio)",
              "options": ["Op1", "Op2", "Op3", "Op4"],
              "answer": "Op1"
            }}
          ],
          "feedback": {{"correct": "String", "incorrect": "String"}}
        }}
      ]
    }}
    Importante: Genera exactamente 6 items para 'ordering' y 5 sentences para 'fill_blanks'.
    '''
    
    try:
        # 2. Llamada a Groq (mismo SDK que OpenAI)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Genera el JSON estricto para esta lección."}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        raw_text = response.choices[0].message.content.strip()
        
        # 3. Sanitización de JSON (Evitar crashes por Markdown)
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:-3].strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:-3].strip()
            
        # 4. Retornar el diccionario limpio
        return json.loads(raw_text)
        
    except Exception as e:
        print(f"Error AI/Parsing: {str(e)}") # Log en consola para debugging
        raise HTTPException(status_code=500, detail="Fallo en generación de IA o Parsing")

# Data Schema
class ProgressPayload(BaseModel):
    user_id: str
    lesson_id: str

# Progress Endpoint
@app.post("/api/progress")
def save_progress(payload: ProgressPayload):
    try:
        response = supabase.table("user_progress").upsert(
    {
        "user_id": payload.user_id,
        "lesson_id": payload.lesson_id
    },
    on_conflict="user_id,lesson_id"
    ).execute()
        return {"status": "success", "data": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/progress/{user_id}")
def get_user_progress(user_id: str):
    try:
        # Select solo la columna lesson_id para ser eficientes
        response = supabase.table("user_progress").select("lesson_id").eq("user_id", user_id).execute()
        
        # Transformar la respuesta de Supabase [{'lesson_id': 'X'}, ...] a una lista simple ['X', ...]
        return [row['lesson_id'] for row in response.data]
    except Exception as e:
        print(f"Error fetching progress: {e}")
        return []
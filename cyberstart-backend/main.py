from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

model = genai.GenerativeModel(
    'gemini-2.5-flash',
    generation_config={'response_mime_type': 'application/json'}
)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "cyberstart-core"}

@app.get("/api/lessons/{lesson_id}")
def get_lesson(lesson_id: str):
    system_prompt = f'''Eres un instructor experto en Software Engineering. Genera una lección estructurada en JSON. Tema basado en el ID: {lesson_id}. El JSON debe tener esta estructura estricta: un "id" (string), un "title" (string), y un array "exercises". Genera exactamente 2 ejercicios: el primero type "ordering" y el segundo type "fill_in_blank". Cada ejercicio requiere las claves: "id", "type", "prompt", "correctAnswer" (array para ordering, string para fill_in_blank), "options" (array, SÓLO para ordering), "mentor" (elige "Levi" o "Any"), y "feedback".'''
    
    try:
        response = model.generate_content(system_prompt)
        return json.loads(response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

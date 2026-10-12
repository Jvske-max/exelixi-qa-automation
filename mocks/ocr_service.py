import asyncio

from fastapi import FastAPI, HTTPException

app = FastAPI()

@app.post('/ocr/extraer')
async def extraccion_exitosa():
    # Caso feliz: documento legible, datos completos
    return {'cedula': 'V-12345678', 'nombre': 'Usuario Prueba', 'confianza': 0.97}

@app.post('/ocr/extraer/ilegible')
async def documento_ilegible():
    # Simula un documento borroso o mal escaneado
    raise HTTPException(status_code=422, detail='No se pudo extraer texto del documento')

@app.post('/ocr/extraer/timeout')
async def proveedor_lento():
    # Simula al proveedor de OCR real respondiendo tarde
    await asyncio.sleep(10)
    return {'cedula': None}

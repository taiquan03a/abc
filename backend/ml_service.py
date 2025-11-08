"""
ML Service Mock: YOLO, ArcFace, OCR endpoints
Trong production sẽ gọi real ML inference service
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Optional
import base64
import json

router = APIRouter(prefix="/ml", tags=["ml"])


@router.post("/face/detect")
async def detect_faces(image_data: dict):
    """
    Face detection (YOLO/SCRFD mock)
    Input: {image: base64 or url}
    Output: {faces: [{bbox, confidence}], count: int}
    """
    # Mock: return 1-2 faces randomly
    import random
    count = random.choice([1, 1, 1, 2])  # mostly 1, sometimes 2
    faces = []
    for i in range(count):
        faces.append({
            "bbox": [100 + i*50, 100 + i*50, 200 + i*50, 200 + i*50],
            "confidence": 0.85 + random.random() * 0.1
        })
    return {"faces": faces, "count": count}


@router.post("/face/embed")
async def face_embedding(image_data: dict):
    """
    ArcFace embedding extraction
    Input: {image: base64}
    Output: {embedding: [512-dim vector], norm: float}
    """
    # Mock: return random normalized vector
    import random
    embedding = [random.gauss(0, 0.1) for _ in range(512)]
    norm = sum(x*x for x in embedding) ** 0.5
    normalized = [x/norm for x in embedding]
    return {"embedding": normalized, "norm": norm}


@router.post("/face/match")
async def face_match(data: dict):
    """
    Face matching (cosine similarity)
    Input: {embedding1: [...], embedding2: [...]}
    Output: {similarity: float, match: bool}
    """
    # Mock: compute cosine similarity
    e1 = data.get("embedding1", [])
    e2 = data.get("embedding2", [])
    if not e1 or not e2 or len(e1) != len(e2):
        raise HTTPException(400, "Invalid embeddings")
    
    dot = sum(a*b for a, b in zip(e1, e2))
    similarity = min(1.0, max(0.0, dot))  # cosine for normalized vectors
    threshold = data.get("threshold", 0.45)
    
    return {
        "similarity": similarity,
        "match": similarity >= threshold,
        "threshold": threshold
    }


@router.post("/face/liveness")
async def liveness_check(image_data: dict):
    """
    Liveness detection (active/passive)
    Input: {image: base64, type: "active"|"passive"}
    Output: {score: float, passed: bool}
    """
    # Mock: return high score
    import random
    score = 0.90 + random.random() * 0.08
    return {"score": score, "passed": score > 0.85}


@router.post("/object/detect")
async def detect_objects(image_data: dict):
    """
    YOLO object detection: headphone, phone, book, monitor
    Input: {image: base64}
    Output: {objects: [{class, bbox, confidence}]}
    """
    # Mock: rarely detect objects
    import random
    objects = []
    if random.random() < 0.1:  # 10% chance
        classes = ["headphone", "phone", "book", "monitor"]
        obj_class = random.choice(classes)
        objects.append({
            "class": obj_class,
            "bbox": [50, 50, 150, 150],
            "confidence": 0.7 + random.random() * 0.2
        })
    return {"objects": objects}


@router.post("/ocr/scan")
async def ocr_scan(image_data: dict):
    """
    OCR màn hình - detect từ khóa cấm
    Input: {image: base64, blacklist: [str]}
    Output: {text: str, matches: [str]}
    """
    # Mock: return some text, check blacklist
    blacklist = image_data.get("blacklist", ["cheat", "answer", "google"])
    # Mock text
    mock_text = "This is a sample screen content. No violations detected."
    # Sometimes add blacklist word
    import random
    if random.random() < 0.2:
        mock_text += " " + random.choice(blacklist)
    
    matches = [word for word in blacklist if word.lower() in mock_text.lower()]
    return {"text": mock_text, "matches": matches}


@router.post("/audio/vad")
async def voice_activity_detection(audio_data: dict):
    """
    Voice Activity Detection
    Input: {audio: base64, duration_ms: int}
    Output: {speaking: bool, energy: float, speakers: int}
    """
    # Mock: detect speaking
    import random
    speaking = random.random() > 0.3
    energy = random.random() * 0.1 if speaking else random.random() * 0.02
    speakers = 2 if energy > 0.05 and random.random() < 0.1 else 1
    return {
        "speaking": speaking,
        "energy": energy,
        "speakers": speakers
    }


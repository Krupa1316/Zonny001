from fastapi import FastAPI
from models import StopwatchModel
import json

app = FastAPI()
stopwatch_model = None

@app.post("/start")
async def start(data: dict):
    global stopwatch_model
    if not stopwatch_model:
        stopwatch_model = StopwatchModel(**data)
    return {"message": "Stopwatch started"}

@app.get("/lap")
def lap():
    global stopwatch_model
    if stopwatch_model:
        stopwatch_model.laps += 1
        return {"message": f"Lap recorded, total laps: {stopwatch_model.laps}"}
    else:
        return {"message": "Stopwatch not started"}
    
@app.get("/current")
def current():
    global stopwatch_model
    if stopwatch_model:
        return {"elapsedMs": stopwatch_model.elapsedMs, "laps": stopwatch_model.laps}
    else:
        return {"message": "Stopwatch not started"}
    
@app.post("/export")
async def export(data: dict):
    global stopwatch_model
    if stopwatch_model:
        with open("stopwatch_export.json", "w") as file:
            json.dump(data, file)
        return {"message": f"Data exported to {file.name}"}
    else:
        return {"message": "Stopwatch not started"}
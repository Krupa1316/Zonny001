from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

app = FastAPI()

class TimerData(BaseModel):
    start_time: int
    end_time: int

@app.post("/timer/")
async def create_item(data: TimerData):
    elapsed_time = data.end_time - data.start_time
    return {"elapsed_time": elapsed_time}
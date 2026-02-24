from pydantic import BaseModel

class StopwatchModel(BaseModel):
    elapsedMs: int = 0
    laps: int = 0
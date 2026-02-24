from pydantic import BaseModel

class TimerData(BaseModel):
    start_time: int
    end_time: int
```

To run the server, you can use the following command:
```bash
uvicorn main:app --reload
```
This will start the FastAPI server with hot reloading enabled. The server will be accessible at `http://localhost:8000`. You can test it by sending a POST request to `http://localhost:8000/timer/` with JSON data in the body like this:
```json
{
    "start_time": 1647323495,
    "end_time": 1647324123
}
```
This will return a response that contains the elapsed time in seconds.
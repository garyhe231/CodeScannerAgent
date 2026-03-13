#!/usr/bin/env python3
"""Launch the Code Scanner Agent."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8008, reload=True)

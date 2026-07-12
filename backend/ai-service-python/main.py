"""Entry point for the AI service.

The documented command is `uvicorn app:app --port 8000`; running `python main.py`
does the same, reading PORT from the environment for convenience.
"""
import os


def main() -> None:
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))


if __name__ == "__main__":
    main()

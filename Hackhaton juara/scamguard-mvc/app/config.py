import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    VIRUSTOTAL_API_KEY = os.getenv("VIRUSTOTAL_API_KEY", "")  # simpan di .env, jangan di-commit

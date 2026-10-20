import os
import sys

# Tambahkan direktori backend ke sys.path agar modul 'app' dapat langsung diimpor
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Import FastAPI instance dari app.main
from app.main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Memulai FarmaSigap pada port {port}...")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

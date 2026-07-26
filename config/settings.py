from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PROJECT_NAME = os.getenv("PROJECT_NAME", "EcoPilot")

ENERGYPLUS_HOME = Path(os.getenv("ENERGYPLUS_HOME", ""))
ENERGYPLUS_EXE = Path(os.getenv("ENERGYPLUS_EXE", ""))

_idd_path_env = os.getenv("IDD_PATH", "").strip()
IDD_PATH = Path(_idd_path_env) if _idd_path_env else (ENERGYPLUS_HOME / "Energy+.idd")

BASELINE_IDF = PROJECT_ROOT / "energyplus" / "baseline" / "building.idf"
WEATHER_FILE = PROJECT_ROOT / "energyplus" / "weather" / "weather.epw"

MODELS_DIR = PROJECT_ROOT / "energyplus" / "models"
OUTPUT_DIR = PROJECT_ROOT / "energyplus" / "outputs"

# Where the dashboard's Setup page saves uploaded .idf/.epw files.
UPLOADED_MODELS_DIR = MODELS_DIR / "uploaded"
UPLOADED_WEATHER_DIR = WEATHER_FILE.parent / "uploaded"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

MAX_OPTIMIZATION_CYCLES = int(os.getenv("MAX_OPTIMIZATION_CYCLES", 10))
SIMULATION_TIMEOUT = int(os.getenv("SIMULATION_TIMEOUT", 600))

STREAMLIT_PORT = int(os.getenv("STREAMLIT_PORT", 8501))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOGS_DIR = PROJECT_ROOT / "logs"

FAISS_INDEX_PATH = PROJECT_ROOT / os.getenv("FAISS_INDEX_PATH", "memory/faiss_index")
KNOWLEDGE_PATH = PROJECT_ROOT / os.getenv("KNOWLEDGE_PATH", "knowledge/processed")

REPORTS_DIR = PROJECT_ROOT / "reports"
MEMORY_DIR = PROJECT_ROOT / "memory"

EXPERIENCE_MEMORY_PATH = MEMORY_DIR / os.getenv("EXPERIENCE_MEMORY_FILE", "experiences.json")
CARBON_INTENSITY_PROFILE_PATH = PROJECT_ROOT / os.getenv(
    "CARBON_INTENSITY_PROFILE_PATH", "config/carbon_intensity.json"
)
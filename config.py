from pathlib import Path

# Default paths - use cleaned data
# Use pathlib for robust cross-platform path resolution
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / 'clean_data'

# Convert to string for compatibility with existing code that expects strings (e.g. .endswith)
DISTANCES_FILE = str(DATA_DIR / 'df_ matriz_distancias.parquet')
EXISTING_SITES_FILE = str(DATA_DIR / 'df_campi_existentes.parquet')
DEMAND_FILE = str(DATA_DIR / 'df_populacao_idade_escolar.parquet')
COORDS_FILE = str(DATA_DIR / 'municipios.parquet')

# Default parameters
P = 5                   # Number of new sites
S_DISTANCE = 100.0          # Max coverage radius (km)
S_TIME = 1.0               # Max coverage time (hours)
USE_DISTANCE_KM = True     # True for km, False for time
TARGET_UF = 'MG'           # 'MG' (Minas Gerais) | None = Brazil
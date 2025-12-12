import sys
import os
import pandas as pd
import numpy as np
import importlib.util
import time

# Paths
BASE_DIR = r"H:\Meu Drive\Mestrado MMC Cefet-MG\Heurísticas Computacionais\Implementação Heurística\github_files"
DATA_DIR = os.path.join(BASE_DIR, "clean_data")
FILE_1_PATH = r"H:\Meu Drive\Mestrado MMC Cefet-MG\Heurísticas Computacionais\Implementação Heurística\github_files\heuristics.py"
FILE_2_PATH = r"C:\Users\matheus.frade\Documents\Python Scripts\mclp-rfept\heuristics.py"

def load_module_from_path(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

print("Loading Data...")
# Load Data
dist_path = os.path.join(DATA_DIR, "df_ matriz_distancias.parquet")
pop_path = os.path.join(DATA_DIR, "df_populacao_idade_escolar.parquet")
campi_path = os.path.join(DATA_DIR, "df_campi_existentes.parquet")

df_dist = pd.read_parquet(dist_path)
df_pop = pd.read_parquet(pop_path)
df_campi = pd.read_parquet(campi_path)

# Prepare Dictionaries
demand_dict = df_pop.set_index('ibge')['populacao'].to_dict()
all_nodes = list(demand_dict.keys())
existing_campi = set(df_campi['ibge'].unique())

# Ensure all existing campi are in demand dict (if valid)
existing_campi = {c for c in existing_campi if c in demand_dict}
candidates = [c for c in all_nodes] # All nodes are candidates

MAX_DIST = 100
P = 100

print(f"Data Loaded. Nodes: {len(all_nodes)}, Candidates: {len(candidates)}, Existing: {len(existing_campi)}")

# Load Heuristics Modules
print("Importing Heuristics Modules...")
h1 = load_module_from_path("heuristics_github", FILE_1_PATH)
h2 = load_module_from_path("heuristics_local", FILE_2_PATH)

print("\n--- Testing H1 (Github) ---")
print("Building Structures H1...")
# Note: h1 has use_km argument, h2 might not or has different signature logic?
# Checking signatures:
# H1: build_sparse_matrix_from_df(distance_df, demand_dict, candidates, all_demand_nodes, max_dist, max_time, use_km=True, pre_covered_nodes=None)
# H2: build_sparse_structures(coverage_map, ...) -> Wait, H2 needs coverage map first? Or does it have separate function?
# H2 has build_sparse_structures but it takes coverage_map. H1 has ALSO build_sparse_structures AND build_sparse_matrix_from_df.
# Let's use build_coverage_map first for both to be fair and comparable, as H2 seems to rely on it.
# H1 build_coverage_map(distance_df, max_dist, max_time, use_km=True, candidates=None)
# H2 build_coverage_map(distance_df, max_dist, max_time, use_km=True, candidates=None)

# Build Coverage Map Common to keep input identical? No, let them build their own to check internal logic.
t0 = time.time()
cov_map_1 = h1.build_coverage_map(df_dist, MAX_DIST, float('inf'), use_km=True, candidates=candidates)
print(f"H1 Coverage Map Built in {time.time()-t0:.2f}s")

t0 = time.time()
cov_map_2 = h2.build_coverage_map(df_dist, MAX_DIST, float('inf'), use_km=True, candidates=candidates)
print(f"H2 Coverage Map Built in {time.time()-t0:.2f}s")

# Check if coverage maps are identical
print(f"Comparing Coverage Maps...")
map_diff = False
keys1 = set(cov_map_1.keys())
keys2 = set(cov_map_2.keys())
if keys1 != keys2:
    print(f"DIFFERENT KEYS! H1: {len(keys1)}, H2: {len(keys2)}")
    map_diff = True
else:
    for k in keys1:
        if cov_map_1[k] != cov_map_2[k]:
            print(f"DIFFERENCE at key {k}")
            map_diff = True
            break
if not map_diff:
    print("Coverage Maps are IDENTICAL.")

# Test Z Calculation on Empty Solution (Baseline)
# calculate_z(solution, coverage_map, demand_dict, pre_covered_nodes)
z1_base = h1.calculate_z([], cov_map_1, demand_dict, existing_campi)
z2_base = h2.calculate_z([], cov_map_2, demand_dict, existing_campi)
print(f"Baseline Z (No new units): H1={z1_base:,.0f}, H2={z2_base:,.0f}")

if z1_base != z2_base:
    print("CRITICAL: Baseline Z calculation mismatch!")

# Run VNS with SAME PARAMETERS
# vns(initial_solution, candidates, coverage_map, demand_dict, pre_covered_nodes, k_max=10, max_iter=5000, max_no_improv=500, max_time_seconds=300, ls_strategy='best', progress_callback=None, sparse_structures=None)
# vns(initial_solution, candidates, coverage_map, demand_dict, pre_covered_nodes, k_max=8, max_iter=100, max_no_improv=None, progress_callback=None)

# I will use a minimal config for speed, but large enough to diverge if logic differs.
VNS_ITER = 20
K_MAX = 3
INITIAL_SOL = [] 

print(f"\nRunning VNS with MATCHED parameters: Iter={VNS_ITER}, K={K_MAX}")

# H1 Call
# Note: H1 VNS signature has extra args (max_time_seconds, ls_strategy, sparse_structures)
t0 = time.time()
sol1, val1 = h1.vns(
    INITIAL_SOL, candidates, cov_map_1, demand_dict, existing_campi,
    k_max=K_MAX, max_iter=VNS_ITER, max_no_improv=VNS_ITER, max_time_seconds=300, ls_strategy='first'
)
print(f"H1 Result: Z={val1:,.0f}, Len={len(sol1)}, Time={time.time()-t0:.2f}s")

# H2 Call
# Note: H2 VNS signature: vns(initial_solution, candidates, coverage_map, demand_dict, pre_covered_nodes, k_max=8, max_iter=100, max_no_improv=None, progress_callback=None)
# And H2 VNS hardcodes ls_strategy='first' inside, but let's check.
t0 = time.time()
sol2, val2 = h2.vns(
    INITIAL_SOL, candidates, cov_map_2, demand_dict, existing_campi,
    k_max=K_MAX, max_iter=VNS_ITER, max_no_improv=VNS_ITER
)
print(f"H2 Result: Z={val2:,.0f}, Len={len(sol2)}, Time={time.time()-t0:.2f}s")

# Check Local Search explicitly
print("\nComparing Local Search Step explicitly...")
# Create a dummy solution
dummy_sol = candidates[:10] 
# Calculate Z for dummy
z1_dummy = h1.calculate_z(dummy_sol, cov_map_1, demand_dict, existing_campi)
z2_dummy = h2.calculate_z(dummy_sol, cov_map_2, demand_dict, existing_campi)
print(f"Dummy Sol Z: H1={z1_dummy:,.0f}, H2={z2_dummy:,.0f}")

# Manually build sparse for LS test
s1_sparse = h1.build_sparse_structures(cov_map_1, demand_dict, candidates, all_nodes, existing_campi)
s2_sparse = h2.build_sparse_structures(cov_map_2, demand_dict, candidates, all_nodes, existing_campi)

# Run LS
# local_search_sparse(solution, candidates, cov_matrix_sparse, demand_vector, cand_to_idx, initial_coverage, max_iter=1000, strategy='first', show_progress=False, progress_callback=None)
# H1 signature: local_search_sparse(... max_iter=1000, strategy='first' ...)
# H2 signature: local_search(... max_iter=10000, strategy='first' ...) -> note input names differ? No, H2 local_search takes cov_matrix_sparse.
ls1_sol, ls1_z = h1.local_search_sparse(dummy_sol, candidates, s1_sparse[0], s1_sparse[1], s1_sparse[2], s1_sparse[4], max_iter=50, strategy='first')
ls2_sol, ls2_z = h2.local_search(dummy_sol, candidates, s2_sparse[0], s2_sparse[1], s2_sparse[2], s2_sparse[4], max_iter=50, strategy='first')

print(f"LS Result H1: Z={ls1_z:,.0f}")
print(f"LS Result H2: Z={ls2_z:,.0f}")

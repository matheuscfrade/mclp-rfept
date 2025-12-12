import pandas as pd
import os
import geopandas as gpd
import streamlit as st
from pathlib import Path
import gdown

# --- CONFIGURAÇÃO DE DOWNLOAD DO GOOGLE DRIVE ---

GDRIVE_FILE_IDS = {
    'BR_Municipios_2024.shp': '15dlkV4afTnd7OTKJeWyzaVO7XPymasp6', 
    'BR_Municipios_2024.shx': '1paVS7mJrrCLctUCFCUuWgz1zgZEp7p4P', 
    'BR_Municipios_2024.dbf': '1u5TYDCIpF5nZsNQS8l7RY3E30jO-GhF8', 
    'BR_Municipios_2024.cpg': '1jkdJ1f5aCybnZ7m5A-7bFn7qFAp3jhE_', 
    'BR_Municipios_2024.prj': '1jb3MaRdHCmg9186qKd4JfGTGxp4h79ib',
    'BR_Municipios_Simplified.cpg': '1VsUPgHefWCTPIRivBSYAWL6sUwnjUNV-',
    'BR_Municipios_Simplified.dbf': '1z2Nw1wuntPpnY2F6Y2JRyq7XiWqY6J_C',
    'BR_Municipios_Simplified.prj': '1W54Phs4ciH09DEv8WKiaEiMzbgDRapKL',
    'BR_Municipios_Simplified.shp': '1eU818GkbM2ITw3NLxAaoc3T9NAwZliQg',
    'BR_Municipios_Simplified.shx': '1hGPOMUrcDZblP7HxxWLnujJIeuu4L71v',
    'df_ matriz_distancias.parquet': '1DbHOFJ5RE-kc534PflH_bX-yHKQzNgiD',
    'df_campi_existentes.parquet': '1SxrL6y5nPJKS9SnFwvGQmWFeZ33HMY_E',
    'df_populacao_idade_escolar.parquet': '1GqBOZbMvjcDe5mxpeD4ccNSOqpsPRVvg',
    'municipios.parquet': '1sFdSnamM9_KDnCFmbV8vZuOpcew2ddII'
}

def ensure_file_from_drive(filepath):
    """
    Verifica se o arquivo existe e é válido. Se for um ponteiro LFS ou não existir,
    tenta baixar do Google Drive usando o ID configurado.
    """
    path = Path(filepath)
    filename = path.name
    
    # Se o arquivo existe e NÃO é um ponteiro LFS, ok.
    if path.exists() and not is_lfs_pointer(filepath):
        return True
        
    # Se chegamos aqui, precisamos baixar
    file_id = GDRIVE_FILE_IDS.get(filename)
    
    if not file_id:
        # Tenta verificar se é um arquivo auxiliar de shapefile (.shx, .dbf...) e se temos o ID dele
        pass 
        
    if not file_id:
        print(f"⚠️ Aviso: ID do Google Drive não configurado para '{filename}'. Não é possível baixar automaticamente.")
        return False
        
    url = f'https://drive.google.com/uc?id={file_id}'
    output = str(filepath)
    
    # Cria diretório se não existir
    path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"⬇️ Baixando {filename} do Google Drive...")
    try:
        gdown.download(url, output, quiet=False)
        # Verifica se baixou algo válido
        if path.exists() and path.stat().st_size > 1000:
            return True
    except Exception as e:
        print(f"❌ Falha ao baixar {filename}: {e}")
        
    return False


def is_lfs_pointer(filepath):
    """
    Verifica se um arquivo é um ponteiro Git LFS.
    """
    try:
        # Ponteiros LFS são arquivos de texto pequenos (geralmente < 200 bytes)
        # começando com "version https://git-lfs.github.com/spec/v1"
        if os.path.getsize(filepath) > 1024:
            return False
            
        with open(filepath, 'rb') as f:
            header = f.read(100)
            if b'version https://git-lfs.github.com/spec/v1' in header:
                return True
    except Exception:
        pass
    return False

def handle_lfs_error(filepath):
    """
    Exibe uma mensagem de erro útil para arquivos de ponteiro LFS e interrompe a execução.
    """
    display_lfs_error_ui(filepath)
    st.stop()

def display_lfs_error_ui(filepath):
    st.error(f"""
    ⚠️ **Arquivo de dados ausente ou inválido (LFS Pointer)**
    
    O arquivo `{filepath}` não foi encontrado ou é apenas um atalho do Git LFS.
    
    **Solução Automática:**
    O sistema tentou baixar do Google Drive mas falhou. Verifique se os IDs estão corretos em `data_loader.py`.
    
    **Solução Manual:**
    1. Baixe os dados manualmente da pasta de dados do projeto no Google Drive ou Repo.
    2. Substitua os arquivos na pasta `clean_data`.
    """)

def check_and_debug_path(filepath):
    """
    Verifica se um arquivo existe. Se não, imprime/registra informações de depuração sobre o diretório.
    """
    path = Path(filepath)
    
    # Tentativa de Auto-Correção (Download)
    if not path.exists() or is_lfs_pointer(filepath):
        if ensure_file_from_drive(filepath):
            return True # Sucesso no download
            
    if not path.exists():
        error_msg = f"❌ ARQUIVO NÃO ENCONTRADO: {filepath}"
        print(error_msg)
        st.error(error_msg)
        display_lfs_error_ui(filepath)
        
        # Debug info
        parent = path.parent
        if parent.exists():
            st.write(f"📂 Conteúdo da pasta '{parent}':")
            try:
                files = [f.name for f in parent.iterdir()]
                st.write(files)
                print(f"Contents of {parent}: {files}")
            except Exception as e:
                st.write(f"Erro ao listar pasta: {e}")
        else:
            st.error(f"❌ A pasta pai também não existe: {parent}")
            # Tentar listar diretório atual de trabalho
            cwd = Path.cwd()
            st.write(f"📂 Conteúdo do diretório atual ({cwd}):")
            try:
                files = [f.name for f in cwd.iterdir()]
                st.write(files)
            except Exception as e:
                st.write(f"Erro ao listar CWD: {e}")
        return False
    return True

def load_distances(filepath, uf_filter=None):
    """
    Carrega a matriz de distâncias de CSV ou Parquet.
    Retorna um DataFrame com colunas ['origem', 'destino', 'distancia', 'tempo'].
    Otimizado para ler em chunks (CSV) ou usar poda de colunas (Parquet).
    """
    if not check_and_debug_path(filepath):
        # Retorna dataframe vazio para evitar quebra, mas erro já é mostrado
        return pd.DataFrame(columns=['origem', 'destino', 'distancia', 'tempo'])

    if is_lfs_pointer(filepath):
        handle_lfs_error(filepath)

    print(f"Carregando distâncias de {filepath}...")
    
    # Verificar extensão do arquivo
    _, ext = os.path.splitext(filepath)
    
    if ext.lower() == '.parquet':
        # Carregar arquivo Parquet - OTIMIZADO PARA MEMÓRIA
        # Carregar apenas colunas necessárias.
        cols_to_load = ['origem', 'destino', 'distancia', 'tempo']
        
        # Verificar se colunas existem
        
        try:
            df = pd.read_parquet(filepath, columns=cols_to_load)
        except Exception as e:
            print(f"Erro ao carregar colunas específicas: {e}. Tentando carga completa...")
            df = pd.read_parquet(filepath)

        # Renomear colunas se necessário (suporte legado)
        rename_map = {}
        if 'origem_cod' in df.columns: rename_map['origem_cod'] = 'origem'
        if 'destino_cod' in df.columns: rename_map['destino_cod'] = 'destino'
        
        if rename_map:
            df = df.rename(columns=rename_map)
            
        # Filtrar por UF se solicitado
        if uf_filter:
            uf_str = str(uf_filter)
            # ... logica de filtro ...
            # Como não carregamos colunas de UF, devemos confiar nos prefixos de ID
            if uf_str.isdigit():
                 mask_orig = df['origem'].astype(str).str.zfill(7).str[:2] == uf_str
                 mask_dest = df['destino'].astype(str).str.zfill(7).str[:2] == uf_str
                 df = df[mask_orig & mask_dest]
            else:
                # Se filtro UF é 'MG' mas não carregamos 'origem_uf', não podemos filtrar facilmente a menos que inferimos do ID.
                pass 
                
        # Manter apenas colunas necessárias (redundante se carregamos apenas elas, mas seguro)
        cols_to_keep = ['origem', 'destino', 'distancia', 'tempo']
        cols_to_keep = [c for c in cols_to_keep if c in df.columns]
        df = df[cols_to_keep]
        
        print(f"Carregados {len(df)} pares de distância do Parquet.")
        return df

    # Lógica de Carregamento CSV (Existente)
    chunks = []
    chunk_size = 500000
    total_rows = 0
    
    # Usaremos engine C com separador explícito para velocidade
    try:
        reader = pd.read_csv(
            filepath, 
            sep=';', 
            chunksize=chunk_size,
            engine='c',
            dtype={
                'origem_cod': 'int32',
                'destino_cod': 'int32',
                'distancia': 'float32',
                'tempo': 'float32'
            }
        )
    except ValueError:
        # Fallback se dtype falhar ou colunas forem diferentes
        print("Aviso: Não foi possível usar dtypes otimizados, voltando para padrão")
        reader = pd.read_csv(filepath, sep=';', chunksize=chunk_size, engine='c')

    for chunk in reader:
        # Padronizar nomes de colunas
        chunk = chunk.rename(columns={
            'origem_cod': 'origem',
            'destino_cod': 'destino'
        })
        
        # Filter by UF if requested
        if uf_filter:
            uf_str = str(uf_filter)
            
            if uf_str.isdigit():
                 mask_orig = chunk['origem'].astype(str).str.zfill(7).str[:2] == uf_str
                 mask_dest = chunk['destino'].astype(str).str.zfill(7).str[:2] == uf_str
                 chunk = chunk[mask_orig & mask_dest]
            else:
                if 'origem_uf' in chunk.columns and 'destino_uf' in chunk.columns:
                     mask_orig = chunk['origem_uf'].astype(str) == uf_str
                     mask_dest = chunk['destino_uf'].astype(str) == uf_str
                     chunk = chunk[mask_orig & mask_dest]
                else:
                     mask_orig = chunk['origem'].astype(str).str.zfill(7).str[:2] == uf_str
                     mask_dest = chunk['destino'].astype(str).str.zfill(7).str[:2] == uf_str
                     chunk = chunk[mask_orig & mask_dest]
        
        if not chunk.empty:
            # Manter apenas colunas necessárias
            cols_to_keep = ['origem', 'destino', 'distancia', 'tempo']
            # Garantir que colunas existem antes de selecionar
            cols_to_keep = [c for c in cols_to_keep if c in chunk.columns]
            chunks.append(chunk[cols_to_keep])
            total_rows += len(chunk)
            
    if chunks:
        df = pd.concat(chunks, ignore_index=True)
    else:
        df = pd.DataFrame(columns=['origem', 'destino', 'distancia', 'tempo'])
    
    print(f"Carregados {len(df)} pares de distância (filtrados do stream).")
    return df

def load_existing_sites(filepath, uf_filter=None):
    """
    Carrega locais existentes.
    Retorna um DataFrame com informações do local.
    """
    print(f"Carregando locais existentes de {filepath}...")
    
    # Handle Streamlit UploadedFile
    if hasattr(filepath, 'name'):
        filename = filepath.name
        if hasattr(filepath, 'seek'): filepath.seek(0)
    else:
        if not check_and_debug_path(filepath):
            return pd.DataFrame(columns=['id', 'possui_campus'])
        filename = str(filepath)
        
    if is_lfs_pointer(filepath):
        handle_lfs_error(filepath)
        
    _, ext = os.path.splitext(filename)
    
    if ext.lower() == '.parquet':
        df = pd.read_parquet(filepath)
    else:
        try:
            df = pd.read_csv(filepath, sep=';', encoding='utf-8')
        except UnicodeDecodeError:
            if hasattr(filepath, 'seek'): filepath.seek(0)
            df = pd.read_csv(filepath, sep=';', encoding='latin1')
    
    # Padronizar coluna ID
    if 'cód.ibge' in df.columns:
        df = df.rename(columns={'cód.ibge': 'id'})
    elif 'cod_ibge' in df.columns:
        df = df.rename(columns={'cod_ibge': 'id'})
    
    # Forçar ID para int
    df['id'] = df['id'].astype(int)
    
    # Verificar coluna 'possui_campus' (case insensitive)
    possui_col = next((c for c in df.columns if c.lower() == 'possui_campus'), None)
    
    if possui_col:
        # Filtrar apenas aqueles marcados como Sim
        # Aceita: S, s, Sim, sim, 1, True, true
        valid_values = ['s', 'sim', '1', 'true']
        df = df[df[possui_col].astype(str).str.lower().isin(valid_values)].copy()
        print(f"Filtrado por '{possui_col}': {len(df)} locais encontrados.")

    if uf_filter:
        uf_str = str(uf_filter)
        if uf_str.isdigit():
             df = df[df['id'].astype(str).str.zfill(7).str[:2] == uf_str].copy()
        elif 'uf' in df.columns:
             df = df[df['uf'].astype(str) == uf_str].copy()
        else:
             df = df[df['id'].astype(str).str.zfill(7).str[:2] == uf_str].copy()
             
    print(f"Carregados {len(df)} locais existentes.")
    return df

def load_demand(filepath, id_col, value_cols, uf_filter=None):
    """
    Carrega dados de demanda.
    filepath: Caminho para CSV
    id_col: Nome da coluna contendo ID do município
    value_cols: Lista de nomes de colunas para somar para demanda total
    """
    print(f"Carregando demanda de {filepath}...")
    print(f"Carregando demanda de {filepath}...")
    
    # Handle Streamlit UploadedFile
    if hasattr(filepath, 'name'):
        filename = filepath.name
        # Resetar ponteiro se for objeto tipo arquivo
        if hasattr(filepath, 'seek'):
            filepath.seek(0)
    else:
        if not check_and_debug_path(filepath):
             return {}, {}, {}
        filename = str(filepath)

    if is_lfs_pointer(filepath):
        handle_lfs_error(filepath)

    _, ext = os.path.splitext(filename)
    
    if ext.lower() == '.parquet':
        df = pd.read_parquet(filepath)
    else:
        # Auto-detectar separador (lida com vírgula e ponto e vírgula)
        try:
            df = pd.read_csv(filepath, sep=None, engine='python', encoding='utf-8')
        except UnicodeDecodeError:
             if hasattr(filepath, 'seek'): filepath.seek(0)
             df = pd.read_csv(filepath, sep=None, engine='python', encoding='latin1')
    
    # Auto-detectar coluna ID se não encontrada
    if id_col not in df.columns:
        # Tentar candidatos
        candidates = ['id', 'ID', 'Id', 'Cód.', 'Cod.', 'Código', 'Codigo', 'Code']
        found_col = None
        for cand in candidates:
            if cand in df.columns:
                found_col = cand
                break
        
        if found_col:
            print(f"Coluna ID '{id_col}' não encontrada. Usando '{found_col}'.")
            id_col = found_col
        else:
            raise ValueError(f"Coluna ID '{id_col}' (ou variantes) não encontrada em {filepath}. Colunas disponíveis: {list(df.columns)}")
        
    # Renomear col id para 'id'
    df = df.rename(columns={id_col: 'id'})
    df['id'] = df['id'].astype(int)
    
    # Calcular demanda total
    missing = [c for c in value_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Colunas de valor {missing} não encontradas em {filepath}")
        
    df['total_demand'] = df[value_cols].sum(axis=1)
    
    if uf_filter:
        uf_str = str(uf_filter)
        if uf_str.isdigit():
             df = df[df['id'].astype(str).str.zfill(7).str[:2] == uf_str].copy()
        elif 'UF' in df.columns:
             df = df[df['UF'].astype(str) == uf_str].copy()
        elif 'uf' in df.columns:
             df = df[df['uf'].astype(str) == uf_str].copy()
        else:
             df = df[df['id'].astype(str).str.zfill(7).str[:2] == uf_str].copy()

    # Criar dicionário {id: demanda}
    demand_dict = df.set_index('id')['total_demand'].to_dict()
    
    # Retornar também dataframe para busca de nomes se disponível
    name_col = None
    
    # Normalizar colunas para busca (remover acentos, lower)
    import unicodedata
    def normalize(s):
        return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').lower()
        
    cols_map = {normalize(c): c for c in df.columns}
    
    # Candidatos: municipio, nome
    for cand in ['municipio', 'nome']:
        if cand in cols_map:
            name_col = cols_map[cand]
            break
            
    names_dict = {}
    if name_col:
        names_dict = df.set_index('id')[name_col].to_dict()
        
    # Criar dicionário {id: uf}
    uf_dict = {}
    uf_col = None
    for cand in ['UF', 'uf']:
        if cand in df.columns:
            uf_col = cand
            break
    
    if uf_col:
        uf_dict = df.set_index('id')[uf_col].to_dict()
        
    print(f"Carregada demanda para {len(demand_dict)} locais.")
    return demand_dict, names_dict, uf_dict

@st.cache_data
def load_coordinates(filepath, uf_filter=None):
    """
    Carrega coordenadas (lat, lon) de CSV.
    Colunas esperadas: codigo_ibge, latitude, longitude
    Retorna: dict {id: (lat, lon)}
    """
    print(f"Carregando coordenadas de {filepath}...")
    try:
        # Lidar com Streamlit UploadedFile
        if hasattr(filepath, 'name'):
            filename = filepath.name
            if hasattr(filepath, 'seek'): filepath.seek(0)
        else:
            if not check_and_debug_path(filepath):
                return {}
            filename = str(filepath)
            
        if is_lfs_pointer(filepath):
            if not ensure_file_from_drive(filepath):
                handle_lfs_error(filepath)
            
        _, ext = os.path.splitext(filename)
        
        if ext.lower() == '.parquet':
            df = pd.read_parquet(filepath)
        else:
            try:
                df = pd.read_csv(filepath, encoding='utf-8')
            except UnicodeDecodeError:
                if hasattr(filepath, 'seek'): filepath.seek(0)
                df = pd.read_csv(filepath, encoding='latin1')
        
        # Padronizar colunas
        if 'codigo_ibge' in df.columns:
            df = df.rename(columns={'codigo_ibge': 'id'})
        
        # Filtrar por UF se necessário (assumindo que primeiros 2 dígitos de ID são código UF)
        if uf_filter:
            uf_str = str(uf_filter)
            if uf_str.isdigit():
                 df = df[df['id'].astype(str).str.zfill(7).str[:2] == uf_str].copy()
            # Se UF for string (ex: 'MG'), podemos precisar de mapeamento ou verificar outras colunas
            # Mas geralmente prefixo de ID é mais seguro se disponível.
            # Assumimos que entrada é código de 2 dígitos ou pulamos se não encontrado.
        
        coords = {}
        for _, row in df.iterrows():
            try:
                coords[int(row['id'])] = (float(row['latitude']), float(row['longitude']))
            except (ValueError, KeyError):
                continue
                
        print(f"Carregadas coordenadas para {len(coords)} locais.")
        return coords
    except Exception as e:
        print(f"Erro ao carregar coordenadas: {e}")
        return {}

@st.cache_data
def load_shapefile(filepath, uf_filter=None, tolerance=0.005):
    """
    Carrega shapefile de municípios usando Geopandas.
    Colunas esperadas: CD_MUN (id), SIGLA_UF (uf)
    Retorna: GeoDataFrame
    """
    print(f"Carregando shapefile de {filepath}...")
    if not check_and_debug_path(filepath):
        return None
        
    if is_lfs_pointer(filepath):
        handle_lfs_error(filepath)

    # Validar arquivos auxiliares do Shapefile
    if filepath.lower().endswith('.shp'):
        base = os.path.splitext(filepath)[0]
        # Extensões obrigatórias e opcionais
        for ext in ['.shx', '.dbf', '.prj', '.cpg']:
            aux_file = base + ext
            path_aux = Path(aux_file)
            if not path_aux.exists() or is_lfs_pointer(aux_file):
                ensure_file_from_drive(aux_file)

    try:
        gdf = gpd.read_file(filepath)
        
        # Padronizar colunas
        if 'CD_MUN' in gdf.columns:
            gdf = gdf.rename(columns={'CD_MUN': 'id'})
        
        # Converter ID para int para correspondência
        gdf['id'] = gdf['id'].astype(int)
        
        # Filtrar por UF
        if uf_filter:
            uf_str = str(uf_filter)
            if 'SIGLA_UF' in gdf.columns:
                 gdf = gdf[gdf['SIGLA_UF'] == uf_str].copy()
            else:
                 # Fallback para prefixo de ID
                 gdf = gdf[gdf['id'].astype(str).str.zfill(7).str[:2] == uf_str].copy()
                 
        # Simplificar Geometria
        if tolerance and tolerance > 0:
            gdf['geometry'] = gdf.simplify(tolerance=tolerance)
            
        print(f"Carregados {len(gdf)} shapes.")
        return gdf
    except Exception as e:
        print(f"Erro ao carregar shapefile: {e}")
        return None

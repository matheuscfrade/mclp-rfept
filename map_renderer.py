import streamlit as st
import pandas as pd
import pydeck as pdk
import os
import config
import data_loader
import report_utils
import math
import json

@st.cache_data(show_spinner=False)
def get_cached_excel(_gdf, demand_col, run_id):
    return report_utils.generate_excel_download(_gdf, demand_col)

@st.cache_data(show_spinner=False)
def get_cached_pdf(_gdf, demand_col, total_demand, covered_demand, coverage_percent, params, _solution_df, run_results, run_id):
    return report_utils.generate_pdf_report(
        _gdf, demand_col, total_demand, covered_demand, coverage_percent, params, _solution_df, run_results
    )


def render_maps(data):
    """
    Renderiza a seção de visualização do mapa, incluindo a caixa de busca,
    mapa de cobertura, mapa de calor de demanda e opções de exportação.
    """
    # Desempacotar dados necessários
    results = data['results']
    s_vns = data['s_vns']
    existing_site_ids = data['existing_site_ids']
    demand_dict = data['demand_dict']
    names_dict = data['names_dict']
    uf_dict = data['uf_dict']
    coords_dict = data['coords_dict']
    coverage_map = data['coverage_map']
    pre_covered = data['pre_covered']
    use_km = data['use_km']
    
    # Recuperar parâmetros armazenados
    target_uf = data.get('target_uf')
    demand_file = data.get('demand_file')
    demand_col = data.get('demand_col')
    
    st.header("🗺️ Visualização Geográfica")
    
    shp_file = os.path.join(config.DATA_DIR, "BR_Municipios_2024.shp")
    
    # Carregar Shapefile (Comum)
    gdf_base = data_loader.load_shapefile(shp_file, uf_filter=target_uf, tolerance=0.005)
        
    if gdf_base is not None:
        # Geometria já simplificada no carregamento

        # --- Caixa de Busca ---
        # Criar lista de tuplas (Label, ID) com UF para desambiguação
        search_items = []
        for i in demand_dict.keys():
            name = names_dict.get(i, "Desconhecido")
            uf = uf_dict.get(i, "")
            label = f"{name} - {uf}" if uf else name
            search_items.append((label, i))
            
        # Ordenar por rótulo
        search_options = sorted(search_items, key=lambda x: x[0])
        
        # Inicializar contador na session state
        if 'map_key_counter' not in st.session_state:
            st.session_state.map_key_counter = 0
            
        def update_map_key():
            st.session_state.map_key_counter += 1
        
        search_selection = st.selectbox(
            "🔍 Buscar Município (Zoom)", 
            options=[(None, None)] + search_options, 
            format_func=lambda x: "Selecione um município..." if x[0] is None else x[0],
            help="Selecione um município para centralizar o mapa. Digite para buscar.",
            on_change=update_map_key,
            key="municipality_search"
        )
            
        # Chave base para esta renderização
        current_map_key = f"map_v{st.session_state.map_key_counter}"

        # --- Preparar Dados (Global) ---
        # Carregar Dados de Demanda globalmente para uso em ambos os mapas e exportação
        gdf_global = gdf_base.copy()
        demand_loaded = False
        
        try:
            df_map = None
            if hasattr(demand_file, 'seek'):
                demand_file.seek(0)
                if hasattr(demand_file, 'name') and demand_file.name.lower().endswith('.parquet'):
                    df_map = pd.read_parquet(demand_file)
                else:
                    try:
                        df_map = pd.read_csv(demand_file, sep=None, engine='python', encoding='utf-8', dtype=str)
                    except UnicodeDecodeError:
                        demand_file.seek(0)
                        df_map = pd.read_csv(demand_file, sep=None, engine='python', encoding='latin1', dtype=str)
            elif os.path.exists(demand_file):
                if demand_file.lower().endswith('.parquet'):
                    df_map = pd.read_parquet(demand_file)
                else:
                    try:
                        df_map = pd.read_csv(demand_file, sep=None, engine='python', encoding='utf-8', dtype=str)
                    except UnicodeDecodeError:
                        df_map = pd.read_csv(demand_file, sep=None, engine='python', encoding='latin1', dtype=str)
            
            if df_map is not None:
                # Identificar coluna ID
                id_candidates = ['id', 'ID', 'Id', 'Cód.', 'Cod.', 'Código', 'Codigo', 'Code']
                id_col_name = None
                for c in df_map.columns:
                    if c in id_candidates:
                        id_col_name = c
                        break
                
                if id_col_name:
                    # Preparar Dados
                    df_map[id_col_name] = pd.to_numeric(df_map[id_col_name], errors='coerce').fillna(0).astype(int)
                    df_map[demand_col] = pd.to_numeric(df_map[demand_col], errors='coerce').fillna(0)
                    
                    # Mesclar
                    gdf_global = gdf_global.merge(df_map, left_on='id', right_on=id_col_name, how='left')
                    
                    # Preencher demanda ausente com 0
                    gdf_global[demand_col] = gdf_global[demand_col].fillna(0)
                    demand_loaded = True
                else:
                    st.error("Coluna de ID não encontrada no arquivo de demanda.")
        except Exception as e:
            st.error(f"Erro ao carregar dados de demanda: {e}")

        col1, col2 = st.columns(2)

        # --- COLUNA 1: Mapa de Cobertura ---
        with col1:
            st.markdown("### 📍 Mapa de Cobertura")
            
            # Lógica de Cache
            current_cache_key = (id(data), st.session_state.get('map_key_counter', 0))
            
            if 'last_map_cache_key' not in st.session_state or st.session_state.last_map_cache_key != current_cache_key:
                
                gdf = gdf_global.copy()
                
                # 1. Calcular Status de Cobertura para TODOS os nós
                status_dict = {i: 'Uncovered' for i in demand_dict.keys()}
                
                # Marcar Cobertura Existente
                for site in existing_site_ids:
                    if site in status_dict: status_dict[site] = 'Existing_Site'
                    for covered in coverage_map.get(site, set()):
                        if covered in status_dict and status_dict[covered] != 'Existing_Site':
                            status_dict[covered] = 'Existing_Covered'
                        
                # Marcar Nova Cobertura
                for site in s_vns:
                    was_covered = status_dict.get(site) == 'Existing_Covered'
                    if status_dict.get(site) != 'Existing_Site':
                        if was_covered:
                            status_dict[site] = 'New_Site_Overlapping'
                        else:
                            status_dict[site] = 'New_Site'
                    
                    for covered in coverage_map.get(site, set()):
                        current_status = status_dict.get(covered)
                        if current_status not in ('Existing_Site', 'Existing_Covered', 'New_Site', 'New_Site_Overlapping'):
                            status_dict[covered] = 'New_Covered'
                            
                # 2. Mesclar com GeoDataFrame
                gdf['status'] = gdf['id'].map(status_dict).fillna('Uncovered')
                
                # Mapear string de status de volta para código para geração de relatório
                status_code_map = {
                    'Existing_Site': 0,
                    'Existing_Covered': 1,
                    'New_Site': 2,
                    'New_Site_Overlapping': 3,
                    'New_Covered': 4,
                    'Uncovered': 5
                }
                gdf['status_code'] = gdf['status'].map(status_code_map).fillna(5).astype(int)
                
                # 3. Definir Cores
                def get_color(status):
                    if status == 'Existing_Site': return [0, 0, 139, 200]
                    elif status == 'Existing_Covered': return [100, 149, 237, 150]
                    elif status == 'New_Site': return [0, 100, 0, 200]
                    elif status == 'New_Site_Overlapping': return [255, 215, 0, 200]
                    elif status == 'New_Covered': return [144, 238, 144, 150]
                    else: return [200, 200, 200, 50]
                        
                gdf['fill_color'] = gdf['status'].apply(get_color)

                # --- NOVO: Adicionar Info de Campi de Cobertura ---
                # Construir dicionário: city_id -> lista de nomes de campi cobrindo
                city_covering_campuses = {}

                # Auxiliar para adicionar info de cobertura
                def register_coverage(site_id, label_suffix=""):
                    site_name = names_dict.get(site_id, f"ID {site_id}")
                    full_label = f"{site_name}{label_suffix}"
                    
                    covered_cities = coverage_map.get(site_id, set())
                    
                    for city_id in covered_cities:
                        if city_id not in city_covering_campuses:
                            city_covering_campuses[city_id] = []
                        city_covering_campuses[city_id].append(full_label)

                # Registrar Locais Existentes
                for site in existing_site_ids:
                    register_coverage(site, " (Existente)")

                # Registrar Novos Locais
                for site in s_vns:
                    register_coverage(site, " (Novo)")

                # Mapear para DataFrame
                def get_covering_str(city_id):
                    campuses = city_covering_campuses.get(city_id, [])
                    if not campuses:
                        return "Nenhum"
                    # Ordenar para exibição consistente
                    return ", ".join(sorted(campuses))

                gdf['covering_campuses'] = gdf['id'].apply(get_covering_str)
                
                # Converter para GeoJSON
                if gdf.crs != "EPSG:4326":
                    gdf = gdf.to_crs("EPSG:4326")
                    
                geojson_data = getattr(gdf, "__geo_interface__", None)
                if not geojson_data:
                     geojson_data = json.loads(gdf.to_json())
        
                # 4. Renderizar Mapa
                layers = []
                
                # Camada de Polígonos
                shape_layer = pdk.Layer(
                    "GeoJsonLayer",
                    geojson_data,
                    pickable=True,
                    stroked=True,
                    filled=True,
                    get_fill_color="properties.fill_color",
                    get_line_color=[255, 255, 255, 100],
                    line_width_min_pixels=0.5,
                    opacity=0.8,
                    auto_highlight=True
                )
                layers.append(shape_layer)
                
                # Camada de Pontos
                site_points = []
                for site in existing_site_ids:
                     lat, lon = coords_dict.get(site, (None, None))
                     if lat: site_points.append({'lat': lat, 'lon': lon, 'type': 'Existente', 'color': [0, 0, 139, 255], 'radius': 2000})
                for site in s_vns:
                     lat, lon = coords_dict.get(site, (None, None))
                     if lat: site_points.append({'lat': lat, 'lon': lon, 'type': 'Novo', 'color': [0, 100, 0, 255], 'radius': 3000})
                     
                if site_points:
                    points_df = pd.DataFrame(site_points)
                    points_layer = pdk.Layer(
                        "ScatterplotLayer",
                        points_df,
                        get_position=["lon", "lat"],
                        get_color="color",
                        get_radius="radius",
                        pickable=False,
                        opacity=1.0,
                        stroked=True,
                        get_line_color=[255, 255, 255, 200]
                    )
                    layers.append(points_layer)
        
                # Estado de Visualização
                active_coords = [coords_dict[i] for i in status_dict if i in coords_dict]
                if active_coords:
                    mean_lat = sum(c[0] for c in active_coords) / len(active_coords)
                    mean_lon = sum(c[1] for c in active_coords) / len(active_coords)
                else:
                    mean_lat, mean_lon = -15, -50
                zoom_level = 6
                    
                view_state = pdk.ViewState(
                    latitude=mean_lat,
                    longitude=mean_lon,
                    zoom=zoom_level,
                    pitch=0,
                )
                
                # Camada de Destaque
                if search_selection[1] is not None:
                    selected_id = search_selection[1]
                    gdf_highlight = gdf[gdf['id'] == selected_id]
                    if not gdf_highlight.empty:
                        geojson_highlight = getattr(gdf_highlight, "__geo_interface__", None)
                        if not geojson_highlight:
                            geojson_highlight = json.loads(gdf_highlight.to_json())
                            
                        highlight_layer = pdk.Layer(
                            "GeoJsonLayer",
                            geojson_highlight,
                            pickable=False,
                            stroked=True,
                            filled=False,
                            get_line_color=[0, 255, 255, 255],
                            line_width_min_pixels=3,
                            opacity=1.0
                        )
                        layers.append(highlight_layer)
    
                # Criar Deck
                deck = pdk.Deck(
                    layers=layers,
                    initial_view_state=view_state,
                    tooltip={
                        "html": "<b>{NM_MUN} - {SIGLA_UF}</b><br/>"
                                "Status: {status}<br/>"
                                "Demanda: {" + demand_col + "}<br/>"
                                "Coberto por: {covering_campuses}",
                        "style": {
                            "backgroundColor": "#333333",
                            "color": "white",
                            "maxWidth": "350px",
                            "whiteSpace": "normal"
                        }
                    }
                )
                
                # Atualizar Cache
                st.session_state.cached_map_deck = deck
                st.session_state.last_map_cache_key = current_cache_key
                st.session_state.cached_layers = layers
                st.session_state.cached_view_state = view_state
                st.session_state.cached_gdf = gdf
            
            # Usar Dados em Cache
            deck = st.session_state.cached_map_deck
            layers = st.session_state.cached_layers
            view_state = st.session_state.cached_view_state
            gdf = st.session_state.get('cached_gdf', None)
            
            st.pydeck_chart(deck, key="map_coverage_static", use_container_width=True)
            
            # Legenda
            st.markdown("""
            <div style="display: flex; gap: 10px; flex-wrap: wrap; font-size: 0.8em;">
                <div><span style="color:darkblue">&#9632;</span> Existente</div>
                <div><span style="color:cornflowerblue">&#9632;</span> Cobertura Existente</div>
                <div><span style="color:darkgreen">&#9632;</span> Novo</div>
                <div><span style="color:gold">&#9632;</span> Novo (Sobreposto)</div>
                <div><span style="color:lightgreen">&#9632;</span> Nova Cobertura</div>
                <div><span style="color:grey">&#9632;</span> Sem Cobertura</div>
                <div><span style="border: 2px solid cyan; display: inline-block; width: 12px; height: 12px;"></span> Selecionado</div>
            </div>
            """, unsafe_allow_html=True)

        # --- COLUNA 2: Mapa de Calor de Demanda ---
        with col2:
            st.markdown("### 🔥 Mapa de Calor da Demanda")
            
            # Lógica de Cache
            current_cache_key = (id(data), st.session_state.get('map_key_counter', 0))
            
            if 'last_demand_cache_key' not in st.session_state or st.session_state.last_demand_cache_key != current_cache_key:
                
                with st.spinner("Gerando mapa de calor..."):
                    try:
                        if demand_loaded:
                            gdf_dem = gdf_global.copy()
                            
                            # --- Implementação PyDeck ---
                            
                            # 1. Calcular Escala de Cores (Logarítmica)
                            
                            # Filtrar valores positivos para cálculo de log
                            positive_demands = gdf_dem[gdf_dem[demand_col] > 0][demand_col]
                            
                            if not positive_demands.empty:
                                min_val = positive_demands.min()
                                max_val = positive_demands.max()
                                
                                # Evitar problemas com log(0) ou log(1) se min_val for pequeno
                                min_log = math.log(max(min_val, 1))
                                max_log = math.log(max(max_val, 1))
                                
                                def get_heat_color(val):
                                    if val <= 0:
                                        return [200, 200, 200, 50] # Grey for 0/Null
                                        
                                    val_log = math.log(max(val, 1))
                                    
                                    if max_log == min_log:
                                        norm = 0.5
                                    else:
                                        norm = (val_log - min_log) / (max_log - min_log)
                                    
                                    # Gradiente de Cores: Amarelo Claro (255, 255, 200) para Vermelho (255, 0, 0)
                                    r = 255
                                    g = int(255 * (1 - norm))
                                    b = int(200 * (1 - norm)) 
                                    
                                    return [r, g, b, 200]
                            else:
                                # Fallback se não houver demanda positiva
                                min_val = 0
                                max_val = 0
                                def get_heat_color(val):
                                    return [200, 200, 200, 50]
    
                            gdf_dem['fill_color'] = gdf_dem[demand_col].apply(get_heat_color)
                            
                            # Converter para GeoJSON
                            if gdf_dem.crs != "EPSG:4326":
                                gdf_dem = gdf_dem.to_crs("EPSG:4326")
                                
                            geojson_dem = getattr(gdf_dem, "__geo_interface__", None)
                            if not geojson_dem:
                                geojson_dem = json.loads(gdf_dem.to_json())
                                
                            # 2. Renderizar Mapa
                            layers_dem = []
                            
                            heat_layer = pdk.Layer(
                                "GeoJsonLayer",
                                geojson_dem,
                                pickable=True,
                                stroked=True,
                                filled=True,
                                get_fill_color="properties.fill_color",
                                get_line_color=[255, 255, 255, 50],
                                line_width_min_pixels=0.5,
                                opacity=0.8,
                                auto_highlight=True
                            )
                            layers_dem.append(heat_layer)
                            
                            # --- Camada de Destaque (Mapa de Demanda) ---
                            if search_selection[1] is not None:
                                selected_id = search_selection[1]
                                # Filtrar para cidade selecionada
                                gdf_highlight_dem = gdf_dem[gdf_dem['id'] == selected_id]
                                
                                if not gdf_highlight_dem.empty:
                                    geojson_highlight_dem = getattr(gdf_highlight_dem, "__geo_interface__", None)
                                    if not geojson_highlight_dem:
                                        geojson_highlight_dem = json.loads(gdf_highlight_dem.to_json())
                                        
                                    highlight_layer_dem = pdk.Layer(
                                        "GeoJsonLayer",
                                        geojson_highlight_dem,
                                        pickable=False,
                                        stroked=True,
                                        filled=False, # Preenchimento transparente
                                        get_line_color=[0, 255, 255, 255], # Ciano
                                        line_width_min_pixels=3,
                                        opacity=1.0
                                    )
                                    layers_dem.append(highlight_layer_dem)
                            
                            # Reutilizar view_state do Mapa de Cobertura (disponível no escopo local)
                            # Definir deck_dem
                            deck_dem = pdk.Deck(
                                layers=layers_dem,
                                initial_view_state=view_state,
                                tooltip={
                                    "html": "<b>{NM_MUN} - {SIGLA_UF}</b><br/>"
                                            "Demanda: {" + demand_col + "}",
                                    "style": {
                                        "backgroundColor": "#333333",
                                        "color": "white",
                                        "maxWidth": "350px",
                                        "whiteSpace": "normal"
                                    }
                                }
                            )
                            
                            # Atualizar Cache
                            st.session_state.cached_demand_deck = deck_dem
                            st.session_state.cached_layers_dem = layers_dem
                            st.session_state.last_demand_cache_key = current_cache_key
                            st.session_state.demand_max_val = max_val # Para legenda
                            
                        else:
                            st.error("Dados de demanda não carregados.")
                            st.session_state.cached_demand_deck = None
                    except Exception as e:
                        st.error(f"Erro ao gerar mapa de calor: {e}")
                        st.session_state.cached_demand_deck = None

            # Usar Dados em Cache
            if st.session_state.get('cached_demand_deck'):
                deck_dem = st.session_state.cached_demand_deck
                max_val = st.session_state.get('demand_max_val', 0)
                
                st.pydeck_chart(deck_dem, key="map_demand_static", use_container_width=True)
                
                # Legenda
                st.markdown(f"""
                <div style="display: flex; align-items: center; gap: 10px; font-size: 0.8em;">
                    <div>Baixa</div>
                    <div style="background: linear-gradient(90deg, rgb(255,255,200), rgb(255,0,0)); width: 100px; height: 10px; border-radius: 5px;"></div>
                    <div>Alta</div>
                    <div><span style="border: 2px solid cyan; display: inline-block; width: 12px; height: 12px;"></span> Selecionado</div>
                </div>
                """, unsafe_allow_html=True)

        # --- Seção de Exportação ---
        st.markdown("---")
        st.header("📂 Exportar Resultados (Cobertura e Mapas)")
        
        col_exp1, col_exp2 = st.columns(2)
        
        with col_exp1:
            st.markdown("##### Relatórios")
            
            # Excel
            try:
                excel_data = get_cached_excel(gdf, demand_col, id(data))
                st.download_button(
                    label="📥 Baixar Excel (.xlsx)",
                    data=excel_data,
                    file_name="mclp_resultados.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error(f"Erro ao gerar Excel: {e}")

            # PDF
            try:
                # Preparar dicionário params
                params = {
                    'p': data.get('p'),
                    'radius': data.get('radius'),
                    'max_time': data.get('max_time'),
                    'use_km': use_km,
                    'target_uf': target_uf,
                    'ls_max_iter': data.get('ls_max_iter'),
                    'ls_strategy': data.get('ls_strategy'),
                    'vns_max_iter': data.get('vns_max_iter'),
                    'vns_k_max': data.get('vns_k_max'),
                    'vns_max_no_improv': data.get('vns_max_no_improv'),
                    'vns_max_time': data.get('vns_max_time'),
                    'vns_ls_strategy': data.get('vns_ls_strategy'),
                    'demand_file_name': data.get('demand_file'),
                    'existing_sites_file_name': data.get('existing_sites_file')
                }
                
                # Calcular totais para relatório
                total_demand = gdf_global[demand_col].sum()
                covered_demand = gdf[gdf['status'] != 'Uncovered'][demand_col].sum()
                coverage_percent = (covered_demand / total_demand * 100) if total_demand > 0 else 0
                
                pdf_data = get_cached_pdf(
                    gdf, 
                    demand_col, 
                    total_demand, 
                    covered_demand, 
                    coverage_percent, 
                    params,
                    data.get('solution_df'),
                    results, # Passar resultados de execução
                    id(data)
                )
                
                st.download_button(
                    label="📥 Baixar Relatório Completo (.pdf)",
                    data=pdf_data,
                    file_name="mclp_relatorio_completo.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Erro ao gerar PDF: {e}")

        with col_exp2:
            st.markdown("##### Mapas Interativos (HTML)")
            
            # Mapa de Cobertura
            try:
                deck_export = pdk.Deck(
                    layers=layers,
                    initial_view_state=view_state,
                    tooltip={
                        "html": "<b>{NM_MUN} - {SIGLA_UF}</b><br/>"
                                "Status: {status}<br/>"
                                "Demanda: {" + demand_col + "}<br/>"
                                "Coberto por: {covering_campuses}",
                        "style": {
                            "backgroundColor": "#333333",
                            "color": "white",
                            "maxWidth": "350px",
                            "whiteSpace": "normal"
                        }
                    }
                )
                html_data = report_utils.generate_html_map(deck_export)
                st.download_button(
                    label="📥 Baixar Cobertura (.html)",
                    data=html_data,
                    file_name="mclp_mapa_cobertura.html",
                    mime="text/html"
                )
            except Exception as e:
                st.error(f"Erro: {e}")

            # Mapa de Demanda
            try:
                # Recriar lógica do Mapa de Demanda para exportação
                gdf_dem_exp = gdf_global.copy()
                
                # Lógica de Escala de Cores (Simplificada)
                positive_demands = gdf_dem_exp[gdf_dem_exp[demand_col] > 0][demand_col]
                if not positive_demands.empty:
                    min_val = positive_demands.min()
                    max_val = positive_demands.max()
                    min_log = math.log(max(min_val, 1))
                    max_log = math.log(max(max_val, 1))
                    
                    def get_heat_color_exp(val):
                        if val <= 0: return [200, 200, 200, 50]
                        val_log = math.log(max(val, 1))
                        if max_log == min_log: norm = 0.5
                        else: norm = (val_log - min_log) / (max_log - min_log)
                        r = 255
                        g = int(255 * (1 - norm))
                        b = int(200 * (1 - norm)) 
                        return [r, g, b, 200]
                else:
                    def get_heat_color_exp(val): return [200, 200, 200, 50]
                    
                gdf_dem_exp['fill_color'] = gdf_dem_exp[demand_col].apply(get_heat_color_exp)
                
                if gdf_dem_exp.crs != "EPSG:4326":
                    gdf_dem_exp = gdf_dem_exp.to_crs("EPSG:4326")
                    
                geojson_dem_exp = getattr(gdf_dem_exp, "__geo_interface__", None)
                if not geojson_dem_exp:
                    geojson_dem_exp = json.loads(gdf_dem_exp.to_json())
                    
                layers_dem_exp = [pdk.Layer(
                    "GeoJsonLayer",
                    geojson_dem_exp,
                    pickable=True,
                    stroked=True,
                    filled=True,
                    get_fill_color="properties.fill_color",
                    get_line_color=[255, 255, 255, 50],
                    line_width_min_pixels=0.5,
                    opacity=0.8
                )]
                
                deck_dem_export = pdk.Deck(
                    layers=layers_dem_exp,
                    initial_view_state=view_state,
                    tooltip={
                        "html": "<b>{NM_MUN} - {SIGLA_UF}</b><br/>"
                                "Demanda: {" + demand_col + "}",
                        "style": {
                            "backgroundColor": "#333333",
                            "color": "white",
                            "maxWidth": "350px",
                            "whiteSpace": "normal"
                        }
                    }
                )
                html_data_dem = report_utils.generate_html_map(deck_dem_export)
                st.download_button(
                    label="📥 Baixar Demanda (.html)",
                    data=html_data_dem,
                    file_name="mclp_mapa_demanda.html",
                    mime="text/html"
                )
            except Exception as e:
                st.error(f"Erro: {e}")

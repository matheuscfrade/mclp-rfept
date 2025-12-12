import streamlit as st
import pandas as pd
import time
import os
import config
import data_loader
import heuristics
import report_utils
import ui_config
import ui_components

# Page Config
ui_config.setup_page_config()

# Custom CSS
ui_config.apply_custom_css()

# Explanation Content (HTML for Modal)
explanation_html = ui_config.EXPLANATION_HTML

def main():
    # --- Rodapé (Renderizar primeiro para garantir visibilidade) ---
    st.markdown(ui_config.FOOTER_HTML, unsafe_allow_html=True)

    # Injetar HTML do Modal
    st.markdown(explanation_html, unsafe_allow_html=True)

    # --- VERIFICAÇÃO INICIAL DE ARQUIVOS ---
    # Verificar e baixar arquivos essenciais antes de carregar a interface
    files_to_check = [
        ("Dados de Demanda", config.DEMAND_FILE),
        ("Campi Existentes", config.EXISTING_SITES_FILE),
        ("Matriz de Distâncias", config.DISTANCES_FILE),
        ("Coordenadas", config.COORDS_FILE)
    ]
    
    # Usar um container vazio para a barra de progresso que desaparecerá após a conclusão
    startup_placeholder = st.empty()
    
    # Verificar se precisamos fazer o check (apenas se algum arquivo faltar)
    needs_check = any(not os.path.exists(f[1]) or data_loader.is_lfs_pointer(f[1]) for f in files_to_check)
    
    if needs_check:
        with startup_placeholder.container():
            st.info("Verificando arquivos de dados necessários para o primeiro uso...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, (name, filepath) in enumerate(files_to_check):
                status_text.text(f"Verificando/Baixando: {name}...")
                success = data_loader.check_and_debug_path(filepath)
                if not success:
                    st.error(f"Falha ao baixar {name}. Verifique sua conexão ou os IDs do Drive.")
                    st.stop()
                progress_bar.progress((i + 1) / len(files_to_check))
            
            time.sleep(0.5) # Breve pausa para ver o 100%
            
        # Limpar a UI de inicialização
        startup_placeholder.empty()

    # Callback para Reset
    def reset_app():
        st.session_state.clear()
        # Explicitamente redefinir valores da barra lateral para o padrão
        st.session_state['config_p'] = config.P
        st.session_state['config_metric'] = "Distância (km)" if config.USE_DISTANCE_KM else "Tempo (horas)"
        st.session_state['config_radius'] = config.S_DISTANCE
        st.session_state['config_max_time'] = config.S_TIME
        st.session_state['config_target_uf'] = config.TARGET_UF or ""
        st.session_state['config_ls_max_iter'] = 100
        st.session_state['config_ls_strategy'] = 'best'
        st.session_state['config_vns_max_iter'] = 100
        st.session_state['config_vns_k_max'] = min(8, config.P)
        st.session_state['config_vns_max_no_improv'] = 50
        st.session_state['config_vns_max_time'] = 300
        st.session_state['config_vns_ls_strategy'] = 'best'
    
    # Custom CSS for the specific button (Force Green)
    st.markdown("""
    <style>
    /* Forçar botão verde para primário */
    div.stButton > button[kind="primary"], button[kind="primary"] {
        background-color: #28a745 !important;
        border-color: #28a745 !important;
        color: white !important;
    }
    div.stButton > button[kind="primary"]:hover, button[kind="primary"]:hover {
        background-color: #218838 !important;
        border-color: #218838 !important;
    }
    div.stButton > button[kind="primary"]:active, button[kind="primary"]:active {
        background-color: #1e7e34 !important;
        border-color: #1e7e34 !important;
    }
    div.stButton > button[kind="primary"]:focus, button[kind="primary"]:focus {
        box-shadow: 0 0 0 0.2rem rgba(40, 167, 69, 0.5) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- Configuração da Barra Lateral (Definida primeiro para disponibilidade de variáveis) ---
    with st.sidebar:
        st.header("⚙️ Configuração")
        
        # Parâmetros do Modelo
        p = st.number_input(
            "Número de Novas Unidades", 
            min_value=1, 
            value=config.P,
            help="Quantidade de novos locais que você deseja selecionar para instalação de campi.",
            key="config_p"
        )
        
        metric = st.radio(
            "Métrica de Cobertura", 
            ["Distância (km)", "Tempo (horas)"],
            help="Escolha se a cobertura será baseada na distância rodoviária ou no tempo de viagem.",
            key="config_metric"
        )
        use_km = metric == "Distância (km)"
        
        if use_km:
            radius = st.number_input(
                "Raio Máximo (km)", 
                min_value=0.1, 
                value=config.S_DISTANCE,
                help="Distância máxima para considerar um município coberto por um campus.",
                key="config_radius"
            )
            max_time = config.S_TIME
        else:
            max_time = st.number_input(
                "Tempo Máximo (horas)", 
                min_value=0.01, 
                value=config.S_TIME,
                help="Tempo máximo de viagem máximo para considerar um município coberto por outro município que possui campus.",
                key="config_max_time"
            )
            radius = config.S_DISTANCE
            
        target_uf = st.text_input(
            "Filtrar por UF (Ex: MG)", 
            value=config.TARGET_UF or "",
            help="Digite a sigla do estado para restringir a análise (ex: MG, SP). Deixe em branco para analisar o Brasil todo.",
            key="config_target_uf"
        ).strip().upper()
        
        if not target_uf:
            target_uf = None
            
        # --- Configurações Avançadas (Busca Local Inicial) ---
        with st.expander("Configurações Avançadas (Busca Local Inicial)"):
            ls_max_iter = st.slider(
                "Máximo de Iterações (Busca Local)",
                10, 500, 100,
                help="Número máximo de iterações para a Busca Local que roda antes do VNS.",
                key="config_ls_max_iter"
            )
            ls_strategy = st.radio(
                "Estratégia (Busca Local)",
                options=['best', 'first'],
                index=0,
                format_func=lambda x: "Best Improvement" if x == 'best' else "First Improvement",
                help="Best: Avalia todos e escolhe o melhor. First: Escolhe o primeiro melhor que encontrar.",
                key="config_ls_strategy"
            )

        # Parâmetros VNS (Colapsados)
        with st.expander("Configurações Avançadas (VNS)"):
            vns_max_iter = st.slider(
                "Máximo de Iterações", 
                10, 500, 100,
                help="Número máximo de tentativas de melhoria.",
                key="config_vns_max_iter"
            )
            
            # Ajustar valor no session_state se exceder o novo limite p antes de criar o slider
            if "config_vns_k_max" in st.session_state and st.session_state.config_vns_k_max > p:
                st.session_state.config_vns_k_max = p
                
            vns_k_max = st.slider(
                "Vizinhanças (k_max)", 
                1, max(1, p), min(8, p),
                help=f"Grau de 'agitação' da solução. Limitado a {p} (número de locais).",
                key="config_vns_k_max"
            )
            vns_max_no_improv = st.slider(
                "Parada sem Melhoria", 
                10, 200, 50,
                help="Pára se não encontrar melhorias após N tentativas.",
                key="config_vns_max_no_improv"
            )
            vns_max_time = st.number_input(
                "Tempo Máximo (s)",
                min_value=10,
                value=300,
                step=10,
                help="Tempo máximo de execução em segundos para o VNS.",
                key="config_vns_max_time"
            )
            vns_ls_strategy = st.radio(
                "Estratégia de Busca Local (VNS)",
                options=['best', 'first'],
                index=0,
                format_func=lambda x: "Best Improvement" if x == 'best' else "First Improvement",
                help="Define se a busca local interna do VNS aplica a primeira melhoria que encontrar (First) ou avalia todas e aplica a melhor (Best).",
                key="config_vns_ls_strategy"
            )
        
        # Arquivos (Colapsados)
        with st.expander("Configurações de Arquivos"):
            st.subheader("1. Demanda")
            
            # 1. Upload de Arquivo (Substituição Opcional)
            uploaded_demand = st.file_uploader(
                "Upload de Arquivo de Demanda (Opcional)", 
                type=["csv", "parquet"],
                accept_multiple_files=False,
                help="Se você subir um arquivo aqui, ele será usado. Caso contrário, será usado o arquivo padrão."
            )
            
            # Lógica: Upload > Caminho Padrão
            if uploaded_demand is not None:
                demand_file = uploaded_demand
                display_path = f"Arquivo Carregado: {uploaded_demand.name}"
            else:
                demand_file = config.DEMAND_FILE
                display_path = config.DEMAND_FILE

            # 2. Entrada de Texto (Exibição Somente Leitura)
            st.text_input(
                "Caminho do Arquivo de Demanda", 
                value=display_path,
                disabled=True,
                help="Este campo mostra o arquivo que será utilizado. Para alterar, faça o upload de um novo arquivo."
            )

            # --- Carregar Dados para Pré-visualização e Seleção de Colunas ---
            df_preview = None
            try:
                # Determinar fonte
                if uploaded_demand is not None:
                    # Reiniciar ponteiro para o início por precaução
                    uploaded_demand.seek(0)
                    if uploaded_demand.name.lower().endswith('.parquet'):
                        df_preview = pd.read_parquet(uploaded_demand)
                    else:
                        try:
                            df_preview = pd.read_csv(uploaded_demand, sep=None, engine='python', encoding='utf-8', dtype=str)
                        except UnicodeDecodeError:
                            uploaded_demand.seek(0)
                            df_preview = pd.read_csv(uploaded_demand, sep=None, engine='python', encoding='latin1', dtype=str)
                elif config.DEMAND_FILE:
                    # Garantir que o arquivo padrão exista
                    # A verificação inicial já garante isso, mas mantemos o check simples
                    file_ready = True
                    
                    if file_ready:
                        if config.DEMAND_FILE.lower().endswith('.parquet'):
                            df_preview = pd.read_parquet(config.DEMAND_FILE)
                        else:
                            try:
                                df_preview = pd.read_csv(config.DEMAND_FILE, sep=None, engine='python', encoding='utf-8', dtype=str)
                            except UnicodeDecodeError:
                                df_preview = pd.read_csv(config.DEMAND_FILE, sep=None, engine='python', encoding='latin1', dtype=str)
                
                if df_preview is not None:
                    # 3. Seleção de Coluna (Menu Suspenso)
                    columns = df_preview.columns.tolist()
                    default_idx = 0
                    if "Total" in columns:
                        default_idx = columns.index("Total")
                    
                    demand_col = st.selectbox(
                        "Coluna de Demanda", 
                        options=columns,
                        index=default_idx,
                        help="Selecione a coluna que contém os dados de demanda."
                    )
                    
                    # 4. Pré-visualização de Dados
                    with st.expander("Pré-visualizar Dados"):
                        st.dataframe(df_preview.head())
                    
                    # 5. Validação Imediata
                    # Verificar coluna de ID
                    id_candidates = ['id', 'ID', 'Id', 'Cód.', 'Cod.', 'Código', 'Codigo', 'Code']
                    found_id = any(c in columns for c in id_candidates)
                    
                    if found_id:
                        st.success(f"✅ Arquivo válido! {len(df_preview)} registros encontrados.")
                    else:
                        st.error("❌ Coluna de ID não encontrada (esperado: 'id', 'Cód.', etc).")
                        
                else:
                    demand_col = st.text_input("Coluna de Demanda", value="Total") # Fallback
                    st.warning("Não foi possível carregar o arquivo para pré-visualização.")

            except Exception as e:
                st.error(f"Erro ao ler arquivo: {e}")
                demand_col = st.text_input("Coluna de Demanda", value="Total") # Fallback
            
            # Template Download
            st.markdown("**Baixar Template de Demanda**")
            st.caption("Baixe um arquivo CSV com os municípios pré-listados para preencher sua própria demanda.")
            
            @st.cache_data
            def get_template_csv():

                source_file = config.DEMAND_FILE
                               
                # Garantir existência antes de gerar template
                if not os.path.exists(source_file) or data_loader.is_lfs_pointer(source_file):
                      data_loader.check_and_debug_path(source_file)

                if not os.path.exists(source_file):
                    return None, f"Arquivo base não encontrado: {source_file}"

                try:
                    # Tentar ler com engine Python para detectar separador e lidar melhor com encoding
                    if source_file.lower().endswith('.parquet'):
                        df_template = pd.read_parquet(source_file)
                    else:
                        # Tentar UTF-8 primeiro (padrão para arquivos modernos)
                        try:
                            df_template = pd.read_csv(source_file, sep=None, engine='python', encoding='utf-8', dtype=str)
                        except UnicodeDecodeError:
                            # Fallback para latin1 se UTF-8 falhar
                            df_template = pd.read_csv(source_file, sep=None, engine='python', encoding='latin1', dtype=str)
                    
                    # 1. Encontrar Coluna de ID
                    id_candidates = ['id', 'ID', 'Id', 'Cód.', 'Cod.', 'Código', 'Codigo', 'Code']
                    id_col = None
                    for cand in id_candidates:
                        if cand in df_template.columns:
                            id_col = cand
                            break
                    
                    # 2. Encontrar Colunas de Nome e UF
                    import unicodedata
                    def normalize(s):
                        return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').lower()
                    
                    cols_map = {normalize(c): c for c in df_template.columns}
                    
                    name_col = cols_map.get('municipio') or cols_map.get('nome')
                    uf_col = cols_map.get('uf')
                    
                    if id_col and name_col:
                        # Criar dataframe limpo
                        new_df = df_template[[id_col, name_col]].copy()
                        if uf_col:
                            new_df['UF'] = df_template[uf_col]
                        
                        # Renomear para padrão
                        new_df = new_df.rename(columns={id_col: 'id', name_col: 'Municipio'})
                        new_df['demanda'] = "" # Coluna vazia
                        
                        return new_df.to_csv(index=False, sep=';', encoding='utf-8'), None
                    else:
                        return None, f"Colunas obrigatórias não encontradas no arquivo base. (ID: {id_col}, Nome: {name_col})"
                except Exception as e:
                    return None, str(e)

            template_csv, error_msg = get_template_csv()
            if template_csv:
                st.download_button(
                    label="📥 Baixar Template (CSV)",
                    data=template_csv,
                    file_name="template_demanda.csv",
                    mime="text/csv",
                    help="Clique para baixar o arquivo base."
                )
            else:
                st.warning(f"Não foi possível gerar o template: {error_msg}")

            st.markdown("---")
            st.subheader("2. Cidades já Cobertas (Cobertura Inicial)")
            
            # Checkbox para iniciar sem cobertura existente
            no_existing_coverage = st.checkbox(
                "Iniciar sem cobertura existente (Greenfield)",
                value=False,
                help="Se marcado, o algoritmo ignorará os campi atuais e selecionará todos os locais do zero."
            )
            
            existing_sites_file = config.EXISTING_SITES_FILE
            
            if not no_existing_coverage:
                # Upload de Arquivo para Campi Existentes (Opcional)
                uploaded_existing = st.file_uploader(
                    "Upload de Arquivo de Campi Existentes (Opcional)", 
                    type=["csv", "parquet"],
                    accept_multiple_files=False,
                    help="Arquivo CSV contendo os IDs dos municípios que já possuem campi. Colunas esperadas: 'id' ou 'cod_ibge'."
                )
                
                if uploaded_existing is not None:
                    existing_sites_file = uploaded_existing
                    display_path_existing = f"Arquivo Carregado: {uploaded_existing.name}"
                else:
                    display_path_existing = config.EXISTING_SITES_FILE
                    
                # Exibição apenas leitura
                st.text_input(
                    "Caminho do Arquivo de Campi", 
                    value=display_path_existing,
                    disabled=True
                )
                
                # --- Pré-visualização e Validação para Campi Existentes ---
                df_preview_existing = None
                try:
                    if uploaded_existing is not None:
                        uploaded_existing.seek(0)
                        if uploaded_existing.name.lower().endswith('.parquet'):
                            df_preview_existing = pd.read_parquet(uploaded_existing)
                        else:
                            try:
                                df_preview_existing = pd.read_csv(uploaded_existing, sep=None, engine='python', encoding='utf-8', dtype=str)
                            except UnicodeDecodeError:
                                uploaded_existing.seek(0)
                                df_preview_existing = pd.read_csv(uploaded_existing, sep=None, engine='python', encoding='latin1', dtype=str)
                    elif config.EXISTING_SITES_FILE:
                         # Arquivo garantido pela inicialização
                         file_ready_exist = True

                         if file_ready_exist:
                            if config.EXISTING_SITES_FILE.lower().endswith('.parquet'):
                                df_preview_existing = pd.read_parquet(config.EXISTING_SITES_FILE)
                            else:
                                try:
                                    df_preview_existing = pd.read_csv(config.EXISTING_SITES_FILE, sep=';', engine='python', encoding='utf-8', dtype=str)
                                except:
                                    df_preview_existing = pd.read_csv(config.EXISTING_SITES_FILE, sep=None, engine='python', encoding='latin1', dtype=str)
                            
                    if df_preview_existing is not None:
                        with st.expander("Pré-visualizar Dados"):
                            st.dataframe(df_preview_existing.head())
                            
                        # Validation
                        cols_exist = df_preview_existing.columns.tolist()
                        id_candidates = ['id', 'ID', 'Id', 'Cód.', 'Cod.', 'Código', 'Codigo', 'Code', 'cod_ibge', 'cód.ibge']
                        found_id_exist = any(c in cols_exist for c in id_candidates)
                        
                        if found_id_exist:
                             st.success(f"✅ Arquivo válido! {len(df_preview_existing)} registros encontrados.")
                        else:
                             st.error("❌ Coluna de ID não encontrada (esperado: 'id', 'cod_ibge', etc).")
                except Exception as e:
                    st.error(f"Erro ao ler arquivo de campi: {e}")

                
                # Download de Modelo
                st.markdown("##### Baixar Modelo")

                template_csv_content = None
                
                template_csv_content = None
                             
                source_file = config.DEMAND_FILE
                if True: # Tentar carregar sempre
                    # Garantir download da fonte se não existir
                    if not os.path.exists(source_file) or data_loader.is_lfs_pointer(source_file):
                          data_loader.check_and_debug_path(source_file)

                    if os.path.exists(source_file):
                        try:
                            if source_file.lower().endswith('.parquet'):
                                df_base = pd.read_parquet(source_file)
                            else:
                                try:
                                    df_base = pd.read_csv(source_file, sep=None, engine='python', encoding='utf-8', dtype=str)
                                except UnicodeDecodeError:
                                    df_base = pd.read_csv(source_file, sep=None, engine='python', encoding='latin1', dtype=str)
                        
                            # Encontrar colunas
                            id_col = next((c for c in df_base.columns if c in ['id', 'ID', 'Id', 'Cód.', 'Cod.', 'Código', 'Codigo', 'Code']), None)
                            
                            # Normalizar para busca por nome
                            import unicodedata
                            def normalize(s):
                                return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').lower()
                            cols_map = {normalize(c): c for c in df_base.columns}
                            name_col = cols_map.get('municipio') or cols_map.get('nome')
                            uf_col = cols_map.get('uf')
                            
                            if id_col and name_col:
                                df_template_existing = df_base[[id_col, name_col]].copy()
                                if uf_col:
                                    df_template_existing['UF'] = df_base[uf_col]
                                
                                df_template_existing = df_template_existing.rename(columns={id_col: 'id', name_col: 'Municipio'})
                                df_template_existing['possui_campus'] = "N" # Default to No
                                
                                csv_template = df_template_existing.to_csv(index=False, sep=';', encoding='utf-8')
                            else:
                                 # Fallback se colunas não forem encontradas
                                 template_data = {'id': [], 'possui_campus': []}
                                 csv_template = pd.DataFrame(template_data).to_csv(index=False, sep=';').encode('utf-8')
                        except Exception as e:
                             # Fallback em caso de erro
                             template_data = {'id': [], 'possui_campus': []}
                             csv_template = pd.DataFrame(template_data).to_csv(index=False, sep=';').encode('utf-8')
                else:
                    # Fallback se arquivo não encontrado
                    template_data = {
                        'id': [1100205, 1302603, 5300108],
                        'nome': ['Porto Velho', 'Manaus', 'Brasília'],
                        'uf': ['RO', 'AM', 'DF'],
                        'possui_campus': ['S', 'N', 'S']
                    }
                    df_template_existing = pd.DataFrame(template_data)
                    csv_template = df_template_existing.to_csv(index=False, sep=';').encode('utf-8')
                
                st.download_button(
                    label="📥 Baixar Template (CSV)",
                    data=csv_template,
                    file_name="template_cobertura_inicial.csv",
                    mime="text/csv",
                    help="Baixe um modelo de arquivo para preencher com os seus dados."
                )
            else:
                existing_sites_file = None
                st.info("ℹ️ A otimização será iniciada sem considerar nenhuma cobertura prévia.")
                
        coords_file = config.COORDS_FILE

    # --- Cabeçalho e UI Principal ---
    
    with st.container():
        # Título com Logo
        col_logo, col_title = st.columns([1, 4], vertical_alignment="top")
        with col_logo:
            st.image("logo.png", width=250)
        with col_title:
            st.title("Maximum Coverage Location Problem")
            st.markdown("""
            <h3 style="font-weight: normal; font-size: 1.2rem; margin-top: -10px;">
            Solucionador Heurístico do Problema de Localização de Máxima Cobertura <br>
            para novos campi da Rede Federal de Educação Profissional e Tecnológica - RFEPT no Brasil
            <a href="#open-modal" class="saiba-mais-link" style="margin-left: 10px; text-decoration: none; font-size: 0.6em; vertical-align: middle;">Saiba mais</a>
            </h3>
            """, unsafe_allow_html=True)
            
            st.write("") # Espaçador
            
            # Inicializar estado da sessão para resultados se não existirem
            if 'optimization_results' not in st.session_state:
                st.session_state['optimization_results'] = None

            # Botões de Ação
            col_b1, col_b2 = st.columns([1, 0.2])
            with col_b1:
                start_optimization = st.button("▶️ INICIAR OTIMIZAÇÃO", type="primary", help="Clique para começar o cálculo da melhor localização para os novos campi.")
            with col_b2:
                st.button("🔄 RESET", help="Limpar dados e reiniciar aplicação", on_click=reset_app)

    # Divisor para separar Cabeçalho dos Resultados
    st.divider()

    if start_optimization:
        # Executar cálculo
        try:
            results_data = calculate_optimization(p, radius, max_time, use_km, target_uf,
                                                  ls_max_iter, ls_strategy, 
                                                  vns_max_iter, vns_k_max, vns_max_no_improv, vns_max_time, vns_ls_strategy,
                                                  demand_file, demand_col, coords_file, existing_sites_file)
            # Armazenar no estado da sessão
            st.session_state['optimization_results'] = results_data
        except ValueError as e:
            st.error(f"Erro nos dados de entrada: {e}")
        except Exception as e:
            st.error(f"Ocorreu um erro inesperado: {e}")

    # Sempre verificar se há resultados para exibir
    if st.session_state['optimization_results']:
        render_results(st.session_state['optimization_results'])

def calculate_optimization(p, radius, max_time, use_km, target_uf, 
                           ls_max_iter, ls_strategy,
                           vns_max_iter, vns_k_max, vns_max_no_improv, vns_max_time, vns_ls_strategy,
                           demand_file, demand_col, coords_file, existing_sites_file):
    
    # 1. Carregar Dados
    with st.status("Carregando Dados...", expanded=True) as status:
        st.write("Carregando distâncias...")
        dist_df = data_loader.load_distances(config.DISTANCES_FILE, uf_filter=target_uf)
        
        existing_site_ids = set()
        if existing_sites_file:
            st.write("Carregando campi existentes...")
            sites_df = data_loader.load_existing_sites(existing_sites_file, uf_filter=target_uf)
            existing_site_ids = set(sites_df['id'].unique())
        else:
            st.write("Iniciando sem cobertura prévia (Greenfield)...")
        
        st.write("Carregando demanda...")
        demand_dict, names_dict, uf_dict = data_loader.load_demand(
            demand_file, 'Cód.', [demand_col], uf_filter=target_uf
        )
        
        st.write("Carregando coordenadas...")
        coords_dict = data_loader.load_coordinates(coords_file, uf_filter=target_uf)
        
        status.update(label="Dados Carregados com Sucesso!", state="complete", expanded=False)

    # Preparar Conjuntos
    I = list(demand_dict.keys())
    J = [i for i in I if i not in existing_site_ids]
    
    # Cobertura e Estruturas Esparsas
    with st.spinner("Preparando Estruturas de Dados (Sparse)..."):
        # 1. Filtrar DF de Distância (Vetorizado)
        relevant_origins = set(J) | existing_site_ids
        mask_valid = dist_df['origem'].isin(relevant_origins) & dist_df['destino'].isin(I)
        dist_filtered = dist_df[mask_valid].copy()
        
        if use_km:
            dist_filtered = dist_filtered[dist_filtered['distancia'] <= radius]
        else:
            dist_filtered = dist_filtered[dist_filtered['tempo'] <= max_time]

        # 2. Identificar Nós Pré-Cobertos
        pre_covered = set(dist_filtered[dist_filtered['origem'].isin(existing_site_ids)]['destino'].unique())
        
        # 3. Construir Matriz Esparsa
        sparse_structures = heuristics.build_sparse_matrix_from_df(
            dist_filtered, demand_dict, J, I, radius, max_time, use_km, pre_covered
        )
        cov_matrix, demand_vector, cand_to_idx, node_to_idx, initial_coverage = sparse_structures

    # --- Execução das Heurísticas ---
    # Calcular Z Inicial
    z_initial = sum(demand_dict[i] for i in pre_covered if i in demand_dict)
    
    # --- Execução das Heurísticas ---
    results = []
    results.append({"Método": "Inicial (Existente)", "Z (Cobertura)": z_initial, "Tempo (s)": 0.0})
    
    # Criar um placeholder para evitar duplicação depois
    z_initial_placeholder = st.empty()
    with z_initial_placeholder.container():
        st.subheader("Valor Z Inicial (Cobertura Existente)")
        st.metric("**Demanda Coberta**", ui_components.format_number_br(z_initial)) 
        st.divider()

    results = results # Manter lista de resultados (já inicializada acima)
    history_data = []
    global_step = 0
    
    # Containers para progresso
    progress_placeholder = st.empty()
    with progress_placeholder.container():
        st.subheader("Progresso da Execução")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Greedy (Guloso)**")
            greedy_prog = st.progress(0)
            greedy_z = st.empty()
            
        with col2:
            st.markdown("**Busca Local**")
            ls_prog = st.progress(0)
            ls_z = st.empty()
            
        with col3:
            st.markdown("**VNS (Meta-heurística)**")
            vns_prog = st.progress(0)
            vns_z = st.empty()

    # 1. Greedy (Guloso)
    t0 = time.time()
    def greedy_callback(step, total, metrics):
        nonlocal global_step
        global_step += 1
        greedy_prog.progress(min(step / total, 1.0))
        greedy_z.metric("Valor Z", ui_components.format_number_br(metrics['z']))
        history_data.append({'Passo': global_step, 'Z': metrics['z'], 'Método': 'Greedy'})
        
    s_greedy = heuristics.greedy_heuristic(J, p, cov_matrix, demand_vector, cand_to_idx, initial_coverage, progress_callback=greedy_callback)
    
    # Calcular Z para Greedy usando busca local de 0 iterações (para garantir consistência)
    _, z_greedy = heuristics.local_search(s_greedy, J, cov_matrix, demand_vector, cand_to_idx, initial_coverage, max_iter=0)

    results.append({"Método": "Greedy", "Z (Cobertura)": z_greedy, "Tempo (s)": time.time() - t0})
    ls_z.metric("Valor Z", ui_components.format_number_br(z_greedy))

    # 2. Busca Local Esparsa
    t0 = time.time()
    def ls_callback(step, total, metrics):
        nonlocal global_step
        ls_prog.progress(min(step / total, 1.0))
        ls_z.metric("Valor Z", ui_components.format_number_br(metrics['z']))
        
        # Logar cada passo (metrics['z'] é o Z atual após melhoria)
        current_z = metrics['z']
        
        # Logar candidatos ("tentativas") se presentes - visualizar esforço de busca
        if 'candidate_zs' in metrics:
            for z_cand in metrics['candidate_zs']:
                # Logar apenas se for diferente o suficiente ou para mostrar atividade
                global_step += 1
                history_data.append({'Passo': global_step, 'Z': z_cand, 'Método': 'Busca Local'})
                
        # Sempre logar o 'z' atual como ponto estável
        global_step += 1
        history_data.append({'Passo': global_step, 'Z': metrics['z'], 'Método': 'Busca Local'})
        
    s_local, z_local = heuristics.local_search(
        s_greedy, J, cov_matrix, demand_vector, cand_to_idx, initial_coverage,
        max_iter=ls_max_iter, strategy=ls_strategy, show_progress=True, progress_callback=ls_callback
    )
    results.append({"Método": "Busca Local", "Z (Cobertura)": z_local, "Tempo (s)": time.time() - t0})
    ls_prog.progress(1.0)
    ls_z.metric("Valor Z", ui_components.format_number_br(z_local))

    # 3. VNS (Esparso)
    t0 = time.time()
    def vns_callback(step, total, metrics):
        nonlocal global_step
        
        # Verificar se é atualização do Loop Principal VNS (tem 'k') ou Loop Interno LS
        is_vns_update = 'k' in metrics
        
        current_z = metrics['z']

        if is_vns_update:
            # 1. Update UI Elements (Only for VNS outer loop)
            vns_prog.progress(min(step / total, 1.0))
            vns_z.metric("Valor Z", ui_components.format_number_br(current_z), f"k={metrics.get('k')}")
            
            # 2. Log End of Iteration Visualization
            if 'z_viz' in metrics:
                 global_step += 1
                 history_data.append({'Passo': global_step, 'Z': metrics['z_viz'], 'Método': 'VNS'})
                 global_step += 1
                 history_data.append({'Passo': global_step, 'Z': current_z, 'Método': 'VNS'})
            
            # 3. Log Best Z Trace
            k = metrics['k']
            if k == 1 or step == total:
                global_step += 1
                history_data.append({'Passo': global_step, 'Z': current_z, 'Método': 'VNS'})
        else:
            # Inner Local Search Update
            # Do NOT update progress bar (avoids flickering/resetting)
            
            # Log candidates ("attempts") if present - visualize the search effort in VNS too
            if 'candidate_zs' in metrics:
                for z_cand in metrics['candidate_zs']:
                    global_step += 1
                    history_data.append({'Passo': global_step, 'Z': z_cand, 'Método': 'VNS'})

            # Just log the trajectory point (Stable incumbent)
            global_step += 1
            history_data.append({'Passo': global_step, 'Z': current_z, 'Método': 'VNS'})
        
    s_vns, z_vns = heuristics.vns(
        s_local, J, None, demand_dict, pre_covered, # None for coverage_map
        k_max=vns_k_max, max_iter=vns_max_iter, max_no_improv=vns_max_no_improv, max_time_seconds=vns_max_time, ls_strategy=vns_ls_strategy,
        progress_callback=vns_callback,
        sparse_structures=sparse_structures
    )
    
    results.append({"Método": "VNS", "Z (Cobertura)": z_vns, "Tempo (s)": time.time() - t0})
    vns_prog.progress(1.0)
    vns_z.metric("Valor Z", ui_components.format_number_br(z_vns))


    # Pós-Otimização: Construir Mapa de Cobertura para UI (Apenas para Solução + Existentes)
    with st.spinner("Preparando visualização..."):
        ui_sites = set(s_vns) | existing_site_ids
        ui_dist_df = dist_filtered[dist_filtered['origem'].isin(ui_sites)]
        # Reconstruir dicionário para componentes de UI
        coverage_map = ui_dist_df.groupby('origem')['destino'].apply(set).to_dict()
        # Garantir auto-cobertura para lógica de UI
        for s in ui_sites:
            if s not in coverage_map: coverage_map[s] = set()
            coverage_map[s].add(s)

    # Limpar barras de progresso para evitar duplicação com render_results
    progress_placeholder.empty()
    # Limpar placeholder de Z Inicial também
    z_initial_placeholder.empty()

    # Retornar todos os dados necessários para renderização
    return {
        'results': results,
        'history_data': history_data,
        's_vns': s_vns,
        'existing_site_ids': existing_site_ids,
        'dist_df': dist_df,
        'demand_dict': demand_dict,
        'names_dict': names_dict,
        'uf_dict': uf_dict,
        'coords_dict': coords_dict,
        'coverage_map': coverage_map,
        'pre_covered': pre_covered,
        'use_km': use_km,
        # Armazenar parâmetros de entrada para garantir consistência durante renderização
        'target_uf': target_uf,
        'demand_file': getattr(demand_file, 'name', str(demand_file)),
        'demand_col': demand_col,
        'p': p,
        'radius': radius,
        'max_time': max_time,
        # Heuristic Params
        'ls_max_iter': ls_max_iter,
        'ls_strategy': ls_strategy,
        'vns_max_iter': vns_max_iter,
        'vns_k_max': vns_k_max,
        'vns_max_no_improv': vns_max_no_improv,
        'vns_max_time': vns_max_time,
        'vns_ls_strategy': vns_ls_strategy,
        # File info
        'existing_sites_file': getattr(existing_sites_file, 'name', str(existing_sites_file)) if existing_sites_file else "Nenhum"
    }

def render_results(data):
    ui_components.render_results(data)

if __name__ == "__main__":
    main()

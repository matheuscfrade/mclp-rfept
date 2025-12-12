import streamlit as st
import pandas as pd
import plotly.express as px
import os
import config
import data_loader
import report_utils
import map_renderer

def format_number_br(value, decimals=0):
    """Formata um número para o padrão brasileiro (1.000,00)."""
    try:
        value = float(value)
    except (ValueError, TypeError):
        return str(value) if value is not None else ""

    if decimals == 0:
        return f"{value:,.0f}".replace(",", ".")
    else:
        return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def render_results(data):
    # Desempacotar dados
    results = data['results']
    history_data = data['history_data']
    s_vns = data['s_vns']
    existing_site_ids = data['existing_site_ids']
    dist_df = data['dist_df']
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

    # --- Cobertura Inicial (Persistente) ---
    z_initial = next((r['Z (Cobertura)'] for r in results if r['Método'] == 'Inicial (Existente)'), 0)
    
    st.subheader("Valor Z Inicial (Cobertura Existente)")
    st.metric("**Demanda Coberta**", format_number_br(z_initial)) 
    st.divider()

    # --- Resumo de Progresso (Persistente) ---
    st.subheader("Progresso da Execução")
    
    col1, col2, col3 = st.columns(3)
    
    # Extrair valores Z dos resultados
    z_greedy = next((r['Z (Cobertura)'] for r in results if r['Método'] == 'Greedy'), 0)
    z_local = next((r['Z (Cobertura)'] for r in results if r['Método'] == 'Busca Local'), 0)
    z_vns = next((r['Z (Cobertura)'] for r in results if r['Método'] == 'VNS'), 0)
    
    with col1:
        st.markdown("**Greedy (Guloso)**")
        st.progress(1.0)
        st.metric("Valor Z", format_number_br(z_greedy))
        
    with col2:
        st.markdown("**Busca Local**")
        st.progress(1.0)
        st.metric("Valor Z", format_number_br(z_local))
        
    with col3:
        st.markdown("**VNS (Meta-heurística)**")
        st.progress(1.0)
        st.metric("Valor Z", format_number_br(z_vns))
        
    # --- Results ---
    st.divider()
    st.header("📊 Resultados")
    
    # Tabela de Resumo
    res_df = pd.DataFrame(results)
    display_res_df = res_df.copy()
    display_res_df['Z (Cobertura)'] = display_res_df['Z (Cobertura)'].apply(lambda x: format_number_br(x))
    display_res_df['Tempo (s)'] = display_res_df['Tempo (s)'].apply(lambda x: f"{format_number_br(x, 2)}s")
    st.table(display_res_df)
    
    # Gráfico de Evolução
    st.subheader("Evolução da Cobertura (Z)")
    if history_data:
        hist_df = pd.DataFrame(history_data)
        
        # Calcular "Melhor Até Agora" para visualização de progresso mais clara
        hist_df['Melhor Z'] = hist_df['Z'].cummax()
        
        # Criar a figura
        import plotly.graph_objects as go
        
        fig = go.Figure()
        
        # 1. Trajetória Bruta (apagada)
        # Agrupamos por método para manter cores se desejado, ou plotamos tudo como um traço
        # Vamos manter cores por método mas transparente
        methods = hist_df['Método'].unique()
        colors = {"Greedy": "#6c757d", "Busca Local": "#007bff", "VNS": "#28a745"}
        
        for method in methods:
            df_m = hist_df[hist_df['Método'] == method]
            fig.add_trace(go.Scatter(
                x=df_m['Passo'], 
                y=df_m['Z'],
                mode='lines',
                name=f"{method} (Trajetória)",
                line=dict(color=colors.get(method, "gray"), width=1.5),
                opacity=0.8, # Make it more visible (was 0.3)
                showlegend=True
            ))
            
        # 2. Melhor Até Agora (Proeminente)
        fig.add_trace(go.Scatter(
            x=hist_df['Passo'], 
            y=hist_df['Melhor Z'],
            mode='lines',
            name='Melhor Z Encontrado',
            line=dict(color='white', width=3), # High contrast
            opacity=1.0
        ))
        
        fig.update_layout(
            title="Progresso da Otimização (Trajetória vs Melhor Global)",
            xaxis_title="Passos (Ações)",
            yaxis_title="População Coberta (Z)",
            legend_title="Legenda",
            hovermode="x unified",
            template="plotly_dark" # Fits the dark theme better
        )
        
        st.plotly_chart(fig, use_container_width=True)

    # Conjunto de todos os locais ativos (existentes + solução)
    all_sites = existing_site_ids | set(s_vns)
    
    # Filtrar distâncias para análise Local -> Local (para campus mais próximo)
    mask_sites = dist_df['origem'].isin(s_vns) & dist_df['destino'].isin(all_sites)
    dist_sites = dist_df[mask_sites].copy()
    dist_lookup = dist_sites.set_index(['origem', 'destino'])[['distancia', 'tempo']].to_dict('index')
    
    solution_data = []
    
    # Rastrear cobertura acumulada (começa com locais existentes)
    # Isso previne contagem dupla na soma da tabela
    covered_so_far = set(pre_covered)
    
    # Ordenar para atribuição determinística
    sorted_s_vns = sorted(list(s_vns))

    for idx, site_id in enumerate(sorted_s_vns):
        # 1. Informações Básicas
        name = names_dict.get(site_id, 'Desconhecido')
        uf = uf_dict.get(site_id, '')
        pop_local = demand_dict.get(site_id, 0)
        lat, lon = coords_dict.get(site_id, (None, None))
        
        # 2. Vizinhos e População Coberta
        all_covered = coverage_map.get(site_id, set())
        
        # Nós unicamente novos cobertos (não cobertos por existentes OU locais de solução anteriores)
        unique_newly_covered = all_covered - covered_so_far
        
        # Atualizar rastreador global
        covered_so_far.update(unique_newly_covered)
        
        # 3. Exibição de Vizinhos (manter lógica mostrando TODOS vizinhos, mas marcar novos)
        neighbors = all_covered - {site_id}
        neighbors_new = neighbors - pre_covered # Manter puramente 'novo vs existente' para lista "Vizinhos" se desejado, ou ficar no único?
        # Usuário quer que soma da tabela coincida. A lista de vizinhos geralmente mostra alcance potencial.
        # Vamos manter lista de vizinhos como "vs Pre-Covered" (Definição original) mas estritamente controlar a coluna "Pop Nova Coberta".
        
        neighbors_list = sorted(list(neighbors_new))
        neighbors_formatted = []
        for n in neighbors_list:
            n_name = names_dict.get(n, str(n))
            n_pop = demand_dict.get(n, 0)
            neighbors_formatted.append(f"{n_name} ({format_number_br(n_pop)})")
        neighbors_str = ", ".join(neighbors_formatted)
        
        pop_vizinhos_new = sum(demand_dict.get(n, 0) for n in neighbors_new)
        
        # 4. População coberta ÚNICA NOVA Total (A métrica que soma para ganho Z)
        pop_nova_coberta = sum(demand_dict.get(n, 0) for n in unique_newly_covered)
        
        # 5. Campus Mais Próximo (Existente ou Outro Selecionado)
        other_sites = all_sites - {site_id}
        
        nearest_site = None
        min_dist = float('inf')
        min_time = float('inf')
        
        for other in other_sites:
            d_info = dist_lookup.get((site_id, other))
            if d_info:
                d = d_info['distancia']
                t = d_info['tempo']
                if use_km:
                    if d < min_dist:
                        min_dist = d
                        min_time = t
                        nearest_site = other
                else:
                    if t < min_time:
                        min_dist = d
                        min_time = t
                        nearest_site = other
                        
        nearest_name = names_dict.get(nearest_site, str(nearest_site)) if nearest_site else "Nenhum"
        
        solution_data.append({
            'municipio_id': site_id,
            'municipio_nome': name,
            'municipio_uf': uf,
            'populacao_local': pop_local,
            'vizinhos': neighbors_str,
            'populacao_vizinhos': pop_vizinhos_new,
            'populacao_nova_coberta': pop_nova_coberta,
            'campus_mais_proximo': nearest_name,
            'distancia_km': min_dist if nearest_site else 0,
            'tempo_h': min_time if nearest_site else 0,
            'Lat': lat, # Keep for map
            'Lon': lon  # Keep for map
        })
        
    sol_df = pd.DataFrame(solution_data)
    
    # Preparar para Exibição: Remover Lat/Lon e configurar colunas
    display_df = sol_df.drop(columns=['Lat', 'Lon'], errors='ignore')
    
    # Renomear colunas para melhor exibição
    rename_map = {
        'municipio_id': 'ID',
        'municipio_nome': 'Município',
        'municipio_uf': 'UF',
        'populacao_local': 'Pop. Local',
        'vizinhos': 'Vizinhos Cobertos',
        'populacao_vizinhos': 'Pop. Vizinhos',
        'populacao_nova_coberta': 'Pop. Nova Coberta',
        'campus_mais_proximo': 'Cidade campus + próx.',
        'distancia_km': 'Distância (km)',
        'tempo_h': 'Tempo (h)'
    }
    display_df = display_df.rename(columns=rename_map)

    # Formatar colunas de Distância e Tempo para 2 casas decimais
    if 'Distância (km)' in display_df.columns:
        display_df['Distância (km)'] = display_df['Distância (km)'].apply(lambda x: format_number_br(x, 2) if x > 0 else "")
    if 'Tempo (h)' in display_df.columns:
        display_df['Tempo (h)'] = display_df['Tempo (h)'].apply(lambda x: format_number_br(x, 2) if x > 0 else "")
    
    st.subheader("Locais Selecionados (Detalhado)")
    
    if display_df.empty:
        st.warning("Nenhum local foi selecionado. Verifique arquivo de demanda.")
        return

    # Botão de Download
    csv = display_df.to_csv(index=False, sep=';').encode('utf-8')
    st.download_button(
        "📥 Baixar Solução (CSV)",
        csv,
        "solucao_vns.csv",
        "text/csv",
        key='download-csv'
    )
    
    # --- Filtros Interativos (Custom) ---
    # st.dataframe não suporta quebra de linha, então usamos st.table com filtros customizados
    st.markdown("##### 🔍 Filtros e Ordenação")
    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
    with col_f1:
        search_term = st.text_input("Filtrar na Tabela",
        help="Digite termos para filtrar. A busca verifica todas as colunas.")
    with col_f2:
        # Ordenação padrão por 'Pop. Nova Coberta' se disponível
        default_idx = 0
        if 'Pop. Nova Coberta' in display_df.columns:
            default_idx = list(display_df.columns).index('Pop. Nova Coberta')
        sort_col = st.selectbox("Ordenar por", display_df.columns, index=default_idx)
    with col_f3:
        sort_asc = st.checkbox("Crescente", value=False)

    # Aplicar Filtro
    filtered_df = display_df.copy()
    if search_term:
        # Busca inteligente: Dividir termos e exigir que TODOS estejam presentes na linha
        terms = search_term.lower().split()
        
        def row_matches(row):
            row_str = " ".join(row.astype(str)).lower()
            return all(term in row_str for term in terms)
            
        mask = filtered_df.apply(row_matches, axis=1)
        filtered_df = filtered_df[mask]
        
    # Aplicar Ordenação
    if sort_col:
        filtered_df = filtered_df.sort_values(by=sort_col, ascending=sort_asc)
        
    # --- Adicionar Linha de Total (Após ordenação, para ficar no final? Não, tipicamente queremos no final distinto dos itens ordenados) ---
    # Na verdade se ordenarmos, queremos que Total seja o último. Então anexar DEPOIS da ordenação.
    if not filtered_df.empty:
        total_local = filtered_df['Pop. Local'].sum()
        total_viz = filtered_df['Pop. Vizinhos'].sum()
        total_nova = filtered_df['Pop. Nova Coberta'].sum()
        
        # Criar um dicionário com todas as colunas para evitar problemas de NaN em colunas específicas se necessário
        # Preenchemos cols string com vazio/traço e numéricas com totais
        total_data = {c: '' for c in filtered_df.columns}
        total_data.update({
            'Município': 'TOTAL GERAL',
            'Pop. Local': total_local,
            'Pop. Vizinhos': total_viz,
            'Pop. Nova Coberta': total_nova
        })
        
        # Para colunas numéricas que não são somadas, definir como vazio (era 0)
        # Verificar cols numéricas específicas conhecidas
        for col in ['Distância (km)', 'Tempo (h)']:
             if col in filtered_df.columns:
                 total_data[col] = "" # Leave blank
        
        total_row = pd.DataFrame([total_data])
        filtered_df = pd.concat([filtered_df, total_row], ignore_index=True)

    # Estilização e Renderização
    non_wrap_cols = [c for c in filtered_df.columns if c != 'Vizinhos Cobertos']
    
    styled_df = filtered_df.style.format({
        'Dist (km)': lambda x: format_number_br(x, 2),
        'Tempo (h)': lambda x: format_number_br(x, 2),
        'Pop. Local': lambda x: format_number_br(x),
        'Pop. Vizinhos': lambda x: format_number_br(x),
        'Pop. Nova Coberta': lambda x: format_number_br(x)
    }).set_properties(subset=non_wrap_cols, **{'white-space': 'nowrap'}) \
      .set_properties(subset=['Vizinhos Cobertos'], **{'white-space': 'normal', 'min-width': '400px'}) \
      .set_table_styles([
          {'selector': 'th', 'props': [('white-space', 'nowrap')]}
      ])
      
    st.caption(f"Mostrando {len(filtered_df)} de {len(display_df)} registros.")
    st.table(styled_df)

    # Passar dataframe de solução para exportação
    data['solution_df'] = display_df
    
    # Visualização do Mapa
    map_renderer.render_maps(data)
    


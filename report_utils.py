import pandas as pd
import io
import base64
from fpdf import FPDF
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import geopandas as gpd
import numpy as np
import os
from datetime import datetime

# --- Helper Functions for Maps ---

def generate_excel_download(gdf, demand_col):
    """Gera um arquivo Excel com os resultados."""
    output = io.BytesIO()
    
    # Selecionar colunas relevantes
    cols = ['id', 'NM_MUN', 'SIGLA_UF', demand_col, 'status']
    # Adicionar distância/tempo se disponível
    if 'dist_to_site' in gdf.columns:
        cols.append('dist_to_site')
    
    df_export = gdf[cols].copy()
    
    # Renomear colunas para melhor legibilidade
    rename_dict = {
        'id': 'ID Município',
        'NM_MUN': 'Município',
        'SIGLA_UF': 'UF',
        demand_col: 'Demanda',
        'status': 'Status de Cobertura',
        'dist_to_site': 'Distância/Tempo ao Site (km/min)'
    }
    df_export.rename(columns=rename_dict, inplace=True)
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Resultados')
        
    return output.getvalue()

def generate_html_map(deck):
    """Gera um arquivo HTML do mapa."""
    return deck.to_html(as_string=True)

def create_static_map_image(gdf):
    """Cria uma imagem de mapa estática usando matplotlib."""
    import matplotlib.patches as mpatches # Import local para evitar conflitos de refatoração
    
    fig, ax = plt.subplots(figsize=(10, 11)) # Aumentar altura para legenda
    
    color_map = {
        0: '#00008B', # DarkBlue
        1: '#6495ED', # CornflowerBlue
        2: '#006400', # DarkGreen
        3: '#FFD700', # Gold
        4: '#90EE90', # LightGreen
        5: '#808080'  # Grey
    }
    
    label_map = {
        0: "Existente",
        1: "Cob. Existente",
        2: "Novo Campus",
        3: "Novo (Sobrep.)",
        4: "Nova Cobertura",
        5: "Sem Cobertura"
    }
    
    # Plotar cada categoria
    for status, color in color_map.items():
        subset = gdf[gdf['status_code'] == status]
        if not subset.empty:
            subset.plot(ax=ax, color=color, edgecolor='white', linewidth=0.2)
            
    # Criar Legenda Manual
    patches = [mpatches.Patch(color=color_map[s], label=label_map[s]) for s in sorted(color_map.keys())]
    ax.legend(handles=patches, loc='lower center', bbox_to_anchor=(0.5, 0), ncol=3, frameon=False, fontsize=9)
            
    ax.set_axis_off()
    plt.tight_layout()
    
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    img_buffer.seek(0)
    return img_buffer

def create_static_heatmap_image(gdf, demand_col):
    """Cria uma imagem estática do mapa de calor usando matplotlib com LogNorm."""
    fig, ax = plt.subplots(figsize=(10, 10))
    
    # Plotar mapa base (cinza)
    gdf.plot(ax=ax, color='#f0f0f0', edgecolor='white', linewidth=0.1)
    
    # Plotar mapa de calor
    subset = gdf[gdf[demand_col] > 0].copy()
    
    if not subset.empty:
        colors = ["#FFFFC8", "#FF0000"] # LightYellow to Red
        cmap = mcolors.LinearSegmentedColormap.from_list("CustomYlRd", colors)
        
        subset.plot(
            column=demand_col,
            ax=ax,
            cmap=cmap, # Use custom map
            norm=mcolors.LogNorm(vmin=subset[demand_col].min(), vmax=subset[demand_col].max()), # Log scale
            legend=True,
            legend_kwds={'label': "Demanda (Escala Log)", 'orientation': "horizontal", 'shrink': 0.6},
            edgecolor='none',
            alpha=0.8
        )
            
    ax.set_axis_off()
    plt.tight_layout()
    
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    img_buffer.seek(0)
    return img_buffer

# --- Internal PDF Drawing Functions ---

def _draw_cover_page(pdf):
    """Desenha a capa do relatório."""
    pdf.add_page()
    pdf.set_font("Arial", "B", 24)
    pdf.ln(60)
    pdf.cell(0, 10, "Relatório de Expansão da Rede Federal", ln=True, align="C")
    pdf.set_font("Arial", "", 16)
    pdf.cell(0, 10, "Otimização de Cobertura (MCLP)", ln=True, align="C")
    
    pdf.ln(40)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Data de Geração: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
    pdf.cell(0, 10, "Sistema de Apoio à Decisão - RFEPT", ln=True, align="C")

def _draw_introduction(pdf):
    """Desenha a seção de Introdução."""
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "1. Introdução", ln=True)
    pdf.set_font("Arial", "", 11)
    
    intro_text = (
        "Este relatório apresenta os resultados da otimização para a expansão da Rede Federal "
        "de Educação Profissional, Científica e Tecnológica. O objetivo é identificar os municípios "
        "ideais para a instalação de novos campi, maximizando a demanda atendida, "
        "respeitando critérios de distância ou tempo de deslocamento.\n\n"
        "O problema foi modelado como um Problema de Localização de Máxima Cobertura (MCLP) e "
        "resolvido utilizando heurísticas computacionais avançadas para garantir eficiência e qualidade "
        "na tomada de decisão."
    )
    pdf.multi_cell(0, 7, intro_text)
    pdf.ln(5)

def _draw_methodology(pdf, params):
    """Desenha a seção de Metodologia e Parâmetros."""
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "2. Metodologia e Parâmetros", ln=True)
    pdf.set_font("Arial", "", 11)
    
    metodologia_text = (
        "A solução foi obtida através de uma abordagem em três etapas:\n"
        "1. Algoritmo Guloso (Greedy): Construção inicial rápida.\n"
        "2. Busca Local: Refinamento da solução através de trocas na vizinhança.\n"
        "3. VNS (Variable Neighborhood Search): Meta-heurística para escapar de ótimos locais.\n\n"
        "Os seguintes parâmetros e arquivos foram utilizados para esta análise:"
    )
    pdf.multi_cell(0, 7, metodologia_text)
    pdf.ln(2)
    
    # Parâmetros Gerais
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, "Parâmetros Gerais:", ln=True)
    pdf.set_font("Courier", "", 9)
    
    pdf.cell(5)
    pdf.cell(0, 5, f"- Número de Novos Campi (P): {params.get('p')}", ln=True)
    
    if params.get('use_km'):
        metric_val = f"{params.get('radius')} km"
        metric_label = "Raio de Cobertura Máximo"
    else:
        metric_val = f"{params.get('max_time')} horas"
        metric_label = "Tempo de Viagem Máximo"
        
    pdf.cell(5)
    pdf.cell(0, 5, f"- {metric_label}: {metric_val}", ln=True)
    
    uf_target = params.get('target_uf') if params.get('target_uf') else "Brasil (Todo o território)"
    pdf.cell(5)
    pdf.cell(0, 5, f"- Região de Análise: {uf_target}", ln=True)
    
    # Arquivos
    pdf.ln(2)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, "Arquivos de Dados:", ln=True)
    pdf.set_font("Courier", "", 9)
    # Usar multi_cell para caminhos longos
    pdf.set_x(15) # Indentation
    pdf.multi_cell(0, 5, f"- Demanda: {params.get('demand_file_name', 'Padrão')}")
    pdf.set_x(15)
    pdf.multi_cell(0, 5, f"- Campi Existentes: {params.get('existing_sites_file_name', 'Nenhum/Padrão')}")

    # Parâmetros Heurísticos
    pdf.ln(2)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, "Configuração das Heurísticas:", ln=True)
    pdf.set_font("Courier", "", 9)
    
    pdf.cell(5)
    pdf.cell(0, 5, f"- Busca Local (Iterações): {params.get('ls_max_iter', '?')}", ln=True)
    pdf.cell(5)
    pdf.cell(0, 5, f"- Busca Local (Estratégia): {'Best Improvement' if params.get('ls_strategy') == 'best' else 'First Improvement'}", ln=True)
    pdf.cell(5)
    pdf.cell(0, 5, f"- VNS (Iterações Máx): {params.get('vns_max_iter', '?')}", ln=True)
    pdf.cell(5)
    pdf.cell(0, 5, f"- VNS (Vizinhanças k_max): {params.get('vns_k_max', '?')}", ln=True)
    pdf.cell(5)
    pdf.cell(0, 5, f"- VNS (Parada sem Melhoria): {params.get('vns_max_no_improv', '?')}", ln=True)
    pdf.cell(5)
    pdf.cell(0, 5, f"- VNS (Tempo Máximo): {params.get('vns_max_time', '?')}s", ln=True)
    pdf.cell(5)
    pdf.cell(0, 5, f"- VNS (Estratégia Busca Local): {'Best Improvement' if params.get('vns_ls_strategy') == 'best' else 'First Improvement'}", ln=True)

    pdf.ln(5)

def _draw_consolidated_results(pdf, total_demand, covered_demand, coverage_percent, run_results):
    """Desenha a tabela de resultados consolidados e comparativo."""
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "3. Resultados Consolidados", ln=True)
    pdf.set_font("Arial", "", 11)
    
    pdf.cell(0, 8, f"Abaixo apresentamos a evolução da cobertura:", ln=True)
    pdf.ln(2)
    
    # Calcular comparativo
    z_initial = 0
    if run_results:
        initial_res = next((r for r in run_results if "Inicial" in r['Método']), None)
        if initial_res:
            z_initial = initial_res.get('Z (Cobertura)', 0)
    
    gain = covered_demand - z_initial
    gain_percent = ((gain / z_initial) * 100) if z_initial > 0 else 100
    
    # Caixa de Métricas Comparativas
    # Layout: | Inicial | Final (Otimizado) | Melhoria (Abs) | Melhoria (%) |
    
    pdf.set_fill_color(240, 240, 240)
    box_height = 25
    pdf.rect(10, pdf.get_y(), 190, box_height, 'F')
    start_y = pdf.get_y()
    
    col_w = 190 / 4
    
    pdf.set_y(start_y + 5)
    
    pdf.set_font("Arial", "B", 11)
    pdf.set_x(10)
    pdf.cell(col_w, 5, "Cobertura Inicial", align="C")
    pdf.cell(col_w, 5, "Cobertura Final", align="C")
    pdf.cell(col_w, 5, "Ganho Absoluto", align="C")
    pdf.cell(col_w, 5, "Ganho %", align="C", ln=True)
    
    pdf.set_font("Arial", "", 12)
    pdf.set_x(10)
    pdf.cell(col_w, 8, f"{z_initial:,.0f}".replace(",", "."), align="C")
    pdf.cell(col_w, 8, f"{covered_demand:,.0f}".replace(",", "."), align="C")
    pdf.set_text_color(0, 100, 0) # Green
    pdf.cell(col_w, 8, f"+{gain:,.0f}".replace(",", "."), align="C")
    pdf.cell(col_w, 8, f"+{gain_percent:.2f}%".replace(".", ","), align="C")
    pdf.set_text_color(0, 0, 0) # Reset
    
    pdf.ln(10)
    pdf.set_y(start_y + box_height + 5)

def _draw_efficiency_table(pdf, run_results):
    """Desenha a tabela de eficiência dos algoritmos."""
    if run_results:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "3.1. Eficiência dos Algoritmos", ln=True)
        pdf.set_font("Arial", "", 10)
        
        # Centralizar Tabela
        x_center = 25
        
        # Cabeçalho
        pdf.set_fill_color(220, 220, 220)
        pdf.set_x(x_center)
        pdf.cell(60, 7, "Método", 1, 0, 'L', True)
        pdf.cell(60, 7, "Demanda Coberta (Z)", 1, 0, 'R', True)
        pdf.cell(40, 7, "Tempo (s)", 1, 1, 'R', True)
        
        # Linhas
        for res in run_results:
            method_name = res.get('Método', '-')
            z_val = res.get('Z (Cobertura)', 0)
            time_val = res.get('Tempo (s)', 0)
            
            # Formatar
            z_str = f"{z_val:,.0f}".replace(",", ".")
            time_str = f"{time_val:.2f}s".replace(".", ",")
            
            pdf.set_x(x_center)
            pdf.cell(60, 7, method_name, 1, 0, 'L')
            pdf.cell(60, 7, z_str, 1, 0, 'R')
            pdf.cell(40, 7, time_str, 1, 1, 'R')
            
        pdf.ln(5)

def _draw_maps(pdf, gdf, demand_col):
    """Desenha os mapas lado a lado."""
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Distribuição Espacial e Demanda", ln=True)
    
    y_maps = pdf.get_y()
    map_w = 90
    
    import tempfile
    
    # Mapa 1: Cobertura
    tmp_path = None
    try:
        img_buffer = create_static_map_image(gdf)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
            tmp_file.write(img_buffer.getvalue())
            tmp_path = tmp_file.name
            
        pdf.image(tmp_path, x=10, y=y_maps, w=map_w)
        pdf.set_xy(10, y_maps + map_w + 2)
        pdf.set_font("Arial", "I", 9)
        pdf.cell(map_w, 5, "Fig 1. Mapa de Cobertura Final", align="C")
        
    except Exception as e:
        pdf.set_xy(10, y_maps)
        pdf.cell(map_w, 10, f"[Mapa Indisponível]", border=1, align="C")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try: os.unlink(tmp_path)
            except: pass

    # Mapa 2: Calor
    tmp_path_heat = None
    try:
        img_buffer_heat = create_static_heatmap_image(gdf, demand_col)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file_heat:
            tmp_file_heat.write(img_buffer_heat.getvalue())
            tmp_path_heat = tmp_file_heat.name
            
        pdf.image(tmp_path_heat, x=110, y=y_maps, w=map_w)
        pdf.set_xy(110, y_maps + map_w + 2)
        pdf.set_font("Arial", "I", 9)
        pdf.cell(map_w, 5, "Fig 2. Mapa de Calor (Demanda)", align="C")
        
    except Exception as e:
        pdf.set_xy(110, y_maps)
        pdf.cell(map_w, 10, f"[Heatmap Indisponível]", border=1, align="C")
    finally:
        if tmp_path_heat and os.path.exists(tmp_path_heat):
            try: os.unlink(tmp_path_heat)
            except: pass
        
    pdf.ln(10)
    # Mover cursor para baixo da área dos mapas
    pdf.set_y(y_maps + map_w + 15)

def _draw_detailed_table(pdf, solution_df, params):
    """Desenha a tabela detalhada de municípios selecionados."""
    # Adicionar nova página em Paisagem ANTES do título para que fiquem juntos
    pdf.add_page(orientation='L')
    
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "4. Detalhamento dos Municípios Selecionados", ln=True)
    pdf.set_font("Arial", "", 11)
    
    if solution_df is not None and not solution_df.empty:
        pdf.multi_cell(0, 7, "A tabela abaixo detalha todos os municípios selecionados para instalação.")
        pdf.ln(5)
        
        # Cabeçalho da Tabela
        # Largura Paisagem ~277mm utilizável
        w_id = 15
        w_mun = 45
        w_uf = 10
        w_pop_loc = 25
        w_viz = 75 
        w_pop_viz = 25
        w_pop_new = 25
        w_campus = 35
        w_dist = 20
        
        pdf.set_font("Arial", "B", 8)
        pdf.set_fill_color(200, 220, 255)
        
        headers = [
            ("ID", w_id), ("Município", w_mun), ("UF", w_uf), 
            ("Pop. Local", w_pop_loc), ("Vizinhos (Alcance)", w_viz), 
            ("Pop. Viz.", w_pop_viz), ("Pop. Nova", w_pop_new),
            ("Campus + Prox", w_campus), ("Dist/Tempo", w_dist)
        ]
        
        for h, w in headers:
            pdf.cell(w, 8, h, border=1, fill=True, align="C")
        pdf.ln()
        
        pdf.set_font("Arial", "", 8)
        
        # Preparar dados para o loop + Total
        rows_to_print = []
        
        total_pop_local = 0
        total_pop_viz = 0
        total_pop_new = 0
        
        for _, row in solution_df.iterrows():
            
            def clean_num(val):
                if isinstance(val, (int, float)): return val
                if isinstance(val, str):
                    return float(val.replace(".", "").replace(",", ".")) if val.strip() else 0
                return 0
                
            p_local = clean_num(row.get('Pop. Local', 0))
            p_viz = clean_num(row.get('Pop. Vizinhos', 0))
            p_new = clean_num(row.get('Pop. Nova Coberta', 0))
            
            total_pop_local += p_local
            total_pop_viz += p_viz
            total_pop_new += p_new
            
            # Dados da linha
            line_data = [
                str(row.get('ID', '')),
                str(row.get('Município', ''))[:30],
                str(row.get('UF', '')),
                str(row.get('Pop. Local', '')), 
                str(row.get('Vizinhos Cobertos', '-')),
                str(row.get('Pop. Vizinhos', '')),
                str(row.get('Pop. Nova Coberta', '')),
                str(row.get('Cidade campus + próx.', ''))[:22], 
            ]
            
            dist_km = row.get('Distância (km)')
            time_h = row.get('Tempo (h)')
            
            val_dist = ""
            if dist_km: val_dist = str(dist_km)
            elif time_h: val_dist = str(time_h)
            
            line_data.append(val_dist)
            rows_to_print.append(line_data)
            
        # Adicionar linha TOTAL
        total_row = [
            "", "TOTAL GERAL", "",
            f"{total_pop_local:,.0f}".replace(",", "."),
            "-",
            f"{total_pop_viz:,.0f}".replace(",", "."),
            f"{total_pop_new:,.0f}".replace(",", "."),
            "-", "-"
        ]
        rows_to_print.append(total_row)
        
        # Render Loop
        for idx, data in enumerate(rows_to_print):
            
            is_total = (idx == len(rows_to_print) - 1)
            if is_total:
                pdf.set_font("Arial", "B", 8)
                pdf.set_fill_color(240, 240, 240)
            else:
                pdf.set_font("Arial", "", 8)
                pdf.set_fill_color(255, 255, 255) 
                
            line_height = 4
            max_lines = 1
            
            # Simular altura e linhas
            for i, text in enumerate(data):
                width = headers[i][1]
                if text:
                    lines = 0
                    effective_width = width - 4
                    words = text.split()
                    curr_w = 0
                    curr_l = 1
                    space = pdf.get_string_width(' ')
                    for w in words:
                        ww = pdf.get_string_width(w)
                        if curr_w + ww > effective_width:
                            curr_l += 1
                            curr_w = ww + space
                        else:
                            curr_w += ww + space
                    if curr_l > max_lines: max_lines = curr_l
            
            row_height = max_lines * line_height
            row_height = max(8, row_height)
            
            if pdf.get_y() + row_height > 190:
                pdf.add_page(orientation='L')
                pdf.set_font("Arial", "B", 8)
                pdf.set_fill_color(200, 220, 255)
                for h, w in headers:
                    pdf.cell(w, 8, h, border=1, fill=True, align="C")
                pdf.ln()
                if is_total: pdf.set_font("Arial", "B", 8)
                else: pdf.set_font("Arial", "", 8)
                
            x_start = pdf.get_x()
            y_start = pdf.get_y()
            
            for i, text in enumerate(data):
                width = headers[i][1]
                x_curr = pdf.get_x()
                y_curr = pdf.get_y()
                
                align = 'L'
                if i in [0, 2, 8]: align = 'C'
                if i in [3, 5, 6]: align = 'R'
                if i == 1 and is_total: align = 'R'
                
                fill = is_total 
                pdf.multi_cell(width, line_height, text, border=0, align=align, fill=fill)
                pdf.set_xy(x_curr + width, y_curr)
            
            # Draw Borders
            pdf.set_xy(x_start, y_start)
            for h, w in headers:
                pdf.rect(pdf.get_x(), pdf.get_y(), w, row_height)
                pdf.set_x(pdf.get_x() + w)
                
            pdf.ln(row_height)
            
    else:
        pdf.multi_cell(0, 7, "Nenhum dado detalhado disponível.")

    pdf.ln(10)

def _draw_conclusion(pdf, params, z_initial, covered_demand):
    """Desenha a seção de Conclusão."""
    pdf.add_page(orientation='P')
    
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "5. Conclusão", ln=True)
    pdf.set_font("Arial", "", 11)
    
    gain = covered_demand - z_initial
    gain_percent = ((gain / z_initial) * 100) if z_initial > 0 else 100
    
    p_val = params.get('p')
    
    conclusao_text = (
        f"A análise realizada para a instalação de {p_val} novos campi demonstra um potencial significativo de expansão. "
        f"Partindo de uma cobertura inicial de {z_initial:,.0f} pessoas, a otimização alcançou um total de {covered_demand:,.0f} pessoas atendidas, "
        f"representando um incremento líquido de {gain:,.0f} pessoas na população coberta (+{gain_percent:.1f}%).\n\n"
        "A implementação das unidades nos locais sugeridos (detalhados na seção 4) maximiza o impacto social dos recursos públicos, "
        "atendendo objetivamente às diretrizes de planejamento estratégico da RFEPT e garantindo que as novas escolas sejam posicionadas "
        "onde há maior demanda."
    ).replace(",", "X").replace(".", ",").replace("X", ".")
    
    pdf.multi_cell(0, 7, conclusao_text)

def generate_pdf_report(gdf, demand_col, total_demand, covered_demand, coverage_percent, params, solution_df=None, run_results=None):
    """
    Gera um relatório em PDF abrangente.
    params: dict contendo 'p', 'radius', 'max_time', 'use_km', 'target_uf', e params heuristicos
    solution_df: DataFrame contendo a tabela de solução detalhada
    run_results: Lista de dicionários com o histórico de execução
    """
    class PDF(FPDF):
        def header(self):
            # Header simétrico
            # self.set_font('Arial', 'B', 15)
            pass # Sem header fixo para capa, ou usar flag

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, 'Página ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')

    pdf = PDF()
    pdf.alias_nb_pages()
    
    # 1. Capa
    _draw_cover_page(pdf)
    
    # 2. Introdução
    _draw_introduction(pdf)
    
    # 3. Metodologia
    _draw_methodology(pdf, params)
    
    # 4. Resultados Consolidados & Eficiência
    _draw_consolidated_results(pdf, total_demand, covered_demand, coverage_percent, run_results)
    _draw_efficiency_table(pdf, run_results)
    
    # 5. Mapas
    _draw_maps(pdf, gdf, demand_col)
    
    # 6. Tabela Detalhada (Muda page para Landscape internamente)
    _draw_detailed_table(pdf, solution_df, params)
    
    # 7. Conclusão
    z_initial = 0
    if run_results:
        initial_res = next((r for r in run_results if "Inicial" in r['Método']), None)
        if initial_res: z_initial = initial_res.get('Z (Cobertura)', 0)
            
    _draw_conclusion(pdf, params, z_initial, covered_demand)
    
    return pdf.output(dest='S').encode('latin-1')

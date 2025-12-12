import os
import time
import pandas as pd
import config
import data_loader
import heuristics
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

# Inicializar Console Rich
console = Console()

def main():
    console.print(Panel.fit(
        "[bold cyan]Localização de Campus da RFEPT[/bold cyan]", 
        title="Heurísticas MCLP", 
        border_style="bold blue"
    ))
    
    # 1. Configuração
    # Você pode sobrescrever estes valores no config.py ou aqui
    p = config.P
    s_dist = config.S_DISTANCE
    s_time = config.S_TIME
    use_km = config.USE_DISTANCE_KM
    target_uf = config.TARGET_UF
    
    # Configuração Flexível de Demanda
    # Usuário pode alterar para usar arquivos/colunas diferentes
    demand_file = config.DEMAND_FILE
    demand_id_col = 'Cód.' # Coluna contendo o ID do município
    demand_value_cols = ['Total'] 
    
    # Configuração de Estratégias de Busca Local
    ls_strategy_initial = 'best' # 'first' ou 'best'
    ls_strategy_vns = 'first'    # 'first' ou 'best'

    # Exibir Tabela de Configuração
    table = Table(title="Configuração")
    table.add_column("Parâmetro", style="cyan")
    table.add_column("Valor", style="magenta")
    
    table.add_row("P (Instalações)", str(p))
    table.add_row("Raio", f"{s_dist} km" if use_km else f"{s_time} h")
    table.add_row("UF Alvo", target_uf)
    table.add_row("Arquivo de Demanda", os.path.basename(demand_file))
    table.add_row("Estratégia LS Inicial", ls_strategy_initial)
    table.add_row("Estratégia LS VNS", ls_strategy_vns)
    
    console.print(table)
    
    # 2. Carregar Dados
    start_time = time.time()
    
    with console.status("[bold green]Carregando dados...[/bold green]") as status:
        # Carregar Distâncias
        status.update("[bold green]Carregando distâncias...[/bold green]")
        dist_df = data_loader.load_distances(config.DISTANCES_FILE, uf_filter=target_uf)
        
        # Carregar Locais Existentes
        status.update("[bold green]Carregando locais existentes...[/bold green]")
        sites_df = data_loader.load_existing_sites(config.EXISTING_SITES_FILE, uf_filter=target_uf)
        existing_site_ids = set(sites_df['id'].unique())
        
        # Carregar Demanda
        status.update("[bold green]Carregando demanda...[/bold green]")
        demand_dict, names_dict, uf_dict = data_loader.load_demand(
            demand_file, 
            demand_id_col, 
            demand_value_cols, 
            uf_filter=target_uf
        )
    
    # Definir Candidatos (J) e Nós de Demanda (I)
    # I = todos os nós com demanda
    I = list(demand_dict.keys())
    J = [i for i in I if i not in existing_site_ids]
    
    # Exibir Estatísticas dos Dados
    stats_table = Table(title="Estatísticas dos Dados")
    stats_table.add_column("Métrica", style="cyan")
    stats_table.add_column("Contagem", style="green")
    
    stats_table.add_row("Total de Nós de Demanda (I)", str(len(I)))
    stats_table.add_row("Total de Candidatos (J)", str(len(J)))
    stats_table.add_row("Locais Existentes", str(len(existing_site_ids)))
    
    console.print(stats_table)
    
    # 3. Construir Mapa de Cobertura (Para exportação e visualização futura)
    # Precisamos saber quais nós cobrem quais outros nós
    # Mas primeiro, vamos lidar com a cobertura existente
    
    relevant_origins = set(J) | existing_site_ids
    mask = dist_df['origem'].isin(relevant_origins) & dist_df['destino'].isin(I)
    dist_filtered = dist_df[mask].copy()
    
    # Manter coverage_map para uso na exportação do CSV
    coverage_map = heuristics.build_coverage_map(
        dist_filtered,
        s_dist,
        s_time,
        use_km,
        candidates=J
    )

    # Calcular cobertura inicial a partir de locais existentes (para exibição)
    console.print("[bold blue]Calculando cobertura inicial...[/bold blue]")
    pre_covered = set()
    for site in existing_site_ids:
        if site in coverage_map:
            pre_covered.update(coverage_map[site])
        if site in demand_dict:
            pre_covered.add(site)
            
    initial_z = sum(demand_dict.get(i, 0) for i in pre_covered)
    console.print(f"Z Inicial (Locais Existentes): [bold]{initial_z:,.0f}[/bold]")

    # === CONSTRUÇÃO ESPARSA PARA OTIMIZAÇÃO (NOVO) ===
    console.print("[bold blue]Construindo estruturas esparsas para otimização...[/bold blue]")
    # Usando o DataFrame filtrado no passo anterior
    cov_matrix_sparse, demand_vector, cand_to_idx, node_to_idx, initial_coverage_vector = heuristics.build_sparse_matrix_from_df(
        dist_filtered, demand_dict, J, I, s_dist, s_time, use_km, pre_covered
    )
    # Agrupar para fácil passagem
    sparse_structures = (cov_matrix_sparse, demand_vector, cand_to_idx, node_to_idx, initial_coverage_vector)

    # Tabela de Resultados
    results_table = Table(title="Resultados das Heurísticas")
    results_table.add_column("Método", style="cyan")
    results_table.add_column("Valor Z", style="green")
    results_table.add_column("Tempo (s)", style="yellow")
    
    # Greedy (Guloso - Agora Esparso)
    t0 = time.time()
    s_greedy = heuristics.greedy_heuristic(J, p, cov_matrix_sparse, demand_vector, cand_to_idx, initial_coverage_vector)
    # Calcular Z usando esparso
    z_greedy = heuristics.calculate_z(s_greedy, cov_matrix_sparse, demand_vector, cand_to_idx, initial_coverage_vector)
    greedy_time = time.time()-t0
    results_table.add_row("Greedy", f"{z_greedy:,.0f}", f"{greedy_time:.2f}")
    
    # Busca Local (Agora Esparsa)
    t0 = time.time()
    s_local, z_local = heuristics.local_search(
        s_greedy, J, cov_matrix_sparse, demand_vector, cand_to_idx, initial_coverage_vector, 
        strategy=ls_strategy_initial
    )
    local_time = time.time()-t0
    results_table.add_row(f"Busca Local ({ls_strategy_initial})", f"{z_local:,.0f}", f"{local_time:.2f}")
    
    # VNS (Já era Esparso, mas agora explicitamente unificado)
    t0 = time.time()
    s_vns, z_vns = heuristics.vns(
        s_local, J, coverage_map, demand_dict, pre_covered, 
        ls_strategy=ls_strategy_vns,
        sparse_structures=sparse_structures
    )
    vns_time = time.time()-t0
    results_table.add_row(f"VNS (LS: {ls_strategy_vns})", f"{z_vns:,.0f}", f"{vns_time:.2f}")

    console.print(results_table)
    
    # 5. Exportar Resultados
    console.print("\n[bold blue]Exportando resultados...[/bold blue]")
    results_dir = os.path.join(os.path.dirname(__file__), 'results')
    os.makedirs(results_dir, exist_ok=True)
    
    # Preparar dados para CSV aprimorado
    solution_data = []
    
    # Conjunto de todos os locais ativos (existentes + solução)
    all_sites = existing_site_ids | set(s_vns)
    
    # Pré-calcular campus mais próximo para cada local da solução
    # Para garantir, vamos filtrar dist_df novamente para distâncias Local -> Local
    mask_sites = dist_df['origem'].isin(s_vns) & dist_df['destino'].isin(all_sites)
    dist_sites = dist_df[mask_sites].copy()
    
    # Create a lookup for distances: (orig, dest) -> (dist, time)
    dist_lookup = dist_sites.set_index(['origem', 'destino'])[['distancia', 'tempo']].to_dict('index')

    for site_id in s_vns:
        # 1. Inf. Básicas
        name = names_dict.get(site_id, 'Desconhecido')
        uf = uf_dict.get(site_id, '')
        pop_local = demand_dict.get(site_id, 0)
        
        # 2. Vizinhos e População Coberta
        all_covered = coverage_map.get(site_id, set())
        
        # Filtrar nós já cobertos por locais EXISTENTES
        newly_covered = all_covered - pre_covered
        
        # Vizinhos (excluir o próprio)
        neighbors = all_covered - {site_id}
        neighbors_list = sorted(list(neighbors))
        neighbors_names = [names_dict.get(n, str(n)) for n in neighbors_list]
        neighbors_str = ", ".join(neighbors_names)
        
        # Vizinhos NÃO cobertos antes (para a coluna específica)
        neighbors_new = neighbors - pre_covered
        pop_vizinhos_new = sum(demand_dict.get(n, 0) for n in neighbors_new)
        
        # Total de população NOVA coberta por este local (local + vizinhos)
        # Este é o ganho marginal contra locais EXISTENTES
        pop_nova_coberta = sum(demand_dict.get(n, 0) for n in newly_covered)
        
        # 3. Campus Mais Próximo (Existente ou Outro Selecionado)
        # Queremos o site mais próximo em all_sites EXCLUINDO o próprio
        other_sites = all_sites - {site_id}
        
        nearest_site = None
        min_dist = float('inf')
        min_time = float('inf')
        
        for other in other_sites:
            # Verificar distância de ida
            d_info = dist_lookup.get((site_id, other))
            if not d_info:
                 # Tentar reverso se simétrico? Geralmente matrizes são direcionadas ou temos ambas as linhas.
                 # Assumindo que carregamos todos os pares.
                 pass
            
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
            'tempo_h': min_time if nearest_site else 0
        })
        
    df_sol = pd.DataFrame(solution_data)
    
    # Gerar nome de arquivo com timestamp
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(results_dir, f'solution_vns_{timestamp}.csv')
    
    df_sol.to_csv(output_file, index=False, sep=';')
    console.print(f"Solução salva em [underline]{output_file}[/underline]")
    
    console.print(f"\n[bold green]Tempo Total de Execução: {time.time() - start_time:.2f}s[/bold green]")

if __name__ == "__main__":
    main()

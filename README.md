# MCLP Heuristics Optimizer - RFEPT

Este repositório contém o código fonte da ferramenta de otimização para a expansão da Rede Federal de Educação Profissional e Tecnológica (RFEPT) utilizando o problema de localização de máxima cobertura (MCLP).

---

# 📖 Manual de Funcionamento

Este aplicativo foi desenvolvido para auxiliar na tomada de decisão estratégica sobre onde instalar novos *campi* da Rede Federal de Educação Profissional, Científica e Tecnológica (RFEPT).

## 1. O Problema Resolvido

O objetivo é maximizar a **cobertura da demanda** (população em idade escolar) instalando um número limitado de novos *campi*.
O problema matemático subjacente é conhecido como **MCLP (Maximal Covering Location Problem)**.

**Premissas:**
*   Um município é considerado "coberto" se estiver dentro de uma distância (km) ou tempo de viagem (horas) aceitável de um município que já possui um campus.
*   Campi já existentes continuam operando e cobrindo suas regiões.
*   Queremos escolher `P` novos locais que cubram o máximo de pessoas que *ainda não são atendidas* pelos campi atuais.

## 2. Como Usar o Aplicativo

### Passo 1: Configuração (Barra Lateral)

Na barra lateral esquerda, você define os parâmetros da simulação:

1.  **Number of New Sites (P)**: Quantos novos campi você deseja instalar? (Ex: 5).
2.  **Coverage Metric**: Escolha entre Distância (km) ou Tempo (horas) como critério de cobertura.
3.  **Radius / Max Time**: O valor limite.
    *   Ex: Se escolher 50km, qualquer município a menos de 50km de um campus será considerado atendido.
4.  **Target UF**: Filtre a análise para um estado específico (Ex: MG, SP). Deixe em branco para analisar o Brasil todo.
5.  **Configurações de Arquivos** (Expansível):
    *   **Demanda**: Você pode fazer upload de um arquivo CSV personalizado com a população. Se não fornecer, o sistema usa os dados do Censo 2022 padrão. Há um botão para baixar um *template* (modelo) para facilitar.
    *   **Campi Existentes**: Você pode fazer upload de um arquivo CSV com os campi atuais.
    *   **Modo Greenfield**: Marque a opção *"Iniciar sem cobertura existente"* para ignorar os campi atuais e planejar a rede do zero.
6.  **VNS Settings**: Configurações avançadas do algoritmo de otimização (Iterações, Vizinhanças).

### Passo 2: Execução

1.  Clique no botão **🚀 INICIAR OTIMIZAÇÃO**.
2.  O sistema irá carregar os dados, calcular a matriz de cobertura e executar os algoritmos (Greedy, Busca Local e VNS).
3.  Caso queira reiniciar a configuração padrão, clique no botão **🔄 RESET**.

### Passo 3: Análise dos Resultados

#### Tabela de Resumo
Mostra o valor "Z" (Total de pessoas cobertas) encontrado por cada método e o tempo de execução.

#### Tabela Detalhada (Locais Selecionados)
Lista os municípios escolhidos. Você pode **filtrar** e **ordenar** esta tabela.
*   **Pop. Nova Coberta**: A métrica mais importante. Quantas pessoas *que antes não tinham acesso* agora passam a ter.
*   **Vizinhos Cobertos**: Lista de municípios vizinhos atendidos.

#### Visualização Geográfica (Mapas)
O sistema exibe dois mapas interativos:
1.  **Mapa de Cobertura**: Mostra os campi existentes (Azul), novos locais (Verde) e suas áreas de cobertura.
2.  **Mapa de Calor da Demanda**: Mostra onde está a concentração de jovens, permitindo validar visualmente se os campi foram para as áreas "quentes" (vermelhas).

> **Dica**: Use a caixa de busca "Buscar Município (Zoom)" para centralizar o mapa em uma cidade específica.

#### Exportação de Relatórios
No final da página, você encontra botões para:
*   📥 **Baixar Excel**: Tabela completa dos resultados.
*   📥 **Baixar Relatório (PDF)**: Um relatório completo com capa, introdução, mapas estáticos e detalhamento da solução, pronto para impressão ou apresentação.
*   📥 **Baixar Mapas (HTML)**: Versões interativas dos mapas para abrir no navegador.

## 3. Metodologia

O sistema utiliza uma abordagem heurística, o que significa que ele busca soluções de alta qualidade em tempo razoável, embora não garanta matematicamente o ótimo global (que seria impossível de calcular para o Brasil todo em tempo hábil).

1.  **Construção**: Começa escolhendo os locais "óbvios" que cobrem muita gente (Greedy).
2.  **Refinamento**: Tenta trocar um local escolhido por outro vizinho para ver se a cobertura total aumenta.
3.  **Diversificação**: O VNS faz trocas aleatórias maiores para testar combinações inusitadas de locais, evitando ficar preso em soluções apenas "boas".

---

# 🛠️ Manual Técnico

Este documento fornece uma visão técnica detalhada do projeto **MCLP Heuristics Optimizer**, desenvolvido para resolver o Problema de Localização de Máxima Cobertura (MCLP) aplicado à expansão da Rede Federal de Educação Profissional, Científica e Tecnológica (RFEPT).

## 1. Estrutura do Projeto

O projeto está organizado na pasta `mclp_heuristics` com a seguinte estrutura:

```
mclp_heuristics/
├── app.py              # Aplicação Web (Streamlit) - Interface principal
├── main.py             # Aplicação CLI (Terminal) - Para execução em lote/debug
├── config.py           # Arquivo de configuração central (caminhos, parâmetros default)
├── data_loader.py      # Módulo de carregamento e tratamento de dados
├── heuristics.py       # Implementação dos algoritmos de otimização
├── report_utils.py     # Módulo de geração de relatórios (PDF, Excel, HTML)
├── map_renderer.py     # Módulo de visualização de mapas (PyDeck)
├── ui_components.py    # Componentes de UI reutilizáveis (Tabelas, Gráficos)
├── ui_config.py        # Configurações de UI (CSS, HTML estático)
├── clean_data/         # Dados de entrada (CSVs e Shapefiles)
├── results/            # Pasta onde os resultados (CSVs) são salvos
└── __pycache__/        # Arquivos compilados do Python
```

## 2. Dependências

As principais bibliotecas utilizadas são:

*   **Streamlit**: Framework para a interface web interativa.
*   **Pandas**: Manipulação de dados tabulares (DataFrames).
*   **Geopandas**: Manipulação de dados geoespaciais (Shapefiles).
*   **PyDeck**: Visualização de mapas interativos e complexos.
*   **ReportLab**: Geração de relatórios PDF profissionais (`fpdf` ou `reportlab`).
*   **Matplotlib**: Geração de gráficos estáticos para inclusão nos relatórios PDF.
*   **Rich**: Formatação de texto e barras de progresso no terminal (`main.py`).

## 3. Módulos e Responsabilidades

### 3.1. `config.py`
Centraliza as constantes do projeto.
*   Define caminhos absolutos para os arquivos de dados (`clean_data`).
*   Define parâmetros padrão (`P`, `S_DISTANCE`, `S_TIME`).
*   Facilita a manutenção, permitindo alterar caminhos em um único lugar.

### 3.2. `data_loader.py`
Responsável por toda a E/S (Entrada/Saída) de dados.
*   **`load_distances`**: Carrega a matriz de distâncias. Implementa leitura em *chunks* (blocos) para otimizar memória, filtrando apenas as colunas necessárias e o estado (UF) alvo.
*   **`load_existing_sites`**: Carrega os campi já existentes.
*   **`load_demand`**: Carrega os dados de população (demanda). Retorna dicionários para acesso rápido (`id -> demanda`, `id -> nome`).
*   **`load_shapefile`**: Carrega a malha municipal para o mapa, com opção de filtro por UF.

### 3.3. `heuristics.py`
O "cérebro" do projeto. Contém a lógica de otimização.
*   **`build_coverage_map`**: Pré-processa a matriz de distâncias em um dicionário `{candidato: {conjunto_de_cobertos}}`. Isso torna as consultas de cobertura O(1) durante a otimização.
*   **`greedy_heuristic`**: Algoritmo Construtivo Guloso. Seleciona iterativamente o local que cobre a maior demanda *ainda não coberta*.
*   **`local_search`**: Busca Local (Best Improvement). Tenta trocar um local selecionado por um não selecionado para ver se melhora a função objetivo (Z).
*   **`vns` (Variable Neighborhood Search)**: Meta-heurística que explora vizinhanças de tamanhos variados (k=1 a k_max) para escapar de ótimos locais.

### 3.4. `report_utils.py`
Responsável pela exportação dos resultados.
*   **`generate_pdf_report`**: Cria um relatório PDF completo com capa, estatísticas, mapas estáticos (via Matplotlib) e tabela detalhada.
*   **`generate_excel_download`**: Formata o DataFrame para exportação em `.xlsx`.
*   **`generate_html_map`**: Exporta os objetos PyDeck para arquivos HTML independentes.

### 3.5. `map_renderer.py`
Responsável pela visualização geoespacial.
*   **`render_maps`**: Gera os mapas interativos usando PyDeck.
*   Gerencia camadas de visualização (demanda, cobertura, locais selecionados).
*   Configura tooltips e estilos visuais do mapa.

### 3.6. `ui_components.py`
Componentes de interface reutilizáveis.
*   **`render_results`**: Exibe tabelas de resultados e gráficos de evolução.
*   Gerencia a lógica de exibição de métricas e filtros de tabelas.

### 3.7. `ui_config.py`
Configurações de estilo e layout.
*   Define CSS personalizado para a aplicação.
*   Contém HTML estático (como modais de ajuda).
*   Configura o tema da página do Streamlit.

### 3.8. `app.py` (Interface)
*   Gerencia o estado da sessão do Streamlit.
*   Recebe inputs do usuário (Parâmetros, Upload de Arquivos).
*   Orquestra a chamada dos outros módulos.
*   Ponto de entrada da aplicação web.

## 4. Fluxo de Dados

1.  **Carregamento**: O sistema carrega a matriz de distâncias. A demanda e os campi existentes podem vir dos arquivos padrão ou de **uploads do usuário** (CSV).
2.  **Mapeamento**: Constrói-se o `coverage_map` baseando-se no Raio (km) ou Tempo (h) máximo.
3.  **Pré-processamento**: Identifica-se a demanda já coberta pelos *campi existentes* (`pre_covered`).
4.  **Otimização**:
    *   O algoritmo ignora a demanda já coberta.
    *   Busca `P` novos locais que maximizem a cobertura da demanda *restante*.
5.  **Pós-processamento**:
    *   Calcula estatísticas detalhadas para cada local escolhido (vizinhos, distância ao campus mais próximo).
    *   Gera visualização no mapa colorindo municípios por status (Novo Campus, Coberto, Descoberto).

## 5. Algoritmos Detalhados

### 5.1. Heurística Construtiva Gulosa (Greedy)

A heurística gulosa constrói uma solução passo a passo, escolhendo sempre o "melhor" candidato disponível naquele momento (aquele que cobre o maior número de alunos ainda não atendidos).

#### Pseudocódigo

```text
Algoritmo 1: Heurística Construtiva Gulosa
1: procedure GREEDY(J, D, p, C_pre)
2:    S ← ∅
3:    Cobertos ← C_pre
4:    enquanto |S| < p faça
5:       MelhorCandidato ← Nulo
6:       MelhorGanho ← -∞
7:       para cada j ∈ (J \ S) faça
8:          // Calcula demanda coberta por j que ainda não está em Cobertos
9:          NovosCobertos ← Cobertura(j) \ Cobertos
10:         Ganho ← Soma(Demanda(i) para i ∈ NovosCobertos)
11:         se Ganho > MelhorGanho então
12:            MelhorGanho ← Ganho
13:            MelhorCandidato ← j
14:         fim se
15:      fim para
16:      se MelhorCandidato ≠ Nulo e MelhorGanho > 0 então
17:         S ← S ∪ {MelhorCandidato}
18:         Cobertos ← Cobertos ∪ Cobertura(MelhorCandidato)
19:      senão
20:         pare // Não há mais ganho possível
21:      fim se
22:   fim enquanto
23:   retorne S
24: fim procedure
```

### 5.2. Busca Local (Best Improvement)

A Busca Local tenta melhorar uma solução existente trocando um local selecionado por um não selecionado. A estratégia "Best Improvement" avalia *todas* as trocas possíveis e realiza a que traz o maior ganho.

#### Pseudocódigo

```text
Algoritmo 2: Busca Local (Best Improvement)
1: procedure LOCAL_SEARCH(S, J)
2:    Melhorou ← Verdadeiro
3:    enquanto Melhorou = Verdadeiro faça
4:       Melhorou ← Falso
5:       MelhorDelta ← 0
6:       MelhorTroca ← Nulo
7:       para cada j_rem ∈ S faça
8:          para cada j_add ∈ (J \ S) faça
9:             Delta ← CalcularBeneficioTroca(j_rem, j_add)
10:            se Delta > MelhorDelta então
11:               MelhorDelta ← Delta
12:               MelhorTroca ← (j_rem, j_add)
13:            fim se
14:         fim para
15:      fim para
16:      se MelhorTroca ≠ Nulo e MelhorDelta > 0 então
17:         ExecutarTroca(S, MelhorTroca)
18:         Melhorou ← Verdadeiro
19:      fim se
20:   fim enquanto
21:   retorne S
22: fim procedure
```

### 5.3. VNS (Variable Neighborhood Search)

O VNS (Busca em Vizinhança Variável) explora sistematicamente vizinhanças de tamanhos crescentes (k=1, k=2, ..., k_max) para escapar de ótimos locais. Ele combina uma fase de "agitação" (Shaking) com a Busca Local.

#### Pseudocódigo

```text
Algoritmo 3: Variable Neighborhood Search (VNS)
1: procedure VNS(S_inicial, k_max, MaxIter)
2:    S_best ← S_inicial
3:    S_curr ← S_inicial
4:    Iteracoes ← 0
5:    enquanto Iteracoes < MaxIter faça
6:       k ← 1
7:       enquanto k ≤ k_max faça
8:          // 1. Agitação (Shaking): Perturbação aleatória de tamanho k
9:          S_linha ← GerarVizinhoAleatorio(S_curr, k)
10:
11:         // 2. Busca Local: Refinamento
12:         S_duas_linhas, Z_novo ← BuscaLocal(S_linha)
13:
14:         // 3. Mudança de Vizinhança
15:         se Z_novo > Z(S_curr) então
16:            S_curr ← S_duas_linhas
17:            se Z(S_curr) > Z(S_best) então
18:               S_best ← S_curr
19:            fim se
20:            k ← 1  // Sucesso: retorna para vizinhança menor
21:         senão
22:            k ← k + 1 // Falha: expande a vizinhança (maior perturbação)
23:         fim se
24:      fim enquanto
25:      Iteracoes ← Iteracoes + 1
26:   fim enquanto
27:   retorne S_best
28: fim procedure
```

## 6. Manutenção e Extensão

*   **Adicionar nova métrica**: Edite `config.py` e `app.py` para incluir a nova opção. Atualize `heuristics.build_coverage_map` para usar a nova coluna.
*   **Alterar dados**: Basta substituir os arquivos CSV na pasta `clean_data` mantendo a estrutura de colunas, ou ajustar `data_loader.py` para novas colunas.
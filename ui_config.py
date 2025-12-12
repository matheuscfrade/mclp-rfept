import streamlit as st

def setup_page_config():
    """Configura as definições da página do Streamlit."""
    st.set_page_config(
        page_title="Otimizador MCLP",
        page_icon="📍",
        layout="wide"
    )

def apply_custom_css():
    """Aplica estilos CSS personalizados à aplicação."""
    st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        background-color: #28a745;
        color: white;
        font-weight: bold;
    }
    
    /* Substituição para botão 'Saiba mais' dentro de colunas */
    [data-testid="stColumn"] .stButton>button {
        background-color: #28a745 !important;
        color: inherit !important;
        border: none !important;
        box-shadow: none !important;
        width: auto !important;
        padding: 0 !important;
        text-decoration: underline;
        font-size: 0.9em;
        margin-top: 0px;
    }
    
    [data-testid="stColumn"] .stButton>button:hover {
        color: #28a745 !important;
        background-color: transparent !important;
    }

    .metric-card {
        background-color: var(--secondary-background-color);
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }

    /* Modal CSS para 'Saiba mais' */
    .modal-window {
        position: fixed;
        background-color: rgba(0, 0, 0, 0.5);
        top: 0;
        right: 0;
        bottom: 0;
        left: 0;
        z-index: 999999;
        visibility: hidden;
        opacity: 0;
        pointer-events: none;
        transition: all 0.3s;
    }
    .modal-window:target {
        visibility: visible;
        opacity: 1;
        pointer-events: auto;
    }
    .modal-window > div {
        width: 800px;
        max-width: 90%;
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        padding: 2em;
        background: #262730; /* Cinza escuro sólido para garantir opacidade */
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 10px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        max-height: 90vh;
        overflow-y: auto;
        color: #ffffff;
    }
    .modal-close {
        color: #aaa;
        line-height: 50px;
        font-size: 80%;
        position: absolute;
        right: 0;
        text-align: center;
        top: 0;
        width: 70px;
        text-decoration: none;
    }
    .modal-close:hover {
        color: black;
    }
    .saiba-mais-link {
        color: inherit;
        text-decoration: underline;
        cursor: pointer;
        font-size: 0.9em;
        background: none;
        border: none;
        padding: 0;
        margin: 0;
        margin-left: 10px;
    }
    .saiba-mais-link:hover {
        color: #28a745;
    }
    
    /* Reduzir padding superior para maximizar espaço de tela */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 10rem !important; /* Espaço aumentado para rodapé fixo */
    }
</style>
""", unsafe_allow_html=True)

# Conteúdo de Explicação (HTML para Modal)
EXPLANATION_HTML = """
<div id="open-modal" class="modal-window">
<div>
<a href="#" title="Close" class="modal-close">✖</a>
<h3>O que esta aplicação faz?</h3>
<p>Esta ferramenta auxilia na escolha de municípios para receber novas unidades (expansões) da Rede Federal de Educação Profissional, Científica e Tecnológica (Institutos Federais, Cefets etc.). O objetivo é maximizar o número de jovens atendidos, respeitando limites de distância ou tempo de viagem.</p>
<h3>Como funciona?</h3>
<ol>
<li><strong>Você define os parâmetros</strong>
<ul>
<li>Número de novas unidades a serem instaladas (ex.: 5)</li>
<li>Distância ou tempo máximo de deslocamento do aluno até o campus (ex.: 100 km ou 90 minutos)</li>
<li>Estado(s) a ser(em) analisado(s) ou todo o Brasil</li>
<li>Outros ajustes estão disponíveis no painel “Configurações” (cada item tem explicação no ícone ❓)</li>
</ul>
</li>
<li><strong>Funcionamento do algoritmo</strong>
<ul>
<li>Parte dos municípios que já possuem campus da Rede Federal e calcula quais outros estão dentro do raio de cobertura definido.</li>
<li>Usa como demanda padrão a população de 14 a 24 anos de cada município (Censo IBGE 2022).</li>
<li>Avalia combinações de novos locais utilizando algoritmos heurísticos avançados para encontrar, em poucos segundos, uma solução de alta qualidade.</li>
</ul>
</li>
<li><strong>Controles da Interface</strong>
<ul>
<li><strong>INICIAR OTIMIZAÇÃO</strong>: Começa o cálculo.</li>
<li><strong>RESET</strong>: Restaura todas as configurações para o padrão e limpa os resultados.</li>
</ul>
</li>
<li><strong>Resultado apresentado</strong>
<ul>
<li>Mapa com os municípios recomendados para receber as novas unidades</li>
<li>Total de jovens que passam a estar dentro do raio de cobertura</li>
<li>Comparação com a cobertura atual</li>
</ul>
</li>
</ol>
<hr>
<h3>🛠️ Bases de Dados</h3>
<ol>
<li><strong>Demanda</strong>
<ul>
<li>População de 14 a 24 anos por município (IBGE – Censo Demográfico 2022)</li>
<li>Pode ser substituída ou ponderada pelo usuário na aba “Configurações de Arquivos”</li>
</ul>
</li>
<li><strong>Matriz de distâncias e tempos de viagem</strong>
<ul>
<li>Tabela completa entre todos os 5.570 municípios brasileiros (distância rodoviária em km e tempo em horas)</li>
<li>Fonte: Carvalho, L. R.; Amaral, P. V. M.; Mendes, P. S. (2020). Matrizes de distâncias e tempo de deslocamento rodoviário entre os municípios brasileiros: uma atualização metodológica para 2020.</li>
<li>Disponível em: <a href="https://ideas.repec.org/p/cdp/texdis/td630.html" target="_blank">Link</a></li>
</ul>
</li>
<li><strong>Campi existentes</strong>
<ul>
<li>Lista de municípios que já possuem pelo menos uma unidade da Rede Federal</li>
<li>São considerados como cobertura inicial do algoritmo</li>
<li>Fonte: Plataforma Nilo Peçanha - PNP</li>
<li>Disponível em: <a href="https://www.gov.br/mec/pt-br/pnp" target="_blank">Link</a></li>
</ul>
</li>
</ol>
<p>Caso precise de mais detalhes, consulte os ícones de ajuda ❓.</p>
<hr>
<h3>🧠 Heurísticas Utilizadas</h3>
<p>Para resolver este problema complexo rapidamente, utilizamos três métodos em sequência:</p>
<ol>
<li><strong>Greedy (Guloso)</strong>: Constrói uma solução inicial escolhendo, passo a passo, o local que cobre o maior número de alunos ainda não atendidos.</li>
<li><strong>Busca Local</strong>: Refina a solução inicial, tentando trocar um local escolhido por um vizinho para ver se a cobertura total aumenta.</li>
<li><strong>VNS (Variable Neighborhood Search)</strong>: Uma técnica avançada que "agita" a solução (fazendo trocas maiores e aleatórias) para escapar de ótimos locais e explorar novas possibilidades, buscando um resultado ainda melhor.</li>
</ol>
</div>
</div>
"""

FOOTER_HTML = """
<div style="position: fixed; bottom: 0; left: 0; width: 100%; background-color: #0e1117; padding: 10px; text-align: center; font-size: 0.8em; color: gray; z-index: 1000; border-top: 1px solid #333;">
    <p style="margin: 0;">MCLP RFEPT - Beta Version 0.1</p>
    <p style="margin: 0;">© 2025 Matheus Costa Frade - Todos os direitos reservados.</p>
    <p style="margin: 0;"><a href="https://www.linkedin.com/in/matheus-frade" target="_blank" style="text-decoration: none; color: inherit;">
        🔗 www.linkedin.com/in/matheus-frade
    </a></p>
</div>
"""

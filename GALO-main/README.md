# Sistema GALO - Gestão Automatizada Logística Otimizada

\<p align="center"\>
\<img src="image\_5fca8a.png" alt="Logo GALO" width="200"/\>
\</p\>

## Visão Geral

O Sistema GALO (Gestão Automatizada Logística Otimizada) é uma plataforma inteligente desenvolvida para otimizar o ciclo de vida de produtos perecíveis, desde o recebimento na central de distribuição até a venda no balcão. Inspirado nas necessidades logísticas do Grupo Mateus, o GALO aborda desafios críticos como a previsão de demanda, minimização de desperdícios e garantia da disponibilidade do produto certo, no lugar certo, na hora certa.

Este projeto foca especificamente na gestão do processo de descongelamento e movimentação de produtos, garantindo que o estoque congelado seja descongelado de forma eficiente para atender à demanda futura, evitando perdas por validade e rupturas de estoque no balcão.

## Problemas que o GALO Resolve

Conforme detalhado em nossa apresentação ([P2 - Redes.pdf](P2 - Redes.pdf)), o GALO foi concebido para responder a perguntas cruciais na gestão de produtos, como:

  * "Será que o produto que separamos hoje será suficiente para a venda no dia X?"
  * "Como evitar desperdício devido a produtos que expiram ou são descongelados em excesso?"
  * "Por que sempre falta produtos específicos em períodos de alta demanda (ex: feriados)?"
  * "Qual o momento ideal para iniciar o descongelamento de um produto?"

Ao fornecer previsões precisas e gerenciar automaticamente as movimentações internas, o GALO transforma a gestão operacional em um processo preditivo e padronizado.

## Como Funciona (Fluxo de Descongelamento)

O coração do Sistema GALO é seu algoritmo de previsão de demanda e o gerenciamento do processo de descongelamento em um fluxo "D-0, D-1, D-2":

1.  **Entrada de Estoque:** Novos produtos chegam e são registrados no estoque (assumido inicialmente como `congelador`).
2.  **Previsão de Demanda (D+2):** Diariamente, o sistema prevê a demanda para o dia **D+2** (o dia da venda).
3.  **Cálculo de Descongelamento (D-0):** Com base na previsão para D+2 e no estoque existente (tanto no congelador quanto em descongelamento), o GALO calcula a quantidade ideal de produtos a serem retirados do congelador **hoje (D-0)** para iniciar o processo de descongelamento.
      * **D-0:** Movimentação do **`congelador`** para a **`estante_esquerda`** (início do descongelamento). Esta etapa requer confirmação manual para simular a ação do funcionário.
4.  **Movimentação Intermediária (D-1):** No dia seguinte ao D-0, os itens que estão na `estante_esquerda` são movidos para a **`estante_central`**.
      * **D-1:** Movimentação da **`estante_esquerda`** para a **`estante_central`** (continuação do descongelamento/preparação). Esta etapa também requer confirmação manual.
5.  **Disponibilização para Venda (D-2):** No dia seguinte ao D-1 (ou seja, D+2 em relação ao início do processo), os itens da `estante_central` são movimentados para o balcão de vendas.
      * **D-2:** Movimentação da **`estante_central`** para o **`balcao`** (disponível para venda). Esta etapa também requer confirmação manual.

Este fluxo garante que os produtos estejam perfeitamente descongelados e prontos para a venda no momento ideal, minimizando perdas e garantindo o suprimento.

## Arquitetura do Projeto

O projeto é construído em Python e utiliza as seguintes bibliotecas principais:

  * **`pandas`**: Para manipulação e análise de dados (vendas, estoque, descongelamento).
  * **`scikit-learn`**: Para o treinamento do modelo de Machine Learning (`RandomForestRegressor`) que prevê a demanda.
  * **`joblib`**: Para serializar e carregar o modelo treinado, permitindo seu reuso sem a necessidade de re-treinamento constante.
  * **`datetime`**: Para manipulação de datas e simulação do fluxo diário.
  * **`os`**: Para operações de sistema de arquivos, como criação de diretórios para modelos e relatórios.
  * **`time`**: Utilizado para simular pausas no processo e interações com o usuário para confirmações de movimentação.

### Estrutura de Pastas

```
.
├── main.py
├── dados_vendas.xlsx    # Planilha com dados de vendas, estoque e descongelamento
├── modelos/               # Diretório para armazenar o modelo de ML treinado (.pkl)
└── relatorios/            # Diretório para armazenar os relatórios gerados (.xlsx)
```

## Como Executar o Projeto

Para rodar o Sistema GALO, siga os passos abaixo:

1.  **Pré-requisitos:**

      * Python 3.x instalado.
      * As bibliotecas listadas em `requirements.txt` (ou mencionadas acima) instaladas. Você pode instalá-las via pip:
        ```bash
        pip install pandas scikit-learn joblib openpyxl
        ```
      * Um arquivo `dados_vendas.xlsx` no mesmo diretório do `main.py`, contendo as abas `vendas`, `estoque` e `descongelamento` com as colunas esperadas (vide código).

2.  **Preparar o `dados_vendas.xlsx`:**
    O arquivo Excel deve conter as seguintes abas e colunas:

      * **`vendas`**:
          * `data_dia` (formato data)
          * `id_produto` (será renomeado para `sku`)
          * `total_venda_dia_kg`
      * **`estoque`**:
          * `id_produto` (será renomeado para `sku`)
          * `kg` (quantidade em kg)
          * `validade` (formato data)
          * `localizacao_estante` (deve ter pelo menos 'congelador'. Se ausente, será padronizado para 'congelador' no carregamento.)
      * **`descongelamento`**:
          * `id_produto` (será renomeado para `sku`)
          * `kg` (quantidade em kg)
          * `validade` (formato data)
          * `localizacao_estante` (deve ter 'estante\_esquerda' e 'estante\_central'. Se ausente, será padronizado para 'estante\_esquerda' no carregamento.)

    **Exemplo Simplificado para `dados_vendas.xlsx`:**

    **Aba: `vendas`**
    | data\_dia   | id\_produto | total\_venda\_dia\_kg |
    |------------|------------|--------------------|
    | 2024-01-01 | SKU001     | 150                |
    | 2024-01-02 | SKU001     | 160                |
    | ...        | ...        | ...                |
    | 2024-01-01 | SKU002     | 80                 |
    | 2024-01-02 | SKU002     | 90                 |

    **Aba: `estoque`**
    | id\_produto | kg    | validade   | localizacao\_estante |
    |------------|-------|------------|---------------------|
    | SKU001     | 500   | 2025-12-31 | congelador          |
    | SKU002     | 300   | 2025-11-15 | congelador          |
    | ...        | ...   | ...        | ...                 |

    **Aba: `descongelamento`**
    (Esta aba pode começar vazia ou com dados de produtos já em processo de descongelamento.)
    | id\_produto | kg    | validade   | localizacao\_estante |
    |------------|-------|------------|---------------------|
    | SKU001     | 50    | 2025-07-10 | estante\_esquerda    |
    | SKU002     | 20    | 2025-07-09 | estante\_central     |
    | ...        | ...   | ...        | ...                 |

3.  **Executar:**
    Abra seu terminal ou prompt de comando, navegue até o diretório onde o `main.py` e o `dados_vendas.xlsx` estão localizados, e execute o script:

    ```bash
    python main.py
    ```

O sistema simulará alguns dias de operação, pedindo sua confirmação para cada movimentação entre estantes. Relatórios de descongelamento e movimentação serão gerados na pasta `relatorios/`.

## Funcionalidades Principais

  * **Previsão de Demanda:** Utiliza um modelo de Random Forest para prever a demanda futura (D+2) de produtos com base em dados históricos de vendas, incluindo dia da semana, mês, trimestre e médias móveis.
  * **Gestão de Estoque:** Carrega e gerencia o estoque no congelador e produtos em processo de descongelamento.
  * **Processo de Descongelamento Otimizado:** Orquestra a movimentação de produtos através de um fluxo D-0 (congelador -\> estante esquerda), D-1 (estante esquerda -\> estante central) e D-2 (estante central -\> balcão de venda).
  * **Simulação Interativa:** Permite simular o processo diário com confirmações manuais para cada movimentação, replicando a interação do funcionário com o sistema.
  * **Geração de Relatórios:** Produz relatórios detalhados sobre as necessidades de descongelamento e todas as movimentações realizadas, auxiliando na auditoria e planejamento.
  * **Re-treinamento Periódico do Modelo:** O modelo de previsão é verificado e re-treinado automaticamente a cada 7 dias (configurável), garantindo que ele se adapte às mudanças nos padrões de venda.

## Desenvolvimento Futuro

  * **Interface do Usuário (Dashboard):** Implementação de uma interface gráfica para visualização dos dados, previsões e status do estoque, conforme sugerido no PDF.
  * **Integração com Sistemas Existentes:** Conexão com sistemas de ERP ou gerenciamento de armazém para automatizar a entrada de dados e a execução de ordens.
  * **Otimização do Fator de Perda:** Desenvolvimento de um módulo para calcular e ajustar dinamicamente o fator de perda (atualmente 1.083), baseado em dados reais de perdas.
  * **Alerta de Ponto de Pedido:** Implementação da funcionalidade de "Ponto de Pedido" para notificar o gerente quando o estoque total estiver baixo, gerando ordens de compra automáticas.
  * **Gerenciamento de Lotes e Validades:** Aprimorar o gerenciamento de estoque para lidar com múltiplos lotes e suas respectivas validades de forma mais granular durante as movimentações.

-----

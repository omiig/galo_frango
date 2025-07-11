# main.py
import pandas as pd
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor
import joblib
import os
import time
import random

class SistemaGALO:
    def __init__(self):
        self.modelo = None
        self.dados_vendas = None
        self.estoque = None
        self.descongelando = None
        self.ultima_execucao_diaria = None
        self.registros_movimentacao = []
        self.estado_salvo_dir = 'estado_sistema'

        # Ponto de Pedido e Quantidade de Pedido padrão
        # Em um sistema real, estes seriam por SKU, idealmente calculados dinamicamente
        self.ponto_pedido_default = 50 # kg: Se o estoque cair abaixo disso, reabastece
        self.qtd_pedido_default = 50 # kg: Quantidade a ser reabastecida (ALTERADO AQUI!)

        # Definição dos principais eventos sazonais e feriados nacionais no BRASIL para 2024-2025
        self.eventos_sazonais = {
            'Carnaval': {
                'datas': [
                    datetime(2024, 2, 12), datetime(2024, 2, 13), # Carnaval 2024
                    datetime(2025, 3, 3), datetime(2025, 3, 4)   # Carnaval 2025
                ],
                'antecedencia_dias': 7
            },
            'Pascoa': {
                'datas': [
                    datetime(2024, 3, 31), # Páscoa 2024
                    datetime(2025, 4, 20)  # Páscoa 2025
                ],
                'antecedencia_dias': 7
            },
            'Dia das Maes': {
                'datas': [
                    datetime(2024, 5, 12), # 2º domingo de maio 2024
                    datetime(2025, 5, 11)  # 2º domingo de maio 2025
                ],
                'antecedencia_dias': 10
            },
            'Black Friday': {
                'datas': [
                    datetime(2024, 11, 29), # Última sexta de novembro 2024
                    datetime(2025, 11, 28)  # Última sexta de novembro 2025
                ],
                'antecedencia_dias': 7
            },
            'Natal': {
                'datas': [
                    datetime(2024, 12, 25),
                    datetime(2025, 12, 25)
                ],
                'antecedencia_dias': 15
            },
            'Ano Novo': {
                'datas': [
                    datetime(2024, 1, 1),
                    datetime(2025, 1, 1),
                    datetime(2026, 1, 1)
                ],
                'antecedencia_dias': 7
            },
            'Tiradentes': {
                'datas': [datetime(y, 4, 21) for y in range(2023, 2026)],
                'antecedencia_dias': 3
            },
            'Dia do Trabalho': {
                'datas': [datetime(y, 5, 1) for y in range(2023, 2026)],
                'antecedencia_dias': 3
            },
            'Corpus Christi': {
                'datas': [
                    datetime(2024, 5, 30),
                    datetime(2025, 6, 19)
                ],
                'antecedencia_dias': 3
            },
            'Independencia Brasil': {
                'datas': [datetime(y, 9, 7) for y in range(2023, 2026)],
                'antecedencia_dias': 3
            },
            'Nossa Senhora Aparecida': {
                'datas': [datetime(y, 10, 12) for y in range(2023, 2026)],
                'antecedencia_dias': 3
            },
            'Finados': {
                'datas': [datetime(y, 11, 2) for y in range(2023, 2026)],
                'antecedencia_dias': 3
            },
            'Proclamacao Republica': {
                'datas': [datetime(y, 11, 15) for y in range(2023, 2026)],
                'antecedencia_dias': 3
            },
        }

    def carregar_dados(self):
        try:
            # Carregar dados de vendas
            self.dados_vendas = pd.read_excel('dados_vendas.xlsx', sheet_name='vendas')
            self.dados_vendas.columns = self.dados_vendas.columns.str.strip().str.lower()
            self.dados_vendas['data_dia'] = pd.to_datetime(self.dados_vendas['data_dia'])
            self.dados_vendas.rename(columns={'id_produto': 'sku'}, inplace=True)
            
            # Se dados_vendas estiver vazio após carregar, crie um DataFrame vazio com as colunas essenciais
            if self.dados_vendas.empty:
                print("Aviso: 'dados_vendas.xlsx' (aba 'vendas') está vazio. Iniciando com DataFrame vazio para vendas.")
                self.dados_vendas = pd.DataFrame(columns=['data_dia', 'sku', 'total_venda_dia_kg'])
                self.dados_vendas['data_dia'] = pd.to_datetime(self.dados_vendas['data_dia']) # Garantir tipo datetime
            else:
                self.dados_vendas = self.dados_vendas.sort_values(by='data_dia').reset_index(drop=True)


            # Carregar ou inicializar estoque (congelador)
            caminho_estoque = os.path.join(self.estado_salvo_dir, 'estoque_congelador.xlsx')
            if os.path.exists(caminho_estoque):
                self.estoque = pd.read_excel(caminho_estoque)
                self.estoque['validade'] = pd.to_datetime(self.estoque['validade'])
                self.estoque['data_entrada_estante'] = pd.to_datetime(self.estoque['data_entrada_estante'])
                print(f"Estoque carregado de {caminho_estoque}")
            else:
                self.estoque = pd.read_excel('dados_vendas.xlsx', sheet_name='estoque')
                self.estoque.columns = self.estoque.columns.str.strip().str.lower()
                self.estoque.rename(columns={'id_produto': 'sku'}, inplace=True)
                self.estoque['validade'] = pd.to_datetime(self.estoque['validade'])
                if 'kg' not in self.estoque.columns:
                    print("Aviso: Coluna 'kg' não encontrada na planilha 'estoque'. Verifique a estrutura.")
                if 'localizacao_estante' not in self.estoque.columns:
                    self.estoque['localizacao_estante'] = 'congelador'
                if 'data_entrada_estante' not in self.estoque.columns:
                    self.estoque['data_entrada_estante'] = pd.NaT

            # Carregar ou inicializar descongelando
            caminho_descongelando = os.path.join(self.estado_salvo_dir, 'estoque_descongelando.xlsx')
            if os.path.exists(caminho_descongelando):
                self.descongelando = pd.read_excel(caminho_descongelando)
                self.descongelando['validade'] = pd.to_datetime(self.descongelando['validade'])
                self.descongelando['data_entrada_estante'] = pd.to_datetime(self.descongelando['data_entrada_estante'])
                print(f"Itens descongelando carregados de {caminho_descongelando}")
            else:
                self.descongelando = pd.read_excel('dados_vendas.xlsx', sheet_name='descongelamento')
                self.descongelando.columns = self.descongelando.columns.str.strip().str.lower()
                self.descongelando.rename(columns={'id_produto': 'sku'}, inplace=True)
                self.descongelando['validade'] = pd.to_datetime(self.descongelando['validade'])
                if 'kg' not in self.descongelando.columns:
                    print("Aviso: Coluna 'kg' não encontrada na planilha 'descongelamento'. Verifique a estrutura.")
                if 'localizacao_estante' not in self.descongelando.columns:
                    self.descongelando['localizacao_estante'] = 'estante_esquerda'
                if 'data_entrada_estante' not in self.descongelando.columns:
                    self.descongelando['data_entrada_estante'] = pd.NaT
            
            # Garante que as colunas 'kg' e 'localizacao_estante' existam após o carregamento
            for df in [self.estoque, self.descongelando]:
                if 'kg' not in df.columns:
                    df['kg'] = 0.0
                if 'localizacao_estante' not in df.columns:
                    df['localizacao_estante'] = 'desconhecido'


        except FileNotFoundError as e:
            print(f"Erro: Arquivo '{e.filename}' não encontrado. Certifique-se de que 'dados_vendasIA.xlsx' e os arquivos de estado existam.")
            raise
        except Exception as e:
            print(f"Erro ao carregar dados: {e}")
            raise

    def salvar_estado(self):
        os.makedirs(self.estado_salvo_dir, exist_ok=True)
        self.estoque.to_excel(os.path.join(self.estado_salvo_dir, 'estoque_congelador.xlsx'), index=False)
        self.descongelando.to_excel(os.path.join(self.estado_salvo_dir, 'estoque_descongelando.xlsx'), index=False)
        print("Estado do estoque e descongelamento salvos.")

    def preparar_features(self):
        # Cria uma cópia para evitar SettingWithCopyWarning
        df = self.dados_vendas.copy()

        if not pd.api.types.is_datetime64_any_dtype(df['data_dia']):
            df['data_dia'] = pd.to_datetime(df['data_dia'])

        # Crie features base (dia_semana, mes, trimestre) apenas se o DataFrame não estiver vazio
        if not df.empty:
            df['dia_semana'] = df['data_dia'].dt.weekday
            df['mes'] = df['data_dia'].dt.month
            df['trimestre'] = df['data_dia'].dt.quarter
        else: # Se o DataFrame estiver vazio, garanta que as colunas existam com tipo correto
            df['dia_semana'] = pd.Series(dtype='int64')
            df['mes'] = pd.Series(dtype='int64')
            df['trimestre'] = pd.Series(dtype='int64')


        # --- Adicionar features de sazonalidade específicas e "dia de pagamento" ---
        all_saz_features = [f'eh_{e.lower().replace(" ", "_")}_prox' for e in self.eventos_sazonais] + ['eh_pagamento_prox']
        for col_name in all_saz_features:
            if col_name not in df.columns:
                df[col_name] = 0.0 # Inicializa com float 0
            else:
                df[col_name] = 0.0 # Reinicializa para garantir que não haja resíduos de execuções anteriores

        # Preenche as colunas de sazonalidade se o DataFrame não estiver vazio
        if not df.empty:
            # Usar apply para preenchimento mais eficiente que iterrows
            def apply_sazonalidade(row):
                data_atual = row['data_dia']
                saz_values = {}
                for evento, info in self.eventos_sazonais.items():
                    col_name = f'eh_{evento.lower().replace(" ", "_")}_prox'
                    is_sazonal = False
                    for data_evento in info['datas']:
                        if (data_evento - timedelta(days=info['antecedencia_dias']) <= data_atual <= data_evento):
                            is_sazonal = True
                            break
                    saz_values[col_name] = 1 if is_sazonal else 0
                saz_values['eh_pagamento_prox'] = 1 if (1 <= data_atual.day <= 5) or (data_atual.day >= 25) else 0
                return pd.Series(saz_values)

            # Aplica a função e atualiza o DataFrame
            sazonalidade_df = df.apply(apply_sazonalidade, axis=1)
            for col in sazonalidade_df.columns:
                df[col] = sazonalidade_df[col]


        # Calcular médias móveis
        skus_para_processar = df['sku'].unique()
        for sku_val in skus_para_processar:
            mask = df['sku'] == sku_val
            # Ordena antes de calcular rolling
            df.loc[mask] = df.loc[mask].sort_values(by='data_dia')
            if not df.loc[mask].empty:
                # Calcula as médias móveis. min_periods=1 é importante para os primeiros dias
                df.loc[mask, 'media_7d'] = df.loc[mask, 'total_venda_dia_kg'].rolling(7, min_periods=1).mean()
                df.loc[mask, 'media_14d'] = df.loc[mask, 'total_venda_dia_kg'].rolling(14, min_periods=1).mean()
            # Se o SKU não tiver dados (ex: recém-adicionado com apenas 1 dia), as médias serão NaN.
            # O preenchimento abaixo garante que essas colunas existam e sejam numéricas.

        # Preencher quaisquer NaNs remanescentes nas médias móveis com 0.0
        # Garante que essas colunas existam e sejam numéricas, mesmo se o DataFrame estiver vazio inicialmente
        for col in ['media_7d', 'media_14d']:
            if col not in df.columns:
                df[col] = 0.0
            else:
                df[col] = df[col].fillna(0.0)

        # Garante que todas as features esperadas pelo modelo existam no DataFrame final,
        # mesmo que estejam vazias ou com zeros.
        expected_features = [
            'dia_semana', 'mes', 'trimestre', 'media_7d', 'media_14d'
        ] + [f'eh_{e.lower().replace(" ", "_")}_prox' for e in self.eventos_sazonais] + ['eh_pagamento_prox']

        for feature_col in expected_features:
            if feature_col not in df.columns:
                df[feature_col] = 0.0 # Adiciona a coluna com zeros se estiver faltando

        self.dados_vendas = df # Atualiza self.dados_vendas com o DataFrame processado

    def treinar_modelo(self, forcar_re_treino=False):
        caminho_modelo = 'modelos/modelo_rf.pkl'
        os.makedirs('modelos', exist_ok=True)

        if not forcar_re_treino and os.path.exists(caminho_modelo):
            print("Carregando modelo existente...")
            self.modelo = joblib.load(caminho_modelo)
        else:
            print("Treinando novo modelo...")
            # Definir as features que o modelo espera
            features = [
                'dia_semana', 'mes', 'trimestre', 'media_7d', 'media_14d'
            ] + [f'eh_{e.lower().replace(" ", "_")}_prox' for e in self.eventos_sazonais] + ['eh_pagamento_prox']

            # Verifica se há dados suficientes para treinar
            # Remove linhas onde as features ou o target (total_venda_dia_kg) são NaN
            dados_para_treino = self.dados_vendas.dropna(subset=features + ['total_venda_dia_kg']).copy()

            if dados_para_treino.empty:
                print("Erro: Não há dados suficientes (após pre-processamento e filtragem de NaNs) para treinar o modelo. Verifique seus dados de vendas iniciais ou a simulação.")
                raise ValueError("Dados insuficientes para treinamento do modelo.")

            # Garante que todas as features necessárias estão no DataFrame antes de selecionar
            missing_features_in_df = [f for f in features if f not in dados_para_treino.columns]
            if missing_features_in_df:
                # Isso não deve acontecer com o prepare_features atualizado, mas é uma segurança
                raise ValueError(f"As seguintes features estão faltando no DataFrame de treino: {missing_features_in_df}. Verifique 'preparar_features'.")

            X = dados_para_treino[features]
            y = dados_para_treino['total_venda_dia_kg']

            if X.empty or y.empty: # Verificação adicional se X ou y ficaram vazios após a seleção (improvável agora)
                print("Erro: X ou y estão vazios após a seleção de features. Verifique a preparação dos dados.")
                raise ValueError("Dados insuficientes para treinamento do modelo após seleção de features.")

            self.modelo = RandomForestRegressor(n_estimators=150, max_depth=8, random_state=42, n_jobs=-1)
            self.modelo.fit(X, y)
            joblib.dump(self.modelo, caminho_modelo)
            print("Modelo treinado e salvo com sucesso.")

    def verificar_e_re_treinar_modelo(self, periodo_re_treino_dias=7):
        caminho_modelo = 'modelos/modelo_rf.pkl'
        os.makedirs('modelos', exist_ok=True)

        if os.path.exists(caminho_modelo):
            data_modificacao = datetime.fromtimestamp(os.path.getmtime(caminho_modelo))
            if (datetime.now() - data_modificacao).days >= periodo_re_treino_dias:
                print(f"Modelo mais antigo que {periodo_re_treino_dias} dias. Re-treinando...")
                self.treinar_modelo(forcar_re_treino=True)
            else:
                print(f"Modelo atualizado (último treino há {(datetime.now() - data_modificacao).days} dias).")
                self.modelo = joblib.load(caminho_modelo)
        else:
            print("Modelo não encontrado. Treinando pela primeira vez...")
            self.treinar_modelo(forcar_re_treino=True)

    def prever_demanda(self, data_hoje):
        data_previsao = data_hoje + timedelta(days=2) # Previsão para D+2
        previsoes = []

        if self.modelo is None:
            raise RuntimeError("O modelo de previsão não foi treinado ou carregado.")

        # Garante que os dados de vendas estão ordenados por data para médias móveis
        self.dados_vendas = self.dados_vendas.sort_values(by='data_dia')

        # Pega todos os SKUs únicos presentes nos dados de vendas ou no estoque
        # Modificado para usar pd.concat para combinar Series
        all_skus_list = []
        if not self.dados_vendas.empty:
            all_skus_list.append(self.dados_vendas['sku'].unique())
        if not self.estoque.empty:
            all_skus_list.append(self.estoque['sku'].unique())
        if self.descongelando is not None and not self.descongelando.empty:
            all_skus_list.append(self.descongelando['sku'].unique())
        
        # Concatena todas as arrays de SKUs e pega os valores únicos
        all_skus = pd.Series(pd.concat([pd.Series(s) for s in all_skus_list]).unique())


        for sku in all_skus:
            dados_sku_recente = self.dados_vendas[
                (self.dados_vendas['sku'] == sku) &
                (self.dados_vendas['data_dia'] < data_previsao)
            ].sort_values(by='data_dia')

            media_7d = 0.0
            media_14d = 0.0
            
            if not dados_sku_recente.empty:
                # Calcula as médias apenas sobre os dados válidos, preenchendo NaN se não houver dados suficientes
                media_7d = dados_sku_recente['total_venda_dia_kg'].tail(7).mean()
                media_14d = dados_sku_recente['total_venda_dia_kg'].tail(14).mean()
            
            # Fallback para caso não haja dados suficientes para as médias, preenche com 0
            if pd.isna(media_7d):
                media_7d = 0.0
            if pd.isna(media_14d):
                media_14d = 0.0
            

            # --- Calcular as features de sazonalidade para a data da PREVISÃO (D+2) ---
            sazonalidade_features_previsao = {}
            for evento, info in self.eventos_sazonais.items():
                col_name = f'eh_{evento.lower().replace(" ", "_")}_prox'
                sazonalidade_features_previsao[col_name] = 0
                for data_evento in info['datas']:
                    if (data_evento - timedelta(days=info['antecedencia_dias']) <= data_previsao <= data_evento):
                        sazonalidade_features_previsao[col_name] = 1
                        break

            eh_pagamento_prox = 0
            if (1 <= data_previsao.day <= 5) or (data_previsao.day >= 25):
                eh_pagamento_prox = 1
            sazonalidade_features_previsao['eh_pagamento_prox'] = eh_pagamento_prox


            features_data = {
                'dia_semana': data_previsao.weekday(),
                'mes': data_previsao.month,
                'trimestre': (data_previsao.month - 1) // 3 + 1,
                'media_7d': media_7d,
                'media_14d': media_14d,
                **sazonalidade_features_previsao
            }

            # Definir a ordem exata das colunas das features que o modelo foi treinado
            features_treinamento = [
                'dia_semana', 'mes', 'trimestre', 'media_7d', 'media_14d'
            ] + [f'eh_{e.lower().replace(" ", "_")}_prox' for e in self.eventos_sazonais] + ['eh_pagamento_prox']

            X_prever = pd.DataFrame([features_data])[features_treinamento]
            
            qtd_prevista = self.modelo.predict(X_prever)[0]
            previsoes.append({
                'sku': sku,
                'data_previsao': data_previsao,
                'qtd_prevista': max(0, round(qtd_prevista, 2))
            })

        return pd.DataFrame(previsoes)


    def calcular_descongelamento(self, previsoes, data_para_validade_estoque):
        relatorio = []
        fator_perda = 1 / (1 - 0.15)

        print(f"\n--- Detalhes do Cálculo de Descongelamento para {data_para_validade_estoque.strftime('%Y-%m-%d')} (Venda D+2) ---")
        for _, row in previsoes.iterrows():
            sku = row['sku']
            data_previsao_venda = row['data_previsao']
            qtd_prevista = row['qtd_prevista']

            estoque_congelador = self.estoque[
                (self.estoque['sku'] == sku) &
                (self.estoque['validade'] >= data_previsao_venda) &
                (self.estoque['localizacao_estante'] == 'congelador')
            ]['kg'].sum()

            em_descongelamento_valido = self.descongelando[
                (self.descongelando['sku'] == sku) &
                (self.descongelando['validade'] >= data_previsao_venda) &
                ((self.descongelando['localizacao_estante'] == 'estante_esquerda') |
                 (self.descongelando['localizacao_estante'] == 'estante_central'))
            ]['kg'].sum()

            qtd_necessaria_venda = qtd_prevista * fator_perda
            qtd_necessaria_descongelar_do_congelador = max(0, qtd_necessaria_venda - estoque_congelador - em_descongelamento_valido)

            print(f"  SKU: {sku}")
            print(f"    Previsão Venda (D+2): {round(qtd_prevista, 2)} kg")
            print(f"    Qtd Necessária c/ Perda ({round((fator_perda - 1) * 100, 1)}%): {round(qtd_necessaria_venda, 2)} kg")
            print(f"    Estoque Congelador (válido p/ D+2): {round(estoque_congelador, 2)} kg")
            print(f"    Em Descongelamento (kg) (para D+2): {round(em_descongelamento_valido, 2)} kg")
            print(f"    >> Qtd para Descongelar HOJE (D-0): {round(qtd_necessaria_descongelar_do_congelador, 2)} kg")
            print("-" * 40)

            relatorio.append({
                'SKU': sku,
                'Data Previsão Venda': data_previsao_venda.strftime('%Y-%m-%d'),
                'Previsão Venda (kg)': round(qtd_prevista, 2),
                'Estoque Congelador (kg)': round(estoque_congelador, 2),
                'Em Descongelamento (kg) (para D+2)': round(em_descongelamento_valido, 2),
                'Qtd Necessária para Descongelar HOJE (kg)': round(qtd_necessaria_descongelar_do_congelador, 2),
            })
        return pd.DataFrame(relatorio)

    def reabastecer_estoque(self, sku, qtd_reabastecer, data_chegada):
        """
        Simula o reabastecimento de um SKU no estoque do congelador.
        Adiciona a quantidade especificada ao estoque.
        """
        if qtd_reabastecer <= 0:
            return

        # Para simplificação, vamos assumir que a validade é 30 dias a partir da data de chegada
        # Em um sistema real, isso viria da NF ou informações do produto.
        validade_padrao = data_chegada + timedelta(days=30) 

        novo_item_estoque = pd.DataFrame([{
            'sku': sku,
            'kg': qtd_reabastecer,
            'validade': validade_padrao,
            'localizacao_estante': 'congelador',
            'data_entrada_estante': data_chegada
        }])
        
        self.estoque = pd.concat([self.estoque, novo_item_estoque], ignore_index=True)
        print(f"*** REABASTECIMENTO: Estoque reabastecido com {round(qtd_reabastecer, 2)} kg de {sku} no congelador. ***")
        
        # Opcional: Registrar a movimentação de reabastecimento
        self.registros_movimentacao.append({
            'data': data_chegada,
            'sku': sku,
            'quantidade_movida': qtd_reabastecer,
            'origem': 'Fornecedor',
            'destino': 'congelador'
        })

    def verificar_e_reabastecer_estoque(self, data_hoje):
        """
        Verifica o nível de estoque no CONGELADOR para cada SKU
        e aciona o reabastecimento se estiver abaixo do ponto de pedido.
        """
        print(f"\n--- Verificando Nível de Estoque do CONGELADOR para Reabastecimento ({data_hoje.strftime('%Y-%m-%d')}) ---")
        
        # Pega todos os SKUs únicos presentes nos dados de vendas ou no estoque
        all_skus_list = []
        if not self.dados_vendas.empty:
            all_skus_list.append(self.dados_vendas['sku'].unique())
        if not self.estoque.empty:
            all_skus_list.append(self.estoque['sku'].unique())
        if self.descongelando is not None and not self.descongelando.empty:
            all_skus_list.append(self.descongelando['sku'].unique())
        
        all_skus = pd.Series(pd.concat([pd.Series(s) for s in all_skus_list]).unique())


        # Garante que 'validade' e 'data_entrada_estante' sejam datetimes para o estoque e descongelando
        if not self.estoque.empty:
            self.estoque['validade'] = pd.to_datetime(self.estoque['validade'])
            self.estoque['data_entrada_estante'] = pd.to_datetime(self.estoque['data_entrada_estante'])
        if not self.descongelando.empty:
            self.descongelando['validade'] = pd.to_datetime(self.descongelando['validade'])
            self.descongelando['data_entrada_estante'] = pd.to_datetime(self.descongelando['data_entrada_estante'])


        for sku in all_skus:
            estoque_congelador_sku = self.estoque[
                (self.estoque['sku'] == sku) &
                (self.estoque['localizacao_estante'] == 'congelador')
            ]['kg'].sum()

            # Apenas considera o estoque do CONGELADOR para a decisão de reabastecimento
            estoque_para_reabastecimento_check = estoque_congelador_sku 

            print(f"  SKU: {sku} - Estoque CONGELADOR Disponível: {round(estoque_congelador_sku, 2)} kg")

            if estoque_para_reabastecimento_check < self.ponto_pedido_default:
                print(f"    -> Estoque de {sku} no CONGELADOR ({round(estoque_congelador_sku, 2)} kg) está abaixo do Ponto de Pedido ({self.ponto_pedido_default} kg).")
                self.reabastecer_estoque(sku, self.qtd_pedido_default, data_hoje)
            else:
                print(f"    -> Estoque de {sku} no CONGELADOR está OK.")
        print("--- Verificação de Reabastecimento Concluída. ---\n")


    def _simular_movimentacao_estante(self, sku, qtd_movida, estante_origem, estante_destino, data_movimento, confirmacao_automatica=False):
        if qtd_movida <= 0.01:
            return

        print(f"\n--- Ordem de Movimentação para o Funcionário ---")
        print(f"Data: {data_movimento.strftime('%Y-%m-%d')}")
        print(f"SKU: {sku}")
        print(f"Quantidade: {round(qtd_movida, 2)} kg")
        print(f"Mover de: {estante_origem.upper()} para: {estante_destino.upper()}")
        print("-------------------------------------------------")

        if not confirmacao_automatica:
            input("Pressione ENTER após a movimentação para confirmar...")
            print("Movimentação confirmada.")
        else:
            print("Movimentação simulada e confirmada automaticamente.")
            time.sleep(0.1)

        if estante_origem == 'congelador' and estante_destino == 'estante_esquerda':
            itens_no_congelador = self.estoque[
                (self.estoque['sku'] == sku) &
                (self.estoque['localizacao_estante'] == 'congelador')
            ].sort_values(by='validade', ascending=True).copy()

            movido_total = 0
            novos_itens_descongelando = []

            for index, row in itens_no_congelador.iterrows():
                if movido_total >= qtd_movida:
                    break
                qtd_disponivel = row['kg']
                qtd_a_mover = min(qtd_disponivel, qtd_movida - movido_total)

                if qtd_a_mover > 0.01:
                    self.estoque.loc[index, 'kg'] -= qtd_a_mover
                    if self.estoque.loc[index, 'kg'] < 0.001:
                        self.estoque = self.estoque.drop(index)
                    
                    novo_item = row.copy()
                    novo_item['kg'] = qtd_a_mover
                    novo_item['localizacao_estante'] = estante_destino
                    novo_item['data_entrada_estante'] = data_movimento
                    novos_itens_descongelando.append(novo_item)
                    movido_total += qtd_a_mover
            
            if novos_itens_descongelando:
                self.descongelando = pd.concat([self.descongelando, pd.DataFrame(novos_itens_descongelando)], ignore_index=True)
            print(f"Moveu {round(movido_total, 2)} kg de {sku} do {estante_origem} para {estante_destino}.")

        elif estante_origem == 'estante_esquerda' and estante_destino == 'estante_central':
            # Filtra itens que entraram na estante_esquerda no DIA ANTERIOR
            itens_a_mover = self.descongelando[
                (self.descongelando['sku'] == sku) &
                (self.descongelando['localizacao_estante'] == 'estante_esquerda') &
                (self.descongelando['data_entrada_estante'] == (data_movimento - timedelta(days=1)))
            ].sort_values(by='validade', ascending=True).copy()

            movido_total = 0
            novos_itens_central = []
            for index, row in itens_a_mover.iterrows():
                if movido_total >= qtd_movida:
                    break
                qtd_disponivel = row['kg']
                qtd_a_mover = min(qtd_disponivel, qtd_movida - movido_total)

                if qtd_a_mover > 0.01:
                    self.descongelando.loc[index, 'kg'] -= qtd_a_mover
                    if self.descongelando.loc[index, 'kg'] < 0.001:
                        self.descongelando = self.descongelando.drop(index)

                    # Adiciona ao descongelando com a nova localização e data de entrada
                    novo_item_central = row.copy()
                    novo_item_central['kg'] = qtd_a_mover
                    novo_item_central['localizacao_estante'] = estante_destino
                    novo_item_central['data_entrada_estante'] = data_movimento
                    novos_itens_central.append(novo_item_central)
                    movido_total += qtd_a_mover

            if novos_itens_central:
                self.descongelando = pd.concat([self.descongelando, pd.DataFrame(novos_itens_central)], ignore_index=True)
            print(f"Moveu {round(movido_total, 2)} kg de {sku} da {estante_origem} para {estante_destino}.")

        elif estante_origem == 'estante_central' and estante_destino == 'balcao':
            # Filtra itens que entraram na estante_central no DIA ANTERIOR
            itens_a_mover = self.descongelando[
                (self.descongelando['sku'] == sku) &
                (self.descongelando['localizacao_estante'] == 'estante_central') &
                (self.descongelando['data_entrada_estante'] == (data_movimento - timedelta(days=1)))
            ].sort_values(by='validade', ascending=True).copy()

            movido_total = 0
            for index, row in itens_a_mover.iterrows():
                if movido_total >= qtd_movida:
                    break
                qtd_disponivel = row['kg']
                qtd_a_mover = min(qtd_disponivel, qtd_movida - movido_total)

                if qtd_a_mover > 0.01:
                    self.descongelando.loc[index, 'kg'] -= qtd_a_mover
                    movido_total += qtd_a_mover
                    if self.descongelando.loc[index, 'kg'] < 0.001:
                        self.descongelando = self.descongelando.drop(index)
            print(f"Moveu {round(movido_total, 2)} kg de {sku} da {estante_origem} para {estante_destino} (balcão/venda).")

        if qtd_movida > 0.01:
            self.registros_movimentacao.append({
                'data': data_movimento,
                'sku': sku,
                'quantidade_movida': qtd_movida,
                'origem': estante_origem,
                'destino': estante_destino
            })

    def simular_venda_diaria(self, data_simulacao):
        """Simula dados de vendas para o dia dado e os adiciona a self.dados_vendas."""
        print(f"\nSimulando vendas para o dia: {data_simulacao.strftime('%Y-%m-%d')}")
        novas_vendas = []
        
        # Pega SKUs do histórico existente ou define um padrão se o histórico estiver vazio
        skus_existentes = self.dados_vendas['sku'].unique() if not self.dados_vendas.empty else ['Frango Inteiro Congelado', 'Coxa de Frango Congelada'] # Exemplo de SKUs padrão

        for sku in skus_existentes:
            # Pega a média histórica de venda para o SKU, ou um valor padrão se não houver histórico
            vendas_historicas_sku = self.dados_vendas[self.dados_vendas['sku'] == sku]['total_venda_dia_kg']
            if not vendas_historicas_sku.empty:
                media_venda = vendas_historicas_sku.mean()
                # Simula uma variação de +/- 20% da média histórica
                simulated_venda = max(0, round(media_venda * random.uniform(0.8, 1.2), 2))
            else:
                # Caso não haja histórico para o SKU (novo SKU ou dados iniciais vazios), simula um valor base
                simulated_venda = round(random.uniform(50, 200), 2) # Exemplo: 50 a 200 kg

            novas_vendas.append({
                'data_dia': data_simulacao,
                'sku': sku,
                'total_venda_dia_kg': simulated_venda
            })
        
        df_novas_vendas = pd.DataFrame(novas_vendas)
        
        # Concatena os novos dados de venda com os dados existentes
        self.dados_vendas = pd.concat([self.dados_vendas, df_novas_vendas], ignore_index=True)
        # Garante que não haja duplicatas para o mesmo dia/sku (mantém a última entrada)
        self.dados_vendas = self.dados_vendas.drop_duplicates(subset=['data_dia', 'sku'], keep='last')
        self.dados_vendas = self.dados_vendas.sort_values(by='data_dia').reset_index(drop=True)
        print(f"Vendas simuladas adicionadas para {data_simulacao.strftime('%Y-%m-%d')}.")


    def gerenciar_descongelamento_diario(self, data_hoje):
        print(f"\n--- Gerenciamento Diário de Descongelamento para {data_hoje.strftime('%Y-%m-%d')} ---")

        # --- Etapa D-0: Retirada do Congelador para Estante Esquerda ---
        print("\n** Etapa D-0: Calculando o que retirar do congelador (para a demanda D+2)... **")
        previsoes_d2 = self.prever_demanda(data_hoje)
        necessario_descongelar_hoje = self.calcular_descongelamento(previsoes_d2, data_hoje + timedelta(days=2))

        skus_para_d0 = necessario_descongelar_hoje[necessario_descongelar_hoje['Qtd Necessária para Descongelar HOJE (kg)'] > 0.01]

        if skus_para_d0.empty:
            print("Nenhum item precisa ser movido do congelador para a estante esquerda hoje (D-0).")
        else:
            print("Itens a serem movidos do congelador para a estante esquerda (D-0):")
            for _, row in skus_para_d0.iterrows():
                self._simular_movimentacao_estante(
                    sku=row['SKU'],
                    qtd_movida=row['Qtd Necessária para Descongelar HOJE (kg)'],
                    estante_origem='congelador',
                    estante_destino='estante_esquerda',
                    data_movimento=data_hoje,
                    confirmacao_automatica=False
                )
        print("** Fim da Etapa D-0. **\n")

        # --- Etapa D-1: Movimentação da Estante Esquerda para a Estante Central (ao final do dia) ---
        print("\n** Etapa D-1: Movendo itens da estante esquerda para a estante central (descongelamento, itens de D-0 anterior)... **")
        # Pega todos os SKUs que entraram na estante_esquerda no dia anterior
        skus_na_estante_esquerda_para_mover = self.descongelando[
            (self.descongelando['localizacao_estante'] == 'estante_esquerda') &
            (self.descongelando['data_entrada_estante'] == (data_hoje - timedelta(days=1)))
        ]['sku'].unique()

        if not skus_na_estante_esquerda_para_mover.size > 0:
            print("Nenhum item da estante esquerda para mover para a estante central hoje (D-1).")
        else:
            print("Itens a serem movidos da estante esquerda para a estante central:")
            for sku in skus_na_estante_esquerda_para_mover:
                # Soma a quantidade total do SKU que atende aos critérios
                qtd_total_sku_na_esquerda = self.descongelando[
                    (self.descongelando['sku'] == sku) &
                    (self.descongelando['localizacao_estante'] == 'estante_esquerda') &
                    (self.descongelando['data_entrada_estante'] == (data_hoje - timedelta(days=1)))
                ]['kg'].sum()
                if qtd_total_sku_na_esquerda > 0.01:
                    print(f"  - SKU: {sku}, Qtd: {round(qtd_total_sku_na_esquerda, 2)} kg")
                    self._simular_movimentacao_estante(
                        sku=sku,
                        qtd_movida=qtd_total_sku_na_esquerda,
                        estante_origem='estante_esquerda',
                        estante_destino='estante_central',
                        data_movimento=data_hoje,
                        confirmacao_automatica=False
                    )
        print("** Fim da Etapa D-1. **\n")


        # --- Etapa D-2: Movimentação da Estante Central para o Balcão de Venda (ao final do dia) ---
        print("\n** Etapa D-2: Movendo itens da estante central para o balcão (venda, itens de D-1 anterior)... **")
        # Pega todos os SKUs que entraram na estante_central no dia anterior
        skus_na_estante_central_para_mover = self.descongelando[
            (self.descongelando['localizacao_estante'] == 'estante_central') &
            (self.descongelando['data_entrada_estante'] == (data_hoje - timedelta(days=1)))
        ]['sku'].unique()

        if not skus_na_estante_central_para_mover.size > 0:
            print("Nenhum item da estante central para mover para o balcão hoje (D-2).")
        else:
            print("Itens a serem movidos da estante central para o balcão:")
            for sku in skus_na_estante_central_para_mover:
                qtd_total_sku_na_central = self.descongelando[
                    (self.descongelando['sku'] == sku) &
                    (self.descongelando['localizacao_estante'] == 'estante_central') &
                    (self.descongelando['data_entrada_estante'] == (data_hoje - timedelta(days=1)))
                ]['kg'].sum()
                if qtd_total_sku_na_central > 0.01:
                    print(f"  - SKU: {sku}, Qtd: {round(qtd_total_sku_na_central, 2)} kg")
                    self._simular_movimentacao_estante(
                        sku=sku,
                        qtd_movida=qtd_total_sku_na_central,
                        estante_origem='estante_central',
                        estante_destino='balcao',
                        data_movimento=data_hoje,
                        confirmacao_automatica=False
                    )
        print("** Fim da Etapa D-2. **\n")


    def gerar_relatorio(self, df_relatorio, sufixo="descongelamento"):
        data_geracao = datetime.now().strftime('%Y%m%d_%H%M%S')
        os.makedirs('relatorios', exist_ok=True)
        nome_arquivo = f'relatorios/relatorio_{sufixo}_{data_geracao}.xlsx'
        if 'Qtd Necessária para Descongelar HOJE (kg)' in df_relatorio.columns:
            df_relatorio = df_relatorio.sort_values(by=['Qtd Necessária para Descongelar HOJE (kg)', 'SKU'],
            ascending=[False, True])
        else:
            print(f"Aviso: Coluna 'Qtd Necessária para Descongelar HOJE (kg)' não encontrada no relatório '{sufixo}'. Ordenação padrão será aplicada.")
            df_relatorio = df_relatorio.sort_values(by=['SKU'], ascending=[True])

        df_relatorio.to_excel(nome_arquivo, index=False)
        print(f"Relatório de {sufixo} gerado: {nome_arquivo}")

    def gerar_relatorio_movimentacao(self):
        if not self.registros_movimentacao:
            print("Não há registros de movimentação para gerar relatório.")
            return

        df_movimentacao = pd.DataFrame(self.registros_movimentacao)
        df_movimentacao['data'] = df_movimentacao['data'].dt.strftime('%Y-%m-%d')
        df_movimentacao = df_movimentacao.sort_values(by=['data', 'origem', 'sku'])

        data_geracao = datetime.now().strftime('%Y%m%d_%H%M%S')
        os.makedirs('relatorios', exist_ok=True)
        nome_arquivo = f'relatorios/relatorio_movimentacao_{data_geracao}.xlsx'
        df_movimentacao.to_excel(nome_arquivo, index=False)
        print(f"Relatório de movimentação gerado: {nome_arquivo}")


if __name__ == "__main__":
    sistema = SistemaGALO()

    try:
        sistema.carregar_dados()
        # A primeira preparação de features e treinamento ainda podem ser feitos aqui com os dados iniciais
        sistema.preparar_features() # Preparar features dos dados históricos iniciais
        sistema.verificar_e_re_treinar_modelo(periodo_re_treino_dias=7)

        if os.path.exists(os.path.join(sistema.estado_salvo_dir, 'ultima_execucao.txt')):
            with open(os.path.join(sistema.estado_salvo_dir, 'ultima_execucao.txt'), 'r') as f:
                last_run_date_str = f.read().strip()
                data_simulacao_hoje = datetime.strptime(last_run_date_str, '%Y-%m-%d') + timedelta(days=1)
                print(f"Continuando simulação a partir de: {data_simulacao_hoje.strftime('%Y-%m-%d')}")
        else:
            # Pega a última data dos dados de venda e adiciona 1 dia para começar a simulação
            if not sistema.dados_vendas.empty:
                data_simulacao_hoje = sistema.dados_vendas['data_dia'].max() + timedelta(days=1)
            else: # Se dados_vendas está vazio, começa de uma data arbitrária
                data_simulacao_hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            print(f"Iniciando nova simulação a partir de: {data_simulacao_hoje.strftime('%Y-%m-%d')}")

        # --- Loop Infinito para Simulação Contínua ---
        while True:
            print(f"\n#####################################################")
            print(f"# EXECUTANDO OPERAÇÕES PARA O DIA: {data_simulacao_hoje.strftime('%Y-%m-%d')} #")
            print(f"#####################################################\n")

            # 1. Simular novas vendas para o dia atual
            sistema.simular_venda_diaria(data_simulacao_hoje)
            
            # 2. Re-preparar features com os novos dados de vendas
            sistema.preparar_features() 
            
            # 3. Re-treinar o modelo se necessário com dados atualizados
            sistema.verificar_e_re_treinar_modelo(periodo_re_treino_dias=7) 

            # 4. Verificar e Reabastecer Estoque antes de calcular descongelamento
            sistema.verificar_e_reabastecer_estoque(data_simulacao_hoje)

            # 5. Gerenciar o descongelamento diário (movimentação entre estantes)
            sistema.gerenciar_descongelamento_diario(data_simulacao_hoje)

            # 6. Previsão e relatório para D+2 (já utiliza o estoque e as vendas atualizadas)
            previsoes_para_d_mais_2 = sistema.prever_demanda(data_simulacao_hoje)
            relatorio_descongelamento = sistema.calcular_descongelamento(previsoes_para_d_mais_2, data_simulacao_hoje + timedelta(days=2))
            sistema.gerar_relatorio(relatorio_descongelamento, sufixo=f"descongelamento_para_{data_simulacao_hoje.strftime('%Y%m%d')}")

            # 7. Salvar o estado do sistema
            sistema.salvar_estado()
            with open(os.path.join(sistema.estado_salvo_dir, 'ultima_execucao.txt'), 'w') as f:
                f.write(data_simulacao_hoje.strftime('%Y-%m-%d'))

            print(f"\nOperações para o dia {data_simulacao_hoje.strftime('%Y-%m-%d')} concluídas.")

            comando = input("Pressione ENTER para avançar para o próximo dia, ou digite 'SAIR' para encerrar: ").strip().upper()
            if comando == "SAIR":
                print("Comando 'SAIR' detectado. Encerrando simulação.")
                break

            data_simulacao_hoje += timedelta(days=1)

        sistema.gerar_relatorio_movimentacao()

        print("\nSistema GALO finalizado com sucesso!")

    except Exception as e:
        print(f"Erro no sistema: {e}")
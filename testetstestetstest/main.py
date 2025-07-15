# modelo_previsao.py

import pandas as pd
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor
import joblib
import os
import time
import random
from sklearn.metrics import mean_absolute_error, mean_squared_error # Importar métricas de erro

class SistemaGALO:
    def __init__(self):
        self.modelo = None
        self.dados_vendas = None
        self.estoque = {}
        self.descongelando = {}
        self.ultima_execucao_diaria = None
        self.registros_movimentacao = []
        self.registros_abastecimento = []

        self.estado_salvo_dir = 'estado_sistema'

        self.ponto_pedido_default = 50 # kg
        self.qtd_pedido_default = 60 # kg

        self.eventos_sazonais = {
            'Carnaval': {
                'datas': [
                    datetime(2024, 2, 12), datetime(2024, 2, 13),
                    datetime(2025, 3, 3), datetime(2025, 3, 4)
                ], 'impacto': 1.2
            },
            'Pascoa': {
                'datas': [
                    datetime(2024, 3, 31),
                    datetime(2025, 4, 20)
                ], 'impacto': 1.1
            },
            'Natal': {
                'datas': [
                    datetime(2024, 12, 25),
                    datetime(2025, 12, 25)
                ], 'impacto': 1.3
            },
            'Ano_Novo': {
                'datas': [
                    datetime(2025, 1, 1),
                    datetime(2026, 1, 1)
                ], 'impacto': 1.15
            },
            'Black_Friday': {
                'datas': [
                    datetime(2024, 11, 29),
                    datetime(2025, 11, 28)
                ], 'impacto': 1.25
            },
             'Dia_das_Maes': {
                'datas': [
                    datetime(2024, 5, 12),
                    datetime(2025, 5, 11)
                ], 'impacto': 1.1
            },
             'Dia_dos_Pais': {
                'datas': [
                    datetime(2024, 8, 11),
                    datetime(2025, 8, 10)
                ], 'impacto': 1.05
            },
            'Dia_das_Criancas': {
                'datas': [
                    datetime(2024, 10, 12),
                    datetime(2025, 10, 12)
                ], 'impacto': 1.05
            },
            'Revolucao_Constitucionalista': { # Feriado apenas em SP
                'datas': [
                    datetime(2024, 7, 9),
                    datetime(2025, 7, 9)
                ], 'impacto': 0.9 # Leve queda por ser um dia útil de feriado regional
            }
        }
        self.feriados_nacionais_2024 = [
            datetime(2024, 1, 1), datetime(2024, 2, 12), datetime(2024, 2, 13), datetime(2024, 3, 29),
            datetime(2024, 4, 21), datetime(2024, 5, 1), datetime(2024, 5, 30), datetime(2024, 9, 7),
            datetime(2024, 10, 12), datetime(2024, 11, 2), datetime(2024, 11, 15), datetime(2024, 11, 20),
            datetime(2024, 12, 25)
        ]
        self.feriados_nacionais_2025 = [
            datetime(2025, 1, 1), datetime(2025, 3, 3), datetime(2025, 3, 4), datetime(2025, 4, 18),
            datetime(2025, 4, 21), datetime(2025, 5, 1), datetime(2025, 6, 19), datetime(2025, 9, 7),
            datetime(2025, 10, 12), datetime(2025, 11, 2), datetime(2025, 11, 15), datetime(2025, 11, 20),
            datetime(2025, 12, 25)
        ]
        self.feriados_nacionais = self.feriados_nacionais_2024 + self.feriados_nacionais_2025


        self.carregar_dados_vendas()
        self.carregar_modelo()
        self.carregar_estado()

    def carregar_dados_vendas(self, path='dados_vendas.csv'):
        if os.path.exists(path):
            try:
                df = pd.read_csv(path, sep=';', decimal=',', encoding='latin-1')
                df['data_dia'] = pd.to_datetime(df['data_dia'], format='%Y-%m-%d')
                self.dados_vendas = df
                print(f"Dados de vendas carregados de {path}. Total de registros: {len(df)}")
            except Exception as e:
                print(f"Erro ao carregar dados de vendas de {path}: {e}")
                self.dados_vendas = pd.DataFrame(columns=['data_dia', 'filial', 'sku', 'quantidade_vendida_kg'])
        else:
            print(f"Arquivo {path} não encontrado. Iniciando com dados de vendas vazios.")
            self.dados_vendas = pd.DataFrame(columns=['data_dia', 'filial', 'sku', 'quantidade_vendida_kg'])

    def salvar_estado(self):
        os.makedirs(self.estado_salvo_dir, exist_ok=True)
        estado_path = os.path.join(self.estado_salvo_dir, 'estado.pkl')
        estado = {
            'estoque': self.estoque,
            'descongelando': self.descongelando,
            'ultima_execucao_diaria': self.ultima_execucao_diaria,
            'registros_movimentacao': self.registros_movimentacao,
            'registros_abastecimento': self.registros_abastecimento
        }
        joblib.dump(estado, estado_path)
        print(f"Estado do sistema salvo em {estado_path}")

    def carregar_estado(self):
        estado_path = os.path.join(self.estado_salvo_dir, 'estado.pkl')
        if os.path.exists(estado_path):
            try:
                estado = joblib.load(estado_path)
                self.estoque = estado.get('estoque', {})
                self.descongelando = estado.get('descongelando', {})
                self.ultima_execucao_diaria = estado.get('ultima_execucao_diaria')
                self.registros_movimentacao = estado.get('registros_movimentacao', [])
                self.registros_abastecimento = estado.get('registros_abastecimento', [])
                print(f"Estado do sistema carregado de {estado_path}")
            except Exception as e:
                print(f"Erro ao carregar estado do sistema de {estado_path}: {e}")
                self.estoque = {}
                self.descongelando = {}
                self.ultima_execucao_diaria = None
                self.registros_movimentacao = []
                self.registros_abastecimento = []
        else:
            print(f"Nenhum estado salvo encontrado em {estado_path}. Iniciando com estado vazio.")
            self.estoque = {}
            self.descongelando = {}
            self.ultima_execucao_diaria = None
            self.registros_movimentacao = []
            self.registros_abastecimento = []

    def carregar_modelo(self):
        model_path = 'modelos/random_forest_model.joblib'
        if os.path.exists(model_path):
            self.modelo = joblib.load(model_path)
            print(f"Modelo carregado de {model_path}")
        else:
            print(f"Modelo não encontrado em {model_path}. Treinando novo modelo.")
            self.treinar_modelo()

    def preparar_features(self, df):
        df['data_venda'] = pd.to_datetime(df['data_venda'])
        df['dia_da_semana'] = df['data_venda'].dt.dayofweek
        df['mes'] = df['data_venda'].dt.month
        df['dia_do_ano'] = df['data_venda'].dt.dayofyear
        df['ano'] = df['data_venda'].dt.year

        df['is_feriado'] = df['data_venda'].isin(self.feriados_nacionais).astype(int)
        for evento, info in self.eventos_sazonais.items():
            df[f'is_{evento.lower()}'] = df['data_venda'].isin(info['datas']).astype(int)
        return df

    def treinar_modelo(self):
        if self.dados_vendas is None or self.dados_vendas.empty:
            print("Não há dados de vendas para treinar o modelo.")
            self.modelo = RandomForestRegressor(random_state=42)
            dummy_data = pd.DataFrame([[0,0,0,0,0,0,0]], columns=['dia_da_semana', 'mes', 'dia_do_ano', 'ano', 'filial_encoded', 'sku_encoded', 'is_feriado'])
            self.modelo.fit(dummy_data, [0])
            self.filial_mapping = {} # Inicializa mapeamentos vazios
            self.sku_mapping = {}
            return

        df_train = self.preparar_features(self.dados_vendas.copy())

        # Codificar 'filial' e 'sku'
        df_train['filial_encoded'] = df_train['filial'].astype('category').cat.codes
        df_train['sku_encoded'] = df_train['sku'].astype('category').cat.codes

        self.filial_mapping = {category: code for code, category in enumerate(df_train['filial'].astype('category').cat.categories)}
        self.sku_mapping = {category: code for code, category in enumerate(df_train['sku'].astype('category').cat.categories)}

        features = ['dia_da_semana', 'mes', 'dia_do_ano', 'ano', 'filial_encoded', 'sku_encoded', 'is_feriado']
        for evento in self.eventos_sazonais.keys():
            features.append(f'is_{evento.lower()}')

        for feature in features:
            if feature not in df_train.columns:
                df_train[feature] = 0

        X = df_train[features]
        y = df_train['quantidade_vendida_kg']

        if len(X) == 0:
            print("Dados de treinamento vazios após preparação de features. Modelo não será treinado de forma eficaz.")
            self.modelo = RandomForestRegressor(random_state=42)
            dummy_data = pd.DataFrame([[0,0,0,0,0,0,0]], columns=['dia_da_semana', 'mes', 'dia_do_ano', 'ano', 'filial_encoded', 'sku_encoded', 'is_feriado'])
            self.modelo.fit(dummy_data, [0])
            return

        self.modelo = RandomForestRegressor(n_estimators=100, random_state=42)
        self.modelo.fit(X, y)

        os.makedirs('modelos', exist_ok=True)
        joblib.dump(self.modelo, 'modelos/random_forest_model.joblib')
        print("Modelo treinado e salvo com sucesso!")

    def prever_demanda_futura(self, data_base, n_dias=3):
        previsoes = {}
        for i in range(1, n_dias + 1):
            data_previsao = data_base + timedelta(days=i)
            for filial_str, filial_code in self.filial_mapping.items():
                for sku_str, sku_code in self.sku_mapping.items():
                    features = self._criar_features_para_previsao(data_previsao, filial_code, sku_code)
                    if self.modelo:
                        demanda_prevista = self.modelo.predict([features])[0]
                        demanda_prevista = max(0, demanda_prevista)
                        previsoes[(data_previsao.strftime('%Y-%m-%d'), filial_str, sku_str)] = demanda_prevista
                    else:
                        previsoes[(data_previsao.strftime('%Y-%m-%d'), filial_str, sku_str)] = 0
        return previsoes

    def _criar_features_para_previsao(self, data, filial_encoded, sku_encoded):
        features = {
            'dia_da_semana': data.dayofweek,
            'mes': data.month,
            'dia_do_ano': data.timetuple().tm_yday,
            'ano': data.year,
            'filial_encoded': filial_encoded,
            'sku_encoded': sku_encoded,
            'is_feriado': int(data in self.feriados_nacionais)
        }
        for evento, info in self.eventos_sazonais.items():
            features[f'is_{evento.lower()}'] = int(data in info['datas'])

        feature_order = ['dia_da_semana', 'mes', 'dia_do_ano', 'ano', 'filial_encoded', 'sku_encoded', 'is_feriado']
        for evento in self.eventos_sazonais.keys():
            feature_order.append(f'is_{evento.lower()}')

        final_features = [features.get(f, 0) for f in feature_order]

        return final_features

    def verificar_e_re_treinar_modelo(self):
        model_path = 'modelos/random_forest_model.joblib'
        if not os.path.exists(model_path):
            print("Modelo não encontrado ou é a primeira execução. Treinando modelo...")
            self.treinar_modelo()
        elif self.modelo is None:
             self.carregar_modelo()
        else:
            print("Modelo já carregado.")

    def prever_demanda_historica(self):
        if self.dados_vendas is None or self.dados_vendas.empty:
            print("Não há dados de vendas para realizar previsão histórica.")
            return pd.DataFrame()

        if not hasattr(self, 'filial_mapping') or not hasattr(self, 'sku_mapping') or not self.filial_mapping or not self.sku_mapping:
             print("Mapeamentos de filial/sku não encontrados ou vazios. Treinando o modelo para garantir mapeamentos...")
             self.treinar_modelo() # Garante que os mapeamentos existam
             if not hasattr(self, 'filial_mapping') or not hasattr(self, 'sku_mapping') or not self.filial_mapping or not self.sku_mapping:
                 print("Não foi possível criar mapeamentos. Abortando previsão histórica.")
                 return pd.DataFrame()

        datas_unicas = self.dados_vendas['data'].unique()
        filiais_unicas = self.dados_vendas['filial'].unique()
        skus_unicos = self.dados_vendas['sku'].unique()

        resultados_previsao = []

        for data_ts in datas_unicas:
            data = pd.to_datetime(data_ts)
            for filial_str in filiais_unicas:
                if filial_str not in self.filial_mapping:
                    continue
                filial_code = self.filial_mapping[filial_str]
                for sku_str in skus_unicos:
                    if sku_str not in self.sku_mapping:
                        continue
                    sku_code = self.sku_mapping[sku_str]

                    features = self._criar_features_para_previsao(data, filial_code, sku_code)

                    if self.modelo:
                        demanda_prevista = self.modelo.predict([features])[0]
                        demanda_prevista = max(0, demanda_prevista)
                    else:
                        demanda_prevista = 0

                    resultados_previsao.append({
                        'data_venda': data,
                        'filial': filial_str,
                        'sku': sku_str,
                        'demanda_prevista_kg': demanda_prevista
                    })

        df_previsao = pd.DataFrame(resultados_previsao)

        df_comparacao = pd.merge(
            df_previsao,
            self.dados_vendas[['data_venda', 'filial', 'sku', 'quantidade_vendida_kg']],
            on=['data_venda', 'filial', 'sku'],
            how='left'
        )
        df_comparacao = df_comparacao.rename(columns={'quantidade_vendida_kg': 'demanda_real_kg'})
        df_comparacao['demanda_real_kg'] = df_comparacao['demanda_real_kg'].fillna(0)

        df_comparacao['erro_absoluto_kg'] = abs(df_comparacao['demanda_prevista_kg'] - df_comparacao['demanda_real_kg'])

        mae = mean_absolute_error(df_comparacao['demanda_real_kg'], df_comparacao['demanda_prevista_kg'])
        rmse = mean_squared_error(df_comparacao['demanda_real_kg'], df_comparacao['demanda_prevista_kg'], squared=False)

        print(f"\n--- Resultados da Previsão Histórica ---")
        print(f"MAE (Erro Médio Absoluto): {mae:.2f} kg")
        print(f"RMSE (Raiz do Erro Quadrático Médio): {rmse:.2f} kg")
        print(f"Número total de comparações: {len(df_comparacao)}")

        self._gerar_relatorio(df_comparacao, "comparacao_previsao_historica")

        return df_comparacao

    def _gerar_relatorio(self, df_relatorio, sufixo):
        data_geracao = datetime.now().strftime('%Y%m%d_%H%M%S')
        os.makedirs('relatorios', exist_ok=True)
        nome_arquivo = f'relatorios/relatorio_{sufixo}_{data_geracao}.xlsx'
        if 'Qtd Necessária para Descongelar HOJE (kg)' in df_relatorio.columns:
            df_relatorio = df_relatorio.sort_values(by=['Qtd Necessária para Descongelar HOJE (kg)', 'SKU'],
            ascending=[False, True])
        elif 'erro_absoluto_kg' in df_relatorio.columns:
            df_relatorio = df_relatorio.sort_values(by=['erro_absoluto_kg'], ascending=False)
        else:
            print(f"Aviso: Coluna 'Qtd Necessária para Descongelar HOJE (kg)' não encontrada no relatório '{sufixo}'. Ordenação padrão será aplicada.")
            df_relatorio = df_relatorio.sort_values(by=['SKU'], ascending=[True])

        df_relatorio.to_excel(nome_arquivo, index=False)
        print(f"Relatório de {sufixo} gerado: {nome_arquivo}")

    def gerar_relatorio_planejamento_diario(self, current_day):
        if not self.modelo:
            print("Modelo não treinado para gerar relatório de planejamento diário.")
            return None

        data_base = datetime(current_day.year, current_day.month, current_day.day)
        previsoes_futuras = self.prever_demanda_futura(data_base, n_dias=3)

        relatorio_data = []
        for (data_str, filial, sku), previsao_kg in previsoes_futuras.items():
            # A previsão é para D+1, D+2, D+3. A "demanda de amanhã" é a previsão para D+1.
            # O planejamento para descongelar HOJE é para atender a demanda de D+2 (2 dias à frente).
            # Se a previsão é para D+1, D+2, D+3...
            # Para o planejamento de hoje (para atender a demanda de daqui a 2 dias),
            # precisamos da previsão para data_base + timedelta(days=2).
            data_prevista_para_descongelar = data_base + timedelta(days=2) # Demanda de D+2

            if data_str == data_prevista_para_descongelar.strftime('%Y-%m-%d'):
                relatorio_data.append({
                    'SKU': sku,
                    'Filial': filial,
                    'Qtd Necessária para Descongelar HOJE (kg)': round(previsao_kg, 2)
                })

        if not relatorio_data:
            print("Nenhum planejamento diário gerado para a data.")
            return None

        df_relatorio = pd.DataFrame(relatorio_data)
        self._gerar_relatorio(df_relatorio, f"planejamento_diario_{data_base.strftime('%Y%m%d')}")
        return df_relatorio

    def log_event(self, event_type, details):
        timestamp = datetime.now()
        log_entry = {
            "timestamp": timestamp,
            "type": event_type,
            **details
        }
        if event_type == "movimentacao":
            self.registros_movimentacao.append(log_entry)
        elif event_type == "abastecimento":
            self.registros_abastecimento.append(log_entry)
        # print(f"Evento logado: {event_type} - {details}") # Opcional: imprimir no console

    def gerar_relatorio_consolidado_filial7(self):
        print("Gerando relatório consolidado para Filial 7...")
        # Simulação de dados para o relatório consolidado
        data_atual_simulada = datetime.now() # Use a data real para o relatório de fechamento

        # Exemplo de dados para o relatório - você precisaria buscar dos processos reais
        # ou consolidar os logs de abastecimento/movimentação por filial
        relatorio_data = []
        # Supondo que você tem uma forma de acessar o peso no balcão e na estante
        # de todos os processos da Filial 7 no final do dia
        # Este é um exemplo, você precisaria adaptar para seus dados reais
        for filial, sku_data in self.estoque.items(): # Isso aqui é apenas um exemplo
            if filial == "Filial 7": # Filtrar pela Filial 7
                for sku, quantidade_total in sku_data.items():
                    # Buscar o consumo real da filial 7 para este SKU para o dia
                    consumo_dia = sum(
                        rec['quantidade_vendida'] for rec in self.registros_abastecimento
                        if rec['filial'] == filial and rec['sku'] == sku and
                        rec['timestamp'].date() == data_atual_simulada.date()
                        and rec['tipo'] == 'retirada' # Se você tiver um tipo para retirada/venda
                    )
                    relatorio_data.append({
                        "Data": data_atual_simulada.strftime('%Y-%m-%d'),
                        "Filial": filial,
                        "SKU": sku,
                        "Estoque Final (kg)": round(quantidade_total, 2), # Exemplo
                        "Consumo do Dia (kg)": round(consumo_dia, 2)
                    })

        # No seu sistema, você já tem 'generated_processes' no Frango_app.py.
        # Seria melhor passar os dados relevantes para o SistemaGALO ou buscar diretamente aqui.
        # Por simplicidade, vou usar um exemplo mais genérico baseado nos logs
        # Se registros_abastecimento contém entradas de "compra" (retirada do balcão)

        df_consolidado = pd.DataFrame()
        if self.registros_abastecimento: # Usar registros de abastecimento/venda se disponíveis
            df_abastecimento = pd.DataFrame(self.registros_abastecimento)
            df_abastecimento['data'] = df_abastecimento['timestamp'].dt.date

            # Exemplo: Consumo do dia para Filial 7
            consumo_filial_7_dia = df_abastecimento[
                (df_abastecimento['filial'] == 'Filial 7') &
                (df_abastecimento['data'] == data_atual_simulada.date())
            ]
            # Assumindo que 'quantidade_movimentada' nos registros de abastecimento é o consumo
            consumo_total_dia_filial7 = consumo_filial_7_dia.groupby('sku')['quantidade_movimentada'].sum().reset_index()
            consumo_total_dia_filial7.rename(columns={'quantidade_movimentada': 'Consumo do Dia (kg)'}, inplace=True)


            # Estoque final para Filial 7 (isso é mais complexo, depende do estado atual dos processos)
            # Para simulação, você pode pegar o 'peso_no_balcao' e 'quantidade_kg' dos processos ativos da Filial 7
            # Como SistemaGALO não tem acesso direto a 'generated_processes', seria preciso passar como argumento ou buscar.
            # Por enquanto, deixarei um placeholder ou usarei um exemplo simplificado.
            # Se você persistir o estoque final diariamente, seria mais fácil.

            # Para um relatório simples:
            # Pegar todos os SKUs da Filial 7 que tiveram movimentação ou venda hoje
            all_skus_filial7 = pd.concat([
                consumo_total_dia_filial7['sku']
            ]).unique()

            final_data = []
            for sku in all_skus_filial7:
                consumo = consumo_total_dia_filial7[consumo_total_dia_filial7['sku'] == sku]['Consumo do Dia (kg)'].iloc[0] if sku in consumo_total_dia_filial7['sku'].values else 0
                # Estoque final é difícil de determinar aqui sem acesso direto aos processos do Frango_app.py
                # Para este relatório, vamos assumir 0, ou uma lógica de placeholder
                estoque_final = 0 # Placeholder: precisa vir do estado real dos processos
                final_data.append({
                    "Data": data_atual_simulada.strftime('%Y-%m-%d'),
                    "Filial": "Filial 7",
                    "SKU": sku,
                    "Estoque Final (kg)": estoque_final,
                    "Consumo do Dia (kg)": round(consumo, 2)
                })
            df_consolidado = pd.DataFrame(final_data)

        if not df_consolidado.empty:
            self._gerar_relatorio(df_consolidado, f"consolidado_filial7_{data_atual_simulada.strftime('%Y%m%d')}")
        else:
            print("Não há dados para gerar o relatório consolidado da Filial 7.")

        return df_consolidado # Retorna o DataFrame, mesmo que vazio

    def gerar_relatorio_abastecimento(self):
        if not self.registros_abastecimento:
            print("Não há registros de abastecimento para gerar relatório.")
            return None

        df_abastecimento = pd.DataFrame(self.registros_abastecimento)
        df_abastecimento['data'] = df_abastecimento['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        df_abastecimento = df_abastecimento.sort_values(by=['data', 'filial', 'sku'])

        self._gerar_relatorio(df_abastecimento, "abastecimento")
        return df_abastecimento

    def gerar_relatorio_movimentacao(self):
        if not self.registros_movimentacao:
            print("Não há registros de movimentação para gerar relatório.")
            return

        df_movimentacao = pd.DataFrame(self.registros_movimentacao)
        df_movimentacao['data'] = df_movimentacao['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        df_movimentacao = df_movimentacao.sort_values(by=['data', 'origem', 'sku'])

        self._gerar_relatorio(df_movimentacao, "movimentacao")
        return df_movimentacao
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor
import joblib
import os

from sklearn.metrics import mean_absolute_error, mean_squared_error

# Eventos sazonais
EVENTOS_SAZONAIS = {
    'Carnaval': {'datas': [datetime(2024, 2, 12), datetime(2024, 2, 13), datetime(2025, 3, 3), datetime(2025, 3, 4)], 'antecedencia_dias': 7},
    'Pascoa': {'datas': [datetime(2024, 3, 31), datetime(2025, 4, 20)], 'antecedencia_dias': 7},
    'Dia das Maes': {'datas': [datetime(2024, 5, 12), datetime(2025, 5, 11)], 'antecedencia_dias': 10},
    'Black Friday': {'datas': [datetime(2024, 11, 29), datetime(2025, 11, 28)], 'antecedencia_dias': 7},
    'Natal': {'datas': [datetime(2024, 12, 25), datetime(2025, 12, 25)], 'antecedencia_dias': 15},
    'Ano Novo': {'datas': [datetime(2024, 1, 1), datetime(2025, 1, 1), datetime(2026, 1, 1)], 'antecedencia_dias': 7},
    'Tiradentes': {'datas': [datetime(y, 4, 21) for y in range(2023, 2026)], 'antecedencia_dias': 3},
    'Dia do Trabalho': {'datas': [datetime(y, 5, 1) for y in range(2023, 2026)], 'antecedencia_dias': 3},
    'Corpus Christi': {'datas': [datetime(2024, 5, 30), datetime(2025, 6, 19)], 'antecedencia_dias': 3},
    'Independencia Brasil': {'datas': [datetime(y, 9, 7) for y in range(2023, 2026)], 'antecedencia_dias': 3},
    'Nossa Senhora Aparecida': {'datas': [datetime(y, 10, 12) for y in range(2023, 2026)], 'antecedencia_dias': 3},
    'Finados': {'datas': [datetime(y, 11, 2) for y in range(2023, 2026)], 'antecedencia_dias': 3},
    'Proclamacao Republica': {'datas': [datetime(y, 11, 15) for y in range(2023, 2026)], 'antecedencia_dias': 3},
}

class PrevisorDemanda:
    def __init__(self, script_dir):
        self.dados_vendas = None
        self.modelo = None
        self.script_dir = script_dir

    def carregar_dados_vendas(self, filepath):
        self.dados_vendas = pd.read_csv(filepath, sep=';', encoding='latin1')
        self.dados_vendas.columns = self.dados_vendas.columns.str.strip().str.lower()
        self.dados_vendas['data_dia'] = pd.to_datetime(self.dados_vendas['data_dia'], dayfirst=True, errors='coerce')
        self.dados_vendas.rename(columns={'id_produto': 'sku'}, inplace=True)
        self.dados_vendas = self.dados_vendas.sort_values(by='data_dia').reset_index(drop=True)

        N_DIAS = 180  # Use apenas os últimos 180 dias
        if len(self.dados_vendas) > N_DIAS:
            self.dados_vendas = self.dados_vendas.iloc[-N_DIAS:]

    def preparar_features(self):
        df = self.dados_vendas.copy()
        df['dia_semana'] = df['data_dia'].dt.weekday
        df['mes'] = df['data_dia'].dt.month
        df['trimestre'] = df['data_dia'].dt.quarter

        # Sazonalidade e pagamento
        for evento, info in EVENTOS_SAZONAIS.items():
            col_name = f'eh_{evento.lower().replace(" ", "_")}_prox'
            df[col_name] = df['data_dia'].apply(
                lambda d: int(any((data_evento - timedelta(days=info['antecedencia_dias']) <= d <= data_evento) for data_evento in info['datas']))
            )
        df['eh_pagamento_prox'] = df['data_dia'].apply(lambda d: int((1 <= d.day <= 5) or (d.day >= 25)))

        # Médias móveis
        for sku in df['sku'].unique():
            mask = df['sku'] == sku
            df.loc[mask, 'media_7d'] = df.loc[mask, 'total_venda_dia_kg'].rolling(7, min_periods=1).mean()
            df.loc[mask, 'media_14d'] = df.loc[mask, 'total_venda_dia_kg'].rolling(14, min_periods=1).mean()
        df['media_7d'] = df['media_7d'].fillna(0.0)
        df['media_14d'] = df['media_14d'].fillna(0.0)
        df = pd.get_dummies(df, columns=['sku'], prefix='sku')
        self.dados_vendas = df

    def treinar_modelo(self):
        sku_cols = [col for col in self.dados_vendas.columns if col.startswith('sku_')]
        features = [
            'dia_semana', 'mes', 'trimestre', 'media_7d', 'media_14d'
        ] + sku_cols + [f'eh_{e.lower().replace(" ", "_")}_prox' for e in EVENTOS_SAZONAIS] + ['eh_pagamento_prox']
        dados_para_treino = self.dados_vendas.dropna(subset=features + ['total_venda_dia_kg'])
        X = dados_para_treino[features]
        y = dados_para_treino['total_venda_dia_kg']
        self.modelo = RandomForestRegressor(n_estimators=150, max_depth=8, random_state=42, n_jobs=-1)
        self.modelo.fit(X, y)
        joblib.dump(self.modelo, os.path.join(self.script_dir, 'modelo_demanda.pkl'))

        y_pred = self.modelo.predict(X)
        mae = mean_absolute_error(y, y_pred)
        rmse = np.sqrt(mean_squared_error(y, y_pred))
        mape = np.mean(np.abs((y - y_pred) / y[y != 0])) * 100

        print(f"MAE: {mae:.2f}")
        print(f"RMSE: {rmse:.2f}")
        print(f"MAPE: {mape:.2f}%")

    def carregar_modelo(self):
        self.modelo = joblib.load(os.path.join(self.script_dir, 'modelo_demanda.pkl'))

    def prever_demanda(self, data_hoje, sku, valor_real=None):
        data_previsao = data_hoje + timedelta(days=2)
        dados_sku = self.dados_vendas[[col for col in self.dados_vendas.columns if not col.startswith('sku_')]]
        media_7d = 0.0
        media_14d = 0.0
        sku_col_name = f'sku_{sku}'
        if sku_col_name in self.dados_vendas.columns:
            mask = self.dados_vendas[sku_col_name] == 1
            dados_sku = self.dados_vendas[mask & (self.dados_vendas['data_dia'] < data_previsao)].sort_values(by='data_dia')
            media_7d = dados_sku['total_venda_dia_kg'].tail(7).mean() if not dados_sku.empty else 0.0
            media_14d = dados_sku['total_venda_dia_kg'].tail(14).mean() if not dados_sku.empty else 0.0

        valor_minimo = 10.0
        historico_suficiente = len(dados_sku) >= 7

        sazonalidade_features = {}
        for evento, info in EVENTOS_SAZONAIS.items():
            col_name = f'eh_{evento.lower().replace(" ", "_")}_prox'
            sazonalidade_features[col_name] = int(any(
                (data_evento - timedelta(days=info['antecedencia_dias']) <= data_previsao <= data_evento)
                for data_evento in info['datas']
            ))
        sazonalidade_features['eh_pagamento_prox'] = int((1 <= data_previsao.day <= 5) or (data_previsao.day >= 25))

        sku_cols = [col for col in self.dados_vendas.columns if col.startswith('sku_')]
        sku_features = {col: 0 for col in sku_cols}
        if sku_col_name in sku_features:
            sku_features[sku_col_name] = 1

        features_data = {
            'dia_semana': data_previsao.weekday(),
            'mes': data_previsao.month,
            'trimestre': (data_previsao.month - 1) // 3 + 1,
            'media_7d': media_7d,
            'media_14d': media_14d,
            **sku_features,
            **sazonalidade_features
        }
        features_treinamento = [
            'dia_semana', 'mes', 'trimestre', 'media_7d', 'media_14d'
        ] + sku_cols + [f'eh_{e.lower().replace(" ", "_")}_prox' for e in EVENTOS_SAZONAIS] + ['eh_pagamento_prox']
        X_prever = pd.DataFrame([features_data])[features_treinamento]
        if self.modelo is None:
            self.carregar_modelo()
        pred = self.modelo.predict(X_prever)[0]

        if not historico_suficiente:
            pred = max(pred, valor_minimo)

        # ✅ Mostrar as métricas se valor real for fornecido
        if valor_real is not None and valor_real > 0:
            mae = abs(valor_real - pred)
            rmse = np.sqrt((valor_real - pred) ** 2)
            mape = abs((valor_real - pred) / valor_real) * 100
            print(f"[{sku}] MAE: {mae:.2f} | RMSE: {rmse:.2f} | MAPE: {mape:.2f}%")

        return max(0, round(pred, 2))
    
if __name__ == "__main__":
    previsor = PrevisorDemanda(script_dir='.')
    previsor.carregar_dados_vendas('dados_vendas.csv')
    previsor.preparar_features()
    previsor.treinar_modelo()  # Aqui está o print das métricas!

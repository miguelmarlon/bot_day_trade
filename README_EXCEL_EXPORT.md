# 📊 Sistema de Exportação para Excel

## Visão Geral

O bot agora possui um sistema completo de exportação de dados para planilhas Excel, permitindo acompanhar todas as operações e o desempenho do sistema de forma organizada e visual.

## Funcionalidades

### 1. **Histórico de Operações** (`historico_operacoes.xlsx`)
Exporta automaticamente todas as operações fechadas com os seguintes dados:
- Trade ID
- Criptomoeda
- Data/Hora de Entrada e Saída
- Preço de Entrada e Saída
- Valor Investido
- Lucro Líquido (USD)
- Retorno (%)
- Duração da operação
- Motivo do fechamento (Stop Loss, Take Profit, Trailing Stop)
- Stop Loss Inicial
- Maior Preço Atingido
- Status

**Formatação automática:**
- ✅ Células verdes para lucros
- ❌ Células vermelhas para prejuízos
- Cabeçalhos formatados e destacados
- Colunas ajustadas automaticamente

### 2. **Monitoramento de Risco** (`monitoramento_risco.xlsx`)
Registra periodicamente o estado das posições abertas:
- Timestamp
- Símbolo
- Side (Long/Short)
- Preço de Entrada e Atual
- PNL (% e USD)
- Stop Loss e Take Profit atuais
- Maior Preço atingido
- Status do Trailing Stop
- Duração
- Status da posição

### 3. **Resumo Diário** (`resumo_diario.xlsx`)
Gera estatísticas agregadas por dia:
- Total de Trades
- Lucro Total (USD)
- Retorno Médio (%)
- Capital Investido
- Taxa de Sucesso (%)

## Como Usar

### Exportação Automática

O sistema exporta automaticamente quando:

1. **Uma operação é fechada** (Stop Loss, Take Profit ou Trailing Stop)
   - Os dados são salvos imediatamente em `outputs/historico_operacoes.xlsx`

2. **O monitor de risco executa** (a cada 1 minuto)
   - Dados de monitoramento são salvos em `outputs/monitoramento_risco.xlsx`

### Exportação Manual

#### 1. Exportar trades do JSON

```python
from scripts.excel_exporter import ExcelExporter

exporter = ExcelExporter()
exporter.export_trades_from_json("logs/trades_principais_em_andamento.json")
```

#### 2. Exportar uma operação específica

```python
from scripts.excel_exporter import export_closed_trade

trade_data = {
    'trade_id': 'BTCUSDT_20250106120000',
    'cripto': 'BTCUSDT',
    'timestamp_entrada': '2025-01-06 12:00:00',
    'preco_entrada': 45000.0,
    'preco_saida': 46000.0,
    'valor_investido': 100,
    'lucro_liquido': 2.22,
    'retorno_percentual': 0.0222,
    'duracao': '2:30:00',
    'saida_por': 'Take Profit',
    'status': 'CONCLUIDO'
}

export_closed_trade(trade_data)
```

#### 3. Gerar resumo diário

```python
from scripts.excel_exporter import generate_daily_summary

generate_daily_summary()
```

#### 4. Exportar dados de monitoramento

```python
from scripts.excel_exporter import export_risk_monitor_data

monitoring_data = {
    'symbol': 'BTCUSDT',
    'side': 'long',
    'entry_price': 45000.0,
    'current_price': 45500.0,
    'pnl_percentage': 0.0111,
    'unrealized_pnl': 1.11,
    'current_stop_loss': 44500.0,
    'take_profit': 46800.0,
    'highest_price': 45800.0,
    'is_trailing_active': True,
    'duration_minutes': 30,
    'status': 'MONITORANDO'
}

export_risk_monitor_data(monitoring_data)
```

## Estrutura dos Arquivos

```
outputs/
├── historico_operacoes.xlsx    # Todas as operações concluídas
├── monitoramento_risco.xlsx    # Log de monitoramento
└── resumo_diario.xlsx           # Estatísticas diárias
```

## Requisitos

As seguintes bibliotecas Python são necessárias:

```bash
pip install pandas openpyxl
```

Já incluídas no `requirements.txt` do projeto.

## Integração no Código

### No Gerenciamento de Risco

O arquivo `scripts/gerenciamento_risco_assin.py` já está integrado:

```python
# Quando uma posição é fechada por Stop Loss ou Take Profit
self._export_trade_to_excel(
    symbol=symbol,
    entry_price=entry_price,
    exit_price=current_price,
    pnl=pnl,
    percentage=percentage,
    reason='Stop Loss',  # ou 'Take Profit' ou 'Trailing Stop'
    entry_time=entry_time
)
```

### No Monitor de Risco

O arquivo `scripts/monitor_risk.py` já está integrado:

```python
# Exporta dados de monitoramento periodicamente
export_risk_data = _get_excel_exporter()
if export_risk_data is not None:
    monitoring_data = {...}
    export_risk_data(monitoring_data)
```

## Personalização

### Alterar Diretório de Saída

```python
exporter = ExcelExporter(outputs_dir='meu_diretorio')
```

### Alterar Nome dos Arquivos

```python
exporter.export_trade_closed(trade_data, filename="minhas_operacoes.xlsx")
```

### Limitar Registros de Monitoramento

Por padrão, mantém os últimos 1000 registros. Para alterar, edite o arquivo `scripts/excel_exporter.py`:

```python
# Linha ~350
if len(df_combined) > 5000:  # Altere o valor aqui
    df_combined = df_combined.tail(5000)
```

## Análise de Dados

### Abrir no Excel

Simplesmente abra os arquivos `.xlsx` no Microsoft Excel, LibreOffice Calc ou Google Sheets.

### Análise Programática com Pandas

```python
import pandas as pd

# Carregar histórico
df = pd.read_excel('outputs/historico_operacoes.xlsx')

# Estatísticas gerais
print(f"Total de operações: {len(df)}")
print(f"Lucro total: ${df['Lucro Líquido (USD)'].sum():.2f}")
print(f"Taxa de sucesso: {(df['Lucro Líquido (USD)'] > 0).mean() * 100:.2f}%")
print(f"Retorno médio: {df['Retorno (%)'].mean():.2f}%")

# Melhores trades
top_trades = df.nlargest(10, 'Lucro Líquido (USD)')
print("\nTop 10 operações:")
print(top_trades[['Criptomoeda', 'Lucro Líquido (USD)', 'Retorno (%)']])
```

## Troubleshooting

### Erro: "Excel Exporter não disponível"

Instale as dependências:
```bash
pip install pandas openpyxl
```

### Arquivo Excel corrompido

Delete o arquivo e o bot criará um novo:
```bash
rm outputs/historico_operacoes.xlsx
```

### Arquivo muito grande

O arquivo de monitoramento é limitado a 1000 registros por padrão. Se ainda assim ficar grande:
1. Faça backup do arquivo
2. Delete o original
3. O bot criará um novo

## Backup Automático

Recomenda-se fazer backup periódico dos arquivos Excel:

```bash
# Linux/Mac
cp -r outputs/ backups/$(date +%Y%m%d)_outputs/

# Windows (PowerShell)
Copy-Item -Path outputs\ -Destination backups\$(Get-Date -Format 'yyyyMMdd')_outputs\ -Recurse
```

## Roadmap

Próximas funcionalidades planejadas:
- [ ] Dashboard visual com gráficos
- [ ] Exportação para Google Sheets automática
- [ ] Alertas por email com resumos
- [ ] Comparação de desempenho entre períodos
- [ ] Análise de correlação entre ativos

## Suporte

Para dúvidas ou problemas, consulte a documentação principal do projeto ou abra uma issue no repositório.

# 🧪 Guia: Como usar a Binance Testnet

## 📋 Passo 1: Obter credenciais da Testnet

1. Acesse: https://testnet.binancefuture.com/
2. Faça login (pode usar GitHub ou Google)
3. Clique em "API Key" no menu superior
4. Crie uma nova API Key
5. Copie a **API Key** e o **Secret Key**

⚠️ **IMPORTANTE**: As chaves da testnet são DIFERENTES das chaves de produção!

---

## 📝 Passo 2: Adicionar credenciais no .env

Abra seu arquivo `.env` e adicione as seguintes linhas:

```env
# Binance Testnet (para testes sem dinheiro real)
BINANCE_TESTNET_API_KEY=sua_chave_testnet_aqui
BINANCE_TESTNET_SECRET_KEY=seu_secret_testnet_aqui

# Binance Produção (já existente)
BINANCE_API_KEY=sua_chave_real_aqui
BINANCE_SECRET_KEY=seu_secret_real_aqui
```

---

## 🚀 Passo 3: Como usar no código

### **Testnet (Simulação - sem dinheiro real)**

```python
from utils.binance_client import BinanceHandler

# Modo TESTNET
handler = await BinanceHandler.create(testnet=True)
```

### **Produção (Real - com dinheiro real)**

```python
from utils.binance_client import BinanceHandler

# Modo PRODUÇÃO (padrão)
handler = await BinanceHandler.create()
# ou explicitamente:
handler = await BinanceHandler.create(testnet=False)
```

---

## 🧪 Passo 4: Executar testes

Execute o script de teste:

```bash
python test_binance_testnet.py
```

Você verá mensagens como:
```
🧪 Modo TESTNET ativado - Nenhuma ordem real será executada!
✅ Candles obtidos: 5 registros
✅ Preço do BTC: $67850.50
```

---

## 💡 Exemplos práticos

### Exemplo 1: Testar estratégia sem risco

```python
import asyncio
from utils.binance_client import BinanceHandler

async def test_strategy():
    # Usa testnet para não gastar dinheiro real
    handler = await BinanceHandler.create(testnet=True)
    
    # Testa sua estratégia
    df = await handler.obter_dados_candles('BTC/USDT', '1h')
    # ... sua lógica de trading aqui ...
    
    await handler.close_connection()

asyncio.run(test_strategy())
```

### Exemplo 2: Alternar entre testnet e produção com variável

```python
import os
from utils.binance_client import BinanceHandler

async def main():
    # Define no .env: USE_TESTNET=True ou False
    use_testnet = os.getenv('USE_TESTNET', 'True') == 'True'
    
    handler = await BinanceHandler.create(testnet=use_testnet)
    
    if use_testnet:
        print("🧪 Rodando em modo TESTE")
    else:
        print("💰 Rodando em modo REAL - CUIDADO!")
    
    # ... seu código aqui ...
    await handler.close_connection()
```

### Exemplo 3: Integrar com suas estratégias

```python
# Em strategies/ma_slowStochastic_combo.py
async def trading_task_ma_slow_stochastic(context):
    try:
        # Use testnet=True durante desenvolvimento
        binance = await BinanceHandler.create(testnet=True)
        
        # ... sua estratégia aqui ...
        
    finally:
        await binance.close_connection()
```

---

## ⚠️ Diferenças importantes

| Aspecto | Testnet | Produção |
|---------|---------|----------|
| **Dinheiro** | Falso (virtual) | Real |
| **Risco** | Zero | Alto |
| **Preços** | Próximos aos reais | Reais |
| **Ordens** | Simuladas | Executadas |
| **Dados** | Disponíveis | Disponíveis |

---

## 🔧 Troubleshooting

### Erro: "Credenciais da testnet não encontradas"
✅ **Solução**: Adicione as variáveis no arquivo `.env`

### Erro: "Invalid API-key, IP, or permissions"
✅ **Solução**: 
1. Verifique se copiou as chaves corretas
2. Certifique-se de que a API Key tem permissões de "Futures"
3. Na testnet, não há restrições de IP

### Erro: "Connection refused"
✅ **Solução**: Verifique sua conexão com internet

---

## 📊 Funcionalidades disponíveis na Testnet

✅ Obter dados de candles (OHLCV)  
✅ Consultar preços  
✅ Consultar saldo (virtual)  
✅ Abrir posições (simuladas)  
✅ Fechar posições (simuladas)  
✅ Cancelar ordens  
✅ Testar estratégias  

❌ Não há dinheiro real envolvido  
❌ Não há ganhos ou perdas reais  

---

## 🎯 Recomendações

1. **Sempre teste primeiro na testnet** antes de usar em produção
2. **Use variáveis de ambiente** para alternar facilmente
3. **Documente** qual modo está usando
4. **Nunca commite** suas chaves de API no Git

---

## 🔐 Segurança

```python
# ✅ BOM - usando variável de ambiente
handler = await BinanceHandler.create(testnet=True)

# ❌ RUIM - hardcoded
handler = BinanceHandler(api_key="abc123", secret="xyz789")
```

---

## 📚 Links úteis

- Testnet Futures: https://testnet.binancefuture.com/
- Documentação CCXT: https://docs.ccxt.com/
- Binance API Docs: https://binance-docs.github.io/apidocs/futures/en/

---

**Pronto para testar!** 🚀

Execute `python test_binance_testnet.py` e comece a desenvolver sem riscos!

"""
Script de teste para validar a integração com a Binance Testnet.

Para usar:
1. Obtenha suas credenciais da testnet em: https://testnet.binancefuture.com/
2. Adicione no arquivo .env:
   BINANCE_TESTNET_API_KEY=sua_chave_testnet
   BINANCE_TESTNET_SECRET_KEY=seu_secret_testnet
3. Execute: python test_binance_testnet.py
"""

import asyncio
from utils.binance_client import BinanceHandler

async def test_testnet():
    """Testa funcionalidades básicas na testnet"""
    handler = None
    
    try:
        # Cria handler em modo TESTNET
        print("🧪 Criando conexão com Binance TESTNET...")
        handler = await BinanceHandler.create(testnet=True)
        
        # 1. Testa busca de dados de candles
        print("\n📊 Testando obtenção de candles...")
        df = await handler.obter_dados_candles('BTC/USDT', timeframe='1h', limit=5)
        if df is not None and not df.empty:
            print(f"✅ Candles obtidos: {len(df)} registros")
            print(df.head())
        else:
            print("❌ Falha ao obter candles")
        
        # 2. Testa busca de preço
        print("\n💰 Testando busca de preço...")
        price_data = await handler.get_price('BTC/USDT')
        if price_data:
            print(f"✅ Preço do BTC: ${price_data.get('price', 'N/A')}")
        else:
            print("❌ Falha ao obter preço")
        
        # 3. Testa busca de saldo
        print("\n💵 Testando busca de saldo...")
        balance = await handler.get_balance('USDT')
        if balance and 'error' not in balance:
            print(f"✅ Saldo USDT: {balance}")
        else:
            print(f"⚠️ Saldo: {balance}")
        
        # 4. Testa listagem de ativos por volume
        print("\n📈 Testando top ativos por volume...")
        volume_report = await handler.get_volume_report(quote_currency='USDT', limit=5)
        if volume_report is not None:
            print(f"✅ Top 5 ativos por volume:")
            print(volume_report)
        else:
            print("❌ Falha ao obter relatório de volume")
        
        print("\n✅ Todos os testes básicos concluídos!")
        print("⚠️ Lembre-se: Você está na TESTNET - nenhuma ordem real foi executada.")
        
    except Exception as e:
        print(f"\n❌ Erro durante os testes: {e}")
        import traceback
        print(traceback.format_exc())
        
    finally:
        if handler:
            await handler.close_connection()
            print("\n🔒 Conexão fechada com sucesso.")

async def test_production_vs_testnet():
    """Compara conexões de produção e testnet"""
    print("="*60)
    print("COMPARANDO PRODUÇÃO vs TESTNET")
    print("="*60)
    
    # Testnet
    print("\n🧪 TESTNET:")
    handler_test = await BinanceHandler.create(testnet=True)
    price_test = await handler_test.get_price('BTC/USDT')
    print(f"Preço BTC (Testnet): ${price_test.get('price', 'N/A')}")
    await handler_test.close_connection()
    
    # Produção
    print("\n💰 PRODUÇÃO:")
    handler_prod = await BinanceHandler.create(testnet=False)
    price_prod = await handler_prod.get_price('BTC/USDT')
    print(f"Preço BTC (Produção): ${price_prod.get('price', 'N/A')}")
    await handler_prod.close_connection()
    
    print("\n✅ Comparação concluída!")

if __name__ == "__main__":
    print("🚀 Iniciando testes da Binance Testnet...\n")
    
    # Descomente a função que deseja testar:
    
    # Teste básico completo
    asyncio.run(test_testnet())
    
    # Comparação entre produção e testnet
    # asyncio.run(test_production_vs_testnet())

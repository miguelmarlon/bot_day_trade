"""
Script de Diagnóstico para Erro 502 Bad Gateway da Binance Testnet

Este script analisa e testa conexões com a API da Binance Testnet
para identificar a causa do erro 502 Bad Gateway.

Possíveis Causas:
1. Testnet está fora do ar ou em manutenção
2. Rate limit atingido (muitas requisições)
3. Problemas de rede/firewall/proxy
4. URL da API incorreta ou endpoint inválido
5. Timeout nas requisições
6. Problemas com o servidor nginx da Binance
"""

import asyncio
import time
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import requests
import ccxt.pro as ccxtpro
from datetime import datetime
import json
from config import BINANCE_API_KEY_TESTNET, BINANCE_SECRET_KEY_TESTNET

# URLs da Binance
TESTNET_SPOT_URL = "https://testnet.binance.vision/api"
TESTNET_FUTURES_URL = "https://testnet.binancefuture.com/fapi"
PROD_SPOT_URL = "https://api.binance.com/api"

def print_separator(title):
    """Imprime separador visual"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def print_result(success, message):
    """Imprime resultado formatado"""
    icon = "✅" if success else "❌"
    print(f"{icon} {message}")

def test_basic_connectivity():
    """Testa conectividade básica com a internet"""
    print_separator("1. TESTE DE CONECTIVIDADE BÁSICA")
    
    test_urls = [
        ("Google", "https://www.google.com"),
        ("Binance Produção", "https://www.binance.com"),
        ("Binance API Produção", "https://api.binance.com"),
    ]
    
    for name, url in test_urls:
        try:
            response = requests.get(url, timeout=5)
            print_result(True, f"{name}: {response.status_code} ({response.elapsed.total_seconds():.2f}s)")
        except Exception as e:
            print_result(False, f"{name}: {str(e)[:100]}")

def test_testnet_endpoints():
    """Testa diferentes endpoints da testnet"""
    print_separator("2. TESTE DOS ENDPOINTS DA TESTNET")
    
    endpoints = [
        ("Spot - Ping", f"{TESTNET_SPOT_URL}/v3/ping"),
        ("Spot - Time", f"{TESTNET_SPOT_URL}/v3/time"),
        ("Spot - Exchange Info", f"{TESTNET_SPOT_URL}/v3/exchangeInfo"),
        ("Futures - Ping", f"{TESTNET_FUTURES_URL}/v1/ping"),
        ("Futures - Time", f"{TESTNET_FUTURES_URL}/v1/time"),
        ("Futures - Exchange Info", f"{TESTNET_FUTURES_URL}/v1/exchangeInfo"),
    ]
    
    for name, url in endpoints:
        try:
            start_time = time.time()
            response = requests.get(url, timeout=10)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                data_size = len(response.content)
                print_result(True, f"{name}: {response.status_code} ({elapsed:.2f}s, {data_size} bytes)")
            elif response.status_code == 502:
                print_result(False, f"{name}: 502 Bad Gateway - Testnet pode estar fora do ar!")
            else:
                print_result(False, f"{name}: {response.status_code} - {response.text[:100]}")
        except requests.exceptions.Timeout:
            print_result(False, f"{name}: Timeout após 10s")
        except Exception as e:
            print_result(False, f"{name}: {str(e)[:100]}")
        
        # Pequeno delay para evitar rate limit
        time.sleep(0.5)

def test_testnet_status():
    """Verifica o status geral da testnet"""
    print_separator("3. STATUS GERAL DA TESTNET")
    
    try:
        # Tenta pegar o tempo do servidor
        response = requests.get(f"{TESTNET_SPOT_URL}/v3/time", timeout=10)
        if response.status_code == 200:
            server_time = response.json()['serverTime']
            local_time = int(time.time() * 1000)
            diff = abs(server_time - local_time)
            
            print_result(True, f"Servidor está respondendo")
            print(f"  Tempo do servidor: {datetime.fromtimestamp(server_time/1000)}")
            print(f"  Tempo local: {datetime.fromtimestamp(local_time/1000)}")
            print(f"  Diferença: {diff}ms")
            
            if diff > 5000:
                print("  ⚠️ AVISO: Diferença de tempo > 5s pode causar problemas")
        else:
            print_result(False, f"Status {response.status_code}: Testnet pode estar indisponível")
    except Exception as e:
        print_result(False, f"Testnet não está respondendo: {str(e)[:100]}")

def test_rate_limits():
    """Testa e mostra informações sobre rate limits"""
    print_separator("4. TESTE DE RATE LIMITS")
    
    print("Fazendo 5 requisições consecutivas para testar rate limit...")
    
    for i in range(5):
        try:
            start_time = time.time()
            response = requests.get(f"{TESTNET_SPOT_URL}/v3/time", timeout=5)
            elapsed = time.time() - start_time
            
            # Extrai headers de rate limit
            weight = response.headers.get('X-MBX-USED-WEIGHT-1M', 'N/A')
            
            if response.status_code == 200:
                print_result(True, f"Requisição {i+1}: {response.status_code} ({elapsed:.2f}s) - Weight usado: {weight}")
            elif response.status_code == 418 or response.status_code == 429:
                print_result(False, f"Requisição {i+1}: RATE LIMIT ATINGIDO!")
                break
            else:
                print_result(False, f"Requisição {i+1}: {response.status_code}")
        except Exception as e:
            print_result(False, f"Requisição {i+1}: {str(e)[:100]}")
        
        time.sleep(0.2)  # 200ms entre requisições

def test_with_ccxt():
    """Testa usando a biblioteca CCXT"""
    print_separator("5. TESTE COM CCXT (Biblioteca do Bot)")
    
    try:
        print("Inicializando exchange CCXT...")
        exchange = ccxtpro.binance({
            'apiKey': BINANCE_API_KEY_TESTNET,
            'secret': BINANCE_SECRET_KEY_TESTNET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'testnet': True,
            }
        })
        
        print_result(True, "Exchange CCXT inicializado")
        print(f"  URLs configuradas:")
        print(f"    - Base: {exchange.urls.get('api', {}).get('public', 'N/A')}")
        print(f"    - Test: {exchange.urls.get('test', 'N/A')}")
        
    except Exception as e:
        print_result(False, f"Erro ao inicializar CCXT: {str(e)[:200]}")

async def test_async_fetch():
    """Testa fetches assíncronos (como o bot faz)"""
    print_separator("6. TESTE DE FETCH ASSÍNCRONO (Simulando Bot)")
    
    try:
        exchange = ccxtpro.binance({
            'apiKey': BINANCE_API_KEY_TESTNET,
            'secret': BINANCE_SECRET_KEY_TESTNET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'testnet': True,
            }
        })
        
        symbols_to_test = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
        
        for symbol in symbols_to_test:
            try:
                print(f"\nTestando {symbol}...")
                
                # Tenta buscar ticker (similar ao que o bot faz)
                start_time = time.time()
                ticker = await exchange.fetch_ticker(symbol)
                elapsed = time.time() - start_time
                
                print_result(True, f"{symbol}: Preço ${ticker['last']} ({elapsed:.2f}s)")
                
                # Pequeno delay
                await asyncio.sleep(0.5)
                
            except Exception as e:
                error_msg = str(e)
                if '502' in error_msg:
                    print_result(False, f"{symbol}: ERRO 502 Bad Gateway!")
                elif 'timeout' in error_msg.lower():
                    print_result(False, f"{symbol}: Timeout!")
                else:
                    print_result(False, f"{symbol}: {error_msg[:150]}")
        
        await exchange.close()
        
    except Exception as e:
        print_result(False, f"Erro no teste assíncrono: {str(e)[:200]}")

def check_common_issues():
    """Verifica problemas comuns"""
    print_separator("7. VERIFICAÇÃO DE PROBLEMAS COMUNS")
    
    issues = []
    
    # 1. Verifica se as credenciais estão configuradas
    if not BINANCE_API_KEY_TESTNET or BINANCE_API_KEY_TESTNET == "":
        issues.append("❌ API Key da testnet não configurada")
    else:
        print_result(True, f"API Key configurada (primeiros 10 chars): {BINANCE_API_KEY_TESTNET[:10]}...")
    
    if not BINANCE_SECRET_KEY_TESTNET or BINANCE_SECRET_KEY_TESTNET == "":
        issues.append("❌ Secret Key da testnet não configurada")
    else:
        print_result(True, "Secret Key configurada")
    
    # 2. Verifica tempo do sistema
    local_time = datetime.now()
    print_result(True, f"Hora local do sistema: {local_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 3. Verifica versões
    try:
        import ccxt
        print_result(True, f"Versão do CCXT: {ccxt.__version__}")
    except:
        issues.append("❌ Erro ao verificar versão do CCXT")
    
    if issues:
        print("\n⚠️ Problemas encontrados:")
        for issue in issues:
            print(f"  {issue}")

def get_recommendations():
    """Fornece recomendações baseadas nos testes"""
    print_separator("8. RECOMENDAÇÕES")
    
    print("""
📋 Possíveis Causas do Erro 502 Bad Gateway:

1️⃣ TESTNET FORA DO AR OU EM MANUTENÇÃO
   ➤ A testnet da Binance frequentemente fica instável
   ➤ Pode estar em manutenção programada ou não programada
   ➤ Solução: Aguardar ou usar API de produção
   
2️⃣ RATE LIMIT ATINGIDO
   ➤ Muitas requisições em curto período
   ➤ Solução: Aumentar delays entre requisições
   ➤ Usar 'enableRateLimit': True no CCXT
   
3️⃣ ENDPOINT INCORRETO OU DESCONTINUADO
   ➤ Verificar se está usando URLs corretas
   ➤ Testnet Spot: https://testnet.binance.vision/api
   ➤ Testnet Futures: https://testnet.binancefuture.com/fapi
   
4️⃣ TIMEOUT NAS REQUISIÇÕES
   ➤ Testnet pode estar lenta
   ➤ Solução: Aumentar timeout para 30-60s
   
5️⃣ PROBLEMAS DE REDE/FIREWALL
   ➤ Verificar firewall/antivírus
   ➤ Testar com VPN ou outra rede

🔧 SOLUÇÕES RECOMENDADAS:

A) TEMPORÁRIA - Usar API de Produção:
   - Trocar 'testnet': True para 'testnet': False
   - CUIDADO: Vai usar dinheiro real!
   
B) IMPLEMENTAR RETRY COM BACKOFF:
   - Já implementado no bot (visto no log: "tentativa 2/3")
   - Pode aumentar tentativas e delays
   
C) VERIFICAR STATUS DA TESTNET:
   - Acessar: https://testnet.binancefuture.com
   - Ver se o site carrega
   
D) MONITORAR HORÁRIOS:
   - Testnet pode ter horários de menor uso
   - Testar em diferentes horários do dia

E) REDUZIR FREQUÊNCIA DE POLLING:
   - Se o bot faz muitas requisições por segundo
   - Aumentar intervalo entre verificações
""")

def save_diagnostic_report():
    """Salva relatório de diagnóstico"""
    print_separator("9. SALVANDO RELATÓRIO")
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'testnet_spot_url': TESTNET_SPOT_URL,
        'testnet_futures_url': TESTNET_FUTURES_URL,
        'api_key_configured': bool(BINANCE_API_KEY_TESTNET),
        'secret_key_configured': bool(BINANCE_SECRET_KEY_TESTNET),
    }
    
    report_file = Path(__file__).parent / 'diagnostic_report_502.json'
    
    try:
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        print_result(True, f"Relatório salvo em: {report_file}")
    except Exception as e:
        print_result(False, f"Erro ao salvar relatório: {e}")

async def main():
    """Executa todos os testes"""
    print("\n" + "🔍 DIAGNÓSTICO DE ERRO 502 BAD GATEWAY - BINANCE TESTNET".center(70))
    print("=" * 70)
    print(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Executa testes síncronos
    test_basic_connectivity()
    test_testnet_endpoints()
    test_testnet_status()
    test_rate_limits()
    test_with_ccxt()
    check_common_issues()
    
    # Executa testes assíncronos
    await test_async_fetch()
    
    # Recomendações e relatório
    get_recommendations()
    save_diagnostic_report()
    
    print("\n" + "="*70)
    print("✅ DIAGNÓSTICO CONCLUÍDO".center(70))
    print("="*70)
    print()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Diagnóstico interrompido pelo usuário")
    except Exception as e:
        print(f"\n\n❌ Erro crítico durante diagnóstico: {e}")
        import traceback
        traceback.print_exc()

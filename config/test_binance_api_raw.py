"""
Teste RAW da API da Binance Testnet - SEM USAR CCXT
Faz requisições HTTP diretas para validar se as credenciais funcionam
"""

import os
import time
import hmac
import hashlib
import requests
from dotenv import load_dotenv
from urllib.parse import urlencode

# Carrega variáveis do .env
load_dotenv()

# URLs da Binance Testnet
BASE_URL = "https://testnet.binancefuture.com"
API_KEY = os.getenv("BINANCE_TESTNET_API_KEY")
SECRET_KEY = os.getenv("BINANCE_TESTNET_SECRET_KEY")


def print_separator(title=""):
    """Imprime um separador visual"""
    print("\n" + "=" * 80)
    if title:
        print(f"  {title}")
        print("=" * 80)


def generate_signature(query_string: str, secret_key: str) -> str:
    """
    Gera a assinatura HMAC SHA256 necessária para autenticação.
    
    Args:
        query_string: String de parâmetros da query (ex: 'symbol=BTCUSDT&timestamp=123456')
        secret_key: Chave secreta da API
    
    Returns:
        Assinatura em hexadecimal
    """
    return hmac.new(
        secret_key.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def test_1_verificar_credenciais():
    """Teste 1: Verifica se as credenciais estão carregadas corretamente"""
    print_separator("TESTE 1: Verificando Credenciais")
    
    print(f"\n📋 Variáveis de Ambiente:")
    print(f"   • BINANCE_TESTNET_API_KEY: {'✅ Definida' if API_KEY else '❌ NÃO ENCONTRADA'}")
    print(f"   • BINANCE_TESTNET_SECRET_KEY: {'✅ Definida' if SECRET_KEY else '❌ NÃO ENCONTRADA'}")
    
    if API_KEY:
        print(f"\n🔑 API Key (primeiros/últimos 10 caracteres):")
        print(f"   {API_KEY[:10]}...{API_KEY[-10:]}")
        print(f"   Comprimento: {len(API_KEY)} caracteres")
    
    if SECRET_KEY:
        print(f"\n🔐 Secret Key (primeiros/últimos 10 caracteres):")
        print(f"   {SECRET_KEY[:10]}...{SECRET_KEY[-10:]}")
        print(f"   Comprimento: {len(SECRET_KEY)} caracteres")
    
    if not API_KEY or not SECRET_KEY:
        print("\n❌ ERRO: Credenciais não encontradas no arquivo .env")
        print("   Certifique-se de ter adicionado:")
        print("   BINANCE_TESTNET_API_KEY=sua_chave")
        print("   BINANCE_TESTNET_SECRET_KEY=seu_secret")
        return False
    
    print("\n✅ Credenciais carregadas com sucesso!")
    return True


def test_2_endpoint_publico():
    """Teste 2: Testa um endpoint público (não requer autenticação)"""
    print_separator("TESTE 2: Endpoint Público (Sem Autenticação)")
    
    print(f"\n🌐 Testando conexão com: {BASE_URL}")
    print("📡 Endpoint: /fapi/v1/ping")
    
    try:
        response = requests.get(f"{BASE_URL}/fapi/v1/ping", timeout=10)
        
        print(f"\n📊 Resposta:")
        print(f"   • Status Code: {response.status_code}")
        print(f"   • Resposta: {response.text}")
        
        if response.status_code == 200:
            print("\n✅ Servidor da testnet está acessível!")
            return True
        else:
            print(f"\n❌ Erro: Status {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Erro de conexão: {e}")
        return False


def test_3_tempo_servidor():
    """Teste 3: Obtém o tempo do servidor"""
    print_separator("TESTE 3: Tempo do Servidor")
    
    print("📡 Endpoint: /fapi/v1/time")
    
    try:
        response = requests.get(f"{BASE_URL}/fapi/v1/time", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            server_time = data.get('serverTime', 0)
            local_time = int(time.time() * 1000)
            diff = abs(server_time - local_time)
            
            print(f"\n📊 Resultado:")
            print(f"   • Tempo do Servidor: {server_time}")
            print(f"   • Tempo Local: {local_time}")
            print(f"   • Diferença: {diff} ms")
            
            if diff > 5000:
                print(f"\n⚠️ AVISO: Diferença de tempo muito grande ({diff} ms)")
                print("   Isso pode causar problemas de autenticação.")
                print("   Sincronize o relógio do seu computador!")
            else:
                print(f"\n✅ Sincronização OK!")
            
            return server_time
        else:
            print(f"\n❌ Erro: Status {response.status_code}")
            return None
            
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        return None


def test_4_endpoint_autenticado():
    """Teste 4: Testa endpoint autenticado (informações da conta)"""
    print_separator("TESTE 4: Endpoint Autenticado (Account Info)")
    
    if not API_KEY or not SECRET_KEY:
        print("\n❌ Credenciais não disponíveis!")
        return False
    
    print("📡 Endpoint: /fapi/v2/account")
    print("🔐 Usando autenticação HMAC SHA256")
    
    try:
        # Timestamp atual
        timestamp = int(time.time() * 1000)
        
        # Parâmetros da requisição
        params = {
            'timestamp': timestamp,
            'recvWindow': 60000  # 60 segundos de janela
        }
        
        # Gera query string
        query_string = urlencode(params)
        print(f"\n📝 Query String: {query_string}")
        
        # Gera assinatura
        signature = generate_signature(query_string, SECRET_KEY)
        print(f"🔏 Signature (primeiros 20 chars): {signature[:20]}...")
        
        # Adiciona assinatura aos parâmetros
        params['signature'] = signature
        
        # Headers
        headers = {
            'X-MBX-APIKEY': API_KEY
        }
        
        print(f"\n🔑 API Key no header: {API_KEY[:10]}...{API_KEY[-10:]}")
        
        # Faz a requisição
        print("\n⏳ Enviando requisição...")
        response = requests.get(
            f"{BASE_URL}/fapi/v2/account",
            params=params,
            headers=headers,
            timeout=10
        )
        
        print(f"\n📊 Resposta:")
        print(f"   • Status Code: {response.status_code}")
        print(f"   • Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ SUCESSO! Autenticação funcionou!")
            print(f"\n💰 Informações da Conta:")
            
            # Mostra informações relevantes
            if 'assets' in data:
                for asset in data['assets']:
                    if float(asset.get('walletBalance', 0)) > 0:
                        print(f"   • {asset['asset']}: {asset['walletBalance']}")
            
            if 'totalWalletBalance' in data:
                print(f"\n   💵 Total Wallet Balance: {data['totalWalletBalance']} USDT")
            
            return True
            
        else:
            print(f"\n❌ ERRO: Status {response.status_code}")
            print(f"\n📄 Resposta completa:")
            print(response.text)
            
            # Analisa erros comuns
            try:
                error_data = response.json()
                error_code = error_data.get('code')
                error_msg = error_data.get('msg')
                
                print(f"\n🔍 Análise do Erro:")
                print(f"   • Código: {error_code}")
                print(f"   • Mensagem: {error_msg}")
                
                if error_code == -2008:
                    print(f"\n💡 SOLUÇÃO PARA ERRO -2008:")
                    print("   1. Verifique se você criou a API Key em: https://testnet.binancefuture.com/")
                    print("   2. Confirme que copiou EXATAMENTE as chaves (sem espaços)")
                    print("   3. Verifique o arquivo .env:")
                    print("      BINANCE_TESTNET_API_KEY=sua_chave_aqui")
                    print("      BINANCE_TESTNET_SECRET_KEY=seu_secret_aqui")
                    print("   4. Certifique-se de que não há aspas nas chaves")
                    
                elif error_code == -1021:
                    print(f"\n💡 SOLUÇÃO PARA ERRO -1021 (Timestamp):")
                    print("   Sincronize o relógio do seu computador!")
                    
            except:
                pass
            
            return False
            
    except Exception as e:
        print(f"\n❌ Exceção: {e}")
        import traceback
        print(traceback.format_exc())
        return False


def test_5_candles_publico():
    """Teste 5: Obtém candles (endpoint público para comparação)"""
    print_separator("TESTE 5: Candles (Endpoint Público)")
    
    print("📡 Endpoint: /fapi/v1/klines")
    print("📊 Symbol: BTCUSDT")
    print("⏱️ Interval: 1h")
    
    try:
        params = {
            'symbol': 'BTCUSDT',
            'interval': '1h',
            'limit': 5
        }
        
        response = requests.get(
            f"{BASE_URL}/fapi/v1/klines",
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            candles = response.json()
            print(f"\n✅ Candles obtidos: {len(candles)} registros")
            
            if candles:
                last_candle = candles[-1]
                close_price = float(last_candle[4])
                print(f"\n💰 Último preço de fechamento: ${close_price:,.2f}")
            
            return True
        else:
            print(f"\n❌ Erro: Status {response.status_code}")
            
            print(response.text)
            return False
            
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        return False


def run_all_tests():
    """Executa todos os testes em sequência"""
    print("\n" + "🧪" * 40)
    print("  TESTE RAW DA API BINANCE TESTNET (SEM CCXT)")
    print("🧪" * 40)
    
    results = {
        'credenciais': False,
        'publico': False,
        'tempo': False,
        'autenticado': False,
        'candles': False
    }
    
    # Teste 1: Credenciais
    results['credenciais'] = test_1_verificar_credenciais()
    if not results['credenciais']:
        print("\n❌ Não é possível continuar sem credenciais!")
        return results
    
    input("\n⏸️ Pressione ENTER para continuar com o próximo teste...")
    
    # Teste 2: Endpoint público
    results['publico'] = test_2_endpoint_publico()
    input("\n⏸️ Pressione ENTER para continuar...")
    
    # Teste 3: Tempo do servidor
    server_time = test_3_tempo_servidor()
    results['tempo'] = server_time is not None
    input("\n⏸️ Pressione ENTER para continuar...")
    
    # Teste 4: Autenticação (TESTE PRINCIPAL)
    results['autenticado'] = test_4_endpoint_autenticado()
    input("\n⏸️ Pressione ENTER para continuar...")
    
    # Teste 5: Candles
    results['candles'] = test_5_candles_publico()
    
    # Resumo final
    print_separator("RESUMO DOS TESTES")
    
    print("\n📊 Resultados:")
    print(f"   1. Credenciais: {'✅ OK' if results['credenciais'] else '❌ FALHOU'}")
    print(f"   2. Endpoint Público: {'✅ OK' if results['publico'] else '❌ FALHOU'}")
    print(f"   3. Tempo Servidor: {'✅ OK' if results['tempo'] else '❌ FALHOU'}")
    print(f"   4. Autenticação: {'✅ OK' if results['autenticado'] else '❌ FALHOU'}")
    print(f"   5. Candles: {'✅ OK' if results['candles'] else '❌ FALHOU'}")
    
    if results['autenticado']:
        print("\n🎉 SUCESSO TOTAL! Suas credenciais funcionam perfeitamente!")
        print("   Agora você pode usar o CCXT com confiança.")
    else:
        print("\n⚠️ A autenticação falhou. Revise as soluções sugeridas acima.")
    
    return results


if __name__ == "__main__":
    run_all_tests()

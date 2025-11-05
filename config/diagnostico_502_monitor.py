"""
Monitor Contínuo do Status da Binance Testnet

Script simples que verifica periodicamente se a testnet está online
e registra quando ocorrem erros 502.

Útil para identificar:
- Padrões de instabilidade (horários específicos)
- Duração das quedas
- Frequência dos erros 502
"""

import time
import requests
from datetime import datetime
from collections import deque
import json
from pathlib import Path

# Configurações
CHECK_INTERVAL = 30  # segundos entre cada verificação
TESTNET_URL = "https://testnet.binance.vision/api/v3/time"
LOG_FILE = Path(__file__).parent / "testnet_status_log.json"
MAX_HISTORY = 100  # Mantém últimas 100 verificações

class TestnetMonitor:
    def __init__(self):
        self.history = deque(maxlen=MAX_HISTORY)
        self.consecutive_errors = 0
        self.consecutive_success = 0
        self.total_checks = 0
        self.total_errors = 0
        self.start_time = datetime.now()
        self.load_history()
    
    def load_history(self):
        """Carrega histórico anterior se existir"""
        if LOG_FILE.exists():
            try:
                with open(LOG_FILE, 'r') as f:
                    data = json.load(f)
                    print(f"📂 Histórico carregado: {len(data.get('history', []))} registros")
            except:
                print("⚠️ Não foi possível carregar histórico anterior")
    
    def save_history(self):
        """Salva histórico atual"""
        try:
            data = {
                'last_update': datetime.now().isoformat(),
                'total_checks': self.total_checks,
                'total_errors': self.total_errors,
                'error_rate': f"{(self.total_errors/self.total_checks*100):.1f}%" if self.total_checks > 0 else "0%",
                'history': list(self.history)
            }
            
            with open(LOG_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Erro ao salvar histórico: {e}")
    
    def check_status(self):
        """Verifica status da testnet"""
        timestamp = datetime.now()
        
        try:
            start_time = time.time()
            response = requests.get(TESTNET_URL, timeout=10)
            response_time = time.time() - start_time
            
            status_code = response.status_code
            is_error = status_code != 200
            
            # Registra resultado
            result = {
                'timestamp': timestamp.isoformat(),
                'status_code': status_code,
                'response_time_ms': int(response_time * 1000),
                'success': not is_error
            }
            
            self.history.append(result)
            self.total_checks += 1
            
            if is_error:
                self.total_errors += 1
                self.consecutive_errors += 1
                self.consecutive_success = 0
                
                # Mostra erro
                icon = "🔴" if status_code == 502 else "❌"
                print(f"{icon} [{timestamp.strftime('%H:%M:%S')}] Erro {status_code} | "
                      f"Consecutivos: {self.consecutive_errors} | "
                      f"Taxa de erro: {(self.total_errors/self.total_checks*100):.1f}%")
                
                if status_code == 502:
                    print("   ⚠️ 502 Bad Gateway - Testnet pode estar em manutenção")
            
            else:
                self.consecutive_success += 1
                self.consecutive_errors = 0
                
                # Mostra sucesso (menos verbose)
                if self.consecutive_success == 1:
                    # Primeira vez OK depois de erros
                    print(f"✅ [{timestamp.strftime('%H:%M:%S')}] Testnet voltou! | "
                          f"Resposta: {int(response_time * 1000)}ms")
                elif self.consecutive_success % 10 == 0:
                    # A cada 10 sucessos
                    print(f"✅ [{timestamp.strftime('%H:%M:%S')}] {self.consecutive_success} checks OK consecutivos | "
                          f"Resposta média: {int(response_time * 1000)}ms")
            
            return result
            
        except requests.exceptions.Timeout:
            self.total_checks += 1
            self.total_errors += 1
            self.consecutive_errors += 1
            self.consecutive_success = 0
            
            result = {
                'timestamp': timestamp.isoformat(),
                'status_code': 'TIMEOUT',
                'response_time_ms': 10000,
                'success': False
            }
            
            self.history.append(result)
            
            print(f"⏱️ [{timestamp.strftime('%H:%M:%S')}] Timeout (>10s) | "
                  f"Consecutivos: {self.consecutive_errors}")
            
            return result
            
        except Exception as e:
            self.total_checks += 1
            self.total_errors += 1
            self.consecutive_errors += 1
            self.consecutive_success = 0
            
            result = {
                'timestamp': timestamp.isoformat(),
                'status_code': 'ERROR',
                'error': str(e)[:100],
                'success': False
            }
            
            self.history.append(result)
            
            print(f"❌ [{timestamp.strftime('%H:%M:%S')}] Erro: {str(e)[:50]}")
            
            return result
    
    def show_stats(self):
        """Mostra estatísticas"""
        print("\n" + "="*60)
        print("📊 ESTATÍSTICAS DO MONITORAMENTO")
        print("="*60)
        
        uptime = datetime.now() - self.start_time
        uptime_str = str(uptime).split('.')[0]
        
        print(f"⏱️ Tempo de monitoramento: {uptime_str}")
        print(f"🔢 Total de verificações: {self.total_checks}")
        print(f"✅ Sucessos: {self.total_checks - self.total_errors}")
        print(f"❌ Erros: {self.total_errors}")
        
        if self.total_checks > 0:
            error_rate = (self.total_errors / self.total_checks) * 100
            success_rate = 100 - error_rate
            print(f"📈 Taxa de sucesso: {success_rate:.1f}%")
            print(f"📉 Taxa de erro: {error_rate:.1f}%")
        
        # Análise dos últimos erros
        recent_errors = [h for h in self.history if not h.get('success', False)]
        if recent_errors:
            print(f"\n🔴 Últimos {len(recent_errors)} erros:")
            for err in recent_errors[-5:]:  # Mostra últimos 5
                ts = datetime.fromisoformat(err['timestamp'])
                status = err.get('status_code', 'UNKNOWN')
                print(f"   • {ts.strftime('%H:%M:%S')}: {status}")
        
        print("="*60 + "\n")
    
    def run(self):
        """Executa monitoramento contínuo"""
        print("\n" + "🔍 MONITOR DE STATUS DA BINANCE TESTNET".center(60))
        print("="*60)
        print(f"URL monitorada: {TESTNET_URL}")
        print(f"Intervalo: {CHECK_INTERVAL}s")
        print(f"Log: {LOG_FILE}")
        print("="*60)
        print("Pressione Ctrl+C para parar\n")
        
        try:
            while True:
                self.check_status()
                
                # Salva histórico a cada 10 checks
                if self.total_checks % 10 == 0:
                    self.save_history()
                
                # Mostra estatísticas a cada 50 checks
                if self.total_checks % 50 == 0:
                    self.show_stats()
                
                time.sleep(CHECK_INTERVAL)
                
        except KeyboardInterrupt:
            print("\n\n⏹️ Monitoramento interrompido pelo usuário")
            self.show_stats()
            self.save_history()
            print(f"📂 Histórico salvo em: {LOG_FILE}")

def quick_check():
    """Faz uma verificação rápida única"""
    print("🔍 Verificação rápida da testnet...\n")
    
    endpoints = [
        ("Spot Time", "https://testnet.binance.vision/api/v3/time"),
        ("Spot Ping", "https://testnet.binance.vision/api/v3/ping"),
        ("Futures Time", "https://testnet.binancefuture.com/fapi/v1/time"),
        ("Futures Ping", "https://testnet.binancefuture.com/fapi/v1/ping"),
    ]
    
    results = []
    for name, url in endpoints:
        try:
            start = time.time()
            response = requests.get(url, timeout=5)
            elapsed = int((time.time() - start) * 1000)
            
            if response.status_code == 200:
                print(f"✅ {name}: OK ({elapsed}ms)")
                results.append(True)
            elif response.status_code == 502:
                print(f"🔴 {name}: 502 Bad Gateway")
                results.append(False)
            else:
                print(f"⚠️ {name}: Status {response.status_code}")
                results.append(False)
        except Exception as e:
            print(f"❌ {name}: {str(e)[:50]}")
            results.append(False)
        
        time.sleep(0.3)
    
    print()
    if all(results):
        print("✅ Testnet está online e funcionando!")
    elif any(results):
        print("⚠️ Testnet está parcialmente online (alguns endpoints falhando)")
    else:
        print("🔴 Testnet parece estar completamente offline!")
    
    print("\nPara monitoramento contínuo, execute:")
    print("  python diagnostico_502_monitor.py --monitor")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--monitor':
        # Modo monitoramento contínuo
        monitor = TestnetMonitor()
        monitor.run()
    else:
        # Modo verificação rápida
        quick_check()
        print("\n💡 Dica: Use --monitor para monitoramento contínuo")

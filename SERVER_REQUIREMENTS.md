# 🖥️ Requisitos de Servidor para Bot de Trading

## 📊 Análise de Recursos

### Componentes do Sistema

1. **Bot do Telegram** (python-telegram-bot)
   - Polling contínuo
   - Processamento de comandos
   - Envio de notificações

2. **Monitor de Risco** (a cada 1 minuto)
   - Busca posições via API Binance
   - Cálculos de PNL
   - Gerenciamento de trailing stops

3. **Estratégias de Trading** (variável)
   - MA Slow Stochastic (4h/1d)
   - MACD Clustering (1h/2h/4h)
   - BTC 1m Scalper
   - Rompimento ETH

4. **Análise Técnica**
   - Indicadores (MACD, RSI, Stochastic, SuperTrend)
   - Machine Learning (XGBoost)
   - Clustering

5. **APIs Externas**
   - Binance (CCXT)
   - News API
   - OpenRouter (LLMs)

---

## 💻 Configurações Recomendadas

### 🟢 **Configuração Mínima (VPS Básico)**
**Cenário:** 1-3 estratégias simultâneas, até 5 posições

```
CPU:     2 vCores (2.4 GHz+)
RAM:     2 GB
Disco:   20 GB SSD
Rede:    100 Mbps
SO:      Ubuntu 22.04 LTS / Debian 11
Custo:   $5-10/mês
```

**Provedores Recomendados:**
- DigitalOcean: Droplet Basic ($6/mês)
- Vultr: Cloud Compute ($5/mês)
- Linode: Nanode 2GB ($10/mês)
- Contabo: VPS S ($5/mês - Europa)

**Limitações:**
- ⚠️ Pode travar com > 3 estratégias simultâneas
- ⚠️ Machine Learning pesado pode causar lentidão
- ⚠️ Não recomendado para produção crítica

---

### 🟡 **Configuração Recomendada (VPS Intermediário)**
**Cenário:** Até 5 estratégias, 10-15 posições, uso moderado de ML

```
CPU:     4 vCores (2.6 GHz+)
RAM:     4 GB
Disco:   40 GB SSD
Rede:    200 Mbps
SO:      Ubuntu 22.04 LTS
Custo:   $15-25/mês
```

**Provedores Recomendados:**
- DigitalOcean: Droplet Regular ($18/mês)
- Vultr: Cloud Compute 4GB ($20/mês)
- Linode: Linode 4GB ($20/mês)
- AWS Lightsail: 4GB ($20/mês)

**Vantagens:**
- ✅ Roda todas as estratégias sem problemas
- ✅ Machine Learning e Clustering funcionam bem
- ✅ Margem para picos de uso
- ✅ Boa para produção

---

### 🔵 **Configuração Ideal (VPS Avançado)**
**Cenário:** Múltiplas estratégias, 20+ posições, ML intensivo, backtests

```
CPU:     8 vCores (3.0 GHz+)
RAM:     8 GB
Disco:   80 GB SSD NVMe
Rede:    500 Mbps
SO:      Ubuntu 22.04 LTS
Custo:   $40-60/mês
```

**Provedores Recomendados:**
- DigitalOcean: Droplet General Purpose ($48/mês)
- Vultr: High Frequency 8GB ($48/mês)
- Linode: Dedicated 8GB ($60/mês)
- Hetzner: CPX41 (€16/mês = ~$17/mês) ⭐ MELHOR CUSTO-BENEFÍCIO

**Vantagens:**
- ✅ Zero preocupações com performance
- ✅ Backtests rápidos
- ✅ Suporta desenvolvimento + produção
- ✅ Margem para expansão

---

## 📈 Consumo Estimado de Recursos

### RAM (Memória)

```python
Bot Base (Telegram + CCXT):              ~150 MB
Monitor de Risco (1 execução):           ~50 MB
Estratégia MA Slow Stochastic:           ~80 MB
Estratégia MACD Clustering:              ~100 MB
Modelo XGBoost carregado:                ~200 MB
Sistema Operacional (Ubuntu):            ~400 MB
---------------------------------------------------
Total Estimado (3 estratégias):          ~1.0 GB
Pico com ML ativo:                       ~1.5 GB
```

**Recomendação:** **4 GB de RAM** para operação confortável

---

### CPU (Processamento)

**Uso Contínuo:**
```
Bot em idle:                             5-10%
Monitor de Risco (1 min):                10-15%
Estratégia processando:                  20-30%
Machine Learning (treino):               60-80%
Backtest executando:                     80-100%
```

**Conclusão:** 
- 2 cores: Suficiente para operação básica
- 4 cores: **Recomendado** para produção
- 8 cores: Ideal para desenvolvimento + backtests

---

### Disco (Armazenamento)

```
Sistema Operacional:                     ~8 GB
Python + Dependências:                   ~2 GB
Logs (1 mês):                            ~500 MB
CSVs de dados históricos:                ~1 GB
Modelos salvos (XGBoost, etc):           ~500 MB
Outputs e relatórios:                    ~1 GB
Margem de segurança:                     ~6 GB
---------------------------------------------------
Total Mínimo:                            ~20 GB
Recomendado:                             40 GB SSD
```

---

### Rede (Largura de Banda)

**Uso Mensal Estimado:**

```
API Binance (posições/preços):           ~2 GB/mês
API News/OpenRouter:                     ~500 MB/mês
Telegram (notificações):                 ~100 MB/mês
Websockets (se usar):                    ~5 GB/mês
---------------------------------------------------
Total Estimado:                          ~8 GB/mês
```

**Velocidade Necessária:**
- Mínimo: 10 Mbps
- Recomendado: 100 Mbps
- Latência: < 100ms para Binance

---

## 🌍 Localização do Servidor

### Latência para Binance

**Servidores da Binance:**
- Principal: AWS Singapore
- Backup: AWS Tokyo
- Europa: AWS Frankfurt

**Recomendações por Região:**

| Região | Latência Típica | Recomendação |
|--------|-----------------|--------------|
| **Ásia (Singapura)** | 10-30ms | ⭐⭐⭐⭐⭐ MELHOR |
| **Ásia (Tóquio)** | 20-50ms | ⭐⭐⭐⭐⭐ ÓTIMO |
| **Europa (Frankfurt)** | 50-100ms | ⭐⭐⭐⭐ BOM |
| **EUA (Leste)** | 150-200ms | ⭐⭐⭐ ACEITÁVEL |
| **América do Sul** | 200-300ms | ⭐⭐ PODE TER PROBLEMAS |

**⚠️ Importante para Day Trading:**
- Latência < 100ms = Ideal
- Latência 100-200ms = Aceitável
- Latência > 200ms = Pode perder oportunidades

---

## 🐧 Sistema Operacional Recomendado

### Ubuntu 22.04 LTS (Recomendado)

**Vantagens:**
- ✅ Suporte até 2027
- ✅ Pacotes Python atualizados
- ✅ Grande comunidade
- ✅ Fácil configuração

**Alternativas:**
- Debian 11: Mais estável, menos recente
- Ubuntu 20.04 LTS: Ainda suportado até 2025
- Rocky Linux 9: Se preferir RHEL-based

**❌ Evite:**
- Windows Server: Overhead desnecessário
- Distribuições não-LTS: Falta de suporte

---

## 🔧 Otimizações de Performance

### 1. Configuração do Python

```bash
# Use Python 3.11+ (mais rápido)
python3.11 -m venv venv

# JIT para NumPy/Pandas
pip install numba

# Async otimizado
pip install uvloop
```

### 2. Configuração do Sistema

```bash
# /etc/sysctl.conf
# Aumenta limites de conexões
net.core.somaxconn = 1024
net.ipv4.tcp_max_syn_backlog = 2048
net.ipv4.ip_local_port_range = 10000 65535

# Melhor gerenciamento de memória
vm.swappiness = 10
vm.vfs_cache_pressure = 50
```

### 3. Configuração do Swap

```bash
# Criar swap de 2GB (se RAM < 4GB)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### 4. Monitoramento de Recursos

```bash
# Instalar ferramentas
sudo apt install htop iotop nethogs

# Monitorar uso
htop        # CPU e RAM
iotop       # Disco
nethogs     # Rede
```

---

## 📊 Benchmark de Performance

### Teste Real (VPS 4GB / 2 vCores)

```
Startup do bot:                          5-8 segundos
Monitor de risco (1 ciclo):              2-4 segundos
Estratégia MA Slow (1 ciclo):            10-15 segundos
Cálculo de indicadores (1 símbolo):      0.5-1 segundo
Predição XGBoost:                        1-2 segundos
Backtest (1 mês, 1 símbolo):             30-60 segundos
```

**Conclusão:** VPS 4GB funciona perfeitamente!

---

## 💰 Comparação de Custos (Mensal)

### Provedores Principais

| Provedor | Config | CPU | RAM | Disco | Preço | Latência SG |
|----------|--------|-----|-----|-------|-------|-------------|
| **Hetzner** 🏆 | CPX21 | 3 vCore | 4 GB | 80 GB | **€8** (~$8.50) | ~180ms |
| **Contabo** | VPS M | 4 vCore | 8 GB | 200 GB | **€10** (~$11) | ~200ms |
| Vultr | Regular | 2 vCore | 4 GB | 80 GB | $20 | 50-100ms |
| DigitalOcean | Droplet | 2 vCore | 4 GB | 80 GB | $18 | 100-150ms |
| Linode | Linode | 2 vCore | 4 GB | 80 GB | $20 | 80-120ms |
| AWS Lightsail | 4GB | 2 vCore | 4 GB | 80 GB | $20 | 30-60ms |

🏆 **Melhor Custo-Benefício:** Hetzner (Alemanha) ou Contabo
⚡ **Melhor Latência:** AWS Lightsail (Singapore) ou Vultr (Tokyo)

---

## 🚀 Configuração Recomendada Final

### Para Produção (Melhor Custo-Benefício)

```yaml
Provedor:    Hetzner CPX31 ou Vultr Tokyo
CPU:         4 vCores
RAM:         4 GB
Disco:       80 GB SSD
Localização: Alemanha (Hetzner) ou Tóquio (Vultr)
Preço:       €12/mês (~$13) ou $20/mês
SO:          Ubuntu 22.04 LTS
Python:      3.11+
```

**Por quê essa configuração?**
- ✅ CPU suficiente para todas as estratégias
- ✅ RAM confortável com margem de segurança
- ✅ Disco rápido (SSD) para logs e dados
- ✅ Latência aceitável para Binance
- ✅ Custo acessível para uso contínuo
- ✅ Margem para crescimento

---

## 🔒 Segurança e Backup

### Configurações Essenciais

```bash
# 1. Firewall
sudo ufw allow 22/tcp     # SSH
sudo ufw enable

# 2. Fail2ban (proteção SSH)
sudo apt install fail2ban

# 3. Backup automático de configs
crontab -e
# 0 3 * * * tar -czf /backup/bot_$(date +\%Y\%m\%d).tar.gz /path/to/bot

# 4. Variáveis de ambiente (.env)
# NUNCA commitar API keys!
```

---

## 📊 Checklist de Deploy

### Antes de Subir para Produção

- [ ] VPS com no mínimo 4GB RAM
- [ ] Ubuntu 22.04 LTS instalado
- [ ] Python 3.11+ configurado
- [ ] Todas as dependências instaladas
- [ ] Arquivo .env configurado (API keys)
- [ ] Firewall configurado
- [ ] Swap configurado (se RAM < 8GB)
- [ ] Monitoramento instalado (htop, etc)
- [ ] Backup automático configurado
- [ ] Testado em testnet primeiro
- [ ] Logs sendo salvos corretamente
- [ ] systemd service configurado (auto-restart)
- [ ] Webhook Telegram ou polling testado
- [ ] Latência para Binance testada (< 200ms)

---

## 🛠️ Script de Setup Automático

```bash
#!/bin/bash
# setup_vps.sh - Configuração automática do VPS

echo "🚀 Configurando VPS para Bot de Trading..."

# Atualiza sistema
sudo apt update && sudo apt upgrade -y

# Instala dependências
sudo apt install -y python3.11 python3.11-venv python3-pip git htop

# Cria usuário para o bot
sudo useradd -m -s /bin/bash bottrader
sudo su - bottrader

# Clona repositório
git clone https://github.com/seu-usuario/bot_mcp.git
cd bot_mcp

# Cria ambiente virtual
python3.11 -m venv venv
source venv/bin/activate

# Instala dependências
pip install --upgrade pip
pip install -r requirements.txt

# Configura variáveis de ambiente
cp .env.example .env
nano .env  # Edite suas API keys

# Testa conexão
python test_binance_testnet.py

# Configura systemd service
sudo nano /etc/systemd/system/bottrader.service

# Inicia serviço
sudo systemctl enable bottrader
sudo systemctl start bottrader

echo "✅ Setup concluído!"
```

---

## 📈 Escalabilidade

### Quando Aumentar Recursos?

**Sinais de que precisa upgrade:**
- ⚠️ Uso de RAM > 80% constante
- ⚠️ CPU > 80% por mais de 5 minutos
- ⚠️ Swap sendo usado frequentemente
- ⚠️ Timeouts frequentes na API
- ⚠️ Latência aumentando
- ⚠️ Bot travando/reiniciando

**Próximos passos:**
1. 4GB → 8GB RAM (+50% performance)
2. 4 cores → 8 cores (+100% estratégias simultâneas)
3. SSD → NVMe (+50% velocidade I/O)

---

## 🎯 Recomendação Final

### 💎 **Configuração Ideal para Seu Bot**

```
🖥️  Provedor:    Hetzner CPX31 ou Vultr High Frequency
💻  CPU:         4 vCores AMD/Intel
🧠  RAM:         4 GB
💾  Disco:       80 GB SSD
🌍  Localização: Frankfurt (Hetzner) ou Tokyo (Vultr)
💰  Custo:       €12-20/mês ($13-22/mês)
🐧  SO:          Ubuntu 22.04 LTS
```

**Por que essa configuração?**
1. ✅ **Custo-benefício imbatível** - Hetzner oferece o melhor preço
2. ✅ **Performance garantida** - 4GB RAM é confortável
3. ✅ **Latência aceitável** - Frankfurt: ~80-120ms para Binance
4. ✅ **Margem de segurança** - Não vai travar
5. ✅ **Escalável** - Fácil fazer upgrade depois

**Alternativa Baixo Custo (Início):**
```
Contabo VPS S: 4 vCore, 8GB RAM, €5/mês
⚠️ Latência maior (~200ms), mas funcional
```

**Alternativa Premium (Trading Intenso):**
```
Vultr Tokyo: 8GB RAM, $48/mês
✅ Latência mínima (~20-50ms para Binance)
```

---

## 📞 Próximos Passos

1. **Escolha o provedor** baseado em orçamento e latência
2. **Teste primeiro em VPS básico** ($5-10/mês) por 1 semana
3. **Monitore recursos** (CPU, RAM, latência)
4. **Faça upgrade se necessário**

**Dica:** Comece com Hetzner CPX21 (€8/mês) e monitore!

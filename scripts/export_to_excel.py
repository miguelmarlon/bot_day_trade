"""
Script de Exportação Manual para Excel
Execute este script para exportar manualmente os dados de trading para Excel.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from scripts.excel_exporter import ExcelExporter

def main():
    """Executa exportação manual de todos os dados."""
    print("=" * 60)
    print("📊 EXPORTAÇÃO MANUAL PARA EXCEL")
    print("=" * 60)
    
    exporter = ExcelExporter()
    
    # 1. Exporta trades do JSON
    print("\n1️⃣ Exportando trades concluídos do JSON...")
    try:
        success = exporter.export_trades_from_json("logs/trades_principais_em_andamento.json")
        if success:
            print("   ✅ Trades exportados com sucesso!")
        else:
            print("   ℹ️ Nenhum trade novo para exportar")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    
    # 2. Gera resumo diário
    print("\n2️⃣ Gerando resumo diário...")
    try:
        success = exporter.export_daily_summary()
        if success:
            print("   ✅ Resumo diário gerado com sucesso!")
        else:
            print("   ℹ️ Não há dados suficientes para gerar resumo")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    
    print("\n" + "=" * 60)
    print("📁 Arquivos salvos em: outputs/")
    print("   - historico_operacoes.xlsx")
    print("   - monitoramento_risco.xlsx")
    print("   - resumo_diario.xlsx")
    print("=" * 60)
    print("\n✅ Exportação concluída!")

if __name__ == "__main__":
    main()

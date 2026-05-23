@echo off & python -x "%~f0" %* & goto :eof
# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
import os
import sys
import json
import subprocess
from datetime import datetime

STATS_FILE = "executar_stats.json"

# Códigos ANSI para cores


class Cores:
    MAGENTA = '\033[95m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'


def colored(texto, cor='magenta'):
    """Função para colorir texto usando códigos ANSI"""
    if cor == 'magenta':
        return f"{Cores.MAGENTA}{texto}{Cores.RESET}"
    elif cor == 'green':
        return f"{Cores.GREEN}{texto}{Cores.RESET}"
    elif cor == 'yellow':
        return f"{Cores.YELLOW}{texto}{Cores.RESET}"
    return texto


def load_stats():
    """Carrega as estatísticas do arquivo JSON."""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Erro ao carregar stats: {e}")
            return {}
    return {}


def save_stats(stats):
    """Salva as estatísticas no arquivo JSON."""
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Erro ao salvar stats: {e}")


def update_stat(script_name):
    """Atualiza as estatísticas de execução de um script."""
    stats = load_stats()
    if script_name not in stats:
        stats[script_name] = {
            'count': 0,
            'first_run': datetime.now().isoformat(),
            'last_run': None
        }
    stats[script_name]['count'] += 1
    stats[script_name]['last_run'] = datetime.now().isoformat()
    save_stats(stats)
    return stats[script_name]['count']


def mostra_opcoes(pergunta, opcoes):
    print("\n", '-'*20)
    print(pergunta)

    # Cria uma lista para exibição
    display_opcoes = list(opcoes)

    # Se houver muitas opções, inverte a exibição (mantendo índices originais na lógica)
    if len(display_opcoes) > 20:
        display_opcoes = display_opcoes[::-1]

    while True:
        for i in range(len(display_opcoes)):
            # Calcula o índice real na lista original 'opcoes'
            if len(opcoes) > 20:
                real_index = len(opcoes) - 1 - i
            else:
                real_index = i

            item = display_opcoes[i]  # O item exibido
            # O item exibido é display_opcoes[i], que correspode a opcoes[real_index] se invertido corretamente
            # Vamos pegar direto do indice real para garantir
            item_nome = opcoes[real_index]

            msg = f"{real_index} - {item_nome}"
            if real_index == 0:
                msg = f"{msg} *"
            print(msg)

        try:
            escolha = input("Digite a opção escolhida:\n")
            if escolha == "":
                escolha = 0
            escolha = int(escolha)
            if escolha >= 0 and escolha < len(opcoes):
                return escolha
            else:
                print("Opção inválida. Por favor, escolha um número válido.")
        except ValueError:
            print("Por favor, insira um número.")


def get_sorted_files():
    """
    Retorna a lista de arquivos ordenados:
    1. Top N scripts mais executados (10% do total)
    2. Restante ordenado por data de modificação
    """
    # Lista arquivos .py
    try:
        files = [f for f in os.listdir(os.getcwd()) if f.endswith('.py')]
    except Exception as e:
        print(f"Erro ao listar arquivos: {e}")
        return []

    # Ordena todos por data (comportamento padrão)
    files_by_date = sorted([(f, os.path.getmtime(f))
                           for f in files], key=lambda x: x[1], reverse=True)
    files_by_date = [f[0] for f in files_by_date]

    # Lógica dos 10%
    total = len(files)
    limit = int(total * 0.1)
    if limit < 3 and total > 0:
        limit = 3  # Garante pelo menos mostrar o Top 3 se houver arquivos

    stats = load_stats()

    # Identifica os mais executados
    files_with_counts = []
    for f in files:
        count = stats.get(f, {}).get('count', 0)
        if count > 0:
            files_with_counts.append((f, count))

    # Ordena por contagem decrescente
    files_with_counts.sort(key=lambda x: x[1], reverse=True)

    # Pega os Top N
    top_files = [x[0] for x in files_with_counts[:limit]]

    if top_files:
        print(colored(
            f"Scripts mais executados: {', '.join(top_files)}", 'green'))

    # Monta a lista final
    final_list = []
    seen = set()

    # Adiciona os Top files primeiro
    for f in top_files:
        final_list.append(f)
        seen.add(f)

    # Adiciona o restante
    for f in files_by_date:
        if f not in seen:
            final_list.append(f)

    return final_list


def check_venv():
    """Verifica se existe pasta venv ou .venv e retorna o executável python se existir."""
    for venv_name in ['.venv', 'venv']:
        venv_dir = os.path.join(os.getcwd(), venv_name)
        if os.path.isdir(venv_dir):
            if sys.platform == 'win32':
                python_exe = os.path.join(venv_dir, 'Scripts', 'python.exe')
            else:
                python_exe = os.path.join(venv_dir, 'bin', 'python')

            if os.path.exists(python_exe):
                return python_exe
    return None

# --- Início do Programa ---


# Verifica Venv
use_venv_python = None
venv_path = check_venv()

if venv_path:
    print(colored(f"Ambiente virtual detectado: {venv_path}", 'green'))
    resp = input(
        "Deseja executar com o venv ativado? (s/n) [s]: ").strip().lower()
    if resp == '' or resp == 's':
        use_venv_python = venv_path
    else:
        use_venv_python = None

while True:
    # Obtém lista de arquivos
    pylst = get_sorted_files()
    arquivo = ''

    if not pylst:
        print("Nenhum arquivo .py encontrado no diretório.")
        sys.exit()

    if len(pylst) == 1:
        arquivo = pylst[0]
        pastaarquivo = os.path.join(os.getcwd(), arquivo)
        print(f"Arquivo único selecionado: {pastaarquivo}")
    else:
        narquivo = mostra_opcoes(
            "Digite o número do arquivo a ser executado", pylst)
        arquivo = pylst[narquivo]
        pastaarquivo = os.path.join(os.getcwd(), arquivo)
        print(pastaarquivo)

    qt = 0
    while True:
        qt += 1
        # Atualiza Stats
        runs = update_stat(arquivo)

        texto1 = f"Executando {arquivo} : {qt} : {datetime.now()} (Total Runs: {runs})\n"
        horainicio = datetime.now()
        print(colored(texto1, 'magenta'))
        print(f"Path: {pastaarquivo}")

        # Define comando
        cmd_python = use_venv_python if use_venv_python else "python"

        # Executa
        try:
            subprocess.call([cmd_python, pastaarquivo])
        except Exception as e:
            print(colored(f"Erro ao executar: {e}", 'magenta'))

        tempodeexecucao = datetime.now() - horainicio
        print("\n" * 5)
        print(colored(f"Tempo de execução {tempodeexecucao}", 'magenta'))

        NomeArquivo = os.path.basename(pastaarquivo)
        msg = f"Pressione ENTER para executar novamente: {NomeArquivo} \nM para retornar ao menu"
        print(colored(msg, 'magenta'))
        
        escolha = input().strip().lower()
        if escolha == 'm':
            break

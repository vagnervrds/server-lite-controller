#!/usr/bin/env python3
# monitor.py - Sistema de monitoramento de recursos corrigido

from flask import Flask, render_template, jsonify, request, Blueprint
import psutil
import json
import time
import os
import threading
import datetime
from pathlib import Path
from logger_config import setup_logger

# Configurar o logger
logger = setup_logger(__name__)

monitorBlueP = Blueprint('monitor', __name__)

# Configuração do arquivo único para dados e configurações
DATA_FILE = 'monitor_data.json'

# Estrutura padrão dos dados
default_data = {
    # Configurações
    "config": {
        "monitor_interval": 60,  # intervalo em segundos para monitoramento
        "monitor_duration": 5,   # duração em segundos de cada monitoramento
        "disk_threshold": 10,    # limite mínimo de uso do disco em percentual
        "network_threshold": 5,  # limite mínimo de uso da rede em percentual
        "idle_time_threshold": 30,  # tempo em minutos para desligar se abaixo do limite
        "debug_mode": True,      # evita desligar o computador no modo de desenvolvimento
        "min_disk_rate": 102400,  # Mínimo 100 KB/s para disco
        "min_network_rate": 10240  # Mínimo 10 KB/s para rede
    },
    # Dados de uso atual
    "usage": {
        "disk_usage": 0,
        "network_usage": 0,
        "disk_usage_percent": 0,
        "network_usage_percent": 0,
        "active_disk": "sistema",
        "active_interface": "total",
        "idle_timer_active": False,
        "idle_time_remaining": 0,
        "below_threshold": False,
        "shutdown_scheduled": False,
        "last_updated": ""
    },
    # Valores máximos PERSISTENTES - só atualizados quando valores maiores são encontrados
    "max_usage": {
        "max_disk_usage": 0,  # Valor máximo PERSISTENTE de velocidade de disco
        "max_network_usage": 0,  # Valor máximo PERSISTENTE de velocidade de rede
        "disk_max_date": "",  # Data quando o máximo de disco foi registrado
        "network_max_date": "",  # Data quando o máximo de rede foi registrado
        "disk_records_count": 0,  # Contador de quantas vezes o máximo de disco foi atualizado
        # Contador de quantas vezes o máximo de rede foi atualizado
        "network_records_count": 0,
        "last_updated": "",
        "first_run_date": ""  # Data da primeira execução do sistema
    },
    # Histórico (últimas 24 horas, uma entrada por 15 minutos)
    "history": [],
    "last_history_update": 0,
    # Valores base anteriores para cálculo de taxa
    "previous_values": {
        "disk_total": 0,
        "network_total": 0,
        "timestamp": 0
    }
}

# Variáveis globais para armazenar o estado do monitoramento
monitoring_active = False
monitoring_thread = None
last_activity_time = {}  # armazenar quando uso abaixo do limite começou
idle_timer_active = False  # indica se o timer para desligamento está ativo
shutdown_scheduled = False  # indica se há um desligamento agendado


def ensure_data_file_exists():
    """Garante que o arquivo de dados existe e está com a estrutura correta"""
    if not Path(DATA_FILE).exists():
        logger.info(
            f"Arquivo de dados {DATA_FILE} não encontrado. Criando novo arquivo.")
        # Inicializar com dados padrão e marcar primeira execução
        new_data = default_data.copy()
        new_data["max_usage"]["first_run_date"] = datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S")

        with open(DATA_FILE, 'w') as f:
            json.dump(new_data, f, indent=2)
        logger.info(f"Arquivo de dados {DATA_FILE} criado com sucesso.")
    else:
        logger.debug(
            f"Arquivo de dados {DATA_FILE} já existe - mantendo dados persistentes.")


def get_data():
    """Carrega todos os dados do arquivo"""
    ensure_data_file_exists()
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            # Verificar se estrutura está completa e atualizar se necessário
            # IMPORTANTE: NÃO sobrescrever max_usage se já existir
            for key in default_data:
                if key not in data:
                    data[key] = default_data[key]
                elif isinstance(default_data[key], dict):
                    for subkey in default_data[key]:
                        if subkey not in data[key]:
                            # Para max_usage, só adicionar chaves que não existem
                            # Manter os valores máximos existentes
                            if key == "max_usage" and subkey in ["max_disk_usage", "max_network_usage"]:
                                if data[key].get(subkey, 0) == 0:
                                    data[key][subkey] = default_data[key][subkey]
                            else:
                                data[key][subkey] = default_data[key][subkey]

            # Verificar se é primeira execução após criação do arquivo
            if not data["max_usage"].get("first_run_date"):
                data["max_usage"]["first_run_date"] = datetime.datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S")
                save_data(data)

            logger.debug("Dados carregados com sucesso.")
            logger.info(f"Máximos persistentes - Disco: {data['max_usage']['max_disk_usage']:.2f} B/s, "
                        f"Rede: {data['max_usage']['max_network_usage']:.2f} B/s")
            return data
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao decodificar JSON do arquivo {DATA_FILE}: {e}")
        logger.info("Usando dados padrão devido a erro no arquivo.")
        return default_data
    except FileNotFoundError as e:
        logger.error(f"Arquivo {DATA_FILE} não encontrado: {e}")
        logger.info("Usando dados padrão devido a arquivo não encontrado.")
        return default_data
    except Exception as e:
        logger.error(
            f"Erro inesperado ao carregar dados do arquivo {DATA_FILE}: {e}")
        logger.info("Usando dados padrão devido a erro inesperado.")
        return default_data


def save_data(data):
    """Salva todos os dados no arquivo"""
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        logger.debug("Dados salvos com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao salvar dados no arquivo {DATA_FILE}: {e}")


def get_config():
    """Obtém apenas a parte de configuração dos dados"""
    logger.debug("Obtendo configurações.")
    return get_data()["config"]


def update_config(new_config):
    """Atualiza apenas a configuração nos dados"""
    logger.info(f"Atualizando configurações: {new_config}")
    data = get_data()
    data["config"].update(new_config)
    save_data(data)
    logger.info("Configurações atualizadas com sucesso.")


def get_usage():
    """Obtém apenas os dados de uso atual"""
    logger.debug("Obtendo dados de uso atual.")
    return get_data()["usage"]


def get_max_usage():
    """Obtém os valores máximos registrados"""
    logger.debug("Obtendo valores máximos.")
    return get_data()["max_usage"]


def get_disk_usage_cumulative():
    """Obtém o uso cumulativo total de disco (soma de leitura + escrita em bytes)"""
    try:
        if os.name == "nt":  # Windows
            disk = psutil.disk_io_counters()
            if disk:
                total = disk.read_bytes + disk.write_bytes
                logger.debug(f"Uso cumulativo disco Windows: {total} bytes")
                return total
            return 0
        else:  # Linux/DietPi
            try:
                # Método principal: ler /proc/diskstats
                with open('/proc/diskstats', 'r') as f:
                    disk_stats = f.readlines()

                total_bytes = 0
                active_disks = []

                for line in disk_stats:
                    parts = line.split()
                    if len(parts) < 14:
                        continue

                    dev_name = parts[2]
                    # Filtrar apenas discos físicos (ignorar partições numeradas)
                    if dev_name.startswith(('sd', 'hd', 'vd', 'nvme', 'mmcblk')):
                        # Para nvme, incluir apenas o disco base (nvme0n1, não nvme0n1p1)
                        if 'nvme' in dev_name and 'p' in dev_name:
                            continue
                        # Para outros, ignorar partições numeradas
                        if any(char.isdigit() for char in dev_name[-2:]) and not dev_name.startswith('nvme'):
                            continue

                        # Campos 5 (setores lidos) e 9 (setores escritos), vezes 512 bytes por setor
                        bytes_read = int(parts[5]) * 512
                        bytes_written = int(parts[9]) * 512
                        disk_total = bytes_read + bytes_written

                        total_bytes += disk_total
                        active_disks.append(f"{dev_name}:{disk_total}")

                logger.debug(f"Discos ativos Linux: {active_disks}")
                logger.debug(
                    f"Uso cumulativo disco Linux total: {total_bytes} bytes")
                return total_bytes

            except Exception as e:
                logger.error(f"Erro ao ler /proc/diskstats: {e}")
                # Fallback para psutil
                try:
                    disk = psutil.disk_io_counters()
                    if disk:
                        total = disk.read_bytes + disk.write_bytes
                        logger.debug(
                            f"Uso cumulativo disco Linux (psutil fallback): {total} bytes")
                        return total
                    return 0
                except Exception as e2:
                    logger.error(f"Erro no fallback psutil para disco: {e2}")
                    return 0

    except Exception as e:
        logger.error(f"Erro geral ao obter uso cumulativo de disco: {e}")
        return 0


def get_network_usage_cumulative():
    """Obtém o uso cumulativo total de rede (soma sent + recv em bytes)"""
    try:
        if os.name == "nt":  # Windows
            net = psutil.net_io_counters()
            if net:
                total = net.bytes_sent + net.bytes_recv
                logger.debug(f"Uso cumulativo rede Windows: {total} bytes")
                return total
            return 0
        else:  # Linux/DietPi
            try:
                # Método principal: ler /proc/net/dev
                with open('/proc/net/dev', 'r') as f:
                    net_data = f.readlines()[2:]  # Pular cabeçalhos

                total_bytes = 0
                active_interfaces = []

                for line in net_data:
                    if ':' in line:
                        interface = line.split(':')[0].strip()
                        # Ignorar interface de loopback
                        if interface != 'lo':
                            values = line.split(':')[1].split()
                            if len(values) >= 9:
                                # bytes recebidos (pos 0) + bytes enviados (pos 8)
                                bytes_recv = int(values[0])
                                bytes_sent = int(values[8])
                                interface_total = bytes_recv + bytes_sent

                                total_bytes += interface_total
                                active_interfaces.append(
                                    f"{interface}:{interface_total}")

                logger.debug(f"Interfaces ativas Linux: {active_interfaces}")
                logger.debug(
                    f"Uso cumulativo rede Linux total: {total_bytes} bytes")
                return total_bytes

            except Exception as e:
                logger.error(f"Erro ao ler /proc/net/dev: {e}")
                # Fallback para psutil
                try:
                    net = psutil.net_io_counters()
                    if net:
                        total = net.bytes_sent + net.bytes_recv
                        logger.debug(
                            f"Uso cumulativo rede Linux (psutil fallback): {total} bytes")
                        return total
                    return 0
                except Exception as e2:
                    logger.error(f"Erro no fallback psutil para rede: {e2}")
                    return 0

    except Exception as e:
        logger.error(f"Erro geral ao obter uso cumulativo de rede: {e}")
        return 0


def calculate_usage_rates():
    """Calcula as taxas de uso baseadas na diferença entre medições consecutivas"""
    data = get_data()
    previous = data["previous_values"]
    current_time = time.time()

    # Obter valores cumulativos atuais
    current_disk = get_disk_usage_cumulative()
    current_network = get_network_usage_cumulative()

    logger.debug(
        f"Valores atuais - Disco: {current_disk}, Rede: {current_network}")

    # Se não há valores anteriores, inicializar sem calcular taxa
    if previous["timestamp"] == 0:
        data["previous_values"] = {
            "disk_total": current_disk,
            "network_total": current_network,
            "timestamp": current_time
        }
        save_data(data)
        logger.info("Primeira medição - inicializando valores base.")
        return 0, 0  # Primeira medição, retornar 0

    # Calcular tempo decorrido
    time_diff = current_time - previous["timestamp"]
    if time_diff <= 0:
        logger.warning("Tempo decorrido inválido, retornando taxas zeradas.")
        return 0, 0

    # Calcular taxas (bytes por segundo)
    disk_diff = current_disk - previous["disk_total"]
    network_diff = current_network - previous["network_total"]

    # Proteger contra valores negativos (possível reset de contadores)
    disk_rate = max(0, disk_diff / time_diff)
    network_rate = max(0, network_diff / time_diff)

    logger.debug(
        f"Diferenças calculadas - Disco: {disk_diff} bytes em {time_diff:.2f}s = {disk_rate:.2f} B/s")
    logger.debug(
        f"Diferenças calculadas - Rede: {network_diff} bytes em {time_diff:.2f}s = {network_rate:.2f} B/s")

    # Atualizar valores anteriores para próxima medição
    data["previous_values"] = {
        "disk_total": current_disk,
        "network_total": current_network,
        "timestamp": current_time
    }
    save_data(data)

    return disk_rate, network_rate


def update_max_usage_persistent(disk_rate, network_rate):
    """Atualiza valores máximos APENAS quando valores maiores são encontrados (dados persistentes)"""
    data = get_data()
    max_data = data["max_usage"]
    config = data["config"]
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Obter valores máximos atuais (persistentes)
    current_max_disk = max_data.get("max_disk_usage", 0)
    current_max_network = max_data.get("max_network_usage", 0)

    # Garantir valores mínimos se for primeira execução
    if current_max_disk == 0:
        current_max_disk = config["min_disk_rate"]
        logger.info(
            f"Inicializando máximo de disco com valor mínimo: {current_max_disk} B/s")

    if current_max_network == 0:
        current_max_network = config["min_network_rate"]
        logger.info(
            f"Inicializando máximo de rede com valor mínimo: {current_max_network} B/s")

    # Verificar se novo máximo de disco foi alcançado
    max_updated = False
    if disk_rate > current_max_disk:
        logger.warning(f"NOVO MÁXIMO DE DISCO REGISTRADO! Anterior: {current_max_disk:.2f} B/s ({current_max_disk/1024:.2f} KB/s) -> "
                       f"Novo: {disk_rate:.2f} B/s ({disk_rate/1024:.2f} KB/s)")

        max_data["max_disk_usage"] = disk_rate
        max_data["disk_max_date"] = current_time
        max_data["disk_records_count"] = max_data.get(
            "disk_records_count", 0) + 1
        current_max_disk = disk_rate
        max_updated = True

    # Verificar se novo máximo de rede foi alcançado
    if network_rate > current_max_network:
        logger.warning(f"NOVO MÁXIMO DE REDE REGISTRADO! Anterior: {current_max_network:.2f} B/s ({current_max_network/1024:.2f} KB/s) -> "
                       f"Novo: {network_rate:.2f} B/s ({network_rate/1024:.2f} KB/s)")

        max_data["max_network_usage"] = network_rate
        max_data["network_max_date"] = current_time
        max_data["network_records_count"] = max_data.get(
            "network_records_count", 0) + 1
        current_max_network = network_rate
        max_updated = True

    # Só atualizar arquivo se houve mudança nos máximos
    if max_updated:
        max_data["last_updated"] = current_time
        data["max_usage"] = max_data
        save_data(data)
        logger.info("Arquivo atualizado com novos valores máximos.")
    else:
        logger.debug(
            f"Usando máximos persistentes - Disco: {current_max_disk:.2f} B/s, Rede: {current_max_network:.2f} B/s")

    return current_max_disk, current_max_network


def update_usage(disk_rate, network_rate):
    """Atualiza os dados de uso atual com as taxas calculadas"""
    logger.debug(
        f"Atualizando uso - Disco: {disk_rate:.2f} B/s, Rede: {network_rate:.2f} B/s")

    data = get_data()
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Obter valores máximos (persistentes - só atualizados se valores maiores forem encontrados)
    max_disk, max_network = update_max_usage_persistent(
        disk_rate, network_rate)

    # Calcular porcentagens de uso baseadas nos máximos persistentes
    disk_percent = (disk_rate / max_disk * 100) if max_disk > 0 else 0
    network_percent = (network_rate / max_network *
                       100) if max_network > 0 else 0

    logger.debug(
        f"Porcentagens calculadas - Disco: {disk_percent:.2f}%, Rede: {network_percent:.2f}%")

    # Verificar se está abaixo dos limiares configurados
    config = data["config"]
    below_threshold = (disk_percent < config["disk_threshold"] and
                       network_percent < config["network_threshold"])

    if below_threshold:
        logger.debug(f"Uso abaixo dos limiares - Disco: {disk_percent:.2f}% < {config['disk_threshold']}%, "
                     f"Rede: {network_percent:.2f}% < {config['network_threshold']}%")

    # Calcular tempo restante para desligamento se timer ativo
    idle_time_remaining = 0
    if idle_timer_active and below_threshold:
        try:
            elapsed_time = (
                time.time() - last_activity_time.get("start_time", time.time())) / 60
            idle_time_remaining = max(
                0, config["idle_time_threshold"] - elapsed_time)
            logger.debug(
                f"Timer inatividade - Decorrido: {elapsed_time:.2f} min, Restante: {idle_time_remaining:.2f} min")
        except Exception as e:
            logger.error(f"Erro ao calcular tempo de inatividade: {e}")
            idle_time_remaining = 0

    # Atualizar dados de uso (NÃO sobrescrever max_usage aqui)
    data["usage"] = {
        "disk_usage": round(disk_rate, 2),
        "network_usage": round(network_rate, 2),
        "disk_usage_percent": round(disk_percent, 2),
        "network_usage_percent": round(network_percent, 2),
        "max_disk_usage": round(max_disk, 2),  # Usar valor persistente
        "max_network_usage": round(max_network, 2),  # Usar valor persistente
        "active_disk": "sistema",
        "active_interface": "total",
        "idle_timer_active": idle_timer_active,
        "idle_time_remaining": round(idle_time_remaining, 1),
        "shutdown_scheduled": shutdown_scheduled,
        "below_threshold": below_threshold,
        "last_updated": current_time
    }

    # Atualizar histórico periodicamente (a cada 15 minutos)
    current_timestamp = time.time()
    last_history_update = data.get("last_history_update", 0)
    if current_timestamp - last_history_update > 900:  # 15 minutos em segundos
        logger.info(
            "Adicionando ponto ao histórico (intervalo de 15 minutos atingido).")
        update_history(disk_rate, network_rate, disk_percent, network_percent)
        data["last_history_update"] = current_timestamp

    save_data(data)
    return data["usage"]


def update_history(disk_usage, network_usage, disk_percent, network_percent):
    """Adiciona um novo ponto ao histórico (limitado a 24 pontos = 24 horas)"""
    logger.debug("Atualizando histórico de uso.")
    data = get_data()
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    new_point = {
        "timestamp": current_time,
        "disk_usage": round(disk_usage, 2),
        "network_usage": round(network_usage, 2),
        "disk_usage_percent": round(disk_percent, 2),
        "network_usage_percent": round(network_percent, 2),
        "active_disk": "sistema",
        "active_interface": "total"
    }

    # Adicionar novo ponto ao histórico
    history = data.get("history", [])
    history.append(new_point)

    # Manter apenas os últimos 24 pontos (6 horas com medições a cada 15 min)
    if len(history) > 24:
        logger.debug(
            f"Removendo pontos antigos do histórico (total: {len(history)} pontos).")
        history = history[-24:]

    data["history"] = history
    logger.info(f"Histórico atualizado. Agora com {len(history)} pontos.")
    save_data(data)


def check_usage_thresholds():
    """Verifica se o uso está abaixo dos limites e controla o timer de inatividade"""
    global idle_timer_active, shutdown_scheduled

    data = get_data()
    config = data["config"]
    usage = data["usage"]
    now = time.time()

    # Obter as porcentagens atuais
    disk_percent = usage.get("disk_usage_percent", 0)
    network_percent = usage.get("network_usage_percent", 0)

    # Verificar se ambos estão abaixo dos limites
    below_threshold = (disk_percent < config["disk_threshold"] and
                       network_percent < config["network_threshold"])

    # Lógica para controlar o timer de inatividade
    if below_threshold:
        if not idle_timer_active:
            # Iniciar o timer
            idle_timer_active = True
            last_activity_time["start_time"] = now
            logger.info(
                f"Uso abaixo do limite detectado. Iniciando temporizador de {config['idle_time_threshold']} minutos.")
            logger.info(
                f"Limiares: Disco < {config['disk_threshold']}% (atual: {disk_percent:.2f}%), Rede < {config['network_threshold']}% (atual: {network_percent:.2f}%)")
        else:
            # Verificar se o tempo de inatividade foi excedido
            try:
                idle_minutes = (now - last_activity_time["start_time"]) / 60
                logger.debug(
                    f"Tempo abaixo do limite: {idle_minutes:.2f} minutos / {config['idle_time_threshold']} minutos")

                if idle_minutes >= config["idle_time_threshold"] and not shutdown_scheduled:
                    # Tempo de inatividade excedido, desligar o computador
                    shutdown_scheduled = True
                    logger.warning(
                        f"Tempo de inatividade de {config['idle_time_threshold']} minutos excedido.")

                    if not config["debug_mode"]:
                        logger.critical(
                            "Desligando o computador em 60 segundos...")
                        # Código para desligar o computador
                        if os.name == "nt":  # Windows
                            os.system("shutdown /s /t 60")
                            logger.info(
                                "Comando de desligamento enviado no Windows: shutdown /s /t 60")
                        else:  # Linux/Mac
                            os.system("shutdown -h +1")
                            logger.info(
                                "Comando de desligamento enviado no Linux/Mac: shutdown -h +1")
                    else:
                        logger.info(
                            "Modo de debug ativado: o desligamento foi simulado, mas não executado.")
            except Exception as e:
                logger.error(f"Erro ao verificar tempo de inatividade: {e}")
    else:
        # Uso subiu acima do limite, reiniciar o timer
        if idle_timer_active:
            idle_timer_active = False
            shutdown_scheduled = False
            logger.info(
                "Uso subiu acima do limite. Temporizador de inatividade resetado.")
            logger.info(
                f"Uso atual: Disco {disk_percent:.2f}%, Rede {network_percent:.2f}%")


def monitor_resources():
    """Função principal de monitoramento que executa em um thread separado"""
    global monitoring_active

    logger.info("Thread de monitoramento iniciada.")

    while monitoring_active:
        try:
            config = get_data()["config"]
            monitor_interval = config["monitor_interval"]

            logger.debug(
                f"Iniciando ciclo de monitoramento (intervalo: {monitor_interval}s)")

            # Calcular taxas de uso baseadas na diferença entre medições
            disk_rate, network_rate = calculate_usage_rates()

            # Atualizar dados de uso (máximos persistentes só atualizados se necessário)
            update_usage(disk_rate, network_rate)

            # Verificar limites e considerar desligamento
            check_usage_thresholds()

            # Aguardar até o próximo intervalo de monitoramento
            logger.debug(
                f"Aguardando {monitor_interval}s até o próximo ciclo.")
            time.sleep(monitor_interval)

        except Exception as e:
            logger.error(f"Erro durante o monitoramento: {e}", exc_info=True)
            logger.info("Aguardando 5 segundos antes de tentar novamente.")
            time.sleep(5)

    logger.info("Thread de monitoramento encerrada.")


def start_monitoring():
    """Inicia o monitoramento em um thread separado"""
    global monitoring_active, monitoring_thread

    if not monitoring_active:
        logger.info("Iniciando sistema de monitoramento.")
        monitoring_active = True
        monitoring_thread = threading.Thread(target=monitor_resources)
        monitoring_thread.daemon = True
        monitoring_thread.start()
        logger.info(
            f"Thread de monitoramento iniciada: {monitoring_thread.name}")
    else:
        logger.warning(
            "Tentativa de iniciar monitoramento, mas já está ativo.")


def stop_monitoring():
    """Para o monitoramento"""
    global monitoring_active

    if monitoring_active:
        logger.info("Parando sistema de monitoramento.")
        monitoring_active = False

        if monitoring_thread:
            logger.debug(
                f"Aguardando encerramento da thread: {monitoring_thread.name}")
            monitoring_thread.join(timeout=2)
            if monitoring_thread.is_alive():
                logger.warning(
                    "Thread de monitoramento não encerrou no timeout especificado.")
            else:
                logger.info("Thread de monitoramento encerrada com sucesso.")
    else:
        logger.warning("Tentativa de parar monitoramento, mas não está ativo.")


def get_disks_info():
    """Obtém informações detalhadas sobre todos os discos disponíveis"""
    disks_info = {}
    try:
        if os.name == "nt":  # Windows
            # No Windows, usar psutil para obter informações de disco
            all_disks = psutil.disk_io_counters(perdisk=True)
            if all_disks:
                for disk_name, disk_io in all_disks.items():
                    disks_info[disk_name] = {
                        'read_bytes': disk_io.read_bytes,
                        'write_bytes': disk_io.write_bytes,
                        'total_bytes': disk_io.read_bytes + disk_io.write_bytes,
                        'read_count': disk_io.read_count,
                        'write_count': disk_io.write_count
                    }
        else:  # Linux/DietPi
            # Tentar ler /proc/diskstats primeiro
            try:
                with open('/proc/diskstats', 'r') as f:
                    disk_stats = f.readlines()

                for line in disk_stats:
                    parts = line.split()
                    if len(parts) < 14:
                        continue

                    dev_name = parts[2]
                    # Filtrar apenas discos físicos (ignorar partições)
                    if dev_name.startswith(('sd', 'hd', 'vd', 'nvme', 'mmcblk')):
                        # Calcular bytes (leitura + escrita)
                        bytes_read = int(parts[5]) * 512
                        bytes_written = int(parts[9]) * 512

                        disks_info[dev_name] = {
                            'read_bytes': bytes_read,
                            'write_bytes': bytes_written,
                            'total_bytes': bytes_read + bytes_written,
                            'read_count': int(parts[3]),
                            'write_count': int(parts[7])
                        }
            except Exception as e:
                logger.error(f"Erro ao ler /proc/diskstats: {e}")

                # Método alternativo: psutil
                try:
                    all_disks = psutil.disk_io_counters(perdisk=True)
                    if all_disks:
                        for disk_name, disk_io in all_disks.items():
                            disks_info[disk_name] = {
                                'read_bytes': disk_io.read_bytes,
                                'write_bytes': disk_io.write_bytes,
                                'total_bytes': disk_io.read_bytes + disk_io.write_bytes,
                                'read_count': disk_io.read_count,
                                'write_count': disk_io.write_count
                            }
                except Exception as e2:
                    logger.error(
                        f"Erro ao obter info de disco via psutil: {e2}")

            # Adicionar informações de espaço em disco para partições montadas
            try:
                partitions = psutil.disk_partitions(all=False)
                for part in partitions:
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        disks_info[f"mount_{part.device.replace('/', '_')}"] = {
                            'device': part.device,
                            'mountpoint': part.mountpoint,
                            'fstype': part.fstype,
                            'total_space': usage.total,
                            'used_space': usage.used,
                            'free_space': usage.free,
                            'percent_used': usage.percent
                        }
                    except:
                        pass
            except Exception as e:
                logger.error(f"Erro ao obter informações de partições: {e}")

    except Exception as e:
        logger.error(f"Erro geral ao obter informações de disco: {e}")

    return disks_info


def get_network_info():
    """Obtém informações detalhadas sobre todas as interfaces de rede"""
    net_info = {}
    try:
        if os.name == "nt":  # Windows
            # No Windows, usar psutil para obter informações de rede
            all_interfaces = psutil.net_io_counters(pernic=True)
            if all_interfaces:
                for if_name, if_io in all_interfaces.items():
                    net_info[if_name] = {
                        'bytes_sent': if_io.bytes_sent,
                        'bytes_recv': if_io.bytes_recv,
                        'total_bytes': if_io.bytes_sent + if_io.bytes_recv,
                        'packets_sent': if_io.packets_sent,
                        'packets_recv': if_io.packets_recv,
                        'errin': if_io.errin,
                        'errout': if_io.errout,
                        'dropin': if_io.dropin,
                        'dropout': if_io.dropout
                    }
        else:  # Linux/DietPi
            # Tentar ler /proc/net/dev primeiro
            try:
                with open('/proc/net/dev', 'r') as f:
                    net_data = f.readlines()[2:]  # Pular cabeçalhos

                for line in net_data:
                    if ':' in line:
                        interface = line.split(':')[0].strip()
                        values = line.split(':')[1].split()

                        # Formato típico de /proc/net/dev:
                        # bytes_recv packets_recv errin dropin fifo frame compressed multicast
                        # bytes_sent packets_sent errout dropout fifo colls carrier compressed
                        if len(values) >= 16:
                            bytes_recv = int(values[0])
                            packets_recv = int(values[1])
                            errin = int(values[2])
                            dropin = int(values[3])

                            bytes_sent = int(values[8])
                            packets_sent = int(values[9])
                            errout = int(values[10])
                            dropout = int(values[11])

                            net_info[interface] = {
                                'bytes_recv': bytes_recv,
                                'bytes_sent': bytes_sent,
                                'total_bytes': bytes_recv + bytes_sent,
                                'packets_recv': packets_recv,
                                'packets_sent': packets_sent,
                                'errin': errin,
                                'errout': errout,
                                'dropin': dropin,
                                'dropout': dropout
                            }
            except Exception as e:
                logger.error(f"Erro ao ler /proc/net/dev: {e}")

                # Método alternativo: psutil
                try:
                    all_interfaces = psutil.net_io_counters(pernic=True)
                    if all_interfaces:
                        for if_name, if_io in all_interfaces.items():
                            net_info[if_name] = {
                                'bytes_sent': if_io.bytes_sent,
                                'bytes_recv': if_io.bytes_recv,
                                'total_bytes': if_io.bytes_sent + if_io.bytes_recv,
                                'packets_sent': if_io.packets_sent,
                                'packets_recv': if_io.packets_recv,
                                'errin': if_io.errin,
                                'errout': if_io.errout,
                                'dropin': if_io.dropin,
                                'dropout': if_io.dropout
                            }
                except Exception as e2:
                    logger.error(
                        f"Erro ao obter info de rede via psutil: {e2}")

            # Adicionar informações de endereços IP e status das interfaces
            try:
                if hasattr(psutil, "net_if_addrs"):
                    interfaces_addrs = psutil.net_if_addrs()
                    for if_name, addrs in interfaces_addrs.items():
                        if if_name in net_info:
                            net_info[if_name]['addresses'] = []
                            for addr in addrs:
                                addr_info = {
                                    'family': str(addr.family),
                                    'address': addr.address
                                }
                                if addr.netmask:
                                    addr_info['netmask'] = addr.netmask
                                if hasattr(addr, 'broadcast') and addr.broadcast:
                                    addr_info['broadcast'] = addr.broadcast
                                net_info[if_name]['addresses'].append(
                                    addr_info)

                if hasattr(psutil, "net_if_stats"):
                    interfaces_stats = psutil.net_if_stats()
                    for if_name, stats in interfaces_stats.items():
                        if if_name in net_info:
                            net_info[if_name]['isup'] = stats.isup
                            net_info[if_name]['speed'] = stats.speed
                            net_info[if_name]['mtu'] = stats.mtu
            except Exception as e:
                logger.error(f"Erro ao obter detalhes adicionais de rede: {e}")

    except Exception as e:
        logger.error(f"Erro geral ao obter informações de rede: {e}")

    return net_info


# =============================================================================
# ROTAS DA API FLASK
# =============================================================================

@monitorBlueP.route('/dashboard/')
def monitor():
    """Rota para a página principal do dashboard"""
    logger.info("Acesso à página principal do dashboard.")
    return render_template('monitor.html')


@monitorBlueP.route('/api/config', methods=['GET', 'POST'])
def config_route():
    """API para obter e atualizar configurações"""
    if request.method == 'GET':
        logger.info("Solicitação GET para obter configurações.")
        return jsonify(get_config())
    elif request.method == 'POST':
        logger.info("Solicitação POST para atualizar configurações.")
        try:
            new_config = request.json
            logger.debug(f"Novas configurações recebidas: {new_config}")
            update_config(new_config)
            return jsonify({"status": "success", "message": "Configurações atualizadas"})
        except Exception as e:
            logger.error(
                f"Erro ao atualizar configurações: {e}", exc_info=True)
            return jsonify({"status": "error", "message": f"Erro ao atualizar configurações: {str(e)}"}), 500


@monitorBlueP.route('/api/usage', methods=['GET'])
def usage_route():
    """API para obter dados de uso atual"""
    logger.info("Solicitação para obter dados de uso.")
    return jsonify(get_usage())


@monitorBlueP.route('/api/history', methods=['GET'])
def history_route():
    """API para obter histórico de uso"""
    logger.info("Solicitação para obter histórico de uso.")
    data = get_data()
    return jsonify(data.get("history", []))


@monitorBlueP.route('/api/disks', methods=['GET'])
def disks_info_route():
    """API para obter informações detalhadas sobre todos os discos"""
    logger.info("Solicitação para obter informações detalhadas de discos.")
    disks_info = get_disks_info()
    return jsonify(disks_info)


@monitorBlueP.route('/api/network', methods=['GET'])
def network_info_route():
    """API para obter informações detalhadas sobre todas as interfaces de rede"""
    logger.info("Solicitação para obter informações detalhadas de rede.")
    network_info = get_network_info()
    return jsonify(network_info)


@monitorBlueP.route('/api/monitor/start', methods=['POST'])
def start_monitor_route():
    """API para iniciar o monitoramento"""
    logger.info("Solicitação para iniciar monitoramento via API.")
    start_monitoring()
    return jsonify({"status": "success", "message": "Monitoramento iniciado"})


@monitorBlueP.route('/api/monitor/stop', methods=['POST'])
def stop_monitor_route():
    """API para parar o monitoramento"""
    logger.info("Solicitação para parar monitoramento via API.")
    stop_monitoring()
    return jsonify({"status": "success", "message": "Monitoramento parado"})


@monitorBlueP.route('/api/status', methods=['GET'])
def status_route():
    """API para verificar o status do monitoramento"""
    logger.debug("Solicitação para verificar status do monitoramento.")
    data = get_data()
    usage = data["usage"]
    config = data["config"]
    max_data = data["max_usage"]

    status_info = {
        "active": monitoring_active,
        "disk_usage_percent": usage.get("disk_usage_percent", 0),
        "network_usage_percent": usage.get("network_usage_percent", 0),
        "disk_usage_rate": usage.get("disk_usage", 0),
        "network_usage_rate": usage.get("network_usage", 0),
        "max_disk_usage": usage.get("max_disk_usage", 0),
        "max_network_usage": usage.get("max_network_usage", 0),
        "active_disk": usage.get("active_disk", "sistema"),
        "active_interface": usage.get("active_interface", "total"),
        "idle_timer_active": idle_timer_active,
        "idle_time_remaining": usage.get("idle_time_remaining", 0),
        "idle_time_threshold": config.get("idle_time_threshold", 30),
        "shutdown_scheduled": shutdown_scheduled,
        "below_threshold": usage.get("below_threshold", False),
        "debug_mode": config.get("debug_mode", True),
        "disk_threshold": config.get("disk_threshold", 10),
        "network_threshold": config.get("network_threshold", 5),
        # Informações dos máximos persistentes
        "max_disk_date": max_data.get("disk_max_date", ""),
        "max_network_date": max_data.get("network_max_date", ""),
        "disk_records_count": max_data.get("disk_records_count", 0),
        "network_records_count": max_data.get("network_records_count", 0),
        "first_run_date": max_data.get("first_run_date", "")
    }

    logger.debug(f"Status atual: {status_info}")
    return jsonify(status_info)


@monitorBlueP.route('/api/reset-max', methods=['POST'])
def reset_max_route():
    """API para resetar os valores máximos (CUIDADO: remove dados persistentes!)"""
    logger.warning("SOLICITAÇÃO PARA RESETAR VALORES MÁXIMOS PERSISTENTES!")
    data = get_data()
    config = data["config"]
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Backup dos valores atuais antes do reset
    old_max_disk = data["max_usage"].get("max_disk_usage", 0)
    old_max_network = data["max_usage"].get("max_network_usage", 0)

    logger.warning(f"Resetando máximos - Disco: {old_max_disk:.2f} B/s -> {config['min_disk_rate']} B/s, "
                   f"Rede: {old_max_network:.2f} B/s -> {config['min_network_rate']} B/s")

    # Resetar dados dos máximos para valores mínimos
    data["max_usage"] = {
        "max_disk_usage": config["min_disk_rate"],
        "max_network_usage": config["min_network_rate"],
        "disk_max_date": current_time,
        "network_max_date": current_time,
        "disk_records_count": 0,
        "network_records_count": 0,
        "last_updated": current_time,
        # Manter data original
        "first_run_date": data["max_usage"].get("first_run_date", current_time)
    }

    # Resetar valores anteriores para recálculo de taxa
    data["previous_values"] = {
        "disk_total": 0,
        "network_total": 0,
        "timestamp": 0
    }

    save_data(data)
    logger.warning(
        "Valores máximos persistentes foram resetados para os valores mínimos configurados.")

    return jsonify({
        "status": "success",
        "message": "Valores máximos resetados para os mínimos configurados",
        "old_max_disk": old_max_disk,
        "old_max_network": old_max_network,
        "new_max_disk": config["min_disk_rate"],
        "new_max_network": config["min_network_rate"]
    })


@monitorBlueP.route('/api/cancel-shutdown', methods=['POST'])
def cancel_shutdown_route():
    """API para cancelar o desligamento programado"""
    global idle_timer_active, shutdown_scheduled

    logger.warning("Solicitação para cancelar desligamento programado.")
    idle_timer_active = False
    shutdown_scheduled = False

    # Cancelar o desligamento programado no sistema operacional
    try:
        if os.name == "nt":  # Windows
            logger.info(
                "Executando comando para cancelar desligamento no Windows: shutdown /a")
            os.system("shutdown /a")
        else:  # Linux/Mac
            logger.info(
                "Executando comando para cancelar desligamento no Linux/Mac: shutdown -c")
            os.system("shutdown -c")
        logger.info(
            "Comando de cancelamento de desligamento executado com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao cancelar desligamento: {e}", exc_info=True)

    return jsonify({"status": "success", "message": "Desligamento cancelado e timer de inatividade resetado"})


@monitorBlueP.route('/api/max-usage-info', methods=['GET'])
def max_usage_info_route():
    """API para obter informações detalhadas sobre os valores máximos persistentes"""
    logger.debug("Solicitação para obter informações detalhadas dos máximos.")
    data = get_data()
    max_data = data["max_usage"]
    config = data["config"]

    max_info = {
        "max_disk_usage": max_data.get("max_disk_usage", 0),
        "max_network_usage": max_data.get("max_network_usage", 0),
        "max_disk_usage_kb": round(max_data.get("max_disk_usage", 0) / 1024, 2),
        "max_network_usage_kb": round(max_data.get("max_network_usage", 0) / 1024, 2),
        "disk_max_date": max_data.get("disk_max_date", ""),
        "network_max_date": max_data.get("network_max_date", ""),
        "disk_records_count": max_data.get("disk_records_count", 0),
        "network_records_count": max_data.get("network_records_count", 0),
        "last_updated": max_data.get("last_updated", ""),
        "first_run_date": max_data.get("first_run_date", ""),
        "min_disk_rate": config.get("min_disk_rate", 102400),
        "min_network_rate": config.get("min_network_rate", 10240),
        "min_disk_rate_kb": round(config.get("min_disk_rate", 102400) / 1024, 2),
        "min_network_rate_kb": round(config.get("min_network_rate", 10240) / 1024, 2)
    }

    return jsonify(max_info)

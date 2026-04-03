#!/usr/bin/env python3
# monitor.py - Sistema de monitoramento de recursos

from flask import render_template, jsonify, request, Blueprint
import psutil
import time
import os
import socket
import threading
import datetime
from logger_config import setup_logger
import database as db

logger = setup_logger(__name__)

monitorBlueP = Blueprint("monitor", __name__)

# ---------------------------------------------------------------------------
# Estado em memória (não precisa de persistência entre requests)
# ---------------------------------------------------------------------------
monitoring_active = False
monitoring_thread = None
idle_timer_active = False
shutdown_scheduled = False
last_activity_time = {}


# ---------------------------------------------------------------------------
# Leitura de I/O cumulativo
# ---------------------------------------------------------------------------


def get_disk_usage_cumulative():
    try:
        if os.name == "nt":
            disk = psutil.disk_io_counters()
            return (disk.read_bytes + disk.write_bytes) if disk else 0
        else:
            with open("/proc/diskstats", "r") as f:
                lines = f.readlines()
            total = 0
            for line in lines:
                parts = line.split()
                if len(parts) < 14:
                    continue
                dev = parts[2]
                if not dev.startswith(("sd", "hd", "vd", "nvme", "mmcblk")):
                    continue
                if "nvme" in dev and "p" in dev:
                    continue
                if any(c.isdigit() for c in dev[-2:]) and "nvme" not in dev:
                    continue
                total += (int(parts[5]) + int(parts[9])) * 512
            return total
    except Exception:
        try:
            disk = psutil.disk_io_counters()
            return (disk.read_bytes + disk.write_bytes) if disk else 0
        except Exception:
            return 0


def get_network_usage_cumulative():
    try:
        if os.name == "nt":
            net = psutil.net_io_counters()
            return (net.bytes_sent + net.bytes_recv) if net else 0
        else:
            with open("/proc/net/dev", "r") as f:
                lines = f.readlines()[2:]
            total = 0
            for line in lines:
                if ":" not in line:
                    continue
                iface = line.split(":")[0].strip()
                if iface == "lo":
                    continue
                values = line.split(":")[1].split()
                if len(values) >= 9:
                    total += int(values[0]) + int(values[8])
            return total
    except Exception:
        try:
            net = psutil.net_io_counters()
            return (net.bytes_sent + net.bytes_recv) if net else 0
        except Exception:
            return 0


# ---------------------------------------------------------------------------
# Cálculo de taxas
# ---------------------------------------------------------------------------


def calculate_usage_rates():
    """
    Lê os valores cumulativos anteriores do banco, calcula a taxa desde
    a última medição e persiste os novos valores base.
    Retorna (disk_rate, network_rate) em bytes/s.
    """
    current_time = time.time()
    current_disk = get_disk_usage_cumulative()
    current_net = get_network_usage_cumulative()

    prev = db.get_monitor_state(
        "previous_values", {"disk_total": 0, "network_total": 0, "timestamp": 0}
    )

    if prev["timestamp"] == 0:
        db.set_monitor_state(
            "previous_values",
            {
                "disk_total": current_disk,
                "network_total": current_net,
                "timestamp": current_time,
            },
        )
        logger.info("Primeira medição — inicializando valores base.")
        return 0, 0

    time_diff = current_time - prev["timestamp"]
    if time_diff <= 0:
        return 0, 0

    disk_rate = max(0, (current_disk - prev["disk_total"]) / time_diff)
    net_rate = max(0, (current_net - prev["network_total"]) / time_diff)

    db.set_monitor_state(
        "previous_values",
        {
            "disk_total": current_disk,
            "network_total": current_net,
            "timestamp": current_time,
        },
    )

    return disk_rate, net_rate


# ---------------------------------------------------------------------------
# Atualização de uso atual
# ---------------------------------------------------------------------------


def update_usage(disk_rate, network_rate):
    config = db.get_monitor_config()

    # Atualiza máximos atomicamente — não afeta nenhum outro dado
    max_disk, max_net = db.update_max_if_greater(
        disk_rate, network_rate, config["min_disk_rate"], config["min_network_rate"]
    )

    disk_percent = (disk_rate / max_disk * 100) if max_disk > 0 else 0
    net_percent = (network_rate / max_net * 100) if max_net > 0 else 0

    below = (
        disk_percent < config["disk_threshold"]
        and net_percent < config["network_threshold"]
    )

    idle_remaining = 0
    if idle_timer_active and below:
        elapsed = (time.time() - last_activity_time.get("start_time", time.time())) / 60
        idle_remaining = max(0, config["idle_time_threshold"] - elapsed)

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    usage = {
        "disk_usage": round(disk_rate, 2),
        "network_usage": round(network_rate, 2),
        "disk_usage_percent": round(disk_percent, 2),
        "network_usage_percent": round(net_percent, 2),
        "max_disk_usage": round(max_disk, 2),
        "max_network_usage": round(max_net, 2),
        "below_threshold": below,
        "idle_timer_active": idle_timer_active,
        "idle_time_remaining": round(idle_remaining, 1),
        "shutdown_scheduled": shutdown_scheduled,
        "last_updated": now,
    }
    db.set_monitor_state("current_usage", usage)

    # Histórico a cada 15 min
    last_hist = db.get_monitor_state("last_history_ts", 0)
    if time.time() - last_hist > 900:
        db.add_history_point(disk_rate, network_rate, disk_percent, net_percent)
        db.set_monitor_state("last_history_ts", time.time())

    return usage


# ---------------------------------------------------------------------------
# Verificação de limiares e desligamento
# ---------------------------------------------------------------------------


def check_usage_thresholds():
    global idle_timer_active, shutdown_scheduled

    usage = db.get_monitor_state("current_usage", {})
    config = db.get_monitor_config()
    now = time.time()

    disk_pct = usage.get("disk_usage_percent", 0)
    net_pct = usage.get("network_usage_percent", 0)
    below = (
        disk_pct < config["disk_threshold"] and net_pct < config["network_threshold"]
    )

    if below:
        if not idle_timer_active:
            idle_timer_active = True
            last_activity_time["start_time"] = now
            logger.info(
                f"Inatividade detectada. Timer de {config['idle_time_threshold']} min iniciado."
            )
        else:
            idle_minutes = (now - last_activity_time["start_time"]) / 60
            if idle_minutes >= config["idle_time_threshold"] and not shutdown_scheduled:
                shutdown_scheduled = True
                if not config["debug_mode"]:
                    cmd = "shutdown /s /t 60" if os.name == "nt" else "shutdown -h +1"
                    os.system(cmd)
                    logger.critical(f"Desligamento agendado: {cmd}")
                else:
                    logger.info("Modo debug: desligamento simulado.")
    else:
        if idle_timer_active:
            idle_timer_active = False
            shutdown_scheduled = False
            logger.info("Uso voltou acima do limite. Timer resetado.")


# ---------------------------------------------------------------------------
# Thread de monitoramento
# ---------------------------------------------------------------------------


def monitor_resources():
    global monitoring_active
    logger.info("Thread de monitoramento iniciada.")
    while monitoring_active:
        try:
            config = db.get_monitor_config()
            disk, net = calculate_usage_rates()
            update_usage(disk, net)
            check_usage_thresholds()
            time.sleep(config["monitor_interval"])
        except Exception as e:
            logger.error(f"Erro no ciclo de monitoramento: {e}", exc_info=True)
            time.sleep(5)
    logger.info("Thread de monitoramento encerrada.")


def start_monitoring():
    global monitoring_active, monitoring_thread
    if not monitoring_active:
        monitoring_active = True
        monitoring_thread = threading.Thread(target=monitor_resources, daemon=True)
        monitoring_thread.start()
        logger.info("Monitoramento iniciado.")


def stop_monitoring():
    global monitoring_active
    if monitoring_active:
        monitoring_active = False
        if monitoring_thread:
            monitoring_thread.join(timeout=2)
        logger.info("Monitoramento parado.")


# ---------------------------------------------------------------------------
# Informações de discos e rede (para os endpoints detalhados)
# ---------------------------------------------------------------------------


def get_disks_info():
    info = {}
    try:
        if os.name == "nt":
            for name, io in (psutil.disk_io_counters(perdisk=True) or {}).items():
                info[name] = {
                    "read_bytes": io.read_bytes,
                    "write_bytes": io.write_bytes,
                    "total_bytes": io.read_bytes + io.write_bytes,
                }
        else:
            try:
                with open("/proc/diskstats", "r") as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) < 14:
                            continue
                        dev = parts[2]
                        if dev.startswith(("sd", "hd", "vd", "nvme", "mmcblk")):
                            r = int(parts[5]) * 512
                            w = int(parts[9]) * 512
                            info[dev] = {
                                "read_bytes": r,
                                "write_bytes": w,
                                "total_bytes": r + w,
                            }
            except Exception:
                pass
            try:
                for part in psutil.disk_partitions(all=False):
                    try:
                        u = psutil.disk_usage(part.mountpoint)
                        info[f"mount_{part.device.replace('/', '_')}"] = {
                            "device": part.device,
                            "mountpoint": part.mountpoint,
                            "total_space": u.total,
                            "used_space": u.used,
                            "free_space": u.free,
                            "percent_used": u.percent,
                        }
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Erro ao obter info de disco: {e}")
    return info


def get_network_info():
    info = {}
    try:
        if os.name == "nt":
            for name, io in (psutil.net_io_counters(pernic=True) or {}).items():
                info[name] = {
                    "bytes_sent": io.bytes_sent,
                    "bytes_recv": io.bytes_recv,
                    "total_bytes": io.bytes_sent + io.bytes_recv,
                }
        else:
            try:
                with open("/proc/net/dev", "r") as f:
                    for line in f.readlines()[2:]:
                        if ":" not in line:
                            continue
                        iface = line.split(":")[0].strip()
                        values = line.split(":")[1].split()
                        if len(values) >= 16:
                            info[iface] = {
                                "bytes_recv": int(values[0]),
                                "bytes_sent": int(values[8]),
                                "total_bytes": int(values[0]) + int(values[8]),
                            }
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Erro ao obter info de rede: {e}")
    return info


# ---------------------------------------------------------------------------
# Rotas da API
# ---------------------------------------------------------------------------


@monitorBlueP.route("/dashboard/")
def monitor():
    return render_template("monitor.html")


@monitorBlueP.route("/api/config", methods=["GET", "POST"])
def config_route():
    if request.method == "GET":
        return jsonify(db.get_monitor_config())
    try:
        db.set_monitor_config(request.json)
        return jsonify({"status": "success", "message": "Configurações atualizadas"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@monitorBlueP.route("/api/usage", methods=["GET"])
def usage_route():
    usage = db.get_monitor_state(
        "current_usage",
        {
            "disk_usage": 0,
            "network_usage": 0,
            "disk_usage_percent": 0,
            "network_usage_percent": 0,
            "max_disk_usage": 0,
            "max_network_usage": 0,
            "below_threshold": False,
            "idle_timer_active": False,
            "idle_time_remaining": 0,
            "shutdown_scheduled": False,
            "last_updated": "",
        },
    )
    return jsonify(usage)


@monitorBlueP.route("/api/history", methods=["GET"])
def history_route():
    return jsonify(db.get_history(hours=12))


@monitorBlueP.route("/api/disks", methods=["GET"])
def disks_info_route():
    return jsonify(get_disks_info())


@monitorBlueP.route("/api/network", methods=["GET"])
def network_info_route():
    return jsonify(get_network_info())


@monitorBlueP.route("/api/monitor/start", methods=["POST"])
def start_monitor_route():
    start_monitoring()
    return jsonify({"status": "success", "message": "Monitoramento iniciado"})


@monitorBlueP.route("/api/monitor/stop", methods=["POST"])
def stop_monitor_route():
    stop_monitoring()
    return jsonify({"status": "success", "message": "Monitoramento parado"})


@monitorBlueP.route("/api/status", methods=["GET"])
def status_route():
    usage = db.get_monitor_state("current_usage", {})
    config = db.get_monitor_config()
    max_u = db.get_max_usage()

    return jsonify(
        {
            "active": monitoring_active,
            "disk_usage_percent": usage.get("disk_usage_percent", 0),
            "network_usage_percent": usage.get("network_usage_percent", 0),
            "disk_usage_rate": usage.get("disk_usage", 0),
            "network_usage_rate": usage.get("network_usage", 0),
            "max_disk_usage": usage.get("max_disk_usage", 0),
            "max_network_usage": usage.get("max_network_usage", 0),
            "idle_timer_active": idle_timer_active,
            "idle_time_remaining": usage.get("idle_time_remaining", 0),
            "idle_time_threshold": config.get("idle_time_threshold", 30),
            "shutdown_scheduled": shutdown_scheduled,
            "below_threshold": usage.get("below_threshold", False),
            "debug_mode": config.get("debug_mode", True),
            "disk_threshold": config.get("disk_threshold", 10),
            "network_threshold": config.get("network_threshold", 5),
            "calibration_completed": True,
            "max_disk_date": max_u.get("disk_max_date", ""),
            "max_network_date": max_u.get("network_max_date", ""),
            "disk_records_count": max_u.get("disk_records_count", 0),
            "network_records_count": max_u.get("network_records_count", 0),
            "first_run_date": max_u.get("first_run_date", ""),
        }
    )


@monitorBlueP.route("/api/reset-max", methods=["POST"])
def reset_max_route():
    config = db.get_monitor_config()
    old = db.get_max_usage()
    db.reset_max_usage(config["min_disk_rate"], config["min_network_rate"])
    db.set_monitor_state(
        "previous_values", {"disk_total": 0, "network_total": 0, "timestamp": 0}
    )
    logger.warning(
        f"Máximos resetados. Anterior — disco: {old.get('max_disk_usage', 0):.0f} B/s, rede: {old.get('max_network_usage', 0):.0f} B/s"
    )
    return jsonify(
        {
            "status": "success",
            "message": "Valores máximos resetados",
            "old_max_disk": old.get("max_disk_usage", 0),
            "old_max_network": old.get("max_network_usage", 0),
        }
    )


@monitorBlueP.route("/api/cancel-shutdown", methods=["POST"])
def cancel_shutdown_route():
    global idle_timer_active, shutdown_scheduled
    idle_timer_active = False
    shutdown_scheduled = False
    try:
        os.system("shutdown /a" if os.name == "nt" else "shutdown -c")
    except Exception as e:
        logger.error(f"Erro ao cancelar desligamento: {e}")
    return jsonify({"status": "success", "message": "Desligamento cancelado"})


@monitorBlueP.route("/api/max-usage-info", methods=["GET"])
def max_usage_info_route():
    max_u = db.get_max_usage()
    config = db.get_monitor_config()
    return jsonify(
        {
            "max_disk_usage": max_u.get("max_disk_usage", 0),
            "max_network_usage": max_u.get("max_network_usage", 0),
            "max_disk_usage_kb": round(max_u.get("max_disk_usage", 0) / 1024, 2),
            "max_network_usage_kb": round(max_u.get("max_network_usage", 0) / 1024, 2),
            "disk_max_date": max_u.get("disk_max_date", ""),
            "network_max_date": max_u.get("network_max_date", ""),
            "disk_records_count": max_u.get("disk_records_count", 0),
            "network_records_count": max_u.get("network_records_count", 0),
            "first_run_date": max_u.get("first_run_date", ""),
            "min_disk_rate": config["min_disk_rate"],
            "min_network_rate": config["min_network_rate"],
        }
    )


def get_local_ip():
    """Obtém o IP local na rede"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip.startswith("127."):
            try:
                for iface_name, iface_info in psutil.net_if_addrs().items():
                    if iface_name.lower().startswith("lo"):
                        continue
                    for addr in iface_info:
                        if (
                            addr.family == socket.AF_INET
                            and not addr.address.startswith("127.")
                        ):
                            return addr.address
            except Exception:
                pass
        return ip


def get_external_ip():
    """Obtém o IP externo (internet)"""
    import urllib.request

    services = [
        "https://api.ipify.org",
        "https://icanhazip.com",
        "https://ifconfig.me/ip",
    ]
    for service in services:
        try:
            with urllib.request.urlopen(service, timeout=3) as response:
                return response.read().decode("utf-8").strip()
        except Exception:
            continue
    return "N/A"


@monitorBlueP.route("/api/system", methods=["GET"])
def system_info_route():
    info = {}

    try:
        info["hostname"] = socket.gethostname()
        info["ip_local"] = get_local_ip()
        info["ip_external"] = get_external_ip()
    except Exception:
        info["hostname"] = "N/A"
        info["ip_local"] = "N/A"
        info["ip_external"] = "N/A"

    try:
        uptime_s = int(time.time() - psutil.boot_time())
        d, r = divmod(uptime_s, 86400)
        h, r = divmod(r, 3600)
        m = r // 60
        parts = []
        if d:
            parts.append(f"{d}d")
        if h:
            parts.append(f"{h}h")
        parts.append(f"{m}m")
        info["uptime"] = " ".join(parts)
        info["uptime_seconds"] = uptime_s
    except Exception:
        info["uptime"] = "N/A"

    try:
        info["cpu_percent"] = psutil.cpu_percent(interval=0.2)
        info["cpu_count"] = psutil.cpu_count(logical=True)
        info["cpu_count_physical"] = psutil.cpu_count(logical=False)
        freq = psutil.cpu_freq()
        info["cpu_freq_mhz"] = round(freq.current, 0) if freq else None
    except Exception:
        info["cpu_percent"] = 0
        info["cpu_count"] = 0
        info["cpu_freq_mhz"] = None

    try:
        vm = psutil.virtual_memory()
        info["ram_total_mb"] = round(vm.total / 1024 / 1024, 1)
        info["ram_used_mb"] = round(vm.used / 1024 / 1024, 1)
        info["ram_available_mb"] = round(vm.available / 1024 / 1024, 1)
        info["ram_percent"] = vm.percent
    except Exception:
        info["ram_percent"] = 0

    try:
        sw = psutil.swap_memory()
        info["swap_total_mb"] = round(sw.total / 1024 / 1024, 1)
        info["swap_used_mb"] = round(sw.used / 1024 / 1024, 1)
        info["swap_percent"] = sw.percent
    except Exception:
        info["swap_percent"] = 0

    info["temperature"] = None
    try:
        temp_file = "/sys/class/thermal/thermal_zone0/temp"
        if os.path.exists(temp_file):
            with open(temp_file, "r") as f:
                info["temperature"] = round(int(f.read().strip()) / 1000, 1)
        else:
            temps = (
                psutil.sensors_temperatures()
                if hasattr(psutil, "sensors_temperatures")
                else {}
            )
            for entries in temps.values():
                if entries:
                    info["temperature"] = round(entries[0].current, 1)
                    break
    except Exception:
        pass

    info["disk_partitions"] = []
    settings = db.get_settings_namespace()
    download_dir = getattr(settings, "DOWNLOAD_DIR", "/mnt/dietpi_userdata")
    mounts = ["/"]
    if download_dir and download_dir != "/" and os.path.exists(download_dir):
        mounts.append(download_dir)
    for mount in mounts:
        try:
            u = psutil.disk_usage(mount)
            info["disk_partitions"].append(
                {
                    "mount": mount,
                    "total_gb": round(u.total / 1024**3, 1),
                    "used_gb": round(u.used / 1024**3, 1),
                    "free_gb": round(u.free / 1024**3, 1),
                    "percent": u.percent,
                }
            )
        except Exception:
            pass

    try:
        import platform

        info["os"] = platform.platform() if os.name != "nt" else "Windows"
    except Exception:
        info["os"] = "N/A"

    return jsonify(info)

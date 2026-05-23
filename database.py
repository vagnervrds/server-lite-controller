"""
database.py - Camada de acesso ao banco de dados SQLite.
Centraliza todas as operações de persistência do sistema.
"""

import os
import sqlite3
import json
import datetime
import threading
from pathlib import Path
from types import SimpleNamespace
from logger_config import setup_logger

logger = setup_logger(__name__)

DB_FILE = "server.db"
_lock = threading.RLock()

EXPECTED_SCHEMA = {
    "settings": {
        "columns": {
            "key": {"type": "TEXT", "primary": True},
            "value": {"type": "TEXT", "not_null": True},
        }
    },
    "monitor_config": {
        "columns": {
            "key": {"type": "TEXT", "primary": True},
            "value": {"type": "TEXT", "not_null": True},
        }
    },
    "monitor_max_usage": {
        "columns": {
            "id": {"type": "INTEGER", "primary": True, "check": "id = 1"},
            "max_disk_usage": {"type": "REAL", "not_null": True, "default": "0"},
            "max_network_usage": {"type": "REAL", "not_null": True, "default": "0"},
            "disk_max_date": {"type": "TEXT", "not_null": True, "default": "''"},
            "network_max_date": {"type": "TEXT", "not_null": True, "default": "''"},
            "disk_records_count": {"type": "INTEGER", "not_null": True, "default": "0"},
            "network_records_count": {
                "type": "INTEGER",
                "not_null": True,
                "default": "0",
            },
            "last_updated": {"type": "TEXT", "not_null": True, "default": "''"},
            "first_run_date": {"type": "TEXT", "not_null": True, "default": "''"},
        }
    },
    "monitor_history": {
        "columns": {
            "id": {"type": "INTEGER", "primary": True, "autoincrement": True},
            "timestamp": {"type": "TEXT", "not_null": True},
            "disk_usage": {"type": "REAL", "not_null": True, "default": "0"},
            "network_usage": {"type": "REAL", "not_null": True, "default": "0"},
            "disk_usage_percent": {"type": "REAL", "not_null": True, "default": "0"},
            "network_usage_percent": {"type": "REAL", "not_null": True, "default": "0"},
        }
    },
    "monitor_state": {
        "columns": {
            "key": {"type": "TEXT", "primary": True},
            "value": {"type": "TEXT", "not_null": True},
        }
    },
}

# ---------------------------------------------------------------------------
# Conexão e inicialização
# ---------------------------------------------------------------------------


def _connect():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Cria todas as tabelas, verifica schema e insere valores padrão se ainda não existirem."""
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        logger.info("Iniciando inicialização do banco de dados...")

    with _lock:
        with _connect() as conn:
            for table_name, table_def in EXPECTED_SCHEMA.items():
                if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
                    logger.info(f"Criando tabela {table_name} se não existir...")
                conn.execute(_build_create_table_sql(table_name, table_def))
            conn.commit()

    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        logger.info("Verificando e migrando schema...")
    _verify_and_migrate_schema()

    with _lock:
        with _connect() as conn:
            if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
                logger.info("Migrando settings.json...")
            _migrate_settings_json()
            _insert_defaults_settings(
                {
                    "DOWNLOAD_DIR": "/mnt/dietpi_userdata",
                    "delug.DELUGE_HOST": "localhost",
                    "delug.DELUGE_PORT": "58846",
                    "delug.DELUGE_USERNAME": "localclient",
                    "delug.DELUGE_PASSWORD": "",
                }
            )
            _insert_defaults_monitor_config(
                {
                    "monitor_interval": "60",
                    "monitor_duration": "5",
                    "disk_threshold": "10",
                    "network_threshold": "5",
                    "idle_time_threshold": "30",
                    "debug_mode": "true",
                    "min_disk_rate": "102400",
                    "min_network_rate": "10240",
                }
            )
            _ensure_max_usage_row()
            conn.commit()

    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        logger.info("Banco de dados inicializado.")


def _build_create_table_sql(table_name: str, table_def: dict) -> str:
    """Constrói SQL de CREATE TABLE a partir da definição do schema."""
    columns_sql = []
    for col_name, col_def in table_def["columns"].items():
        parts = [col_name, col_def["type"]]
        if col_def.get("primary"):
            parts.append("PRIMARY KEY")
        if col_def.get("autoincrement"):
            parts.append("AUTOINCREMENT")
        if col_def.get("not_null"):
            parts.append("NOT NULL")
        if col_def.get("default") is not None:
            parts.append(f"DEFAULT {col_def['default']}")
        if col_def.get("check"):
            parts.append(f"CHECK ({col_def['check']})")
        columns_sql.append(" ".join(parts))
    return f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns_sql)})"


def _get_table_info(conn, table_name: str) -> dict:
    """Retorna informações das colunas de uma tabela existente."""
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    columns = {}
    for row in cursor.fetchall():
        columns[row["name"]] = {
            "type": row["type"],
            "notnull": bool(row["notnull"]),
            "default": row["dflt_value"],
            "pk": bool(row["pk"]),
        }
    return columns


def _verify_and_migrate_schema():
    """Verifica se o schema do banco corresponde ao esperado e migra se necessário."""
    with _lock:
        with _connect() as conn:
            changes_made = False

            for table_name, expected_def in EXPECTED_SCHEMA.items():
                existing_columns = _get_table_info(conn, table_name)

                for col_name, col_def in expected_def["columns"].items():
                    if col_name not in existing_columns:
                        try:
                            sql = _build_add_column_sql(table_name, col_name, col_def)
                            conn.execute(sql)
                            changes_made = True
                            logger.info(f"Coluna adicionada: {table_name}.{col_name}")
                        except Exception as e:
                            logger.error(
                                f"Erro ao adicionar coluna {table_name}.{col_name}: {e}"
                            )

            if changes_made:
                conn.commit()
                logger.info("Migração de schema concluída.")


def _build_add_column_sql(table_name: str, col_name: str, col_def: dict) -> str:
    """Constrói SQL de ALTER TABLE para adicionar coluna."""
    parts = [col_name, col_def["type"]]
    if col_def.get("not_null"):
        parts.append("NOT NULL")
    if col_def.get("default") is not None:
        parts.append(f"DEFAULT {col_def['default']}")
    return f"ALTER TABLE {table_name} ADD COLUMN {' '.join(parts)}"


def _migrate_settings_json():
    """
    Lê settings.json (ou settings.json.migrated se o original não existir)
    e importa os valores para o banco com INSERT OR REPLACE.
    Roda toda vez que o banco é criado do zero — é idempotente.
    """
    candidates = ["settings.json", "settings.json.migrated"]
    path = next((Path(p) for p in candidates if Path(p).exists()), None)

    if path is None:
        logger.warning("settings.json não encontrado — usando valores padrão.")
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        flat = {}
        for key, value in data.items():
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    flat[f"{key}.{subkey}"] = str(subvalue)
            else:
                flat[key] = str(value)

        with _lock:
            with _connect() as conn:
                for key, value in flat.items():
                    conn.execute(
                        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                        (key, value),
                    )
                conn.commit()

        if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
            logger.info(
                f"Settings carregados de '{path}' — {len(flat)} chaves importadas."
            )

    except Exception as e:
        logger.error(f"Erro ao carregar settings de '{path}': {e}")


def _insert_defaults_settings(defaults):
    with _lock:
        with _connect() as conn:
            for key, value in defaults.items():
                conn.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                    (key, value),
                )
            conn.commit()


def _insert_defaults_monitor_config(defaults):
    with _lock:
        with _connect() as conn:
            for key, value in defaults.items():
                conn.execute(
                    "INSERT OR IGNORE INTO monitor_config (key, value) VALUES (?, ?)",
                    (key, value),
                )
            conn.commit()


def _ensure_max_usage_row():
    now = _now()
    with _lock:
        with _connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO monitor_max_usage "
                "(id, first_run_date, last_updated) VALUES (1, ?, ?)",
                (now, now),
            )
            conn.commit()


def _now():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def get_setting(key: str, default=None):
    with _connect() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value):
    with _lock:
        with _connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value)),
            )
            conn.commit()


def get_settings_namespace() -> SimpleNamespace:
    """
    Retorna as configurações como SimpleNamespace, replicando a estrutura
    que ler_settings() retornava do JSON:
      settings.DOWNLOAD_DIR
      settings.delug.DELUGE_HOST  (etc.)
    """
    with _connect() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()

    flat = {row["key"]: row["value"] for row in rows}
    ns = SimpleNamespace()

    for key, value in flat.items():
        if "." in key:
            parent, child = key.split(".", 1)
            if not hasattr(ns, parent):
                setattr(ns, parent, SimpleNamespace())
            setattr(getattr(ns, parent), child, _cast(value))
        else:
            setattr(ns, key, _cast(value))

    return ns


def set_settings_from_dict(data: dict):
    """Aceita tanto dict plano {'DOWNLOAD_DIR': '...'} quanto aninhado {'delug': {'HOST': ...}}."""
    with _lock:
        with _connect() as conn:
            for key, value in data.items():
                if isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        conn.execute(
                            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                            (f"{key}.{subkey}", str(subvalue)),
                        )
                else:
                    conn.execute(
                        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                        (key, str(value)),
                    )
            conn.commit()


def _cast(value: str):
    """Tenta converter string para int ou float se aplicável."""
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


# ---------------------------------------------------------------------------
# Monitor config
# ---------------------------------------------------------------------------


def get_monitor_config() -> dict:
    with _connect() as conn:
        rows = conn.execute("SELECT key, value FROM monitor_config").fetchall()

    raw = {row["key"]: row["value"] for row in rows}
    return {
        "monitor_interval": int(raw.get("monitor_interval", 60)),
        "monitor_duration": int(raw.get("monitor_duration", 5)),
        "disk_threshold": int(raw.get("disk_threshold", 10)),
        "network_threshold": int(raw.get("network_threshold", 5)),
        "idle_time_threshold": int(raw.get("idle_time_threshold", 30)),
        "debug_mode": raw.get("debug_mode", "true").lower() == "true",
        "shutdown_enabled": raw.get("shutdown_enabled", "false").lower() == "true",
        "min_disk_rate": int(raw.get("min_disk_rate", 102400)),
        "min_network_rate": int(raw.get("min_network_rate", 10240)),
    }


def set_monitor_config(config: dict):
    with _lock:
        with _connect() as conn:
            for key, value in config.items():
                conn.execute(
                    "INSERT OR REPLACE INTO monitor_config (key, value) VALUES (?, ?)",
                    (key, str(value)),
                )
            conn.commit()


# ---------------------------------------------------------------------------
# Monitor max usage  (o ponto crítico — cada campo é atualizado atomicamente)
# ---------------------------------------------------------------------------


def get_max_usage() -> dict:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM monitor_max_usage WHERE id = 1").fetchone()
        return dict(row) if row else {}


def update_max_if_greater(
    disk_rate: float, network_rate: float, min_disk: float, min_network: float
):
    """
    Atualiza o máximo de disco e/ou rede APENAS se o novo valor for maior
    que o atual. Operações independentes — não sobrescrevem o outro campo.
    Retorna (max_disk, max_network) efetivos após a operação.
    """
    now = _now()
    with _lock:
        with _connect() as conn:
            row = conn.execute(
                "SELECT max_disk_usage, max_network_usage FROM monitor_max_usage WHERE id = 1"
            ).fetchone()

            cur_disk = row["max_disk_usage"] or min_disk
            cur_network = row["max_network_usage"] or min_network

            if disk_rate > cur_disk:
                conn.execute(
                    """
                    UPDATE monitor_max_usage
                    SET max_disk_usage     = ?,
                        disk_max_date      = ?,
                        disk_records_count = disk_records_count + 1,
                        last_updated       = ?
                    WHERE id = 1
                """,
                    (disk_rate, now, now),
                )
                cur_disk = disk_rate
                logger.info(f"Novo máximo de disco: {disk_rate:.0f} B/s")

            if network_rate > cur_network:
                conn.execute(
                    """
                    UPDATE monitor_max_usage
                    SET max_network_usage     = ?,
                        network_max_date      = ?,
                        network_records_count = network_records_count + 1,
                        last_updated          = ?
                    WHERE id = 1
                """,
                    (network_rate, now, now),
                )
                cur_network = network_rate
                logger.info(f"Novo máximo de rede: {network_rate:.0f} B/s")

            conn.commit()
            return cur_disk, cur_network


def reset_max_usage(min_disk: float, min_network: float):
    now = _now()
    with _lock:
        with _connect() as conn:
            row = conn.execute(
                "SELECT first_run_date FROM monitor_max_usage WHERE id = 1"
            ).fetchone()
            first_run = row["first_run_date"] if row else now

            conn.execute(
                """
                INSERT OR REPLACE INTO monitor_max_usage
                (id, max_disk_usage, max_network_usage,
                 disk_max_date, network_max_date,
                 disk_records_count, network_records_count,
                 last_updated, first_run_date)
                VALUES (1, ?, ?, ?, ?, 0, 0, ?, ?)
            """,
                (min_disk, min_network, now, now, now, first_run),
            )
            conn.commit()


# ---------------------------------------------------------------------------
# Monitor history
# ---------------------------------------------------------------------------


def add_history_point(
    disk_usage: float, network_usage: float, disk_percent: float, network_percent: float
):
    now = _now()
    with _lock:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO monitor_history
                (timestamp, disk_usage, network_usage, disk_usage_percent, network_usage_percent)
                VALUES (?, ?, ?, ?, ?)
            """,
                (now, disk_usage, network_usage, disk_percent, network_percent),
            )

    # Mantém apenas os últimos 288 pontos (24h com medição a cada 5min)
    conn.execute("""
        DELETE FROM monitor_history
        WHERE id NOT IN (
            SELECT id FROM monitor_history ORDER BY id DESC LIMIT 288
        )
    """)
    conn.commit()


def get_history(limit: int = 288, hours: int = 24) -> list:
    since = (datetime.datetime.utcnow() - datetime.timedelta(hours=hours)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT timestamp, disk_usage, network_usage,
            disk_usage_percent, network_usage_percent
            FROM monitor_history
            WHERE timestamp >= ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (since, limit),
        ).fetchall()
        return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Monitor state (previous_values para cálculo de taxa, etc.)
# ---------------------------------------------------------------------------


def get_monitor_state(key: str, default=None):
    with _connect() as conn:
        row = conn.execute(
            "SELECT value FROM monitor_state WHERE key = ?", (key,)
        ).fetchone()
        if row:
            try:
                return json.loads(row["value"])
            except Exception:
                return row["value"]
        return default


def set_monitor_state(key: str, value):
    with _lock:
        with _connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO monitor_state (key, value) VALUES (?, ?)",
                (key, json.dumps(value)),
            )
            conn.commit()


# Auto-inicializa ao ser importado.
init_db()

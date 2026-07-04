from __future__ import annotations

import io
import json
import os
import re
import tarfile
import threading
import uuid
from datetime import datetime
from pathlib import Path

import docker
import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file

# ── Config ─────────────────────────────────────────────────────────────────────
CONTAINER   = "f2m_engine"
PG_CONTAINER = "f2m_postgres"
ENGINE_DATA_DIR = "/app/engine_data"
PG_DSN      = "postgresql://f2m:change_me_please@postgres:5432/f2m_platform"

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/data/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Файл маппинга: restaurant → числовой префикс (хранится вне БД)
RESTAURANT_PREFIXES_FILE = UPLOAD_DIR / "restaurant_prefixes.json"
DISH_ID_MULTIPLIER = 10_000_000  # original dish_id должен быть < 10 млн

docker_client = docker.from_env()

sessions: dict[str, dict] = {}
tasks: dict[str, dict] = {}
_pipeline_lock = threading.Lock()
_prefixes_lock = threading.Lock()

# ── Engine field schema ────────────────────────────────────────────────────────
ENGINE_FIELDS = [
    {"key": "dish_id",     "label": "ID блюда",       "required": True,  "target_col": "ID блюда",                            "hint": "Уникальный идентификатор (PLU, артикул)"},
    {"key": "dish_name",   "label": "Название",        "required": True,  "target_col": "Название блюда",                      "hint": "Название блюда"},
    {"key": "ingredients", "label": "Состав",          "required": False, "target_col": "Состав",                              "hint": "Состав через запятую. Без — аннотация частичная"},
    {"key": "category",    "label": "Категория",       "required": False, "target_col": "Категория",                           "hint": "Категория раздела меню"},
    {"key": "proteins",    "label": "Белки (г)",       "required": False, "target_col": "Белки / nutrition_facts,proteins",    "hint": "Белки на 100г или на порцию"},
    {"key": "fats",        "label": "Жиры (г)",        "required": False, "target_col": "Жиры / nutrition_facts,fats",         "hint": "Жиры на 100г или на порцию"},
    {"key": "carbs",       "label": "Углеводы (г)",    "required": False, "target_col": "Углеводы / nutrition_facts,carbohydrates", "hint": "Углеводы на 100г или на порцию"},
]

AUTO_DETECT: dict[str, list[str]] = {
    "dish_id":     ["id", "plu", "артикул", "арт", "код"],
    "dish_name":   ["назв", "наим", "name", "блюд", "товар"],
    "ingredients": ["состав", "ingredi", "ингр", "описание"],
    "category":    ["катег", "раздел", "category", "group"],
    "proteins":    ["бел", "protein"],
    "fats":        ["жир", "fat"],
    "carbs":       ["угл", "carb", "carbohydr"],
}

app = Flask(__name__)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", fields=ENGINE_FIELDS)


@app.route("/api/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file:
        return jsonify(error="Файл не прикреплён"), 400

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("xlsx", "xls", "csv"):
        return jsonify(error="Поддерживаются: xlsx, xls, csv"), 400

    file_id = str(uuid.uuid4())[:8]
    path = UPLOAD_DIR / f"{file_id}.{ext}"
    file.save(str(path))

    df = _read_file(path, ext)
    if df is None:
        return jsonify(error="Не удалось прочитать файл"), 400

    df.columns = [str(c).strip() for c in df.columns]
    sessions[file_id] = {"df": df, "path": str(path), "ext": ext, "filename": file.filename}

    auto = _auto_detect_mapping(list(df.columns))
    return jsonify({
        "file_id": file_id,
        "filename": file.filename,
        "columns": list(df.columns),
        "total_rows": len(df),
        "preview": _df_preview(df, 5),
        "auto_mapping": auto,
    })


@app.route("/api/preview", methods=["POST"])
def preview():
    data = request.json or {}
    file_id = data.get("file_id")
    mapping = data.get("mapping", {})

    sess = sessions.get(file_id)
    if not sess:
        return jsonify(error="Сессия истекла, загрузите файл снова"), 400

    df = sess["df"]
    rows, errors, warnings = [], [], []

    for i, (_, row) in enumerate(df.iterrows()):
        mapped: dict[str, str] = {}
        for field in ENGINE_FIELDS:
            col = mapping.get(field["key"])
            if col and col in df.columns:
                val = row[col]
                mapped[field["key"]] = "" if pd.isna(val) else str(val).strip()
            else:
                mapped[field["key"]] = ""

        if not mapped.get("dish_id") and i < 30:
            errors.append(f"Строка {i + 2}: нет ID блюда")
        if not mapped.get("dish_name") and i < 30:
            errors.append(f"Строка {i + 2}: нет названия")
        rows.append(mapped)

    no_ing = sum(1 for r in rows if not r.get("ingredients"))
    if no_ing:
        warnings.append(f"{no_ing} из {len(rows)} блюд без состава — аннотация вкуса будет частичной")

    return jsonify({"rows": rows[:50], "total": len(rows), "errors": errors[:10], "warnings": warnings})


@app.route("/api/load", methods=["POST"])
def load():
    data = request.json or {}
    file_id = data.get("file_id")
    mapping = data.get("mapping", {})
    restaurant = re.sub(r"[^a-zA-Z0-9_\-]", "", (data.get("restaurant") or "").strip())[:64]

    if not restaurant:
        return jsonify(error="Не указан ресторан"), 400

    sess = sessions.get(file_id)
    if not sess:
        return jsonify(error="Сессия истекла"), 400

    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {"status": "running", "log": [], "dishes": 0, "error": None, "started_at": _now()}

    t = threading.Thread(target=_run_pipeline, args=(file_id, mapping, task_id, restaurant), daemon=True)
    t.start()
    return jsonify({"task_id": task_id})


@app.route("/api/task/<task_id>")
def task_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify(error="Не найдено"), 404
    return jsonify(task)


@app.route("/api/status")
def engine_status():
    restaurant = re.sub(r"[^a-zA-Z0-9_\-]", "", request.args.get("restaurant", "").strip())
    if restaurant:
        try:
            sql = (
                f"SELECT COUNT(*), to_char(MAX(updated_at),'DD.MM.YYYY HH24:MI') "
                f"FROM dish_features_cache WHERE restaurant = '{restaurant}'"
            )
            rc, out, _ = _pg_exec(sql)
            if rc == 0 and out.strip():
                parts = out.strip().split('|')
                count = int(parts[0]) if parts[0].strip().isdigit() else 0
                ts    = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
                info  = {"count": count}
                if ts:
                    info["last_updated"] = ts
                return jsonify(info)
        except Exception:
            pass
        return jsonify({"count": 0, "last_updated": None})

    try:
        script = (
            "import json, pathlib; "
            "p = pathlib.Path('/app/engine_data/dish_features_cache.json'); "
            "data = json.loads(p.read_text()) if p.exists() else []; "
            "mtime = p.stat().st_mtime if p.exists() else None; "
            "print(json.dumps({'count': len(data), 'mtime': mtime}))"
        )
        rc, out, _ = _exec(CONTAINER, ["python3", "-c", script])
        if rc == 0 and out.strip():
            info = json.loads(out.strip())
            if info.get("mtime"):
                from datetime import datetime
                ts = datetime.fromtimestamp(info["mtime"])
                info["last_updated"] = ts.strftime("%d.%m.%Y %H:%M")
            return jsonify(info)
    except Exception:
        pass
    return jsonify({"count": 0, "last_updated": None, "error": "Engine unavailable"})


@app.route("/api/reannotate", methods=["POST"])
def reannotate():
    data = request.json or {}
    restaurant = re.sub(r"[^a-zA-Z0-9_\-]", "", (data.get("restaurant") or "").strip())[:64]
    if not restaurant:
        return jsonify({"error": "Укажите ресторан"}), 400

    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {"status": "running", "log": [], "dishes": 0, "error": None, "started_at": _now()}

    def run():
        task = tasks[task_id]
        log = task["log"].append

        with _pipeline_lock:
            try:
                log(f"🔬 Переаннотирую блюда ресторана '{restaurant}'...")

                backup_path = UPLOAD_DIR / f"menu_{restaurant}.xlsx"
                if not backup_path.exists():
                    task["status"] = "error"
                    task["error"] = f"Файл меню для ресторана '{restaurant}' не найден. Загрузите меню заново."
                    log(f"❌ {task['error']}")
                    return

                rc, err = _copy_to_container(CONTAINER, backup_path, "/tmp/menu_upload.xlsx")
                if rc != 0:
                    task["status"] = "error"
                    task["error"] = f"Копирование в контейнер: {err}"
                    log(f"❌ {task['error']}")
                    return
                log("✅ Файл меню загружен в контейнер")

                rc, out, err = _exec(CONTAINER, [
                    "python", "-m", "f2m_engine.cli", "build-dish-features",
                    "--menu", "/tmp/menu_upload.xlsx", "--out", ENGINE_DATA_DIR
                ], timeout=180)
                if rc != 0:
                    task["status"] = "error"
                    task["error"] = (err or out).strip()[:500]
                    log(f"❌ {task['error']}")
                    return
                log("✅ Аннотация завершена")

                log("💾 Импорт в базу...")
                rc, out, err = _exec(CONTAINER, [
                    "python", "-m", "f2m_engine.cli", "import-derived-to-postgres",
                    "--derived", ENGINE_DATA_DIR, "--dsn", PG_DSN
                ], timeout=120)
                if rc != 0:
                    task["status"] = "error"
                    task["error"] = (err or out).strip()[:500]
                    log(f"❌ {task['error']}")
                    return
                log("✅ Данные в базе")

                sql = f"UPDATE dish_features_cache SET restaurant = '{restaurant}' WHERE restaurant IS NULL;"
                rc, _, err = _pg_exec(sql)
                if rc != 0:
                    task["status"] = "error"
                    task["error"] = f"Ресторан не присвоен: {err.strip()[:200]}"
                    log(f"❌ {task['error']}")
                    return
                log(f"✅ Ресторан '{restaurant}' присвоен")

                if not _invalidate_cache(restaurant):
                    log("⚠ Кэш не сброшен (Redis недоступен)")
                else:
                    log("✅ Кэш сброшен")

                task["status"] = "done"
                task["finished_at"] = _now()
                log(f"🎉 Переаннотация ресторана '{restaurant}' завершена")
            except Exception as e:
                task["status"] = "error"
                task["error"] = str(e)
                log(f"❌ {e}")

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"task_id": task_id})


@app.route("/api/restaurants")
def list_restaurants():
    try:
        sql = "SELECT restaurant, COUNT(*) FROM dish_features_cache WHERE restaurant IS NOT NULL GROUP BY restaurant ORDER BY restaurant"
        rc, out, _ = _pg_exec(sql)
        if rc != 0:
            return jsonify([])
        prefixes = _load_prefixes()
        rows = []
        for line in out.strip().splitlines():
            parts = line.strip().split('|')
            if len(parts) == 2 and parts[0].strip():
                name = parts[0].strip()
                rows.append({
                    "restaurant": name,
                    "dish_count": int(parts[1].strip()),
                    "prefix": prefixes.get(name),
                })
        return jsonify(rows)
    except Exception:
        return jsonify([])


@app.route("/api/template")
def download_template():
    buf = io.BytesIO()
    cols = [f["target_col"] for f in ENGINE_FIELDS]
    sample = [
        ["12345", "Борщ классический", "Свёкла, капуста, морковь, томат, говядина", "Супы", 3.5, 2.1, 8.2],
        ["12346", "Цезарь с курицей", "Курица, салат, пармезан, сухарики, соус цезарь", "Салаты", 18.0, 14.0, 6.0],
    ]
    df = pd.DataFrame(sample, columns=cols)
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="Меню", index=False)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="menu_template.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ── Pipeline ───────────────────────────────────────────────────────────────────

def _run_pipeline(file_id: str, mapping: dict, task_id: str, restaurant: str = "default"):
    task = tasks[task_id]
    df = sessions[file_id]["df"]

    def log(msg: str):
        task["log"].append(msg)

    def fail(msg: str):
        task["status"] = "error"
        task["error"] = msg
        log(f"❌ {msg}")

    with _pipeline_lock:
        try:
            log("📋 Формирую Excel...")

            out_cols: dict[str, list] = {}
            for field in ENGINE_FIELDS:
                excel_col = mapping.get(field["key"])
                if excel_col and excel_col in df.columns:
                    out_cols[field["target_col"]] = df[excel_col].tolist()

            if "ID блюда" not in out_cols:
                return fail("Не выбрано поле ID блюда")
            if "Название блюда" not in out_cols:
                return fail("Не выбрано поле Название")

            out_df = pd.DataFrame(out_cols)
            dish_count = len(out_df)
            task["dishes"] = dish_count

            # Применяем числовой префикс для глобальной уникальности dish_id
            prefix = _get_or_create_prefix(restaurant)
            try:
                out_df["ID блюда"] = _apply_prefix(out_df["ID блюда"], prefix)
                log(f"✅ Префикс ресторана #{prefix} → dish_id начинаются с {prefix * DISH_ID_MULTIPLIER}")
            except Exception as e:
                return fail(f"Не удалось применить префикс dish_id: {e}")

            tmp_path = UPLOAD_DIR / f"{task_id}_engine.xlsx"
            with pd.ExcelWriter(str(tmp_path), engine="openpyxl") as writer:
                out_df.to_excel(writer, sheet_name="Меню", index=False)

            log(f"✅ Excel сформирован: {dish_count} блюд")

            # Сохраняем резервную копию для reannotate
            backup_path = UPLOAD_DIR / f"menu_{restaurant}.xlsx"
            import shutil
            shutil.copy2(tmp_path, backup_path)

            log("📦 Копирую файл в контейнер движка...")
            rc, err = _copy_to_container(CONTAINER, tmp_path, "/tmp/menu_upload.xlsx")
            if rc != 0:
                return fail(f"Копирование в контейнер: {err}")
            log("✅ Файл в контейнере")

            log("🔬 Запускаю аннотацию блюд (может занять ~30с)...")
            rc, out, err = _exec(CONTAINER, [
                "python", "-m", "f2m_engine.cli", "build-dish-features",
                "--menu", "/tmp/menu_upload.xlsx", "--out", ENGINE_DATA_DIR
            ], timeout=180)
            if rc != 0:
                return fail(f"build-dish-features: {(err or out).strip()[:500]}")
            log("✅ Аннотация завершена")

            log("💾 Сохраняю в базу данных...")
            rc, out, err = _exec(CONTAINER, [
                "python", "-m", "f2m_engine.cli", "import-derived-to-postgres",
                "--derived", ENGINE_DATA_DIR, "--dsn", PG_DSN
            ], timeout=120)
            if rc != 0:
                return fail(f"import-derived-to-postgres: {(err or out).strip()[:500]}")
            log("✅ Данные в базе")

            log(f"🏷️  Назначаю ресторан '{restaurant}'...")
            sql = f"UPDATE dish_features_cache SET restaurant = '{restaurant}' WHERE restaurant IS NULL;"
            rc, _, err = _pg_exec(sql)
            if rc != 0:
                return fail(f"Ресторан не присвоен: {err.strip()[:200]}")
            log(f"✅ Ресторан '{restaurant}' присвоен")

            log("🗑️  Сбрасываю кэш рекомендаций...")
            if not _invalidate_cache(restaurant):
                log("⚠ Кэш не сброшен (Redis недоступен), рекомендации могут быть устаревшими")
            else:
                log("✅ Кэш сброшен")

            task["status"] = "done"
            task["finished_at"] = _now()
            log(f"🎉 Загружено {dish_count} блюд в ресторан '{restaurant}'. Рекомендации обновлены.")

        except Exception as e:
            fail(str(e))


def _invalidate_cache(restaurant: str | None = None) -> bool:
    pattern = f"recs:{restaurant}:*" if restaurant else "recs:*"
    script = (
        "import redis, os; "
        f"r = redis.from_url(os.environ.get('REDIS_URL','redis://redis:6379/0')); "
        f"[r.delete(k) for k in r.scan_iter(b'{pattern}')]"
    )
    rc, _, _ = _exec(CONTAINER, ["python3", "-c", script], timeout=10)
    return rc == 0


# ── Restaurant prefix helpers ──────────────────────────────────────────────────

def _load_prefixes() -> dict[str, int]:
    if RESTAURANT_PREFIXES_FILE.exists():
        return json.loads(RESTAURANT_PREFIXES_FILE.read_text())
    return {}


def _get_or_create_prefix(restaurant: str) -> int:
    with _prefixes_lock:
        prefixes = _load_prefixes()
        if restaurant not in prefixes:
            next_prefix = max(prefixes.values(), default=0) + 1
            prefixes[restaurant] = next_prefix
            RESTAURANT_PREFIXES_FILE.write_text(json.dumps(prefixes, ensure_ascii=False, indent=2))
        return prefixes[restaurant]


def _apply_prefix(dish_id_series: "pd.Series", prefix: int) -> "pd.Series":
    """Превращает оригинальный dish_id в глобально уникальный: prefix * MULTIPLIER + original_id."""
    return (dish_id_series.astype(str).str.extract(r'(\d+)', expand=False)
            .astype(float).astype(int)
            .apply(lambda x: prefix * DISH_ID_MULTIPLIER + x))


# ── Docker helpers ─────────────────────────────────────────────────────────────

def _exec(container_name: str, cmd: list[str], timeout: int = 60) -> tuple[int, str, str]:
    try:
        container = docker_client.containers.get(container_name)
        result = container.exec_run(cmd, demux=True)
        stdout = result.output[0].decode(errors="replace") if result.output[0] else ""
        stderr = result.output[1].decode(errors="replace") if result.output[1] else ""
        return result.exit_code, stdout, stderr
    except Exception as e:
        return 1, "", str(e)


def _pg_exec(sql: str) -> tuple[int, str, str]:
    return _exec(PG_CONTAINER, [
        "psql", "-U", "f2m", "-d", "f2m_platform", "-t", "-A", "-F", "|", "-c", sql
    ])


def _copy_to_container(container_name: str, local_path: Path, container_path: str) -> tuple[int, str]:
    try:
        container = docker_client.containers.get(container_name)
        data = local_path.read_bytes()

        tar_buf = io.BytesIO()
        with tarfile.open(fileobj=tar_buf, mode="w") as tar:
            info = tarfile.TarInfo(name=os.path.basename(container_path))
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        tar_buf.seek(0)

        container.put_archive(os.path.dirname(container_path), tar_buf)
        return 0, ""
    except Exception as e:
        return 1, str(e)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _read_file(path: Path, ext: str) -> "pd.DataFrame | None":
    try:
        if ext in ("xlsx", "xls"):
            return pd.read_excel(str(path))
        for enc in ("utf-8-sig", "utf-8", "cp1251"):
            try:
                return pd.read_csv(str(path), encoding=enc)
            except UnicodeDecodeError:
                continue
    except Exception:
        pass
    return None


def _df_preview(df: pd.DataFrame, n: int) -> list[dict]:
    return df.head(n).fillna("").astype(str).to_dict("records")


def _auto_detect_mapping(columns: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    cols_lower = {c: c.lower() for c in columns}
    for field_key, hints in AUTO_DETECT.items():
        for col, col_l in cols_lower.items():
            if any(h in col_l for h in hints):
                result[field_key] = col
                break
    return result


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


if __name__ == "__main__":
    print(f"[admin] Upload dir: {UPLOAD_DIR}")
    app.run(host="0.0.0.0", debug=True, port=5050, use_reloader=False)

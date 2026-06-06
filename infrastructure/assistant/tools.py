"""Outils LangChain exposés à l'assistant Nodalys.

Chaque outil ouvre sa propre connexion : c'est l'assistant qui décide
quand interroger la base.

Règle RGPD : les données nominatives sont anonymisées avant transmission
au LLM (initiales pour les noms, masquage des emails).
"""

from __future__ import annotations

import os
from pathlib import Path

from langchain_core.tools import tool
from sqlalchemy import create_engine, text

QUERIES_DIR = Path(__file__).parent.parent / "queries"




def _engine_from_env(env_var: str = "DB_URL"):
    url = os.environ.get(env_var)
    if not url:
        raise RuntimeError(f"Variable d'environnement {env_var!r} non définie.")
    return create_engine(url, future=True)


@tool
def query_db(query_name: str) -> str:
    """Exécute une requête SQL prédéfinie et renvoie toutes les lignes
    avec les données nominatives anonymisées (initiales, emails masqués).

    Requêtes disponibles : contrats_actifs, feedbacks_recents,
    stagiaires_par_session, top_formations.
    """
    # sql_path = QUERIES_DIR / f"{query_name}.sql"
    # if not sql_path.exists():
    #     return "Requête inconnue : {}. Disponibles : {}".format(
    #         query_name,
    #         ", ".join(p.stem for p in QUERIES_DIR.glob("*.sql")),
    #     )
    # sql = sql_path.read_text(encoding="utf-8")
    # engine = _engine_from_env("DB_URL")
    # with engine.connect() as conn:
    #     result = conn.execute(text(sql))
    #     rows = result.fetchall()
    #     col_names = list(result.keys())
    # 
    # if not rows:
    #     return "Aucun résultat."
    # 
    # lines = [_anonymize_row(col_names, row) for row in rows]
    # return f"{len(rows)} résultat(s) — {query_name}\n" + "\n".join(lines)
    raise NotImplementedError(f"Requêtes Postgresql à définir")

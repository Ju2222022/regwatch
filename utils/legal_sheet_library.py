"""
utils/legal_sheet_library.py
Utilitaire partagé pour la bibliothèque de fiches légales.
Gère : lecture, écriture, commit GitHub, index.
"""

import json
import base64
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

ROOT       = Path(__file__).parent.parent
INDEX_FILE = ROOT / "data" / "legal_sheets_index.json"
SHEETS_DIR = ROOT / "data" / "legal_sheets"

GITHUB_REPO = "Ju2222022/regwatch"
GITHUB_API  = "https://api.github.com"


# ── Index helpers ─────────────────────────────────────────────────────────────

def load_index(gh_token: str = "") -> dict:
    """Charge l'index depuis GitHub (source of truth) ou filesystem local."""
    # Essayer GitHub d'abord
    if gh_token:
        try:
            url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/data/legal_sheets_index.json"
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {gh_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            content = base64.b64decode(data["content"]).decode("utf-8")
            return json.loads(content)
        except Exception:
            pass
    # Fallback filesystem local
    if INDEX_FILE.exists():
        with open(INDEX_FILE) as f:
            return json.load(f)
    return {"_meta": {}, "sheets": []}


def save_index(index: dict):
    """Sauvegarde l'index localement (GitHub commit géré séparément)."""
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


def get_sheet_entry(index: dict, category: str, market: str) -> dict | None:
    """Retourne l'entrée d'index pour une CAT + marché donnée, ou None."""
    for sheet in index.get("sheets", []):
        if sheet["category"] == category and sheet["market"] == market:
            return sheet
    return None


def sheet_path(category: str, market: str) -> Path:
    """Chemin local du PDF pour une CAT + marché."""
    return SHEETS_DIR / market / f"{category}.pdf"


def list_available_sheets(index: dict) -> list:
    """Retourne la liste des fiches disponibles sous forme lisible."""
    return [
        {
            "label": f"{s['category']} — {s['market']}",
            "category": s["category"],
            "market": s["market"],
            "filename": s.get("filename", ""),
            "uploaded": s.get("uploaded", ""),
            "size_kb": s.get("size_kb", 0),
        }
        for s in index.get("sheets", [])
    ]


# ── GitHub API helpers ────────────────────────────────────────────────────────

def _github_get_file_sha(gh_token: str, path: str) -> str | None:
    """Récupère le SHA d'un fichier GitHub (nécessaire pour le mettre à jour)."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data.get("sha")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def _github_commit_file(
    gh_token: str,
    path: str,
    content_b64: str,
    message: str,
    sha: str | None = None,
) -> bool:
    """Committe un fichier sur GitHub (créé ou mis à jour)."""
    payload = {
        "message": message,
        "content": content_b64,
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="PUT"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status in (200, 201)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise Exception(f"GitHub commit error {e.code}: {body[:300]}")


# ── Main operations ───────────────────────────────────────────────────────────

def upload_sheet(
    pdf_bytes: bytes,
    filename: str,
    category: str,
    market: str,
    gh_token: str,
) -> tuple[bool, str]:
    """
    Upload une fiche légale PDF vers GitHub et met à jour l'index.
    Returns: (success: bool, message: str)
    """
    if not gh_token:
        return False, "GH_TOKEN not configured in Streamlit secrets."

    github_path = f"data/legal_sheets/{market}/{category}.pdf"
    content_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    # Récupérer le SHA si le fichier existe déjà
    try:
        sha = _github_get_file_sha(gh_token, github_path)
    except Exception as e:
        return False, f"Error checking existing file: {e}"

    # Committer le PDF
    try:
        action = "Update" if sha else "Add"
        _github_commit_file(
            gh_token, github_path, content_b64,
            message=f"feat: {action} legal sheet {category} — {market}",
            sha=sha,
        )
    except Exception as e:
        return False, f"Error uploading PDF: {e}"

    # Mettre à jour l'index local + committer
    index = load_index(gh_token)
    entry = get_sheet_entry(index, category, market)
    new_entry = {
        "category":  category,
        "market":    market,
        "filename":  filename,
        "github_path": github_path,
        "uploaded":  datetime.now().strftime("%Y-%m-%d %H:%M"),
        "size_kb":   round(len(pdf_bytes) / 1024, 1),
    }
    if entry:
        index["sheets"] = [
            new_entry if (s["category"] == category and s["market"] == market) else s
            for s in index["sheets"]
        ]
    else:
        index["sheets"].append(new_entry)

    save_index(index)

    # Committer l'index mis à jour
    index_b64 = base64.b64encode(
        json.dumps(index, indent=2, ensure_ascii=False).encode("utf-8")
    ).decode("utf-8")
    try:
        sha_index = _github_get_file_sha(gh_token, "data/legal_sheets_index.json")
        _github_commit_file(
            gh_token, "data/legal_sheets_index.json", index_b64,
            message=f"chore: update legal sheets index ({category} — {market})",
            sha=sha_index,
        )
    except Exception as e:
        return True, f"PDF uploaded but index commit failed: {e}"

    return True, f"✅ Sheet {category} — {market} uploaded successfully."


def delete_sheet(category: str, market: str, gh_token: str) -> tuple[bool, str]:
    """Supprime une fiche de la bibliothèque (GitHub + index)."""
    if not gh_token:
        return False, "GH_TOKEN not configured."

    github_path = f"data/legal_sheets/{market}/{category}.pdf"

    # Récupérer SHA
    try:
        sha = _github_get_file_sha(gh_token, github_path)
    except Exception as e:
        return False, f"Error: {e}"

    if not sha:
        # Fichier n'existe pas sur GitHub, juste nettoyer l'index
        pass
    else:
        # Supprimer le fichier GitHub
        payload = json.dumps({
            "message": f"feat: Remove legal sheet {category} — {market}",
            "sha": sha,
            "branch": "main",
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{github_path}",
            data=payload,
            headers={
                "Authorization": f"Bearer {gh_token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="DELETE"
        )
        try:
            with urllib.request.urlopen(req, timeout=15):
                pass
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            return False, f"GitHub delete error {e.code}: {body[:200]}"

    # Mettre à jour l'index
    index = load_index()
    index["sheets"] = [
        s for s in index["sheets"]
        if not (s["category"] == category and s["market"] == market)
    ]
    save_index(index)

    # Committer l'index
    try:
        index_b64 = base64.b64encode(
            json.dumps(index, indent=2, ensure_ascii=False).encode("utf-8")
        ).decode("utf-8")
        sha_index = _github_get_file_sha(gh_token, "data/legal_sheets_index.json")
        _github_commit_file(
            gh_token, "data/legal_sheets_index.json", index_b64,
            message=f"chore: remove {category} — {market} from index",
            sha=sha_index,
        )
    except Exception:
        pass

    return True, f"✅ Sheet {category} — {market} deleted."


def fetch_sheet_text(category: str, market: str, gh_token: str = "") -> tuple[str, str]:
    """
    Télécharge et extrait le texte d'une fiche depuis GitHub.
    Returns: (text: str, title: str)
    """
    github_path = f"data/legal_sheets/{market}/{category}.pdf"
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{github_path}"

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"

    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        pdf_bytes = base64.b64decode(data["content"])
    except Exception as e:
        return "", f"Error fetching from GitHub: {e}"

    # Extraire le texte via PyPDF2
    try:
        import io
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        text = "\n".join(
            page.extract_text() or "" for page in reader.pages
        )
        title = f"{category} — {market}"
        return text, title
    except Exception as e:
        return "", f"Error reading PDF: {e}"

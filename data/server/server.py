from pathlib import Path
import logging
from logging import FileHandler

import requests
from flask import Flask, jsonify, send_from_directory

from .crawler import (
    CATEGORIAS,
    RAW_DOCUMENTS_DIR,
    contar_arquivos_baixados,
    carregar_catalogo,
    obter_progresso,
    scrape_bdtd,
)


BASE_DIR = Path(__file__).resolve().parents[2]
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "crawler.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("bdtd-server")
app = Flask(__name__)
LOG_PATH = LOG_DIR / "crawler.log"


def reiniciar_log():
    raiz = logging.getLogger()
    for handler in list(raiz.handlers):
        if isinstance(handler, FileHandler) and Path(handler.baseFilename) == LOG_PATH:
            raiz.removeHandler(handler)
            handler.close()
    if LOG_PATH.exists():
        LOG_PATH.unlink()
    handler = FileHandler(LOG_PATH, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    raiz.addHandler(handler)


def resumo_contadores():
    contadores = contar_arquivos_baixados()
    catalogo = carregar_catalogo()
    return {
        "dissertacoes": contadores["dissertacoes"],
        "teses": contadores["teses"],
        "outros": contadores["outros"],
        "arquivos_fisicos": sum(contadores.values()),
        "documentos_total": len(catalogo), #
    }


@app.route("/api/documentos/<categoria>", methods=["GET"])
def documentos_por_categoria(categoria):
    if categoria not in CATEGORIAS:
        return jsonify({"erro": "Categoria inválida"}), 404

    documentos = []
    catalogo = [item for item in carregar_catalogo() if item["categoria"] == categoria]
    for item in catalogo:
        arquivo = RAW_DOCUMENTS_DIR / categoria / item["arquivo"]
        if arquivo.exists():
            documentos.append({
                "nome": arquivo.name,
                "tamanho": arquivo.stat().st_size,
                "doi": item.get("doi"),
            })
    documentos.sort(key=lambda item: item["nome"].casefold())
    return jsonify({"categoria": categoria, "total": len(documentos), "documentos": documentos})


@app.route("/api/documentos", methods=["GET"])
def todos_documentos():
    documentos = [
        {
            "nome": item["arquivo"],
            "categoria": item["categoria"],
            "titulo": item["titulo"],
            "doi": item.get("doi"),
            "url": f"/arquivos/{item['categoria']}/{item['arquivo']}",
        }
        for item in carregar_catalogo()
        if (RAW_DOCUMENTS_DIR / item["categoria"] / item["arquivo"]).exists()
    ]
    documentos.sort(key=lambda item: item["nome"].casefold())
    return jsonify({"total": len(documentos), "documentos": documentos})


@app.route("/arquivos/<categoria>/<path:nome>", methods=["GET"])
def arquivo_baixado(categoria, nome):
    if categoria not in CATEGORIAS:
        return jsonify({"erro": "Categoria inválida"}), 404
    return send_from_directory(RAW_DOCUMENTS_DIR / categoria, nome, as_attachment=False)


@app.after_request
def permitir_frontend(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


@app.route("/api", methods=["GET"])
def api():
    reiniciar_log()
    logger.info("Requisição recebida em /api")
    try:
        resposta = scrape_bdtd()
        logger.info("Resposta /api pronta: total=%d", resposta["documentos_total"])
        return jsonify(resposta)
    except requests.RequestException as erro:
        return jsonify({"erro": f"Falha ao acessar a API BDTD: {erro}"}), 502
    except ValueError as erro:
        return jsonify({"erro": f"Resposta inválida da API BDTD: {erro}"}), 502


@app.route("/api/contadores", methods=["GET"])
def contadores():
    resposta = resumo_contadores()
    logger.info("Contadores locais: %s", resposta)
    return jsonify(resposta)


@app.route("/api/progresso", methods=["GET"])
def progresso():
    return jsonify(obter_progresso())


if __name__ == "__main__":
    app.run(debug=True)

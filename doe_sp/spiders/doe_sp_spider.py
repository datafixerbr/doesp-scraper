import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import scrapy
from scrapy.http import Response
from scrapy_playwright.page import PageMethod


class DoeSpSpider(scrapy.Spider):
    name = "doesp_spider"
    allowed_domains = ["doe.sp.gov.br", "do-api-web-search.doe.sp.gov.br"]

    BASE_PATH = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    OUTPUT_DIR = "resultados_doe"

    # Diretório de persistência
    OUTPUT_PATH = os.path.join(BASE_PATH, OUTPUT_DIR)

    # URL Base para a montagem dos links das matérias
    BASE_ARTICLE_URL = "https://www.doe.sp.gov.br/"

    def __init__(
        self,
        termos: Optional[str] = None,
        data_inicio: Optional[str] = None,
        data_fim: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)

        if not all([termos, data_inicio, data_fim]):
            self.logger.error(
                "Erro fatal: É necessário fornecer termos, data_inicio e data_fim."
            )
            raise ValueError("Parâmetros obrigatórios ausentes.")

        # Transforma a string separada por vírgulas em uma lista, removendo espaços em branco
        self.lista_termos = [t.strip() for t in termos.split(",")]
        self.data_inicio = data_inicio
        self.data_fim = data_fim

        if not os.path.exists(self.OUTPUT_PATH):
            os.makedirs(self.OUTPUT_PATH)
            self.logger.info(f"Diretório de resultados criado em: {self.OUTPUT_PATH}")

    def start_requests(self):
        self.logger.info(f"Iniciando buscas para {len(self.lista_termos)} termo(s).")

        # Inicia uma requisição de página 1 para CADA termo da lista
        for termo in self.lista_termos:
            yield self.build_api_request(termo_atual=termo, page_number=1)

    def build_api_request(self, termo_atual: str, page_number: int) -> scrapy.Request:
        params = {
            "periodStartingDate": "personalized",
            "PageNumber": str(page_number),
            "Terms[0]": termo_atual,  # A API recebe o termo específico desta iteração
            "FromDate": self.data_inicio,
            "ToDate": self.data_fim,
            "PageSize": "20",
            "SortField": "Date",
        }

        api_url = f"https://do-api-web-search.doe.sp.gov.br/v2/advanced-search/publications?{urlencode(params)}"

        return scrapy.Request(
            url=api_url,
            callback=self.parse_api_response,
            headers={"Accept": "application/json"},
            # Transportamos o termo_atual no meta para não perdê-lo durante a paginação
            meta={"page_number": page_number, "termo_atual": termo_atual},
        )

    def parse_api_response(self, response: Response):
        page_number = response.meta.get("page_number", 1)
        termo_atual = response.meta.get("termo_atual")

        self.logger.info(
            f"API | Termo: '{termo_atual}' | Página {page_number} | Status: {response.status}"
        )

        try:
            data = json.loads(response.text)
            items = data.get("items")

            if not items:
                self.logger.info(f"Fim da busca para o termo '{termo_atual}'.")
                return

            for item in items:
                slug = item.get("slug")
                if not slug:
                    continue

                url_materia = f"{self.BASE_ARTICLE_URL}{slug}"

                yield scrapy.Request(
                    url=url_materia,
                    callback=self.parse_materia,
                    meta={
                        "playwright": True,
                        "playwright_page_methods": [
                            PageMethod(
                                "wait_for_selector",
                                'div[title="HTML Viewer"]',
                                timeout=45000,
                            )
                        ],
                    },
                    errback=self.errback_close_page,
                )

            # Continua a paginação para o TERMO ATUAL
            if len(items) > 0:
                next_page = page_number + 1
                yield self.build_api_request(
                    termo_atual=termo_atual, page_number=next_page
                )

        except json.JSONDecodeError as e:
            self.logger.error(
                f"Falha ao processar JSON. Termo: {termo_atual} | Pág: {page_number}. Erro: {e}"
            )

    def parse_materia(self, response: Response):
        self.logger.info(f"Extraindo dados da URL: {response.url}")

        try:
            # 1. Extração do Conteúdo Principal
            viewer_node = response.xpath('//div[@title="HTML Viewer"]')

            if not viewer_node:
                self.logger.error(
                    f"A div title='HTML Viewer' não foi encontrada em: {response.url}"
                )
                return

            textos_paragrafos = viewer_node.xpath(".//p//text()").getall()
            texto_bruto = " ".join(textos_paragrafos)
            texto_limpo = re.sub(r"\s+", " ", texto_bruto).strip()

            # 2. Extração do Código de Autenticação
            xpath_autenticacao = '//*[contains(text(), "Este documento pode ser verificado pelo código")]/parent::*/following-sibling::div[1]/text()'
            codigo_autenticacao = response.xpath(xpath_autenticacao).get()

            if not codigo_autenticacao:
                codigo_autenticacao = "NAO_LOCALIZADO"
            else:
                codigo_autenticacao = codigo_autenticacao.strip()

            # 3. Formatação e Persistência
            materia_id = response.url.split("-")[-1]
            if not materia_id.isdigit():
                materia_id = str(int(datetime.now(timezone.utc).timestamp() * 1000))

            timestamp_iso = datetime.now(timezone.utc).isoformat()

            conteudo_final = (
                f"Data de Extração: {timestamp_iso}\n"
                f"Código de Autenticação: {codigo_autenticacao}\n"
                f"URL Origem: {response.url}\n"
                f"{'-'*50}\n\n"
                f"{texto_limpo}"
            )

            filepath = os.path.join(self.OUTPUT_PATH, f"{materia_id}.txt")

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(conteudo_final)

            self.logger.info(
                f"Arquivo salvo: {filepath} | Autenticação: {codigo_autenticacao}"
            )

        except Exception as e:
            self.logger.error(f"Erro ao extrair matéria {response.url}: {e}")

    async def errback_close_page(self, failure):
        page = failure.request.meta.get("playwright_page")
        if page:
            await page.close()
        self.logger.error(f"Timeout/Falha na renderização JS: {repr(failure)}")

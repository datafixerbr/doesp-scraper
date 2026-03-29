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
        termo: Optional[str] = None,
        data_inicio: Optional[str] = None,
        data_fim: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)

        # Validação rígida
        if not all([termo, data_inicio, data_fim]):
            self.logger.error(
                "Erro fatal: É necessário fornecer termo, data_inicio e data_fim."
            )
            raise ValueError("Parâmetros obrigatórios ausentes.")

        self.termo = termo
        self.data_inicio = data_inicio
        self.data_fim = data_fim

        if not os.path.exists(self.OUTPUT_PATH):
            os.makedirs(self.OUTPUT_PATH)

    def start_requests(self):
        self.logger.info("Iniciando consumo direto da API do DOE-SP. Página inicial: 1")
        # Inicia a recursão de paginação na página 1
        yield self.build_api_request(page_number=1)

    def build_api_request(self, page_number: int) -> scrapy.Request:
        """Constrói a requisição para a API REST de busca com base na página atual."""
        params = {
            "periodStartingDate": "personalized",
            "PageNumber": str(page_number),
            "Terms[0]": self.termo,
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
            meta={"page_number": page_number},  # Passamos o estado da página via meta
        )

    def parse_api_response(self, response: Response):
        page_number = response.meta.get("page_number", 1)
        self.logger.info(
            f"Processando resposta da API - Página {page_number} | Status: {response.status}"
        )

        try:
            data = json.loads(response.text)
            items = data.get("items")

            # Condição de parada: se não há a chave ou a lista está vazia, esgotamos os resultados
            if not items:
                self.logger.info(
                    f"Fim da paginação alcançado. Nenhum item na página {page_number}."
                )
                return

            self.logger.info(
                f"Página {page_number}: Encontradas {len(items)} publicações. Despachando para renderização..."
            )

            # 1. Processa os itens da página atual
            for item in items:
                slug = item.get("slug")
                if not slug:
                    continue

                url_materia = f"{self.BASE_ARTICLE_URL}{slug}"

                # Despacha o Playwright para a URL da matéria
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

            # 2. Continua a paginação
            # Se a API retornou itens, assumimos que pode haver uma próxima página.
            # O Scrapy gerencia a fila de forma assíncrona, então ele não vai "esperar"
            # as matérias acabarem de baixar para chamar a próxima página da API.
            if len(items) > 0:
                next_page = page_number + 1
                self.logger.info(f"Solicitando próxima página da API: {next_page}...")
                yield self.build_api_request(next_page)

        except json.JSONDecodeError as e:
            self.logger.error(
                f"Falha ao processar o JSON da API na página {page_number}. Erro: {e}"
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

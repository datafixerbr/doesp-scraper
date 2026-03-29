# Scrapy settings for doe_sp project

BOT_NAME = "doe_sp"

SPIDER_MODULES = ["doe_sp.spiders"]
NEWSPIDER_MODULE = "doe_sp.spiders"

ADDONS = {}

# ==============================================================================
# 1. POLÍTICAS DE RASTREAMENTO E CONCORRÊNCIA
# ==============================================================================
# Falso para portais governamentais públicos, pois o robots.txt muitas vezes 
# bloqueia rotas de busca de forma genérica.
ROBOTSTXT_OBEY = False 

# Reduzimos a concorrência global. O Playwright é pesado. 
# 4 a 8 requisições simultâneas é um limite seguro para evitar estourar a memória.
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 4

# Um pequeno delay ajuda a não sobrecarregar o servidor alvo e evita bloqueios (Rate Limit)
DOWNLOAD_DELAY = 1

# ==============================================================================
# 2. CONFIGURAÇÕES DO MOTOR ASSÍNCRONO E PLAYWRIGHT (OBRIGATÓRIO)
# ==============================================================================
# Substitui o manipulador padrão de download do Scrapy pelo do Playwright
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

# Muda o loop de eventos do Twisted para o Asyncio (necessário para o Playwright funcionar)
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# Configurações do Navegador Chromium
PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True, # Roda sem interface gráfica (ideal para servidores/produção)
    "timeout": 60000, # 60 segundos de tolerância para o navegador iniciar
}
# Timeout estendido para renderização de páginas lentas governamentais (60 segundos)
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 60000 

# ==============================================================================
# 3. RESILIÊNCIA, TIMEOUTS E TRATAMENTO DE ERROS
# ==============================================================================
# Habilita e configura as tentativas de repetição em caso de falha (Timeout, 500, 502, 503)
RETRY_ENABLED = True
RETRY_TIMES = 3 # Conforme os requisitos do projeto
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Aumenta o tempo que o Scrapy espera por uma resposta de rede (antes do Playwright)
DOWNLOAD_TIMEOUT = 60

# ==============================================================================
# 4. ROTAÇÃO DE USER-AGENTS E CABEÇALHOS
# ==============================================================================
# Desativa cookies para evitar rastreamento de sessão que possa levar a bloqueios
COOKIES_ENABLED = False

# Lista de User-Agents modernos para rotação
USER_AGENTS_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
]

# Configuração de Middlewares
DOWNLOADER_MIDDLEWARES = {
    # Desativa o middleware padrão de User-Agent do Scrapy
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
    # Habilita o Retry
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': 90,
    # Habilita nosso middleware customizado de rotação (definido no final deste arquivo)
    'doe_sp.settings.RotateUserAgentMiddleware': 400,
}

# ==============================================================================
# 5. CONFIGURAÇÕES GERAIS E DE EXPORTAÇÃO
# ==============================================================================
FEED_EXPORT_ENCODING = "utf-8"

# ==============================================================================
# 6. CLASSES INLINE (FACILITADORES)
# ==============================================================================
# Colocamos o Middleware de User-Agent diretamente aqui para manter o projeto 
# contido sem precisar criar novos arquivos ou instalar bibliotecas extras.
import random

class RotateUserAgentMiddleware:
    def process_request(self, request, spider):
        # A API e o Playwright usarão um User-Agent aleatório a cada requisição
        request.headers['User-Agent'] = random.choice(USER_AGENTS_LIST)

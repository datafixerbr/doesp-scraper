# DOE-SP Scraper: Diário Oficial do Estado de São Paulo

Este projeto é um web scraper híbrido, robusto e escalável, desenvolvido em Python para extrair
publicações e atos normativos do Diário Oficial do Estado de São Paulo (DOE-SP).

A arquitetura combina a velocidade de requisições HTTP diretas (consumindo uma API não documentada
do portal) com o poder de renderização JavaScript do **Playwright** para extrair o conteúdo dinâmico
das matérias, incluindo o código de autenticação único de cada documento.

## 🚀 Principais Funcionalidades

- **Scraping Híbrido:** Paginação e busca feitas via API REST (rápido e leve), enquanto o Playwright
  é acionado apenas para as páginas finais que dependem de JS.
- **Extração Defensiva:** Utilização de XPaths semânticos em vez de seletores CSS voláteis,
  garantindo a resiliência do código contra mudanças de layout do site.
- **Paginação Automática:** O crawler mapeia iterativamente todas as páginas da API até esgotar os
  resultados da busca.
- **Armazenamento Estruturado:** Cada publicação é salva individualmente em um arquivo `.txt`
  contendo metadados (URL, Data de Extração, Autenticação) e o texto na íntegra.

---

## 🛠️ Pré-requisitos

Certifique-se de ter os seguintes componentes instalados em seu ambiente:

- **Python:** Versão 3.10 ou superior.
- **Gerenciador de Pacotes:** O projeto suporta `uv` (recomendado) ou `pip`.

---

## ⚙️ Instalação

**1. Clone o repositório**

```bash
git clone [https://github.com/seu-usuario/doesp-scraper.git](https://github.com/seu-usuario/doesp-scraper.git)
cd doesp-scraper
```

**2. Instale as dependências** Se estiver usando o uv (conforme o uv.lock do projeto):

```bash
uv sync
```

Ou, se preferir o pip tradicional (tendo exportado um requirements.txt):

```bash
pip install scrapy scrapy-playwright
```

**3. Instale os binários do navegador (Playwright)** O Scrapy-Playwright precisa do motor do
Chromium para renderizar as páginas governamentais. Execute:

```bash
playwright install chromium

```

> No Linux, caso encontre erros de dependências de sistema, rode também: playwright install-deps
> chromium.

## 💻 Como Usar

A execução do crawler é feita via linha de comando, passando os argumentos obrigatórios de busca
para a API do DOE-SP.

O comando base utiliza três parâmetros (`-a`):

- termos: As palavras-chave da busca. Para pesquisar mais de um termo simultaneamente, separe-os por
  vírgula e sem espaços extras (ex: "CComSoc,Licitação,Pregão").
- data_inicio: A data inicial da busca no formato `YYYY-M-D`.
- data_fim: A data final da busca no formato `YYYY-M-D`.

**Comando de Execução:**

```bash
scrapy crawl doesp_spider -a termos="Pregão,Licitação" -a data_inicio="2021-1-1" -a data_fim="2026-3-27"
```

## 📂 Onde ficam os resultados?

O crawler criará automaticamente uma pasta chamada `resultados_doe` na raiz do projeto. Cada arquivo
será salvo com o ID da matéria e terá a seguinte estrutura interna:

```text
Data de Extração: 2026-03-29T11:00:00.000000+00:00
Código de Autenticação: 2023.08.23.1.3.35.16.1.15.37.252519
URL Origem: [https://www.doe.sp.gov.br/executivo/secretaria-de-seguranca-publica/](https://www.doe.sp.gov.br/executivo/secretaria-de-seguranca-publica/)...
--------------------------------------------------

DESPACHO Nº CCOMSOC–094/104/23 Referências: 1) Empenho nº 2023NE00090...
```

## 🏗️ Estrutura do Projeto

- `doe_sp/spiders/spider.py`: Contém a lógica de consumo da API, paginação e regras de negócio do
  web scraping (Scrapy + Playwright).
- `doe_sp/settings.py`: Arquivo de configuração. Ajustado com limits de concorrência seguros,
  User-Agents dinâmicos, integração do Asyncio e políticas de Retry (resiliência).
- `resultados_doe/`: Diretório autogerado onde os documentos .txt são armazenados.

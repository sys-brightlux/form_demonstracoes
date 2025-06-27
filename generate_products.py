import mysql.connector
import os
import sys
import json
from decimal import Decimal

# --- CONFIGURAÇÃO ---
# Adicione aqui todas as famílias que você quer que apareçam no seu formulário.
# O script vai iterar sobre esta lista.
FAMILIES_TO_QUERY = [
    "LED HBMI",
    "IP69K",
    "LEX100",
    "INFINITY",
    "CRYF"
]

def get_products_by_family(connection, family_name):
    """
    Usa uma conexão existente para buscar uma lista agregada de produtos para uma família.
    Retorna uma lista de dicionários ou uma lista vazia.
    """
    products_list = []
    try:
        cursor = connection.cursor()
        
        # A consulta final e otimizada que desenvolvemos
        query = """
            SELECT
                MIN(p.Pro_Codigo) AS Representative_Codigo,
                SUBSTRING(p.Pro_Descricao, 1, LOCATE('W', p.Pro_Descricao)) AS Aggregated_Descricao,
                p_main.TPrcItm_Valor
            FROM
                produtos AS p
            JOIN prodreferencia AS pr ON p.Pro_Codigo = pr.Pro_Codigo
            JOIN tabprecoitem AS p_main ON p.Pro_Codigo = p_main.Pro_Codigo
            JOIN (
                SELECT
                    SUBSTRING(p_inner.Pro_Descricao, 1, LOCATE('W', p_inner.Pro_Descricao)) AS Inner_Agg_Desc,
                    MAX(tpi_inner.TPrcItm_Valor) AS Max_Valor
                FROM produtos AS p_inner
                JOIN prodreferencia AS pr_inner ON p_inner.Pro_Codigo = pr_inner.Pro_Codigo
                JOIN tabprecoitem AS tpi_inner ON p_inner.Pro_Codigo = tpi_inner.Pro_Codigo
                WHERE
                    p_inner.Pro_Descricao LIKE %s
                    AND pr_inner.Pro_RefSituacao = 'A' AND tpi_inner.TPrc_Codigo = 1 AND tpi_inner.TPrcItm_Valor > 1
                    AND LOCATE('W', p_inner.Pro_Descricao) > 0
                GROUP BY Inner_Agg_Desc
            ) AS max_prices
            ON SUBSTRING(p.Pro_Descricao, 1, LOCATE('W', p.Pro_Descricao)) = max_prices.Inner_Agg_Desc
            AND p_main.TPrcItm_Valor = max_prices.Max_Valor
            WHERE pr.Pro_RefSituacao = 'A' AND p.Pro_Descricao LIKE %s AND LOCATE('W', p.Pro_Descricao) > 0
            GROUP BY Aggregated_Descricao, p_main.TPrcItm_Valor
            ORDER BY Aggregated_Descricao;
        """
        
        search_pattern = f"%{family_name}%"
        cursor.execute(query, (search_pattern, search_pattern))

        for (rep_codigo, agg_descricao, tprit_valor) in cursor:
            price = float(tprit_valor) if isinstance(tprit_valor, Decimal) else tprit_valor
            products_list.append({"code": rep_codigo, "description": agg_descricao, "price": price})
        
        cursor.close()
        return products_list

    except mysql.connector.Error as err:
        print(f"  -> Erro ao buscar dados para a família '{family_name}': {err}")
        return [] # Retorna lista vazia em caso de erro para não quebrar o processo

def main():
    """
    Função principal que orquestra a busca para todas as famílias e gera o arquivo JSON.
    """
    all_products_data = {}
    connection = None

    try:
        # Obter credenciais das variáveis de ambiente
        db_host = os.environ.get('DB_HOST')
        db_user = os.environ.get('DB_USER')
        db_password = os.environ.get('DB_PASSWORD')
        db_name = os.environ.get('DB_NAME')

        if not all([db_host, db_user, db_password, db_name]):
            print("Erro Crítico: As variáveis de ambiente do banco de dados não foram definidas.")
            sys.exit(1)

        print(f"Iniciando processo. Conectando a {db_host}...")
        connection = mysql.connector.connect(host=db_host, user=db_user, password=db_password, database=db_name)
        print("Conexão bem-sucedida.")

        # Itera sobre a lista de famílias definida no início do script
        for family in FAMILIES_TO_QUERY:
            print(f"- Processando família: '{family}'...")
            products = get_products_by_family(connection, family)
            all_products_data[family] = products
            print(f"  -> {len(products)} produtos agregados encontrados.")

        # Escreve o resultado final em um arquivo JSON
        output_filename = 'products.json'
        print(f"\nGerando arquivo final '{output_filename}'...")
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(all_products_data, f, ensure_ascii=False, indent=2) # indent=2 para um arquivo menor
        
        print(f"Arquivo '{output_filename}' gerado com sucesso!")

    except mysql.connector.Error as err:
        print(f"Erro Crítico de Conexão: {err}")
        sys.exit(1)

    finally:
        if connection and connection.is_connected():
            connection.close()
            print("Conexão com o MySQL foi fechada.")


if __name__ == "__main__":
    main()
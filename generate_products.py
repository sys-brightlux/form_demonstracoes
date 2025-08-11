import mysql.connector
import os
import sys
import json
import base64
from decimal import Decimal

# --- CONFIGURAÇÃO ---
# Adicione aqui todas as famílias que você quer que apareçam no seu formulário.
# O script vai iterar sobre esta lista.
FAMILIES_TO_QUERY = [
    "LED HBMI",
    "IP69K",
    "LEX100",
    "INFINITY",
    "CRYF",
    "URBJET",
    "LED ORI",
    "UFO",
    "HELYOS",
    "LED HTC-PCL",
    "LED HTS",
    "LED HTB2",
    "LED GRD"
]

def get_products_by_family(connection, family_name):
    """
    Usa uma conexão existente para buscar uma lista agregada de produtos para uma família.
    Para a família 'CRYF', adiciona itens especiais com descrição modificada.
    Retorna uma lista de dicionários ou uma lista vazia.
    """
    products_list = []
    try:
        # ETAPA 1: Executar a consulta normal para obter a lista base de produtos
        cursor = connection.cursor()
        
        # Usaremos a consulta de valor mínimo, conforme o exemplo anterior
        query_min_valor = """
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
                    MIN(tpi_inner.TPrcItm_Valor) AS Min_Valor
                FROM produtos AS p_inner
                JOIN prodreferencia AS pr_inner ON p_inner.Pro_Codigo = pr_inner.Pro_Codigo
                JOIN tabprecoitem AS tpi_inner ON p_inner.Pro_Codigo = tpi_inner.Pro_Codigo
                WHERE
                    p_inner.Pro_Descricao LIKE %s
                    AND pr_inner.Pro_RefSituacao = 'A' AND tpi_inner.TPrc_Codigo = 4 AND tpi_inner.TPrcItm_Valor > 1
                    AND LOCATE('W', p_inner.Pro_Descricao) > 0
                GROUP BY Inner_Agg_Desc
            ) AS min_prices
            ON SUBSTRING(p.Pro_Descricao, 1, LOCATE('W', p.Pro_Descricao)) = min_prices.Inner_Agg_Desc
            AND p_main.TPrcItm_Valor = min_prices.Min_Valor
            WHERE pr.Pro_RefSituacao = 'A' AND p.Pro_Descricao LIKE %s AND LOCATE('W', p.Pro_Descricao) > 0
            GROUP BY Aggregated_Descricao, p_main.TPrcItm_Valor
            ORDER BY Aggregated_Descricao;            
        """
        
        search_pattern = f"%{family_name}%"
        cursor.execute(query_min_valor, (search_pattern, search_pattern))

        for (rep_codigo, agg_descricao, tprit_valor) in cursor:
            price = float(tprit_valor) if isinstance(tprit_valor, Decimal) else tprit_valor
            products_list.append({"code": rep_codigo, "description": agg_descricao, "price": price})
        
        cursor.close()

        # ETAPA 2: Se a família for "CRYF", buscar e adicionar os itens especiais.
        if family_name == "CRYF":
            print(f"  -> Aplicando regra especial para a família '{family_name}'...")
            special_cursor = connection.cursor()
            
            # Consulta simples para buscar os itens específicos pelo código
            query_special_items = """
                SELECT p.Pro_Codigo, p.Pro_Descricao, tpi.TPrcItm_Valor
                FROM produtos p
                JOIN tabprecoitem tpi ON p.Pro_Codigo = tpi.Pro_Codigo
                WHERE p.Pro_Codigo IN (%s, %s) AND tpi.TPrc_Codigo = 4
            """
            
            # Códigos dos produtos especiais
            special_item_codes = (3976, 4009)
            special_cursor.execute(query_special_items, special_item_codes)
            
            for (code, original_description, price_decimal) in special_cursor:
                # Encontra a posição do 'W' para pegar a descrição base
                w_position = original_description.find('W')
                if w_position != -1:
                    # Cria a nova descrição agregada com o sufixo /RGB/
                    base_description = original_description[:w_position + 1]
                    new_description = f"{base_description}/RGB/"
                    
                    price = float(price_decimal) if isinstance(price_decimal, Decimal) else price_decimal
                    
                    special_product = {"code": code, "description": new_description, "price": price}
                    products_list.append(special_product)
                    print(f"    -> Adicionado item RGB especial: {special_product}")
            
            special_cursor.close()

         # ETAPA 2.2: Se a família for "UFO", remover itens que contenham "ALÇA".
        if family_name == "UFO":
            print(f"  -> Aplicando filtro 'ALÇA' para a família '{family_name}'...")
            count_before = len(products_list)
            
            # Filtra a lista, mantendo apenas os produtos cuja descrição NÃO contenha "ALÇA"
            # O .upper() garante que a verificação não diferencia maiúsculas de minúsculas
            products_list = [
                product for product in products_list
                if "ALÇA" not in product.get("description", "").upper()
            ]
            
            count_after = len(products_list)
            removed_count = count_before - count_after
            if removed_count > 0:
                print(f"    -> {removed_count} produto(s) com 'ALÇA' foi(ram) removido(s).")
        ### FIM DO NOVO ###
        
        # ETAPA 3: Retornar a lista (modificada ou não)
        return products_list

    except mysql.connector.Error as err:
        print(f"  -> Erro ao buscar dados para a família '{family_name}': {err}")
        return []

def main():
    """
    Função principal que orquestra a busca, codifica os dados e gera o arquivo final.
    """
    all_products_data = {}
    connection = None

    try:
        # Obter credenciais das variáveis de ambiente
        db_host = "192.168.1.60"
        db_user = "brightled"
        db_password = "1050374"
        db_name = "brightled"

        if not all([db_host, db_user, db_password, db_name]):
            print("Erro Crítico: As variáveis de ambiente do banco de dados não foram definidas.")
            sys.exit(1)

        print(f"Iniciando processo. Conectando a {db_host}...")
        connection = mysql.connector.connect(host=db_host, user=db_user, password=db_password, database=db_name)
        print("Conexão bem-sucedida.")

        for family in FAMILIES_TO_QUERY:
            print(f"- Processando família: '{family}'...")
            products = get_products_by_family(connection, family)
            all_products_data[family] = products
            print(f"  -> {len(products)} produtos agregados encontrados.")

        filtered_products_data = {
            family: [
                product for product in products_list
                if "DRIVER" not in product.get("description", "").upper()
            ]
            for family, products_list in all_products_data.items()
        }

        # Nome do arquivo de saída ofuscado
        output_filename = 'asset.dat'
        print(f"\nCodificando dados em Base64...")

        json_string = json.dumps(filtered_products_data, ensure_ascii=False, separators=(',', ':'))
        json_bytes = json_string.encode('utf-8')
        base64_bytes = base64.b64encode(json_bytes)
        base64_string = base64_bytes.decode('utf-8')

        print(f"Gerando arquivo de dados ofuscado '{output_filename}'...")
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(base64_string)
        
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
        
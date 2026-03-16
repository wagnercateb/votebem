import requests

def get_deputies():
    url = "https://dadosabertos.camara.leg.br/api/v2/deputados"
    params = {
        'idLegislatura': '57',
        'itens': 1000
    }
    r = requests.get(url, params=params)
    data = r.json()['dados']
    return data

def generate_sql(data):
    # MySQL/MariaDB compatible bulk update using JOIN and VALUES
    sql = "UPDATE voting_congressman AS c\nJOIN (VALUES\n"
    values = []
    for d in data:
        email = d.get('email', '')
        if email:
            # Escape single quotes in email just in case (though unlikely in emails)
            email_escaped = email.replace("'", "''")
            values.append(f"({d['id']}, '{email_escaped}')")
    sql += ",\n".join(values)
    sql += "\n) AS v(id, email) ON c.id_cadastro = v.id\nSET c.email = v.email;"
    return sql

if __name__ == "__main__":
    data = get_deputies()
    sql = generate_sql(data)
    with open('update_emails.sql', 'w', encoding='utf-8') as f:
        f.write(sql)
    print(f"SQL generated: {len(data)} deputies")
